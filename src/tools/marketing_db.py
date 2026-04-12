"""
Database operations for the marketing agent system.
All functions use parameterised queries.
"""
import logging
from datetime import date, datetime, timezone

from src.db.connection import db

logger = logging.getLogger(__name__)


def _serialize(row: dict) -> dict:
    return {
        k: v.isoformat() if isinstance(v, (datetime, date)) else v
        for k, v in row.items()
    }


def get_all_strategies(status: str | None = None) -> list[dict]:
    """Return all marketing strategies, optionally filtered by status."""
    with db() as conn:
        cur = conn.cursor()
        if status:
            cur.execute(
                "SELECT * FROM marketing_strategies WHERE status = %s ORDER BY priority, name",
                (status,),
            )
        else:
            cur.execute("SELECT * FROM marketing_strategies ORDER BY priority, name")
        return [_serialize(row) for row in cur.fetchall()]


def get_strategy_by_id(strategy_id: int) -> dict | None:
    """Return a single marketing strategy by id."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM marketing_strategies WHERE id = %s", (strategy_id,))
        row = cur.fetchone()
        return _serialize(row) if row else None


def get_latest_digest() -> dict | None:
    """Return the most recent weekly digest, or None if none exist."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM marketing_digests ORDER BY week_date DESC LIMIT 1"
        )
        row = cur.fetchone()
        return _serialize(row) if row else None


def get_digest_archive(limit: int = 12) -> list[dict]:
    """Return the N most recent digests, newest first."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, week_date, created_at FROM marketing_digests ORDER BY week_date DESC LIMIT %s",
            (limit,),
        )
        return [_serialize(row) for row in cur.fetchall()]


def get_digest_by_id(digest_id: int) -> dict | None:
    """Return a single digest by id."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM marketing_digests WHERE id = %s", (digest_id,))
        row = cur.fetchone()
        return _serialize(row) if row else None


def save_digest(week_date: str, content: str) -> None:
    """Insert or replace the digest for a given Monday date."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO marketing_digests (week_date, content)
            VALUES (%s, %s)
            ON CONFLICT (week_date) DO UPDATE SET content = EXCLUDED.content, created_at = now()
            """,
            (week_date, content),
        )


def save_research_finding(
    run_date: str,
    topic: str,
    summary: str,
    *,
    source_url: str | None = None,
    strategy_id: int | None = None,
) -> None:
    """Insert a single research finding."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO marketing_research (strategy_id, run_date, topic, summary, source_url)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (strategy_id, run_date, topic, summary, source_url),
        )


def get_recent_research(days: int = 14, strategy_slug: str | None = None) -> list[dict]:
    """Return research findings from the last N days, optionally filtered by strategy slug."""
    with db() as conn:
        cur = conn.cursor()
        if strategy_slug:
            cur.execute(
                """
                SELECT r.* FROM marketing_research r
                JOIN marketing_strategies s ON r.strategy_id = s.id
                WHERE r.run_date >= CURRENT_DATE - %s * INTERVAL '1 day'
                  AND s.slug = %s
                ORDER BY r.run_date DESC, r.id DESC
                """,
                (days, strategy_slug),
            )
        else:
            cur.execute(
                """
                SELECT * FROM marketing_research
                WHERE run_date >= CURRENT_DATE - %s * INTERVAL '1 day'
                ORDER BY run_date DESC, id DESC
                """,
                (days,),
            )
        return [_serialize(row) for row in cur.fetchall()]


def update_strategy_reviewed(strategy_id: int) -> None:
    """Set last_reviewed_at = now() for a strategy."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE marketing_strategies SET last_reviewed_at = now() WHERE id = %s",
            (strategy_id,),
        )


def get_pipeline_stats() -> dict:
    """Return contact counts by status and overdue follow-up count for the digest."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM contacts
            WHERE name != '[removed]'
            GROUP BY status ORDER BY status
            """
        )
        by_status = {row["status"]: row["count"] for row in cur.fetchall()}

        cur.execute(
            """
            SELECT COUNT(*) AS count FROM contacts
            WHERE status = 'contacted'
              AND id NOT IN (
                SELECT DISTINCT contact_id FROM interactions
                WHERE created_at >= now() - INTERVAL '60 days'
              )
            """
        )
        overdue = cur.fetchone()["count"]

        cur.execute(
            "SELECT COUNT(*) AS count FROM approval_queue WHERE status = 'pending'"
        )
        pending_approvals = cur.fetchone()["count"]

    return {
        "by_status": by_status,
        "overdue_follow_ups": overdue,
        "pending_approvals": pending_approvals,
    }
