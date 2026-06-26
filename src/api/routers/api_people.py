from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.jwt_auth import require_jwt
from src.db.connection import db

router = APIRouter(prefix="/api/people", tags=["mobile-people"])

_EDITABLE_FIELDS = (
    "name", "city", "country", "email", "phone", "website",
    "relationship", "notes",
)


class PersonCreate(BaseModel):
    name: str
    city: str = ""
    country: str = "DE"
    email: str = ""
    phone: str = ""
    website: str = ""
    relationship: str = ""
    notes: str = ""


class PersonUpdate(BaseModel):
    name: str | None = None
    city: str | None = None
    country: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    relationship: str | None = None
    notes: str | None = None


def _serialize(row: dict) -> dict:
    r = dict(row)
    for key in ("created_at", "updated_at"):
        if key in r and r[key] is not None:
            r[key] = r[key].isoformat()
    return r


@router.get("")
def list_people(
    search: str = Query(""),
    _role: str = Depends(require_jwt),
) -> list[dict]:
    with db() as conn:
        cur = conn.cursor()
        if search:
            cur.execute(
                """
                SELECT id, name, city, country, email, phone, website,
                       relationship, notes, created_at, updated_at
                FROM people
                WHERE name ILIKE %s
                   OR email ILIKE %s
                   OR city ILIKE %s
                ORDER BY name ASC
                """,
                [f"%{search}%", f"%{search}%", f"%{search}%"],
            )
        else:
            cur.execute(
                """
                SELECT id, name, city, country, email, phone, website,
                       relationship, notes, created_at, updated_at
                FROM people
                ORDER BY name ASC
                """
            )
        return [_serialize(dict(row)) for row in cur.fetchall()]


@router.get("/{person_id}")
def get_person(person_id: int, _role: str = Depends(require_jwt)) -> dict:
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, city, country, email, phone, website,
                   relationship, notes, created_at, updated_at
            FROM people
            WHERE id = %s
            """,
            [person_id],
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Person not found")
        return _serialize(dict(row))


@router.post("", status_code=201)
def create_person(body: PersonCreate, role: str = Depends(require_jwt)) -> dict:
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="name is required")
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO people (name, city, country, email, phone, website,
                                relationship, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            [
                body.name.strip(),
                body.city.strip(),
                body.country or "DE",
                body.email.strip(),
                body.phone.strip(),
                body.website.strip(),
                body.relationship.strip(),
                body.notes.strip(),
            ],
        )
        row = cur.fetchone()
        person_id = row["id"] if row else 0
        return {"id": person_id}


@router.put("/{person_id}", status_code=204)
def update_person(person_id: int, body: PersonUpdate, role: str = Depends(require_jwt)) -> None:
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    provided = body.model_dump(exclude_unset=True)
    updates = {
        column: (value if value != "" else None)
        for column, value in provided.items()
        if column in _EDITABLE_FIELDS
    }
    if not updates:
        raise HTTPException(status_code=422, detail="No editable fields provided")
    set_clause = ", ".join(f"{column} = %s" for column in updates)
    values = list(updates.values()) + [person_id]
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE people SET {set_clause}, updated_at = NOW() WHERE id = %s",
            values,
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Person not found")


@router.delete("/{person_id}", status_code=204)
def delete_person(person_id: int, role: str = Depends(require_jwt)) -> None:
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    with db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM people WHERE id = %s", [person_id])
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Person not found")
