"""Tests for marketing MCP tools in src/mcp/server.py."""
import json
from unittest.mock import patch

import pytest


# marketing_action_items reads strategy docs from disk — tested manually


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
