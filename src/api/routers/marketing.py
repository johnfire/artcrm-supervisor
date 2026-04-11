from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from src.tools.marketing_db import get_all_strategies, get_latest_digest, get_digest_archive, get_digest_by_id

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent.parent / "ui" / "templates"))


@router.get("/marketing/", response_class=HTMLResponse)
def marketing_page(request: Request):
    strategies = get_all_strategies()
    digest = get_latest_digest()
    archive = get_digest_archive(limit=12)
    return templates.TemplateResponse("marketing.html", {
        "request": request,
        "strategies": strategies,
        "digest": digest,
        "archive": archive,
    })


@router.get("/marketing/digest/{digest_id}", response_class=HTMLResponse)
def marketing_digest(request: Request, digest_id: int):
    digest = get_digest_by_id(digest_id)
    if not digest:
        return RedirectResponse(url="/marketing/")
    strategies = get_all_strategies()
    archive = get_digest_archive(limit=12)
    return templates.TemplateResponse("marketing.html", {
        "request": request,
        "strategies": strategies,
        "digest": digest,
        "archive": archive,
    })
