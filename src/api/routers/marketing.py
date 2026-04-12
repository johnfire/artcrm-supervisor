from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

import mistune

from src.tools.marketing_db import (
    get_all_strategies, get_latest_digest, get_digest_archive,
    get_digest_by_id, get_strategy_by_id, get_recent_research,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent.parent / "ui" / "templates"))
_md = mistune.create_markdown(escape=False)
_REPO_ROOT = Path(__file__).parent.parent.parent.parent


def _render_digest(digest: dict | None) -> dict | None:
    if digest and digest.get("content"):
        digest = dict(digest)
        digest["content_html"] = _md(digest["content"])
    return digest


@router.get("/marketing/", response_class=HTMLResponse)
def marketing_page(request: Request):
    strategies = get_all_strategies()
    digest = _render_digest(get_latest_digest())
    archive = get_digest_archive(limit=12)
    return templates.TemplateResponse("marketing.html", {
        "request": request,
        "strategies": strategies,
        "digest": digest,
        "archive": archive,
    })


@router.get("/marketing/strategy/{strategy_id}", response_class=HTMLResponse)
def strategy_editor(request: Request, strategy_id: int):
    strategy = get_strategy_by_id(strategy_id)
    if not strategy:
        return RedirectResponse(url="/marketing/")
    doc_path = _REPO_ROOT / strategy["doc_path"]
    content = doc_path.read_text(encoding="utf-8") if doc_path.exists() else ""
    research = get_recent_research(days=30, strategy_slug=strategy["slug"])
    return templates.TemplateResponse("strategy.html", {
        "request": request,
        "strategy": strategy,
        "content": content,
        "preview_html": _md(content),
        "research": research,
    })


@router.post("/marketing/strategy/{strategy_id}/save", response_class=HTMLResponse)
def strategy_save(request: Request, strategy_id: int, content: str = Form(...)):
    strategy = get_strategy_by_id(strategy_id)
    if not strategy:
        return RedirectResponse(url="/marketing/")
    doc_path = _REPO_ROOT / strategy["doc_path"]
    doc_path.write_text(content, encoding="utf-8")
    return templates.TemplateResponse("partials/strategy_preview.html", {
        "request": request,
        "preview_html": _md(content),
    })


@router.get("/marketing/digest/{digest_id}", response_class=HTMLResponse)
def marketing_digest(request: Request, digest_id: int):
    digest = _render_digest(get_digest_by_id(digest_id))
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
