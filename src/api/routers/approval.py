from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from src.db.connection import db

router = APIRouter(prefix="/approvals", tags=["approvals"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent.parent / "ui" / "templates"))


def _fetch_pending(conn) -> list[dict]:
    cur = conn.cursor()
    cur.execute("""
        SELECT
            aq.id, aq.draft_subject, aq.draft_body, aq.created_at,
            c.name AS contact_name, c.city, c.email
        FROM approval_queue aq
        JOIN contacts c ON c.id = aq.contact_id
        WHERE aq.status = 'pending'
        ORDER BY aq.created_at ASC
    """)
    return [dict(row) for row in cur.fetchall()]


@router.get("/", response_class=HTMLResponse)
def approval_list(request: Request):
    with db() as conn:
        items = _fetch_pending(conn)
    return templates.TemplateResponse("approval.html", {"request": request, "items": items})


@router.post("/{item_id}/approve", response_class=HTMLResponse)
def approve(request: Request, item_id: int, note: str = Form(default="")):
    with db() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE approval_queue
            SET status = 'approved', reviewed_at = NOW(), reviewer_note = %s
            WHERE id = %s AND status = 'pending'
        """, (note or None, item_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Item not found or already reviewed")
        items = _fetch_pending(conn)
    return templates.TemplateResponse("partials/approval_list.html", {"request": request, "items": items})


@router.post("/{item_id}/reject", response_class=HTMLResponse)
def reject(request: Request, item_id: int, note: str = Form(default="")):
    with db() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE approval_queue
            SET status = 'rejected', reviewed_at = NOW(), reviewer_note = %s
            WHERE id = %s AND status = 'pending'
        """, (note or None, item_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Item not found or already reviewed")
        items = _fetch_pending(conn)
    return templates.TemplateResponse("partials/approval_list.html", {"request": request, "items": items})


@router.post("/{item_id}/edit", response_class=HTMLResponse)
def edit_and_approve(
    request: Request,
    item_id: int,
    final_subject: str = Form(...),
    final_body: str = Form(...),
    note: str = Form(default=""),
):
    with db() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE approval_queue
            SET status = 'edited', reviewed_at = NOW(), reviewer_note = %s,
                final_subject = %s, final_body = %s
            WHERE id = %s AND status = 'pending'
        """, (note or None, final_subject, final_body, item_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Item not found or already reviewed")
        items = _fetch_pending(conn)
    return templates.TemplateResponse("partials/approval_list.html", {"request": request, "items": items})
