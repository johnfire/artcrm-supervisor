from fastapi import APIRouter, Depends, Form, Request, HTTPException
from src.api.auth import require_login, require_admin
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

import mistune

from src.tools.marketing_db import (
    get_all_strategies, get_latest_digest, get_digest_archive,
    get_digest_by_id, get_strategy_by_id, get_recent_research,
)
from src.tools.memory import capture_thought, search_artcrm_thoughts

router = APIRouter(dependencies=[Depends(require_login)])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent.parent / "ui" / "templates"))
# escape=True: digest/strategy content is machine-generated from LLM output over scraped
# web data (untrusted), then emitted with `| safe`. Escaping raw HTML blocks stored XSS.
_md = mistune.create_markdown(escape=True)
_REPO_ROOT = Path(__file__).parent.parent.parent.parent


def _resolve_doc_path(doc_path_value: str) -> Path:
    """Resolve a strategy doc path from the DB and confirm it stays under the repo root.

    `doc_path` comes from the DB; without this check a tampered/imported value could
    read or write arbitrary files via path traversal (e.g. ``../../etc/...``).
    """
    resolved = (_REPO_ROOT / doc_path_value).resolve()
    if not resolved.is_relative_to(_REPO_ROOT.resolve()):
        raise HTTPException(status_code=400, detail="Invalid document path")
    return resolved


def _render_digest(digest: dict | None) -> dict | None:
    if digest and digest.get("content"):
        digest = dict(digest)
        digest["content_html"] = _md(digest["content"])
    return digest


@router.get("/marketing/observations", response_class=HTMLResponse)
def observations_list(request: Request, topic: str = ""):
    query = f"{topic} " if topic else ""
    thoughts = search_artcrm_thoughts(f"{query}artcrm", limit=20)
    return templates.TemplateResponse("partials/observations_list.html", {
        "request": request,
        "observations": thoughts,
        "topic": topic,
    })


@router.post("/marketing/observations", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def add_observation(request: Request, content: str = Form(...)):
    if content.strip():
        capture_thought(content.strip())
    thoughts = search_artcrm_thoughts("artcrm", limit=20)
    return templates.TemplateResponse("partials/observations_list.html", {
        "request": request,
        "observations": thoughts,
        "topic": "",
    })


@router.get("/marketing/", response_class=HTMLResponse)
def marketing_page(request: Request):
    strategies = get_all_strategies()
    digest = _render_digest(get_latest_digest())
    archive = get_digest_archive(limit=12)
    observations = search_artcrm_thoughts("artcrm", limit=20)
    return templates.TemplateResponse("marketing.html", {
        "request": request,
        "strategies": strategies,
        "digest": digest,
        "archive": archive,
        "observations": observations,
    })


@router.get("/marketing/strategy/{strategy_id}", response_class=HTMLResponse)
def strategy_editor(request: Request, strategy_id: int):
    strategy = get_strategy_by_id(strategy_id)
    if not strategy:
        return RedirectResponse(url="/marketing/")
    doc_path = _resolve_doc_path(strategy["doc_path"])
    content = doc_path.read_text(encoding="utf-8") if doc_path.exists() else ""
    research = get_recent_research(days=30, strategy_slug=strategy["slug"])
    return templates.TemplateResponse("strategy.html", {
        "request": request,
        "strategy": strategy,
        "content": content,
        "preview_html": _md(content),
        "research": research,
    })


@router.post("/marketing/strategy/{strategy_id}/save", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def strategy_save(request: Request, strategy_id: int, content: str = Form(...)):
    strategy = get_strategy_by_id(strategy_id)
    if not strategy:
        return RedirectResponse(url="/marketing/")
    doc_path = _resolve_doc_path(strategy["doc_path"])
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
