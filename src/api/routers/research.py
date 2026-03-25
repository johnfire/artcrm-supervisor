from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from src.db.connection import db

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent.parent / "ui" / "templates"))


@router.get("/research/", response_class=HTMLResponse)
def research_queue(request: Request):
    with db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT city, country,
                   COUNT(*) AS industries,
                   COUNT(*) FILTER (WHERE last_run_at IS NOT NULL) AS done,
                   MAX(last_run_at) AS last_run_at,
                   SUM(run_count) AS total_runs
            FROM research_queue
            GROUP BY city, country
            ORDER BY MIN(COALESCE(last_run_at, '1970-01-01')) ASC, city ASC
        """)
        cities = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT COUNT(*) AS cnt FROM research_queue WHERE last_run_at IS NULL")
        pending = cur.fetchone()["cnt"]

        cur.execute("SELECT COUNT(*) AS cnt FROM research_queue WHERE last_run_at IS NOT NULL")
        completed = cur.fetchone()["cnt"]

    return templates.TemplateResponse("research.html", {
        "request": request,
        "cities": cities,
        "pending": pending,
        "completed": completed,
        "total": pending + completed,
    })
