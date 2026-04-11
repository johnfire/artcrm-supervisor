# src/marketing/strategy_agent.py
"""
Marketing Strategy Agent.

Reads all active strategy docs, parses open action items, cross-references
pipeline stats and recent research findings, then uses Claude Sonnet to
generate a weekly markdown digest stored in marketing_digests.

Run via: uv run python -m src.marketing.run_strategy
"""
import logging
import re
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

from langchain_core.messages import HumanMessage

from src.tools.marketing_db import (
    get_all_strategies,
    get_recent_research,
    get_pipeline_stats,
    save_digest,
    update_strategy_reviewed,
)

logger = logging.getLogger(__name__)

# Repo root — strategy docs are relative to this
REPO_ROOT = Path(__file__).parent.parent.parent


def _parse_action_items(doc_path: str) -> list[str]:
    """Extract unchecked `- [ ] ...` lines from a markdown file."""
    full_path = REPO_ROOT / doc_path
    if not full_path.exists():
        logger.warning("strategy doc not found: %s", full_path)
        return []
    content = full_path.read_text(encoding="utf-8")
    return re.findall(r"- \[ \] (.+)", content)


def _read_doc(doc_path: str) -> str:
    """Read a strategy doc, return its content (up to 4000 chars)."""
    full_path = REPO_ROOT / doc_path
    if not full_path.exists():
        return ""
    return full_path.read_text(encoding="utf-8")[:4000]


def _weeks_since_reviewed(last_reviewed_at: str | None) -> int | None:
    """Return weeks since last_reviewed_at, or None if never reviewed."""
    if not last_reviewed_at:
        return None
    dt = datetime.fromisoformat(last_reviewed_at.replace("Z", "+00:00"))
    delta = datetime.now(timezone.utc) - dt
    return delta.days // 7


def run(llm) -> str:
    """
    Run the strategy agent. Returns the generated digest content.
    `llm` is a LangChain BaseChatModel (use Claude Sonnet).
    """
    today = date.today()
    # Monday of this week
    week_date = str(today - timedelta(days=today.weekday()))

    strategies = get_all_strategies(status="active")
    logger.info("strategy_agent: reviewing %d active strategies", len(strategies))

    # --- Collect action items and doc summaries ---
    strategy_sections = []
    for s in strategies:
        action_items = _parse_action_items(s["doc_path"])
        weeks_since = _weeks_since_reviewed(s.get("last_reviewed_at"))
        neglected = weeks_since is not None and weeks_since >= 3

        section = f"### {s['name']} (slug: {s['slug']}, priority: {s['priority']})\n"
        if neglected:
            section += f"**WARNING: Not reviewed in {weeks_since} weeks.**\n"
        elif weeks_since is None:
            section += "**WARNING: Never reviewed.**\n"

        if action_items:
            section += f"Open action items ({len(action_items)}):\n"
            for item in action_items[:10]:  # cap at 10 per strategy
                section += f"- [ ] {item}\n"
        else:
            section += "No open action items found in doc.\n"
        strategy_sections.append(section)

    # --- Pipeline stats ---
    pipeline = get_pipeline_stats()
    pipeline_text = (
        f"Pipeline: {pipeline['by_status']}\n"
        f"Overdue follow-ups (no contact in 60d): {pipeline['overdue_follow_ups']}\n"
        f"Pending approvals: {pipeline['pending_approvals']}"
    )

    # --- Research findings this week ---
    findings = get_recent_research(days=7)
    if findings:
        research_text = "\n".join(
            f"- [{f['topic']}] {f['summary']}" for f in findings
        )
    else:
        research_text = "No research findings this week."

    # --- Build LLM prompt ---
    strategies_block = "\n\n".join(strategy_sections)
    prompt = f"""You are the marketing coordinator for Christopher Rehm, a watercolor and oil painter
based in Klosterlechfeld, Bavaria. Your job is to write his weekly marketing digest.

Today is {today.isoformat()}. Write a digest for the week of {week_date}.

## Strategy Status

{strategies_block}

## Pipeline (email outreach)

{pipeline_text}

## Research Findings This Week

{research_text}

---

Write a structured markdown digest with these sections:

### Focus this week
2-3 concrete recommended actions, highest priority first. Be specific — name the strategy and the action.

### Open action items
List all open action items grouped by strategy. Use `- [ ]` checkbox format.

### Research findings
Summarize what was found this week. If nothing, say so briefly.

### Pipeline signals
Note anything notable from the email outreach pipeline (contacts stacking up, overdue follow-ups, pending approvals).

### Strategies on hold
Brief note on any paused/on_hold strategies.

Keep the whole digest under 600 words. Write in a direct, practical tone. No marketing fluff."""

    logger.info("strategy_agent: generating digest with LLM")
    response = llm.invoke([HumanMessage(content=prompt)])
    digest_content = response.content

    # --- Save digest ---
    save_digest(week_date, digest_content)
    logger.info("strategy_agent: digest saved for week %s", week_date)

    # --- Mark all active strategies as reviewed ---
    for s in strategies:
        update_strategy_reviewed(s["id"])

    return digest_content
