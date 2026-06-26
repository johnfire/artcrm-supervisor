from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.jwt_auth import require_jwt
from src.api.approval_send import send_and_log
from src.db.connection import db

router = APIRouter(prefix="/api/approvals", tags=["mobile-approvals"])

# Statuses the client may list. 'rejected' is the dropped-drafts view.
_LISTABLE_STATUSES = {"pending", "on_hold", "rejected"}


def _fetch_by_status(conn, status: str) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT aq.id, aq.draft_subject, aq.draft_body, aq.created_at,
               aq.reviewed_at, aq.reviewer_note,
               c.id AS contact_id, c.name, c.city, c.email, c.website
        FROM approval_queue aq
        JOIN contacts c ON c.id = aq.contact_id
        WHERE aq.status = %s
        ORDER BY aq.created_at ASC
        """,
        [status],
    )
    rows = []
    for row in cur.fetchall():
        record = dict(row)
        record["created_at"] = record["created_at"].isoformat() if record["created_at"] else None
        record["reviewed_at"] = record["reviewed_at"].isoformat() if record.get("reviewed_at") else None
        rows.append(record)
    return rows


@router.get("")
def list_approvals(status: str = Query("pending"), _role: str = Depends(require_jwt)) -> list[dict]:
    if status not in _LISTABLE_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status. Valid: {sorted(_LISTABLE_STATUSES)}")
    with db() as conn:
        return _fetch_by_status(conn, status)


def _load_reviewable(cur, approval_id: int) -> dict:
    """Fetch a draft that can still be acted on (pending or on_hold), or 404."""
    cur.execute(
        """
        SELECT aq.draft_subject, aq.draft_body, aq.contact_id, c.email
        FROM approval_queue aq JOIN contacts c ON c.id = aq.contact_id
        WHERE aq.id = %s AND aq.status IN ('pending', 'on_hold')
        """,
        [approval_id],
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Approval not found or already reviewed")
    return dict(row)


@router.post("/{approval_id}/approve", status_code=200)
def approve(approval_id: int, role: str = Depends(require_jwt)) -> dict:
    """Approve a draft AND send it. (Previously this only flagged 'approved' and
    nothing ever sent the mail — drafts approved from mobile never went out.)"""
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    with db() as conn:
        cur = conn.cursor()
        draft = _load_reviewable(cur, approval_id)

    success, send_status = send_and_log(
        item_id=approval_id, contact_id=draft["contact_id"],
        to_email=draft["email"] or "", subject=draft["draft_subject"], body=draft["draft_body"],
    )
    final_status = "approved" if success else "approved_unsent"

    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE approval_queue SET status=%s, reviewed_at=NOW(), reviewer_note=%s WHERE id=%s",
            [final_status, None if success else send_status, approval_id],
        )
    return {"status": final_status, "sent": success}


class EditBody(BaseModel):
    subject: str
    body: str
    note: str = ""


@router.post("/{approval_id}/edit", status_code=200)
def edit_and_send(approval_id: int, body: EditBody, role: str = Depends(require_jwt)) -> dict:
    """Edit a draft's subject/body, then send it."""
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    with db() as conn:
        cur = conn.cursor()
        draft = _load_reviewable(cur, approval_id)

    success, send_status = send_and_log(
        item_id=approval_id, contact_id=draft["contact_id"],
        to_email=draft["email"] or "", subject=body.subject, body=body.body,
    )
    final_status = "edited" if success else "edited_unsent"

    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE approval_queue
            SET status=%s, reviewed_at=NOW(), reviewer_note=%s, final_subject=%s, final_body=%s
            WHERE id=%s
            """,
            [final_status, (body.note or send_status) or None, body.subject, body.body, approval_id],
        )
    return {"status": final_status, "sent": success}


class RejectBody(BaseModel):
    reason: str = ""


@router.post("/{approval_id}/reject", status_code=204)
def reject(approval_id: int, body: RejectBody, role: str = Depends(require_jwt)) -> None:
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE approval_queue
            SET status='rejected', reviewed_at=NOW(), reviewer_note=%s
            WHERE id=%s AND status IN ('pending', 'on_hold')
            RETURNING contact_id
            """,
            [body.reason or None, approval_id],
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Approval not found or already reviewed")
        cur.execute(
            "UPDATE contacts SET status='dropped', updated_at=NOW() WHERE id=%s",
            [row["contact_id"]],
        )


class HoldBody(BaseModel):
    note: str = ""


@router.post("/{approval_id}/hold", status_code=204)
def hold(approval_id: int, body: HoldBody, role: str = Depends(require_jwt)) -> None:
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE approval_queue SET status='on_hold', reviewer_note=%s
            WHERE id=%s AND status IN ('pending', 'rejected')
            RETURNING contact_id
            """,
            [body.note or None, approval_id],
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Approval not found or not holdable")
        cur.execute(
            """
            UPDATE contacts SET status='on_hold', updated_at=NOW()
            WHERE id=%s AND status NOT IN ('contacted', 'meeting', 'accepted', 'dormant', 'do_not_contact')
            """,
            [row["contact_id"]],
        )


@router.delete("/{approval_id}", status_code=204)
def delete_approval(approval_id: int, role: str = Depends(require_jwt)) -> None:
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    with db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM approval_queue WHERE id=%s", [approval_id])
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Approval not found")
