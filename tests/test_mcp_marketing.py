"""Tests for marketing MCP tools in src/mcp/server.py."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest


class TestMarketingActionItems:
    def test_returns_no_items_message_when_no_active_strategies(self):
        with patch("src.tools.marketing_db.get_all_strategies", return_value=[]):
            from src.mcp.server import marketing_action_items
            result = marketing_action_items()
        assert "No open action items" in result

    def test_returns_action_items_from_strategy_doc(self, tmp_path):
        doc = tmp_path / "strategy.md"
        doc.write_text("# Strategy\n\n- [ ] Do the thing\n- [x] Done thing\n- [ ] Another item\n")
        fake = [{"name": "Test Strategy", "doc_path": str(doc)}]
        with patch("src.tools.marketing_db.get_all_strategies", return_value=fake):
            from src.mcp.server import marketing_action_items
            result = marketing_action_items()
        assert "Test Strategy" in result
        assert "Do the thing" in result
        assert "Another item" in result
        assert "Done thing" not in result

    def test_skips_strategy_docs_that_dont_exist(self, tmp_path):
        fake = [{"name": "Ghost Strategy", "doc_path": str(tmp_path / "missing.md")}]
        with patch("src.tools.marketing_db.get_all_strategies", return_value=fake):
            from src.mcp.server import marketing_action_items
            result = marketing_action_items()
        assert "No open action items" in result


class TestMarketingDigestLatest:
    def test_returns_no_digest_message_when_empty(self):
        with patch("src.tools.marketing_db.get_latest_digest", return_value=None):
            from src.mcp.server import marketing_digest_latest
            result = marketing_digest_latest()
        assert "No digest yet" in result

    def test_returns_digest_content(self):
        fake = {"week_date": "2026-04-07", "content": "# Test digest"}
        with patch("src.tools.marketing_db.get_latest_digest", return_value=fake):
            from src.mcp.server import marketing_digest_latest
            result = marketing_digest_latest()
        assert "Week: 2026-04-07" in result
        assert "# Test digest" in result


class TestMarketingStrategyList:
    def test_returns_json_string(self):
        fake = [{"id": 1, "name": "Test"}]
        with patch("src.tools.marketing_db.get_all_strategies", return_value=fake):
            from src.mcp.server import marketing_strategy_list
            result = marketing_strategy_list()
        parsed = json.loads(result)
        assert any(s["name"] == "Test" for s in parsed)


class TestMarketingResearchRecent:
    def test_returns_no_findings_message(self):
        with patch("src.tools.marketing_db.get_recent_research", return_value=[]):
            from src.mcp.server import marketing_research_recent
            result = marketing_research_recent()
        assert "No research findings" in result

    def test_returns_json_when_findings_exist(self):
        fake = [{"id": 1, "topic": "galleries", "summary": "Found some"}]
        with patch("src.tools.marketing_db.get_recent_research", return_value=fake):
            from src.mcp.server import marketing_research_recent
            result = marketing_research_recent()
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert parsed[0]["topic"] == "galleries"
