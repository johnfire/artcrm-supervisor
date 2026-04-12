"""Tests for src/tools/memory.py — Open Brain wrapper."""
from unittest.mock import patch
import pytest

from src.tools import memory as mem
from src.tools.memory import capture_thought, search_artcrm_thoughts


class TestCaptureThought:
    def test_calls_mcp_tool_with_artcrm_project(self):
        with patch("src.tools.memory._run_tool") as mock_run:
            capture_thought("Munich galleries are cold this month")
        mock_run.assert_called_once_with(
            "capture_thought",
            {"content": "Munich galleries are cold this month", "project": "artcrm"},
        )

    def test_returns_none_silently_when_not_configured(self):
        with patch("src.tools.memory.OPEN_BRAIN_URL", ""), \
             patch("src.tools.memory.OPEN_BRAIN_TOKEN", ""):
            result = capture_thought("test")
        assert result is None


class TestSearchArtcrmThoughts:
    def test_returns_empty_list_when_not_configured(self):
        with patch("src.tools.memory.OPEN_BRAIN_URL", ""), \
             patch("src.tools.memory.OPEN_BRAIN_TOKEN", ""):
            result = search_artcrm_thoughts("email tone gallery")
        assert result == []

    def test_returns_empty_list_on_empty_response(self):
        with patch("src.tools.memory._run_tool", return_value=""):
            result = search_artcrm_thoughts("email tone gallery")
        assert result == []

    def test_parses_content_from_search_result(self):
        raw = (
            "Found 1 thought(s):\n\n"
            "--- Result 1 (75.0% match) ---\n"
            "Captured: 4/12/2026\n"
            "Type: observation\n"
            "Project: artcrm\n"
            "Status: active\n"
            "Topics: outreach\n\n"
            "Keep emails under 150 words — galleries respond better to brevity."
        )
        with patch("src.tools.memory._run_tool", return_value=raw):
            result = search_artcrm_thoughts("email tone")
        assert len(result) == 1
        assert "150 words" in result[0]

    def test_parses_multiple_results(self):
        raw = (
            "Found 2 thought(s):\n\n"
            "--- Result 1 (80.0% match) ---\n"
            "Captured: 4/12/2026\n"
            "Type: observation\n"
            "Project: artcrm\n"
            "Status: active\n"
            "Topics: outreach\n\n"
            "Keep emails short — under 150 words works best.\n"
            "--- Result 2 (70.0% match) ---\n"
            "Captured: 4/11/2026\n"
            "Type: observation\n"
            "Project: artcrm\n"
            "Status: active\n"
            "Topics: city\n\n"
            "Munich galleries prefer personal visits over cold email."
        )
        with patch("src.tools.memory._run_tool", return_value=raw):
            result = search_artcrm_thoughts("email tone")
        assert len(result) == 2
        assert "150 words" in result[0]
        assert "Munich" in result[1]
