from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.jwt_auth import require_jwt
from src.db.connection import db

router = APIRouter(prefix="/api/inbox", tags=["mobile-inbox"])

VALID_CLASSIFICATIONS = {
    "interested", "warm", "not_interested", "opt_out",
    "bounced", "auto_reply", "unclassified",
}


@router.get("")
def list_inbox(_role: str = Depends(require_jwt)) -> list[dict]:
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT i.id, i.from_email, i.subject, i.body,
                   i.received_at, i.classification,
                   c.id AS contact_id, c.name AS contact_name, c.city
            FROM inbox_messages i
            LEFT JOIN contacts c ON c.id = i.matched_contact_id
            WHERE i.processed = TRUE
              AND i.received_at >= NOW() - INTERVAL '30 days'
            ORDER BY i.received_at DESC
            LIMIT 200
            """
        )
        rows = []
        for row in cur.fetchall():
            r = dict(row)
            r["received_at"] = r["received_at"].isoformat() if r["received_at"] else None
            rows.append(r)
        return rows


class ClassifyBody(BaseModel):
    classification: str


@router.post("/{message_id}/classify", status_code=204)
def classify(message_id: int, body: ClassifyBody, role: str = Depends(require_jwt)) -> None:
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    if body.classification not in VALID_CLASSIFICATIONS:
        raise HTTPException(status_code=422, detail=f"Invalid classification. Valid: {VALID_CLASSIFICATIONS}")
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE inbox_messages SET classification=%s WHERE id=%s",
            [body.classification, message_id],
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Message not found")
