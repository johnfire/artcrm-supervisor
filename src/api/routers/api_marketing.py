from fastapi import APIRouter, Depends

from src.api.jwt_auth import require_jwt
from src.tools.marketing_db import get_recent_research, get_all_strategies, get_digest_archive

router = APIRouter(prefix="/api/marketing", tags=["mobile-marketing"])


@router.get("/observations")
def observations(_role: str = Depends(require_jwt)) -> list[dict]:
    return get_recent_research(days=60)


@router.get("/strategies")
def strategies(_role: str = Depends(require_jwt)) -> list[dict]:
    return get_all_strategies()


@router.get("/digests")
def digests(_role: str = Depends(require_jwt)) -> list[dict]:
    return get_digest_archive(limit=12)
