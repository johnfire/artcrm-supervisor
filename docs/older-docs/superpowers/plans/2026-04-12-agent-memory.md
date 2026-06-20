# Agent Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give artcrm agents two types of memory — an outreach quality loop that learns from warm replies, and a shared observation layer backed by Open Brain.

**Architecture:** A new `src/tools/memory.py` wraps Open Brain's MCP HTTP API (mcp SDK async, called via `asyncio.run()`). A new DB table `outreach_outcomes` tracks warm reply signals. The followup agent writes outcomes, the outreach agent reads learnings from Open Brain before drafting, the research agent writes city observations after scanning. A weekly analysis job synthesizes outcomes into Open Brain. The marketing page gains an Observations section.

**Tech Stack:** Python, PostgreSQL, Open Brain MCP (HTTP/mcp SDK 1.26), FastAPI/HTMX, Claude Sonnet (analysis), existing agent packages.

---

## File Map

**New files:**

- `migrations/011_outreach_outcomes.sql` — DB table
- `src/tools/memory.py` — Open Brain wrapper (`capture_thought`, `search_artcrm_thoughts`)
- `scripts/setup_memory.py` — one-time topic hint registration
- `src/supervisor/run_outreach_analysis.py` — weekly analysis job
- `src/ui/templates/partials/observations_list.html` — HTMX partial for observations

**Modified files:**

- `src/config.py` — add `OPEN_BRAIN_URL`, `OPEN_BRAIN_TOKEN`
- `src/tools/db.py` — add `record_warm_outcome()`, `get_outreach_outcomes()`
- `src/tools/__init__.py` — export new db functions
- `../artcrm-followup-agent/artcrm_followup_agent/protocols.py` — add `WarmOutcomeRecorder`
- `../artcrm-followup-agent/artcrm_followup_agent/graph.py` — call `record_warm_outcome` after warm/interested
- `src/supervisor/run_followup.py` — inject `record_warm_outcome`
- `src/supervisor/graph.py` — inject `record_warm_outcome`
- `../artcrm-outreach-agent/artcrm_outreach_agent/state.py` — add `learnings: list[str]`
- `../artcrm-outreach-agent/artcrm_outreach_agent/prompts.py` — `draft_email_prompt` accepts `learnings`
- `../artcrm-outreach-agent/artcrm_outreach_agent/graph.py` — pass learnings from state to prompt
- `src/supervisor/run_outreach.py` — fetch learnings, pass to `agent.invoke()`
- `src/supervisor/run_research.py` — `capture_thought` after agent run
- `src/api/routers/marketing.py` — add `GET/POST /marketing/observations`
- `src/ui/templates/marketing.html` — Observations section
- `src/ui/static/style.css` — observation card styles

**Test files:**

- `tests/test_memory.py` — new
- `tests/test_tools.py` — add `record_warm_outcome` tests
- `../artcrm-followup-agent/tests/` — warm outcome injection test
- `../artcrm-outreach-agent/tests/` — learnings injection test

---

## Task 1: DB Migration + Config

**Files:**

- Create: `migrations/011_outreach_outcomes.sql`
- Modify: `src/config.py`

- [ ] **Step 1: Write the migration**

Create `migrations/011_outreach_outcomes.sql`:

```sql
CREATE TABLE IF NOT EXISTS outreach_outcomes (
    id                   SERIAL PRIMARY KEY,
    contact_id           INTEGER NOT NULL REFERENCES contacts(id),
    sent_interaction_id  INTEGER REFERENCES interactions(id),
    reply_interaction_id INTEGER REFERENCES interactions(id),
    warm                 BOOLEAN NOT NULL DEFAULT true,
    word_count           INTEGER,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS outreach_outcomes_contact_id_idx ON outreach_outcomes(contact_id);
CREATE INDEX IF NOT EXISTS outreach_outcomes_created_at_idx ON outreach_outcomes(created_at);
```

- [ ] **Step 2: Apply the migration**

```bash
uv run python scripts/migrate.py
```

Expected: migration applies without error. Verify:

```bash
uv run python -c "
from src.db.connection import db
with db() as conn:
    cur = conn.cursor()
    cur.execute(\"SELECT COUNT(*) FROM outreach_outcomes\")
    print('table exists, rows:', cur.fetchone()[0])
"
```

- [ ] **Step 3: Add Open Brain config to src/config.py**

Add after the `EMAIL_ENABLED` line:

```python
# --- Open Brain memory ---
OPEN_BRAIN_URL: str = os.getenv("OPEN_BRAIN_URL", "")
OPEN_BRAIN_TOKEN: str = os.getenv("OPEN_BRAIN_TOKEN", "")
```

- [ ] **Step 4: Add values to .env**

Add to your `.env` file (get the exact values from `~/.claude.json` under `mcpServers.open-brain`):

```
OPEN_BRAIN_URL=https://qaonmvqhlvrrvfkqcjbf.supabase.co/functions/v1/open-brain-mcp
OPEN_BRAIN_TOKEN=<the Bearer token from ~/.claude.json mcpServers.open-brain.headers.Authorization>
```

- [ ] **Step 5: Commit**

```bash
git add migrations/011_outreach_outcomes.sql src/config.py
git commit -m "feat: add outreach_outcomes table and Open Brain config"
```

---

## Task 2: memory.py — Open Brain Wrapper

**Files:**

- Create: `src/tools/memory.py`
- Create: `tests/test_memory.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_memory.py`:

```python
"""Tests for src/tools/memory.py — Open Brain wrapper."""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


class TestCaptureThought:
    def test_calls_mcp_tool_with_artcrm_project(self):
        mock_result = MagicMock()
        mock_result.content = []

        with patch("src.tools.memory._run_tool") as mock_run:
            from src.tools.memory import capture_thought
            capture_thought("Munich galleries are cold this month")
        mock_run.assert_called_once_with(
            "capture_thought",
            {"content": "Munich galleries are cold this month", "project": "artcrm"},
        )

    def test_returns_none_silently_when_not_configured(self):
        with patch("src.tools.memory.OPEN_BRAIN_URL", ""), \
             patch("src.tools.memory.OPEN_BRAIN_TOKEN", ""):
            from src.tools.memory import capture_thought
            result = capture_thought("test")
        assert result is None


class TestSearchArtcrmThoughts:
    def test_returns_empty_list_when_not_configured(self):
        with patch("src.tools.memory.OPEN_BRAIN_URL", ""), \
             patch("src.tools.memory.OPEN_BRAIN_TOKEN", ""):
            from src.tools.memory import search_artcrm_thoughts
            result = search_artcrm_thoughts("email tone gallery")
        assert result == []

    def test_returns_empty_list_on_empty_response(self):
        with patch("src.tools.memory._run_tool", return_value=""):
            from src.tools.memory import search_artcrm_thoughts
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
            from src.tools.memory import search_artcrm_thoughts
            result = search_artcrm_thoughts("email tone")
        assert len(result) == 1
        assert "150 words" in result[0]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run python -m pytest tests/test_memory.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.tools.memory'`

- [ ] **Step 3: Write memory.py**

Create `src/tools/memory.py`:

```python
"""
Open Brain memory wrapper.

Provides two functions used by agents and the supervisor:
  capture_thought(content) — write an observation or learning to Open Brain
  search_artcrm_thoughts(query) — semantic search over artcrm-tagged thoughts

Both are no-ops when OPEN_BRAIN_URL / OPEN_BRAIN_TOKEN are not configured,
so tests and dev environments don't need the service available.
"""
import asyncio
import logging
import re

logger = logging.getLogger(__name__)


def _get_config() -> tuple[str, str]:
    from src.config import OPEN_BRAIN_URL, OPEN_BRAIN_TOKEN
    return OPEN_BRAIN_URL, OPEN_BRAIN_TOKEN


def _run_tool(tool_name: str, arguments: dict) -> str:
    """Call an Open Brain MCP tool synchronously. Returns empty string on failure."""
    url, token = _get_config()
    if not url or not token:
        return ""

    async def _inner() -> str:
        from mcp.client.streamable_http import streamablehttp_client
        from mcp import ClientSession
        headers = {"Authorization": f"Bearer {token}"}
        async with streamablehttp_client(url, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                texts = [c.text for c in result.content if hasattr(c, "text")]
                return "\n".join(texts)

    try:
        return asyncio.run(_inner())
    except Exception as e:
        logger.warning("memory: %s failed: %s", tool_name, e)
        return ""


def capture_thought(content: str, project: str = "artcrm") -> None:
    """Write an observation or learning to Open Brain."""
    _run_tool("capture_thought", {"content": content, "project": project})


def search_artcrm_thoughts(query: str, limit: int = 5) -> list[str]:
    """
    Semantic search over artcrm thoughts in Open Brain.
    Returns a list of content strings (metadata stripped), up to `limit`.
    Returns [] when unconfigured or on error.
    """
    raw = _run_tool("search_thoughts", {"query": f"artcrm {query}", "limit": limit, "threshold": 0.45})
    if not raw:
        return []

    results = []
    _METADATA = re.compile(
        r"^(Captured:|Type:|Project:|Status:|Topics:|People:|Actions:|---)",
        re.MULTILINE,
    )
    for block in re.split(r"--- Result \d+.*---", raw):
        lines = [
            l.strip() for l in block.splitlines()
            if l.strip() and not _METADATA.match(l.strip())
            and not l.strip().startswith("Found ")
        ]
        content = " ".join(lines).strip()
        if content:
            results.append(content)

    return results[:limit]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run python -m pytest tests/test_memory.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/tools/memory.py tests/test_memory.py
git commit -m "feat: Open Brain memory wrapper — capture_thought and search_artcrm_thoughts"
```

---

## Task 3: record_warm_outcome in DB Layer

**Files:**

- Modify: `src/tools/db.py`
- Modify: `src/tools/__init__.py`
- Test: `tests/test_tools.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_tools.py` inside the existing test file:

```python
class TestRecordWarmOutcome:
    def test_inserts_outcome_row(self):
        fake_sent = {"id": 10, "summary": "Subject: Hello World body word word word"}
        fake_reply = {"id": 11}
        fake_queue = {"id": 5, "draft_body": "word " * 120}

        with patch("src.tools.db.db") as mock_db:
            mock_conn = MagicMock()
            mock_db.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_db.return_value.__exit__ = MagicMock(return_value=False)
            mock_cur = MagicMock()
            mock_conn.cursor.return_value = mock_cur
            mock_cur.fetchone.side_effect = [fake_sent, fake_reply, fake_queue]

            from src.tools.db import record_warm_outcome
            record_warm_outcome(contact_id=42)

        mock_cur.execute.assert_called()

    def test_skips_silently_when_no_sent_interaction(self):
        with patch("src.tools.db.db") as mock_db:
            mock_conn = MagicMock()
            mock_db.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_db.return_value.__exit__ = MagicMock(return_value=False)
            mock_cur = MagicMock()
            mock_conn.cursor.return_value = mock_cur
            mock_cur.fetchone.return_value = None

            from src.tools.db import record_warm_outcome
            record_warm_outcome(contact_id=42)  # should not raise
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run python -m pytest tests/test_tools.py::TestRecordWarmOutcome -v
```

Expected: FAIL with `cannot import name 'record_warm_outcome'`

- [ ] **Step 3: Implement record_warm_outcome in src/tools/db.py**

Add after the `mark_bad_email` function (around line 265):

```python
def record_warm_outcome(contact_id: int) -> None:
    """
    Record that a contact sent a warm/interested reply.
    Looks up the most recent outbound and inbound interactions for the contact,
    and the most recently approved queue item for word count.
    Silently skips if no outbound interaction exists yet.
    """
    with db() as conn:
        cur = conn.cursor()

        # Most recent outbound interaction (the sent email)
        cur.execute(
            """
            SELECT id FROM interactions
            WHERE contact_id = %s AND direction = 'outbound' AND method = 'email'
            ORDER BY created_at DESC LIMIT 1
            """,
            (contact_id,),
        )
        sent_row = cur.fetchone()
        if not sent_row:
            logger.info("record_warm_outcome: no outbound interaction found for contact_id=%d — skipping", contact_id)
            return
        sent_interaction_id = sent_row["id"]

        # Most recent inbound interaction (the warm reply just logged)
        cur.execute(
            """
            SELECT id FROM interactions
            WHERE contact_id = %s AND direction = 'inbound' AND method = 'email'
            ORDER BY created_at DESC LIMIT 1
            """,
            (contact_id,),
        )
        reply_row = cur.fetchone()
        reply_interaction_id = reply_row["id"] if reply_row else None

        # Word count from the most recently approved draft body
        cur.execute(
            """
            SELECT draft_body FROM approval_queue
            WHERE contact_id = %s AND status IN ('approved', 'approved_unsent')
            ORDER BY reviewed_at DESC LIMIT 1
            """,
            (contact_id,),
        )
        queue_row = cur.fetchone()
        word_count = len(queue_row["draft_body"].split()) if queue_row else None

        cur.execute(
            """
            INSERT INTO outreach_outcomes
                (contact_id, sent_interaction_id, reply_interaction_id, warm, word_count)
            VALUES (%s, %s, %s, true, %s)
            """,
            (contact_id, sent_interaction_id, reply_interaction_id, word_count),
        )
        logger.info("record_warm_outcome: recorded for contact_id=%d word_count=%s", contact_id, word_count)
```

- [ ] **Step 4: Export from src/tools/**init**.py**

Add `mark_bad_email` line (around line 16), add `record_warm_outcome` after it:

```python
    mark_bad_email,
    record_warm_outcome,
```

And in `__all__` (around line 44), add:

```python
    "log_interaction", "get_contact_interactions", "set_opt_out", "mark_bad_email", "record_warm_outcome", "set_visit_when_nearby",
```

- [ ] **Step 5: Also add get_outreach_outcomes to db.py**

Add after `record_warm_outcome`:

```python
def get_outreach_outcomes(days: int = 90) -> list[dict]:
    """Return outreach_outcomes with sent email bodies for the last N days."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                oo.id, oo.contact_id, oo.warm, oo.word_count, oo.created_at,
                aq.draft_subject, aq.draft_body,
                c.name AS contact_name, c.city, c.type AS contact_type
            FROM outreach_outcomes oo
            JOIN contacts c ON c.id = oo.contact_id
            LEFT JOIN approval_queue aq ON aq.contact_id = oo.contact_id
                AND aq.status IN ('approved', 'approved_unsent')
            WHERE oo.created_at >= NOW() - %s * INTERVAL '1 day'
            ORDER BY oo.created_at DESC
            """,
            (days,),
        )
        return [_serialize_row(dict(r)) for r in cur.fetchall()]
```

- [ ] **Step 6: Run tests**

```bash
uv run python -m pytest tests/test_tools.py -v
```

Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add src/tools/db.py src/tools/__init__.py
git commit -m "feat: record_warm_outcome and get_outreach_outcomes DB helpers"
```

---

## Task 4: Followup Agent — Warm Outcome Recording

**Files:**

- Modify: `../artcrm-followup-agent/artcrm_followup_agent/protocols.py`
- Modify: `../artcrm-followup-agent/artcrm_followup_agent/graph.py`
- Modify: `src/supervisor/run_followup.py`
- Modify: `src/supervisor/graph.py`

- [ ] **Step 1: Add WarmOutcomeRecorder protocol**

In `../artcrm-followup-agent/artcrm_followup_agent/protocols.py`, add before `RunStarter`:

```python
class WarmOutcomeRecorder(Protocol):
    """Record that a contact sent a warm or interested reply. Used for outreach quality analysis."""
    def __call__(self, contact_id: int) -> None: ...
```

Also add the import at the top of protocols.py if not present:
`from typing import Any, Protocol` (already there)

- [ ] **Step 2: Add to create_followup_agent signature**

In `../artcrm-followup-agent/artcrm_followup_agent/graph.py`, update the `create_followup_agent` function signature. Add `record_warm_outcome: WarmOutcomeRecorder,` after `handle_bounce`:

```python
def create_followup_agent(
    llm: LanguageModel,
    fetch_inbox: InboxFetcher,
    match_contact: ContactMatcher,
    log_interaction: InteractionLogger,
    set_opt_out: OptOutSetter,
    handle_bounce: BounceHandler,
    record_warm_outcome: WarmOutcomeRecorder,   # ← add this line
    set_visit_when_nearby: VisitFlagSetter,
    ...
```

Also add `WarmOutcomeRecorder` to the imports from `.protocols`:

```python
from .protocols import (
    AgentMission, LanguageModel, InboxFetcher, ContactMatcher,
    InteractionLogger, OptOutSetter, BounceHandler, WarmOutcomeRecorder,
    VisitFlagSetter, InboxClassificationSaver, OverdueFetcher,
    ApprovalQueuer, RunStarter, RunFinisher,
)
```

- [ ] **Step 3: Call record_warm_outcome after warm/interested classification**

In `../artcrm-followup-agent/artcrm_followup_agent/graph.py`, find the block around line 240 that logs the interaction:

```python
            try:
                log_interaction(
                    contact_id=contact["id"],
                    method="email",
                    direction="inbound",
                    summary=f"{classification}: {msg.get('subject', '')}",
                    outcome=outcome_map.get(classification, "no_reply"),
                )
            except Exception:
                pass
```

After that `except` block, add:

```python
            # Record warm signal for outreach quality loop
            if classification in ("interested", "warm"):
                try:
                    record_warm_outcome(contact["id"])
                except Exception as e:
                    logger.warning("record_warm_outcome failed: contact_id=%s error=%s", contact.get("id"), e)
```

- [ ] **Step 4: Inject in run_followup.py**

In `src/supervisor/run_followup.py`, update the imports:

```python
    from src.tools import (
        read_inbox, match_contact_by_email, log_interaction, set_opt_out,
        mark_bad_email, set_visit_when_nearby, save_inbox_classification,
        record_warm_outcome,
        get_overdue_contacts, queue_for_approval,
        start_run, finish_run, get_llm,
    )
```

And update the `create_followup_agent` call to include:

```python
    agent = create_followup_agent(
        ...
        handle_bounce=mark_bad_email,
        record_warm_outcome=record_warm_outcome,
        ...
    )
```

- [ ] **Step 5: Inject in graph.py**

In `src/supervisor/graph.py`, find the `create_followup_agent` call and add `record_warm_outcome=record_warm_outcome` to the kwargs. Also import it at the top of the function where other tools are imported:

```python
        from src.tools import (
            ...
            record_warm_outcome,
            ...
        )
```

And add it to the `create_followup_agent(...)` call:

```python
        followup = create_followup_agent(
            ...
            handle_bounce=mark_bad_email,
            record_warm_outcome=record_warm_outcome,
            ...
        )
```

- [ ] **Step 6: Run supervisor tests**

```bash
uv run python -m pytest tests/test_supervisor.py -v
```

Expected: all pass

- [ ] **Step 7: Commit**

```bash
cd ../artcrm-followup-agent && git add artcrm_followup_agent/protocols.py artcrm_followup_agent/graph.py && git commit -m "feat: WarmOutcomeRecorder protocol — record warm reply signal for outreach quality loop" && cd ../artcrm-supervisor
git add src/supervisor/run_followup.py src/supervisor/graph.py
git commit -m "feat: inject record_warm_outcome into followup agent"
```

---

## Task 5: Outreach Agent — Learnings Injection

**Files:**

- Modify: `../artcrm-outreach-agent/artcrm_outreach_agent/state.py`
- Modify: `../artcrm-outreach-agent/artcrm_outreach_agent/prompts.py`
- Modify: `../artcrm-outreach-agent/artcrm_outreach_agent/graph.py`
- Modify: `src/supervisor/run_outreach.py`

- [ ] **Step 1: Add learnings to OutreachState**

In `../artcrm-outreach-agent/artcrm_outreach_agent/state.py`:

```python
from typing import TypedDict


class OutreachState(TypedDict):
    # --- inputs ---
    limit: int
    learnings: list[str]    # ← add: style notes from Open Brain, empty list if none

    # --- working state ---
    run_id: int
    contacts: list[dict]
    drafts: list[dict]
    errors: list[str]

    # --- output ---
    queued_count: int
    blocked_count: int
    summary: str
```

- [ ] **Step 2: Update draft_email_prompt to accept learnings**

In `../artcrm-outreach-agent/artcrm_outreach_agent/prompts.py`, update the `draft_email_prompt` signature and system prompt:

```python
def draft_email_prompt(
    mission: AgentMission,
    contact: dict,
    language: str,
    interactions: list[dict],
    website_content: str,
    learnings: list[str] | None = None,
) -> tuple[str, str]:
    opt_out = OPT_OUT_LINE.get(language, OPT_OUT_LINE["en"])

    learnings_section = ""
    if learnings:
        items = "\n".join(f"- {l}" for l in learnings)
        learnings_section = f"\nRecent learnings from past outreach (apply these patterns):\n{items}\n"

    system = (
        f"You are {mission.identity}.\n"
        f"Outreach style: {mission.outreach_style}"
        f"{learnings_section}"
    )
    # rest of function unchanged
```

- [ ] **Step 3: Pass learnings from state in draft_all**

In `../artcrm-outreach-agent/artcrm_outreach_agent/graph.py`, update the `init` function to include `learnings`:

```python
    def init(state: OutreachState) -> dict:
        run_id = start_run("outreach_agent", {"limit": state.get("limit", 20)})
        return {
            "run_id": run_id,
            "limit": state.get("limit", 20),
            "learnings": state.get("learnings", []),   # ← add
            "contacts": [],
            "drafts": [],
            "errors": [],
            "queued_count": 0,
            "blocked_count": 0,
            "summary": "",
        }
```

And in `draft_all`, pass learnings to `draft_email_prompt`:

```python
            system, user = draft_email_prompt(
                mission, contact, language,
                interactions=interactions,
                website_content=website_content,
                learnings=state.get("learnings", []),   # ← add
            )
```

- [ ] **Step 4: Fetch learnings in run_outreach.py before invoke**

In `src/supervisor/run_outreach.py`, update `main()`:

```python
def main():
    ...
    from src.tools.memory import search_artcrm_thoughts

    city_label = args.city or "all cities"
    logger.info("outreach: running for %s (limit=%d)", city_label, args.limit)

    learnings = search_artcrm_thoughts("outreach email tone style", limit=5)
    if learnings:
        logger.info("outreach: injecting %d learnings from Open Brain", len(learnings))

    result = agent.invoke({"limit": args.limit, "learnings": learnings})
    logger.info("Done: %s", result.get("summary", ""))
```

- [ ] **Step 5: Run tests**

```bash
uv run python -m pytest tests/ -v
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
cd ../artcrm-outreach-agent && git add artcrm_outreach_agent/state.py artcrm_outreach_agent/prompts.py artcrm_outreach_agent/graph.py && git commit -m "feat: inject Open Brain learnings into outreach draft prompt" && cd ../artcrm-supervisor
git add src/supervisor/run_outreach.py
git commit -m "feat: fetch Open Brain learnings before outreach run"
```

---

## Task 6: Research Agent — City Observation

**Files:**

- Modify: `src/supervisor/run_research.py`

- [ ] **Step 1: Capture city observation after research run**

In `src/supervisor/run_research.py`, after the `record_scan_result` call:

```python
    result = agent.invoke({
        "city": args.city,
        "country": args.country,
        "level": args.level,
    })

    summary = result.get("summary", "")
    contacts_found = len(result.get("saved_ids", []))
    record_scan_result(args.city, args.country, args.level, contacts_found)

    # Capture city scan observation in Open Brain for shared memory
    if contacts_found > 0:
        from src.tools.memory import capture_thought
        observation = (
            f"artcrm city scan: {args.city} (level {args.level}). "
            f"Found {contacts_found} new contacts. {summary}"
        )
        capture_thought(observation)
        logger.info("outreach memory: captured city observation for %s", args.city)

    logger.info("Done: %s", summary)
```

- [ ] **Step 2: Run tests**

```bash
uv run python -m pytest tests/ -v
```

Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add src/supervisor/run_research.py
git commit -m "feat: capture city scan observation in Open Brain after research run"
```

---

## Task 7: Weekly Analysis Job

**Files:**

- Create: `src/supervisor/run_outreach_analysis.py`

- [ ] **Step 1: Create the analysis job**

Create `src/supervisor/run_outreach_analysis.py`:

```python
"""
Weekly outreach quality analysis.

Reads outreach_outcomes for the last 90 days, groups warm vs cold,
fetches the draft bodies, and asks Claude Sonnet to synthesize patterns.
Writes the synthesis to Open Brain.

Skips if fewer than MIN_WARM_OUTCOMES warm outcomes exist (not enough signal).

Usage:
    uv run python -m src.supervisor.run_outreach_analysis
    uv run python -m src.supervisor.run_outreach_analysis --days 60
"""
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MIN_WARM_OUTCOMES = 5


def main():
    parser = argparse.ArgumentParser(description="Analyse outreach outcomes and write learnings to Open Brain")
    parser.add_argument("--days", type=int, default=90)
    args = parser.parse_args()

    from src.tools.db import get_outreach_outcomes
    from src.tools.memory import capture_thought
    from src.tools.llm import get_llm
    from langchain_core.messages import SystemMessage, HumanMessage

    outcomes = get_outreach_outcomes(days=args.days)
    warm = [o for o in outcomes if o["warm"]]
    cold = [o for o in outcomes if not o["warm"]]

    if len(warm) < MIN_WARM_OUTCOMES:
        logger.info(
            "analysis: only %d warm outcomes (need %d) — skipping, not enough signal yet",
            len(warm), MIN_WARM_OUTCOMES,
        )
        return

    def _fmt(o: dict) -> str:
        body = (o.get("draft_body") or "")[:800]
        subject = o.get("draft_subject") or ""
        words = o.get("word_count") or "?"
        city = o.get("city") or "?"
        ctype = o.get("contact_type") or "?"
        return f"[{ctype} / {city} / {words} words]\nSubject: {subject}\n{body}"

    warm_block = "\n\n---\n\n".join(_fmt(o) for o in warm[:20])
    cold_block  = "\n\n---\n\n".join(_fmt(o) for o in cold[:20])

    system = (
        "You are analysing email outreach patterns for a watercolor painter "
        "reaching out to galleries and venues in Germany. "
        "Be specific and actionable. Write in English. "
        "Keep your answer under 200 words — bullet points preferred."
    )
    user = (
        f"Below are emails that received WARM replies ({len(warm)} total, showing up to 20):\n\n"
        f"{warm_block}\n\n"
        f"---\n\n"
        f"And emails that did NOT receive warm replies ({len(cold)} total, showing up to 20):\n\n"
        f"{cold_block}\n\n"
        f"What patterns distinguish the emails that got warm replies? "
        f"Consider: tone, length, subject line style, personalization, opening sentence, "
        f"mention of specific venue details, and language style. "
        f"Be specific — mention word counts, phrases, or structural patterns you notice."
    )

    llm = get_llm("claude")
    response = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    synthesis = response.content.strip()

    thought = (
        f"artcrm outreach learning ({args.days}-day analysis, "
        f"{len(warm)} warm / {len(cold)} cold):\n\n{synthesis}"
    )
    capture_thought(thought)
    logger.info("analysis: learning written to Open Brain (%d chars)", len(thought))
    logger.info("synthesis:\n%s", synthesis)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add to crontab**

Run:

```bash
crontab -e
```

Add this line (Monday 7:30am, after research at 6am and strategy at 7am):

```
30 7 * * 1  cd ~/programming/art-crm/artcrm-supervisor && .venv/bin/python -m src.supervisor.run_outreach_analysis >> ~/logs/artcrm-outreach-analysis.log 2>&1
```

Verify:

```bash
crontab -l | grep outreach-analysis
```

- [ ] **Step 3: Run tests**

```bash
uv run python -m pytest tests/ -v
```

Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add src/supervisor/run_outreach_analysis.py
git commit -m "feat: weekly outreach analysis job — synthesises warm/cold patterns to Open Brain"
```

---

## Task 8: Marketing UI — Observations Section

**Files:**

- Modify: `src/api/routers/marketing.py`
- Modify: `src/ui/templates/marketing.html`
- Create: `src/ui/templates/partials/observations_list.html`
- Modify: `src/ui/static/style.css`

- [ ] **Step 1: Add observation endpoints to marketing.py**

In `src/api/routers/marketing.py`, add after the existing imports:

```python
from src.tools.memory import capture_thought, search_artcrm_thoughts
```

Add these two routes before the `marketing_digest` route:

```python
@router.get("/marketing/observations", response_class=HTMLResponse)
def observations_list(request: Request, topic: str = ""):
    query = f"{topic} " if topic else ""
    thoughts = search_artcrm_thoughts(f"{query}artcrm", limit=20)
    return templates.TemplateResponse("partials/observations_list.html", {
        "request": request,
        "observations": thoughts,
        "topic": topic,
    })


@router.post("/marketing/observations", response_class=HTMLResponse)
def add_observation(request: Request, content: str = Form(...)):
    if content.strip():
        capture_thought(content.strip())
    thoughts = search_artcrm_thoughts("artcrm", limit=20)
    return templates.TemplateResponse("partials/observations_list.html", {
        "request": request,
        "observations": thoughts,
        "topic": "",
    })
```

- [ ] **Step 2: Load observations on the main marketing page**

In `src/api/routers/marketing.py`, update `marketing_page()`:

```python
@router.get("/marketing/", response_class=HTMLResponse)
def marketing_page(request: Request):
    strategies = get_all_strategies()
    digest = _render_digest(get_latest_digest())
    archive = get_digest_archive(limit=12)
    observations = search_artcrm_thoughts("artcrm", limit=20)
    return templates.TemplateResponse("marketing.html", {
        "request": request,
        "strategies": strategies,
        "digest": digest,
        "archive": archive,
        "observations": observations,
    })
```

- [ ] **Step 3: Create partials/observations_list.html**

Create `src/ui/templates/partials/observations_list.html`:

```html
{% if observations %} {% for obs in observations %}
<article class="observation-card">
  <p class="observation-content">{{ obs }}</p>
</article>
{% endfor %} {% else %}
<p class="muted">
  No observations yet. Add one below or run a city research scan.
</p>
{% endif %}
```

- [ ] **Step 4: Add Observations section to marketing.html**

In `src/ui/templates/marketing.html`, add before `{% endblock %}`:

```html
<section style="margin-top:2rem;" id="observations-section">
  <h2
    style="font-size:1rem; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); margin-bottom:.75rem;"
  >
    Observations
  </h2>

  <form
    hx-post="/marketing/observations"
    hx-target="#observations-list"
    hx-swap="innerHTML"
    hx-on::after-request="this.reset()"
    style="display:flex; gap:.5rem; margin-bottom:1rem;"
  >
    <input
      type="text"
      name="content"
      placeholder="What did you notice? (city, venue type, tone, season...)"
      style="flex:1;"
    />
    <button type="submit" class="btn-primary btn-sm">Add</button>
  </form>

  <div
    id="observations-list"
    hx-get="/marketing/observations"
    hx-trigger="load"
  >
    {% include "partials/observations_list.html" %}
  </div>
</section>
```

- [ ] **Step 5: Add CSS for observation cards**

In `src/ui/static/style.css`, append:

```css
.observation-card {
  padding: 0.6rem 0.75rem;
  border-left: 2px solid var(--border);
  margin-bottom: 0.5rem;
  background: var(--surface);
}
.observation-content {
  margin: 0;
  line-height: 1.5;
  font-size: 0.92rem;
}
```

- [ ] **Step 6: Run tests**

```bash
uv run python -m pytest tests/ -v
```

Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add src/api/routers/marketing.py src/ui/templates/marketing.html src/ui/templates/partials/observations_list.html src/ui/static/style.css
git commit -m "feat: Observations section on marketing page — add/view Open Brain artcrm thoughts"
```

---

## Task 9: Setup Script + Final Push

**Files:**

- Create: `scripts/setup_memory.py`

- [ ] **Step 1: Create the setup script**

Create `scripts/setup_memory.py`:

```python
"""
One-time setup for the agent memory system.

1. Verifies outreach_outcomes table exists (created by migration 011)
2. Registers topic hints in Open Brain to guide thought classification

Run once after deploying:
    uv run python scripts/setup_memory.py
"""
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TOPIC_HINTS = [
    {
        "topic": "artcrm-outreach",
        "description": "Email tone, word count, subject lines, response rates for art CRM outreach",
        "category": "projects",
    },
    {
        "topic": "artcrm-city",
        "description": "City-level notes for art CRM: venue density, responsiveness, regional patterns",
        "category": "projects",
    },
    {
        "topic": "artcrm-venue",
        "description": "Venue type patterns for art CRM: galleries, hotels, cafes, coworking spaces",
        "category": "projects",
    },
    {
        "topic": "artcrm-seasonal",
        "description": "Seasonal observations for art CRM: plein air season, events, time-of-year patterns",
        "category": "projects",
    },
]


def main():
    from src.tools.memory import _run_tool

    for hint in TOPIC_HINTS:
        result = _run_tool("add_topic_hint", hint)
        logger.info("Registered topic hint '%s': %s", hint["topic"], result[:80] if result else "ok")

    logger.info("Setup complete.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the setup script**

```bash
uv run python scripts/setup_memory.py
```

Expected: 4 topic hints registered, no errors.

- [ ] **Step 3: Run full test suite**

```bash
uv run python -m pytest tests/ -v
```

Expected: all pass

- [ ] **Step 4: Final commit and push**

```bash
git add scripts/setup_memory.py
git commit -m "feat: setup_memory.py — register Open Brain topic hints for artcrm"
git push
```

---

## Verification

After deployment, verify the system end-to-end:

```bash
# 1. Check the table exists and is queryable
uv run python -c "from src.tools.db import get_outreach_outcomes; print(get_outreach_outcomes())"

# 2. Test a manual Open Brain write
uv run python -c "
from src.tools.memory import capture_thought, search_artcrm_thoughts
capture_thought('artcrm test: memory system deployed successfully', project='artcrm')
import time; time.sleep(2)
results = search_artcrm_thoughts('memory system deployed')
print('found:', results)
"

# 3. Test the marketing observations page loads
uv run uvicorn src.api.main:app --port 8001 &
curl -s http://localhost:8001/marketing/ | grep -o 'Observations'
```
