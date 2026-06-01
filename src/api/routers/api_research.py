import subprocess
import sys
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from src.api.jwt_auth import require_jwt

router = APIRouter(prefix="/api/research", tags=["mobile-research"])


class ResearchRequest(BaseModel):
    city: str
    level: int
    country: str = "DE"


def _run_research(city: str, level: int, country: str) -> None:
    subprocess.Popen(
        [sys.executable, "-m", "src.supervisor.run_research",
         "--city", city, "--level", str(level), "--country", country],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


@router.post("/run", status_code=202)
def run_research(
    body: ResearchRequest,
    background_tasks: BackgroundTasks,
    role: str = Depends(require_jwt),
) -> dict:
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    if body.level not in range(1, 6):
        raise HTTPException(status_code=422, detail="Level must be 1-5")
    background_tasks.add_task(_run_research, body.city, body.level, body.country)
    return {"status": "queued", "city": body.city, "level": body.level}
