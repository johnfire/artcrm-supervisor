# tests/test_marketing_db.py
from unittest.mock import MagicMock, patch


def make_mock_conn(rows=None):
    cur = MagicMock()
    cur.fetchone.return_value = rows[0] if rows else None
    cur.fetchall.return_value = rows or []
    conn = MagicMock()
    conn.cursor.return_value = cur
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    return conn, cur


class TestGetAllStrategies:
    def test_returns_list(self):
        from src.tools.marketing_db import get_all_strategies
        conn, cur = make_mock_conn([
            {"id": 1, "name": "Plein Air", "slug": "plein-air", "doc_path": "plein-air-strategy.md",
             "status": "active", "priority": 2, "last_reviewed_at": None, "next_action_due": None, "notes": None}
        ])
        with patch("src.tools.marketing_db.db") as mock_db:
            mock_db.return_value.__enter__.return_value = conn
            result = get_all_strategies()
        assert len(result) == 1
        assert result[0]["slug"] == "plein-air"


class TestGetLatestDigest:
    def test_returns_none_when_empty(self):
        from src.tools.marketing_db import get_latest_digest
        conn, cur = make_mock_conn([])
        cur.fetchone.return_value = None
        with patch("src.tools.marketing_db.db") as mock_db:
            mock_db.return_value.__enter__.return_value = conn
            result = get_latest_digest()
        assert result is None

    def test_returns_digest_dict(self):
        from src.tools.marketing_db import get_latest_digest
        conn, cur = make_mock_conn()
        cur.fetchone.return_value = {"id": 1, "week_date": "2026-04-07", "content": "# Week\nStuff"}
        with patch("src.tools.marketing_db.db") as mock_db:
            mock_db.return_value.__enter__.return_value = conn
            result = get_latest_digest()
        assert result["content"] == "# Week\nStuff"


class TestSaveDigest:
    def test_inserts_new_digest(self):
        from src.tools.marketing_db import save_digest
        conn, cur = make_mock_conn()
        with patch("src.tools.marketing_db.db") as mock_db:
            mock_db.return_value.__enter__.return_value = conn
            save_digest("2026-04-07", "# Digest content")
        assert cur.execute.called
        call_args = cur.execute.call_args[0]
        assert "INSERT INTO marketing_digests" in call_args[0]


class TestSaveResearchFinding:
    def test_inserts_finding(self):
        from src.tools.marketing_db import save_research_finding
        conn, cur = make_mock_conn()
        with patch("src.tools.marketing_db.db") as mock_db:
            mock_db.return_value.__enter__.return_value = conn
            save_research_finding(
                run_date="2026-04-07",
                topic="Art marketing Europe",
                summary="Artists are using Instagram Reels...",
                source_url="https://example.com",
                strategy_id=None,
            )
        assert cur.execute.called


class TestGetRecentResearch:
    def test_returns_findings(self):
        from src.tools.marketing_db import get_recent_research
        conn, cur = make_mock_conn([
            {"id": 1, "strategy_id": None, "run_date": "2026-04-07",
             "topic": "General", "summary": "...", "source_url": None}
        ])
        with patch("src.tools.marketing_db.db") as mock_db:
            mock_db.return_value.__enter__.return_value = conn
            result = get_recent_research(days=14)
        assert len(result) == 1


class TestUpdateStrategyReviewed:
    def test_updates_timestamp(self):
        from src.tools.marketing_db import update_strategy_reviewed
        conn, cur = make_mock_conn()
        with patch("src.tools.marketing_db.db") as mock_db:
            mock_db.return_value.__enter__.return_value = conn
            update_strategy_reviewed(strategy_id=1)
        assert cur.execute.called
        call_args = cur.execute.call_args[0]
        assert "last_reviewed_at" in call_args[0]
