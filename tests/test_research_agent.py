"""Tests for marketing research agent — pure logic, no real LLM or network calls."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestReadDoc:
    def test_returns_content_up_to_3000_chars(self, tmp_path):
        from src.marketing.research_agent import _read_doc, REPO_ROOT

        doc = tmp_path / "strategy.md"
        doc.write_text("x" * 5000, encoding="utf-8")

        rel_path = str(doc.relative_to(tmp_path))
        with patch("src.marketing.research_agent.REPO_ROOT", tmp_path):
            result = _read_doc(rel_path)

        assert len(result) == 3000

    def test_returns_empty_string_for_missing_file(self):
        from src.marketing.research_agent import _read_doc

        result = _read_doc("nonexistent/path/does_not_exist.md")
        assert result == ""


class TestGetMonitoringQueries:
    def test_returns_empty_for_blank_doc(self):
        from src.marketing.research_agent import _get_monitoring_queries

        mock_llm = MagicMock()
        result = _get_monitoring_queries(mock_llm, "some strategy", "")
        assert result == []
        mock_llm.invoke.assert_not_called()

    def test_returns_max_2_queries(self):
        from src.marketing.research_agent import _get_monitoring_queries

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "query one\nquery two\nquery three\nquery four\nquery five"
        mock_llm.invoke.return_value = mock_response

        result = _get_monitoring_queries(mock_llm, "test strategy", "some content here")
        assert len(result) == 2
        assert result[0] == "query one"
        assert result[1] == "query two"


class TestSynthesizeFindings:
    def test_returns_none_for_empty_results(self):
        from src.marketing.research_agent import _synthesize_findings

        mock_llm = MagicMock()
        result = _synthesize_findings(mock_llm, "some query", [])
        assert result is None
        mock_llm.invoke.assert_not_called()

    def test_returns_none_for_skip_response(self):
        from src.marketing.research_agent import _synthesize_findings

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "SKIP"
        mock_llm.invoke.return_value = mock_response

        results = [{"title": "T", "url": "http://x.com", "snippet": "S"}]
        result = _synthesize_findings(mock_llm, "some query", results)
        assert result is None


class TestRunResearchAgent:
    def test_run_returns_count(self):
        from src.marketing.research_agent import run, GENERAL_QUERIES

        mock_llm = MagicMock()

        fake_strategy = {
            "id": 1,
            "name": "Plein Air",
            "doc_path": "",  # empty doc_path → _get_monitoring_queries returns [] quickly
        }

        with (
            patch(
                "src.marketing.research_agent.web_search",
                return_value=[{"title": "T", "url": "http://x.com", "snippet": "S"}],
            ),
            patch(
                "src.marketing.research_agent._synthesize_findings",
                return_value="A useful finding about art marketing.",
            ),
            patch(
                "src.marketing.research_agent.get_all_strategies",
                return_value=[fake_strategy],
            ),
            patch("src.marketing.research_agent.save_research_finding") as mock_save,
        ):
            count = run(mock_llm)

        assert count == len(GENERAL_QUERIES)
        assert mock_save.call_count == len(GENERAL_QUERIES)
