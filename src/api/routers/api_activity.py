from fastapi import APIRouter, Depends

from src.api.jwt_auth import require_jwt
from src.db.connection import db

router = APIRouter(prefix="/api/activity", tags=["mobile-activity"])


@router.get("")
def list_activity(_role: str = Depends(require_jwt)) -> dict:
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, agent_name, status, summary, started_at, finished_at
            FROM agent_runs
            ORDER BY started_at DESC
            LIMIT 50
            """
        )
        runs = []
        for row in cur.fetchall():
            r = dict(row)
            r["started_at"] = r["started_at"].isoformat() if r["started_at"] else None
            r["finished_at"] = r["finished_at"].isoformat() if r["finished_at"] else None
            runs.append(r)

        cur.execute(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE status = 'pending')   AS pending,
                COUNT(*) FILTER (WHERE status = 'approved')  AS approved,
                COUNT(*) FILTER (WHERE status = 'rejected')  AS rejected,
                COUNT(*) FILTER (WHERE status = 'edited')    AS edited
            FROM approval_queue
            """
        )
        queue_stats = dict(cur.fetchone())

        return {
            "runs": runs,
            "queue_stats": queue_stats,
        }
