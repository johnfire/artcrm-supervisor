"""Tests for marketing strategy agent — pure logic, no LLM calls."""
import tempfile
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestParseActionItems:
    def test_returns_items_from_markdown(self, tmp_path):
        from src.marketing.strategy_agent import _parse_action_items, REPO_ROOT

        doc = tmp_path / "strategy.md"
        doc.write_text("- [ ] Do X\n- [x] Done Y\n- [ ] Do Z\n")

        # Patch REPO_ROOT so the function resolves relative to tmp_path
        rel_path = str(doc.relative_to(tmp_path))
        with patch("src.marketing.strategy_agent.REPO_ROOT", tmp_path):
            result = _parse_action_items(rel_path)

        assert result == ["Do X", "Do Z"]

    def test_returns_empty_for_missing_file(self):
        from src.marketing.strategy_agent import _parse_action_items

        result = _parse_action_items("nonexistent/path/does_not_exist.md")
        assert result == []


class TestWeeksSinceReviewed:
    def test_returns_none_for_never_reviewed(self):
        from src.marketing.strategy_agent import _weeks_since_reviewed

        assert _weeks_since_reviewed(None) is None

    def test_returns_weeks_count(self):
        from src.marketing.strategy_agent import _weeks_since_reviewed

        dt = datetime.now(timezone.utc) - timedelta(days=21)
        result = _weeks_since_reviewed(dt.isoformat())
        assert result == 3


class TestBuildDigestPrompt:
    def test_includes_week_date_and_pipeline(self, tmp_path):
        from src.marketing.strategy_agent import _build_digest_prompt
        from datetime import date

        today = date(2026, 4, 21)
        pipeline = {"by_status": {"cold": 5}, "overdue_follow_ups": 1, "pending_approvals": 0}
        prompt = _build_digest_prompt(today, "2026-04-20", [], pipeline, [])

        assert "2026-04-21" in prompt
        assert "2026-04-20" in prompt
        assert "No research findings this week." in prompt

    def test_research_findings_appear_in_prompt(self):
        from src.marketing.strategy_agent import _build_digest_prompt
        from datetime import date

        findings = [{"topic": "Instagram tips", "summary": "Post reels for reach."}]
        pipeline = {"by_status": {}, "overdue_follow_ups": 0, "pending_approvals": 0}
        prompt = _build_digest_prompt(date.today(), "2026-04-20", [], pipeline, findings)

        assert "Instagram tips" in prompt
        assert "Post reels for reach." in prompt


class TestRunStrategyAgent:
    def test_run_calls_save_digest(self):
        from src.marketing.strategy_agent import run

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="## Weekly Digest\nTest content here.")

        with patch("src.marketing.strategy_agent.get_all_strategies") as mock_strats, \
             patch("src.marketing.strategy_agent.get_recent_research") as mock_research, \
             patch("src.marketing.strategy_agent.get_pipeline_stats") as mock_pipeline, \
             patch("src.marketing.strategy_agent.save_digest") as mock_save, \
             patch("src.marketing.strategy_agent.update_strategy_reviewed") as mock_update:

            mock_strats.return_value = []
            mock_research.return_value = []
            mock_pipeline.return_value = {
                "by_status": {"cold": 10, "contacted": 5},
                "overdue_follow_ups": 2,
                "pending_approvals": 1,
            }

            result = run(mock_llm)

            mock_save.assert_called_once()
            call_args = mock_save.call_args[0]
            # First arg is week_date string, second is digest content
            assert isinstance(call_args[0], str) and len(call_args[0]) == 10  # "YYYY-MM-DD"
            assert isinstance(call_args[1], str) and len(call_args[1]) > 0
            assert result == "## Weekly Digest\nTest content here."
