from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from src.tools.db import get_all_city_scan_status

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent.parent / "ui" / "templates"))

LEVEL_LABELS = {
    1: "Galleries / Cafes / Designers / Coworking",
    2: "Gift / Esoteric / Concept Stores",
    3: "Restaurants",
    4: "Corporate Offices",
    5: "Hotels",
}


@router.get("/research/", response_class=HTMLResponse)
def research_page(request: Request):
    cities = get_all_city_scan_status()

    # Build per-city level map for easy template access
    for c in cities:
        scans_by_level = {s["level"]: s for s in (c["scans"] or [])}
        c["levels"] = [scans_by_level.get(lvl) for lvl in range(1, 6)]
        c["total_contacts"] = c.get("total_contacts") or 0
        c["scanned_levels"] = len(c["scans"] or [])
        emailed = c.get("emailed_by_level") or {}
        c["emailed"] = [emailed.get(str(lvl), 0) for lvl in range(1, 6)]

    total = len(cities)
    unscanned = sum(1 for c in cities if not c["scans"])
    level_done = {
        lvl: sum(1 for c in cities if c["levels"][lvl - 1] is not None)
        for lvl in range(1, 6)
    }

    totals = {
        "contacts": sum(c["total_contacts"] for c in cities),
        "scans": [sum(1 for c in cities if c["levels"][lvl - 1] is not None) for lvl in range(1, 6)],
        "emailed": [sum(c["emailed"][lvl - 1] for c in cities) for lvl in range(1, 6)],
    }

    return templates.TemplateResponse("research.html", {
        "request": request,
        "cities": cities,
        "level_labels": LEVEL_LABELS,
        "total": total,
        "level_done": level_done,
        "unscanned": unscanned,
        "levels": range(1, 6),
        "totals": totals,
    })
