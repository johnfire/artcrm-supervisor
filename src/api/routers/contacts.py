from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from src.db.connection import db

router = APIRouter(prefix="/contacts", tags=["contacts"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent.parent / "ui" / "templates"))

VALID_STATUSES = (
    "candidate", "cold", "contacted", "meeting", "proposal",
    "accepted", "rejected", "dormant", "on_hold", "dropped",
)


@router.get("/", response_class=HTMLResponse)
def contact_list(
    request: Request,
    status: str = Query(default=""),
    q: str = Query(default=""),
):
    with db() as conn:
        cur = conn.cursor()

        conditions = []
        params = []
        if status and status in VALID_STATUSES:
            conditions.append("c.status = %s")
            params.append(status)
        if q:
            conditions.append("(lower(c.name) LIKE %s OR lower(c.city) LIKE %s)")
            params += [f"%{q.lower()}%", f"%{q.lower()}%"]

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        cur.execute(
            f"""
            SELECT
                c.id, c.name, c.city, c.country, c.type, c.status,
                c.email, c.fit_score,
                MAX(i.interaction_date) AS last_contact
            FROM contacts c
            LEFT JOIN interactions i ON i.contact_id = c.id
            {where}
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            LIMIT 200
            """,
            params,
        )
        contacts = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT DISTINCT status FROM contacts WHERE status IS NOT NULL ORDER BY status")
        statuses = [r["status"] for r in cur.fetchall()]

    return templates.TemplateResponse("contacts.html", {
        "request": request,
        "contacts": contacts,
        "statuses": statuses,
        "active_status": status,
        "query": q,
    })
