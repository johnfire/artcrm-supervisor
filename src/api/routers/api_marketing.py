from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.jwt_auth import require_jwt
from src.tools.marketing_db import (
    get_recent_research, get_all_strategies, get_digest_archive, get_strategy_by_id,
)
from src.tools.memory import capture_thought

router = APIRouter(prefix="/api/marketing", tags=["mobile-marketing"])

_REPO_ROOT = Path(__file__).parent.parent.parent.parent


def _resolve_doc_path(doc_path_value: str) -> Path:
    """Resolve a strategy doc path from the DB and confirm it stays under the repo root.

    `doc_path` comes from the DB; without this check a tampered/imported value could
    read or write arbitrary files via path traversal (M-2).
    """
    resolved = (_REPO_ROOT / doc_path_value).resolve()
    if not resolved.is_relative_to(_REPO_ROOT.resolve()):
        raise HTTPException(status_code=400, detail="Invalid document path")
    return resolved


@router.get("/observations")
def observations(_role: str = Depends(require_jwt)) -> list[dict]:
    return get_recent_research(days=60)


class ObservationBody(BaseModel):
    content: str


@router.post("/observations", status_code=201)
def add_observation(body: ObservationBody, role: str = Depends(require_jwt)) -> dict:
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="content is required")
    capture_thought(content)
    return {"status": "captured"}


@router.get("/strategies")
def strategies(_role: str = Depends(require_jwt)) -> list[dict]:
    return get_all_strategies()


@router.get("/strategy/{strategy_id}")
def strategy_detail(strategy_id: int, _role: str = Depends(require_jwt)) -> dict:
    strategy = get_strategy_by_id(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    doc_path = _resolve_doc_path(strategy["doc_path"])
    content = doc_path.read_text(encoding="utf-8") if doc_path.exists() else ""
    return {"strategy": strategy, "content": content}


class StrategyContent(BaseModel):
    content: str


@router.put("/strategy/{strategy_id}", status_code=204)
def strategy_save(strategy_id: int, body: StrategyContent, role: str = Depends(require_jwt)) -> None:
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    strategy = get_strategy_by_id(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    doc_path = _resolve_doc_path(strategy["doc_path"])
    doc_path.write_text(body.content, encoding="utf-8")


@router.get("/digests")
def digests(_role: str = Depends(require_jwt)) -> list[dict]:
    return get_digest_archive(limit=12)
