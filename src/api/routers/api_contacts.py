from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.jwt_auth import require_jwt
from src.db.connection import db

router = APIRouter(prefix="/api/contacts", tags=["mobile-contacts"])

VALID_STATUSES = {
    "candidate", "cold", "contacted", "meeting", "proposal", "accepted",
    "rejected", "dormant", "on_hold", "dropped", "do_not_contact",
    "networking_visit", "bad_email",
}

# Columns the client may edit. Names are interpolated into the UPDATE statement,
# so they MUST come only from this allowlist — never from the request payload.
_EDITABLE_FIELDS = (
    "name", "city", "country", "type", "status", "fit_score",
    "email", "phone", "website", "preferred_contact_method", "decision_maker",
    "last_visited_at", "best_visit_time", "visit_duration",
    "first_impression", "last_impression", "materials_left", "followup_promised",
    "access_notes", "space_notes", "price_sensitivity", "notes",
)

_VALID_INTERACTION_METHODS = {"email", "call", "visit", "meeting", "note", "other"}
_VALID_INTERACTION_DIRECTIONS = {"inbound", "outbound"}

_SORT_COLUMNS = {
    "name": "c.name",
    "city": "c.city",
    "type": "c.type",
    "status": "c.status",
    "fit": "c.fit_score",
    "last_contact": "MAX(i.interaction_date)",
}


class ContactCreate(BaseModel):
    name: str
    city: str
    country: str = "DE"
    type: str = ""
    email: str = ""
    phone: str = ""
    website: str = ""
    notes: str = ""
    status: str = "candidate"


class ContactUpdate(BaseModel):
    name: str | None = None
    city: str | None = None
    country: str | None = None
    type: str | None = None
    status: str | None = None
    fit_score: int | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    preferred_contact_method: str | None = None
    decision_maker: str | None = None
    last_visited_at: str | None = None
    best_visit_time: str | None = None
    visit_duration: str | None = None
    first_impression: str | None = None
    last_impression: str | None = None
    materials_left: str | None = None
    followup_promised: str | None = None
    access_notes: str | None = None
    space_notes: str | None = None
    price_sensitivity: str | None = None
    notes: str | None = None


class InteractionCreate(BaseModel):
    method: str
    direction: str = "outbound"
    summary: str = ""
    outcome: str = "no_reply"


def _serialize(row: dict) -> dict:
    r = dict(row)
    for key in ("created_at", "updated_at", "last_contact", "enriched_at"):
        if key in r and r[key] is not None:
            r[key] = r[key].isoformat()
    return r


@router.get("")
def list_contacts(
    search: str = Query(""),
    status: str = Query(""),
    type: str = Query(""),
    sort: str = Query("name"),
    dir: str = Query("asc"),
    page: int = Query(1, ge=1),
    _role: str = Depends(require_jwt),
) -> list[dict]:
    # sort column comes only from the allowlist (interpolated into SQL); dir is boolean.
    sort_column = _SORT_COLUMNS.get(sort, "c.name")
    sort_direction = "DESC" if dir == "desc" else "ASC"
    with db() as conn:
        cur = conn.cursor()
        params: list = []
        where = ["c.deleted_at IS NULL"]
        if search:
            where.append("(c.name ILIKE %s OR c.city ILIKE %s OR c.type ILIKE %s)")
            params += [f"%{search}%", f"%{search}%", f"%{search}%"]
        if status:
            where.append("c.status = %s")
            params.append(status)
        if type:
            where.append("lower(c.type) = lower(%s)")
            params.append(type)
        where_clause = " AND ".join(where)
        offset = (page - 1) * 50
        cur.execute(
            f"""
            SELECT c.id, c.name, c.city, c.country, c.type, c.status,
                   c.email, c.website, c.fit_score, c.flagged,
                   MAX(i.interaction_date) AS last_contact
            FROM contacts c
            LEFT JOIN interactions i ON i.contact_id = c.id
            WHERE {where_clause}
            GROUP BY c.id
            ORDER BY {sort_column} {sort_direction} NULLS LAST
            LIMIT 50 OFFSET %s
            """,
            params + [offset],
        )
        return [_serialize(dict(row)) for row in cur.fetchall()]


@router.get("/{contact_id}")
def get_contact(contact_id: int, _role: str = Depends(require_jwt)) -> dict:
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT c.*, MAX(i.interaction_date) AS last_contact
            FROM contacts c
            LEFT JOIN interactions i ON i.contact_id = c.id
            WHERE c.id = %s AND c.deleted_at IS NULL
            GROUP BY c.id
            """,
            [contact_id],
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Contact not found")
        contact = _serialize(dict(row))

        cur.execute(
            """
            SELECT method, direction, summary, outcome, interaction_date
            FROM interactions
            WHERE contact_id = %s
            ORDER BY interaction_date DESC
            LIMIT 20
            """,
            [contact_id],
        )
        contact["interactions"] = [
            {**dict(r), "interaction_date": r["interaction_date"].isoformat() if r["interaction_date"] else None}
            for r in cur.fetchall()
        ]
        return contact


@router.post("", status_code=201)
def create_contact(body: ContactCreate, role: str = Depends(require_jwt)) -> dict:
    """Create a contact (for adding a venue 'on the run'). Reuses save_contact so
    chain-filtering, email/name dedup, and consent-log creation stay consistent."""
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    if not body.name.strip() or not body.city.strip():
        raise HTTPException(status_code=422, detail="name and city are required")
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status. Valid: {sorted(VALID_STATUSES)}")
    from src.tools.db import save_contact
    contact_id = save_contact(
        body.name.strip(), body.city.strip(),
        country=body.country or "DE", type=body.type, website=body.website,
        email=body.email, phone=body.phone, notes=body.notes, status=body.status,
    )
    if not contact_id:
        raise HTTPException(status_code=409, detail="Contact not created (ignored chain or save error)")
    return {"id": contact_id}


@router.put("/{contact_id}", status_code=204)
def update_contact(contact_id: int, body: ContactUpdate, role: str = Depends(require_jwt)) -> None:
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    provided = body.model_dump(exclude_unset=True)
    if provided.get("status") is not None and provided["status"] not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status. Valid: {sorted(VALID_STATUSES)}")
    # Keep only allowlisted columns; turn blank strings into NULL.
    updates = {
        column: (value if value != "" else None)
        for column, value in provided.items()
        if column in _EDITABLE_FIELDS
    }
    if not updates:
        raise HTTPException(status_code=422, detail="No editable fields provided")
    set_clause = ", ".join(f"{column} = %s" for column in updates)
    values = list(updates.values()) + [contact_id]
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE contacts SET {set_clause}, updated_at = NOW() "
            f"WHERE id = %s AND deleted_at IS NULL",
            values,
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Contact not found")


@router.delete("/{contact_id}", status_code=204)
def delete_contact(contact_id: int, role: str = Depends(require_jwt)) -> None:
    """Soft-delete (sets deleted_at) so a field mistake is recoverable."""
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE contacts SET deleted_at = NOW(), updated_at = NOW() "
            "WHERE id = %s AND deleted_at IS NULL",
            [contact_id],
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Contact not found")


@router.post("/{contact_id}/unflag", status_code=204)
def unflag_contact(contact_id: int, role: str = Depends(require_jwt)) -> None:
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE contacts SET flagged = FALSE, updated_at = NOW() "
            "WHERE id = %s AND deleted_at IS NULL",
            [contact_id],
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Contact not found")


@router.post("/{contact_id}/interactions", status_code=201)
def add_interaction(contact_id: int, body: InteractionCreate, role: str = Depends(require_jwt)) -> dict:
    """Log a visit/call/email against a contact — the 'on the run' debrief capture."""
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    if body.method not in _VALID_INTERACTION_METHODS:
        raise HTTPException(status_code=422, detail=f"Invalid method. Valid: {sorted(_VALID_INTERACTION_METHODS)}")
    if body.direction not in _VALID_INTERACTION_DIRECTIONS:
        raise HTTPException(status_code=422, detail=f"Invalid direction. Valid: {sorted(_VALID_INTERACTION_DIRECTIONS)}")
    with db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM contacts WHERE id = %s AND deleted_at IS NULL", [contact_id])
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Contact not found")
    from src.tools.db import log_interaction
    log_interaction(contact_id, body.method, body.direction, body.summary, body.outcome)
    return {"status": "logged"}
