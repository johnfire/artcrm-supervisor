# General Marketing Agent System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a two-agent marketing coordination system (research + strategy) that generates a weekly digest at `/marketing`, tracks all marketing strategies, and exposes conversational MCP tools.

**Architecture:** Two plain-Python sequential agents in `src/marketing/` (no LangGraph — simple batch jobs with no branching). `marketing_db.py` handles all DB access. The UI router and MCP tools are read-only consumers of what the agents write.

**Tech Stack:** Python, psycopg2, LangChain (for LLM calls), Jinja2 templates, FastAPI, FastMCP. All patterns follow existing codebase conventions.

---

## File Map

**Create:**

- `src/db/migrations/010_marketing_tables.sql` — 3 new tables + seed data
- `src/tools/marketing_db.py` — all DB functions for marketing tables
- `src/marketing/__init__.py` — empty
- `src/marketing/strategy_agent.py` — strategy agent logic
- `src/marketing/run_strategy.py` — entry point: `uv run python -m src.marketing.run_strategy`
- `src/marketing/research_agent.py` — research agent logic
- `src/marketing/run_research.py` — entry point: `uv run python -m src.marketing.run_research`
- `src/api/routers/marketing.py` — FastAPI router for `/marketing`
- `src/ui/templates/marketing.html` — page template
- `tests/test_marketing_db.py` — DB function unit tests

**Modify:**

- `src/api/main.py` — register marketing router
- `src/ui/templates/base.html` — add Marketing nav link
- `src/mcp/server.py` — add 4 MCP tools

---

## Stage 1: Foundation

### Task 1: DB Migration

**Files:**

- Create: `src/db/migrations/010_marketing_tables.sql`

- [ ] **Step 1: Write the migration**

```sql
-- Marketing strategies: one row per strategy, tracking layer alongside the markdown doc
CREATE TABLE IF NOT EXISTS marketing_strategies (
    id               serial PRIMARY KEY,
    name             text NOT NULL,
    slug             text UNIQUE NOT NULL,
    doc_path         text NOT NULL,
    status           text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'on_hold', 'paused')),
    priority         int NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    last_reviewed_at timestamptz,
    next_action_due  date,
    notes            text,
    created_at       timestamptz NOT NULL DEFAULT now()
);

-- Marketing research findings: one row per finding from the research agent
CREATE TABLE IF NOT EXISTS marketing_research (
    id          serial PRIMARY KEY,
    strategy_id int REFERENCES marketing_strategies(id) ON DELETE SET NULL,
    run_date    date NOT NULL,
    topic       text NOT NULL,
    summary     text NOT NULL,
    source_url  text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Weekly digests: one row per Monday
CREATE TABLE IF NOT EXISTS marketing_digests (
    id         serial PRIMARY KEY,
    week_date  date UNIQUE NOT NULL,
    content    text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Seed the three initial strategies
INSERT INTO marketing_strategies (name, slug, doc_path, status, priority)
VALUES
    ('Plein Air Visibility',  'plein-air',      'plein-air-strategy.md', 'active', 2),
    ('Art Markets',           'markets',         'markets-strategy.md',   'active', 2),
    ('Email Outreach Pipeline','email-outreach', 'AGENTS.md',             'active', 1)
ON CONFLICT (slug) DO NOTHING;
```

- [ ] **Step 2: Run the migration**

```bash
cd ~/programming/art-crm/artcrm-supervisor
uv run python scripts/migrate.py
```

Expected output includes lines mentioning `010_marketing_tables.sql` and no errors.

- [ ] **Step 3: Verify tables exist**

```bash
psql $DATABASE_URL -c "\dt marketing_*"
```

Expected: three rows — `marketing_strategies`, `marketing_research`, `marketing_digests`.

```bash
psql $DATABASE_URL -c "SELECT id, name, slug FROM marketing_strategies;"
```

Expected: 3 rows seeded.

- [ ] **Step 4: Commit**

```bash
git add src/db/migrations/010_marketing_tables.sql
git commit -m "feat: add marketing tables migration (strategies, research, digests)"
```

---

### Task 2: DB Tools

**Files:**

- Create: `src/tools/marketing_db.py`
- Test: `tests/test_marketing_db.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/programming/art-crm/artcrm-supervisor
uv run pytest tests/test_marketing_db.py -v 2>&1 | head -30
```

Expected: `ImportError` or `ModuleNotFoundError` — `src.tools.marketing_db` doesn't exist yet.

- [ ] **Step 3: Write the implementation**

```python
# src/tools/marketing_db.py
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
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_marketing_db.py -v
```

Expected: all 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/tools/marketing_db.py tests/test_marketing_db.py
git commit -m "feat: add marketing DB tools with tests"
```

---

### Task 3: UI Page (skeleton)

**Files:**

- Create: `src/api/routers/marketing.py`
- Create: `src/ui/templates/marketing.html`
- Modify: `src/api/main.py`
- Modify: `src/ui/templates/base.html`

- [ ] **Step 1: Write the router**

```python
# src/api/routers/marketing.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from src.tools.marketing_db import get_all_strategies, get_latest_digest, get_digest_archive, get_digest_by_id

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent.parent / "ui" / "templates"))


@router.get("/marketing/", response_class=HTMLResponse)
def marketing_page(request: Request):
    strategies = get_all_strategies()
    digest = get_latest_digest()
    archive = get_digest_archive(limit=12)
    return templates.TemplateResponse("marketing.html", {
        "request": request,
        "strategies": strategies,
        "digest": digest,
        "archive": archive,
    })


@router.get("/marketing/digest/{digest_id}", response_class=HTMLResponse)
def marketing_digest(request: Request, digest_id: int):
    digest = get_digest_by_id(digest_id)
    if not digest:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/marketing/")
    strategies = get_all_strategies()
    archive = get_digest_archive(limit=12)
    return templates.TemplateResponse("marketing.html", {
        "request": request,
        "strategies": strategies,
        "digest": digest,
        "archive": archive,
    })
```

- [ ] **Step 2: Write the template**

```html
{# src/ui/templates/marketing.html #} {% extends "base.html" %} {% block title
%}Marketing — ArtCRM Supervisor{% endblock %} {% block content %}
<div class="page-header">
  <h1>Marketing</h1>
  <span class="muted">Weekly strategy digest</span>
</div>

{% if digest %}
<section style="margin-bottom: 2rem;">
  <h2
    style="font-size:1rem; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); margin-bottom:.75rem;"
  >
    Digest — {{ digest.week_date }}
  </h2>
  <div class="digest-content" style="max-width:72ch; line-height:1.7;">
    {{ digest.content | replace('\n', '<br />') | safe }}
  </div>
</section>
{% else %}
<section style="margin-bottom: 2rem;">
  <p class="muted">
    No digest yet. Run
    <code>uv run python -m src.marketing.run_strategy</code> to generate one.
  </p>
</section>
{% endif %}

<section style="margin-bottom: 2rem;">
  <h2
    style="font-size:1rem; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); margin-bottom:.75rem;"
  >
    Strategies
  </h2>
  <table>
    <thead>
      <tr>
        <th>Name</th>
        <th>Status</th>
        <th>Priority</th>
        <th>Last reviewed</th>
        <th>Doc</th>
      </tr>
    </thead>
    <tbody>
      {% for s in strategies %}
      <tr>
        <td><strong>{{ s.name }}</strong></td>
        <td>
          <span
            class="badge {% if s.status == 'active' %}badge-green{% elif s.status == 'on_hold' %}badge-yellow{% else %}badge-grey{% endif %}"
          >
            {{ s.status }}
          </span>
        </td>
        <td class="center">{{ s.priority }}</td>
        <td class="muted small">
          {{ s.last_reviewed_at[:10] if s.last_reviewed_at else '—' }}
        </td>
        <td class="small">
          <a href="/static/docs/{{ s.doc_path }}" target="_blank"
            >{{ s.doc_path }}</a
          >
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</section>

{% if archive %}
<section>
  <h2
    style="font-size:1rem; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); margin-bottom:.75rem;"
  >
    Archive
  </h2>
  <ul style="list-style:none; padding:0; margin:0;">
    {% for d in archive %}
    <li style="margin-bottom:.25rem;">
      <a href="/marketing/digest/{{ d.id }}">{{ d.week_date }}</a>
      <span class="muted small">
        — {{ d.created_at[:10] if d.created_at else '' }}</span
      >
    </li>
    {% endfor %}
  </ul>
</section>
{% endif %} {% endblock %}
```

- [ ] **Step 3: Register the router in `src/api/main.py`**

Current line 7:

```python
from src.api.routers import approval, activity, contacts, people, research, inbox
```

Change to:

```python
from src.api.routers import approval, activity, contacts, people, research, inbox, marketing
```

After `app.include_router(inbox.router)` add:

```python
app.include_router(marketing.router)
```

- [ ] **Step 4: Add Marketing to nav in `src/ui/templates/base.html`**

After the Inbox nav link (line 30), add:

```html
    <a href="/marketing/" {% if request.url.path.startswith('/marketing') %}class="active"{% endif %}>
      Marketing
    </a>
```

- [ ] **Step 5: Start the server and verify the page loads**

```bash
uv run python -m src.api.main
```

Open `http://127.0.0.1:8000/marketing/` — expect the page to load with "No digest yet" message and the 3 seeded strategies in the table.

- [ ] **Step 6: Commit**

```bash
git add src/api/routers/marketing.py src/ui/templates/marketing.html src/api/main.py src/ui/templates/base.html
git commit -m "feat: add /marketing page (skeleton — strategies table, digest placeholder)"
```

---

## Stage 2: Strategy Agent

### Task 4: Strategy Agent

**Files:**

- Create: `src/marketing/__init__.py`
- Create: `src/marketing/strategy_agent.py`
- Create: `src/marketing/run_strategy.py`

- [ ] **Step 1: Create `src/marketing/__init__.py`**

Empty file:

```python
# src/marketing/__init__.py
```

- [ ] **Step 2: Write the strategy agent**

```python
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
```

- [ ] **Step 3: Write the entry point**

```python
# src/marketing/run_strategy.py
"""
Entry point for the marketing strategy agent.

Usage:
    uv run python -m src.marketing.run_strategy
"""
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    from src.tools.llm import get_llm
    from src.marketing.strategy_agent import run

    logger.info("Marketing strategy agent starting")
    llm = get_llm("claude")
    digest = run(llm)
    logger.info("Digest generated (%d chars)", len(digest))
    print("\n" + "=" * 60)
    print(digest)
    print("=" * 60)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the strategy agent manually**

```bash
uv run python -m src.marketing.run_strategy
```

Expected: logs show "reviewing 3 active strategies", "generating digest with LLM", "digest saved". Digest printed to stdout. No errors.

- [ ] **Step 5: Verify digest appears on the page**

Open `http://127.0.0.1:8000/marketing/` — digest content should now appear at the top.

- [ ] **Step 6: Commit**

```bash
git add src/marketing/__init__.py src/marketing/strategy_agent.py src/marketing/run_strategy.py
git commit -m "feat: add marketing strategy agent — generates weekly digest from strategy docs"
```

---

## Stage 3: Research Agent

### Task 5: Research Agent

**Files:**

- Create: `src/marketing/research_agent.py`
- Create: `src/marketing/run_research.py`

- [ ] **Step 1: Write the research agent**

```python
# src/marketing/research_agent.py
"""
Marketing Research Agent.

Two work streams:
1. General scan — fixed web searches on broad art marketing topics
2. Targeted monitoring — per-strategy searches generated by the LLM from each doc

Run via: uv run python -m src.marketing.run_research
"""
import logging
from datetime import date
from pathlib import Path

from langchain_core.messages import HumanMessage

from src.tools.marketing_db import (
    get_all_strategies,
    save_research_finding,
)
from src.tools.search import web_search

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent.parent

GENERAL_QUERIES = [
    "art marketing strategies for painters 2025 2026",
    "how to sell original paintings online Europe",
    "plein air painting marketing visibility strategies",
    "selling fine art at markets Germany Bavaria",
    "Instagram marketing for fine art painters",
    "art galleries Germany emerging artists open submissions 2026",
]


def _read_doc(doc_path: str) -> str:
    full_path = REPO_ROOT / doc_path
    if not full_path.exists():
        return ""
    return full_path.read_text(encoding="utf-8")[:3000]


def _get_monitoring_queries(llm, strategy_name: str, doc_content: str) -> list[str]:
    """Ask the LLM what to search for given this strategy doc."""
    if not doc_content.strip():
        return []
    prompt = f"""Given this marketing strategy document for artist Christopher Rehm, identify 2 specific
web search queries worth running this week — things to monitor: specific websites to check for updates,
application deadlines, events, regulatory changes, or opportunities mentioned in the doc.

Strategy: {strategy_name}

Document:
{doc_content}

Reply with exactly 2 search queries, one per line, no numbering or bullets. Just the queries."""

    response = llm.invoke([HumanMessage(content=prompt)])
    lines = [line.strip() for line in response.content.strip().splitlines() if line.strip()]
    return lines[:2]


def _synthesize_findings(llm, query: str, results: list[dict]) -> str | None:
    """Summarize search results into a 2-3 sentence finding."""
    if not results:
        return None
    snippets = "\n".join(
        f"- {r['title']}: {r['snippet']}" for r in results[:5]
    )
    prompt = f"""Summarize these web search results in 2-3 sentences for artist Christopher Rehm.
Focus on anything actionable or relevant to marketing original artwork.
If results are irrelevant or empty, reply with exactly: SKIP

Search query: {query}

Results:
{snippets}"""

    response = llm.invoke([HumanMessage(content=prompt)])
    summary = response.content.strip()
    if summary == "SKIP" or len(summary) < 20:
        return None
    return summary


def run(llm) -> int:
    """
    Run the research agent. Returns total number of findings saved.
    `llm` is a LangChain BaseChatModel (use CHEAP_LLM).
    """
    today = str(date.today())
    total_saved = 0

    # --- Work stream 1: General scan ---
    logger.info("research_agent: running %d general queries", len(GENERAL_QUERIES))
    for query in GENERAL_QUERIES:
        results = web_search(query, max_results=5)
        summary = _synthesize_findings(llm, query, results)
        if summary:
            source_url = results[0]["url"] if results else None
            save_research_finding(
                run_date=today,
                topic=query[:100],
                summary=summary,
                source_url=source_url,
                strategy_id=None,
            )
            total_saved += 1
            logger.info("research_agent: saved general finding for '%s'", query[:50])

    # --- Work stream 2: Targeted monitoring per strategy ---
    strategies = get_all_strategies(status="active")
    for s in strategies:
        doc_content = _read_doc(s["doc_path"])
        queries = _get_monitoring_queries(llm, s["name"], doc_content)
        logger.info(
            "research_agent: %d targeted queries for strategy '%s'",
            len(queries), s["name"]
        )
        for query in queries:
            results = web_search(query, max_results=5)
            summary = _synthesize_findings(llm, query, results)
            if summary:
                source_url = results[0]["url"] if results else None
                save_research_finding(
                    run_date=today,
                    topic=query[:100],
                    summary=summary,
                    source_url=source_url,
                    strategy_id=s["id"],
                )
                total_saved += 1
                logger.info(
                    "research_agent: saved targeted finding for strategy '%s'",
                    s["name"]
                )

    logger.info("research_agent: done — %d findings saved", total_saved)
    return total_saved
```

- [ ] **Step 2: Write the entry point**

```python
# src/marketing/run_research.py
"""
Entry point for the marketing research agent.

Usage:
    uv run python -m src.marketing.run_research
"""
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    from src.config import CHEAP_LLM
    from src.tools.llm import get_llm
    from src.marketing.research_agent import run

    logger.info("Marketing research agent starting")
    llm = get_llm(CHEAP_LLM)
    count = run(llm)
    logger.info("Research agent complete — %d findings saved", count)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the research agent manually**

```bash
uv run python -m src.marketing.run_research
```

Expected: logs show general queries running, targeted queries per strategy, total findings saved. No errors.

- [ ] **Step 4: Re-run the strategy agent to pick up research findings**

```bash
uv run python -m src.marketing.run_strategy
```

Expected: digest now includes a populated "Research findings" section.

Verify at `http://127.0.0.1:8000/marketing/`.

- [ ] **Step 5: Commit**

```bash
git add src/marketing/research_agent.py src/marketing/run_research.py
git commit -m "feat: add marketing research agent — general scan + targeted monitoring per strategy"
```

---

## Stage 4: MCP Tools

### Task 6: MCP Tools

**Files:**

- Modify: `src/mcp/server.py`

- [ ] **Step 1: Add the 4 MCP tools to `src/mcp/server.py`**

At the end of the file, after the existing tools, add:

```python
# =============================================================================
# MARKETING
# =============================================================================

@server.tool()
def marketing_digest_latest() -> str:
    """Get the most recent weekly marketing digest as markdown."""
    from src.tools.marketing_db import get_latest_digest
    digest = get_latest_digest()
    if not digest:
        return "No digest yet. Run: uv run python -m src.marketing.run_strategy"
    return f"**Week: {digest['week_date']}**\n\n{digest['content']}"


@server.tool()
def marketing_strategy_list() -> str:
    """List all marketing strategies with status, priority, and last reviewed date."""
    import json
    from src.tools.marketing_db import get_all_strategies
    strategies = get_all_strategies()
    return json.dumps(strategies, indent=2)


@server.tool()
def marketing_action_items() -> str:
    """List all open action items (unchecked checkboxes) across all active strategy docs."""
    import re
    from pathlib import Path
    from src.tools.marketing_db import get_all_strategies

    repo_root = Path(__file__).parent.parent.parent
    strategies = get_all_strategies(status="active")
    lines = []
    for s in strategies:
        doc_path = repo_root / s["doc_path"]
        if not doc_path.exists():
            continue
        content = doc_path.read_text(encoding="utf-8")
        items = re.findall(r"- \[ \] (.+)", content)
        if items:
            lines.append(f"## {s['name']}")
            for item in items:
                lines.append(f"- [ ] {item}")
            lines.append("")

    if not lines:
        return "No open action items found across active strategy docs."
    return "\n".join(lines)


@server.tool()
def marketing_research_recent(days: int = 14, strategy_slug: str = "") -> str:
    """
    Return recent marketing research findings.
    Args:
        days: How many days back to look (default 14).
        strategy_slug: Filter by strategy slug (e.g. 'plein-air'). Empty = all findings.
    """
    import json
    from src.tools.marketing_db import get_recent_research
    slug = strategy_slug if strategy_slug else None
    findings = get_recent_research(days=days, strategy_slug=slug)
    if not findings:
        return f"No research findings in the last {days} days."
    return json.dumps(findings, indent=2)
```

- [ ] **Step 2: Restart the MCP server and verify tools appear**

```bash
uv run python -m src.mcp.server
```

Check that `marketing_digest_latest`, `marketing_strategy_list`, `marketing_action_items`, `marketing_research_recent` appear in the tool list. No import errors.

- [ ] **Step 3: Commit**

```bash
git add src/mcp/server.py
git commit -m "feat: add 4 marketing MCP tools for conversational access"
```

---

## Stage 5: Cron Automation

### Task 7: Cron Jobs

**Files:**

- None (crontab edit only)

- [ ] **Step 1: Add the two Monday cron jobs**

```bash
crontab -e
```

Add these two lines:

```cron
0 6 * * 1  cd ~/programming/art-crm/artcrm-supervisor && uv run python -m src.marketing.run_research >> ~/logs/marketing-research.log 2>&1
0 7 * * 1  cd ~/programming/art-crm/artcrm-supervisor && uv run python -m src.marketing.run_strategy >> ~/logs/marketing-strategy.log 2>&1
```

- [ ] **Step 2: Verify crontab**

```bash
crontab -l | grep marketing
```

Expected: both lines visible.

- [ ] **Step 3: Verify log directory exists**

```bash
ls ~/logs/
```

Expected: directory exists (already used by existing crons per RUNBOOK).

- [ ] **Step 4: Final commit — update RUNBOOK with marketing agent info**

Add the following section to `RUNBOOK.md` after the existing agent descriptions, under a new `## Marketing Agents` heading:

````markdown
## Marketing Agents

Two agents that run every Monday to keep all marketing strategies coordinated.

### Marketing Research Agent

Runs Monday 6:00am. Performs general art marketing web searches and targeted monitoring
per strategy doc.

```bash
uv run python -m src.marketing.run_research
```
````

Logs: `~/logs/marketing-research.log`

### Marketing Strategy Agent

Runs Monday 7:00am (after research). Reads strategy docs, pipeline stats, and research
findings, then generates a weekly digest stored in `marketing_digests`.

```bash
uv run python -m src.marketing.run_strategy
```

Logs: `~/logs/marketing-strategy.log`

Digest visible at: `http://127.0.0.1:8000/marketing/`

````

```bash
git add RUNBOOK.md
git commit -m "docs: add marketing agent runbook entries"
````

---

## Self-Review

**Spec coverage check:**

| Spec requirement                                                         | Covered by task |
| ------------------------------------------------------------------------ | --------------- |
| 3 new DB tables                                                          | Task 1          |
| Seed 3 strategies at migration time                                      | Task 1          |
| DB functions (get, save, update)                                         | Task 2          |
| `/marketing` page with digest + strategies + archive                     | Task 3          |
| Marketing nav link                                                       | Task 3          |
| Strategy agent: parse action items                                       | Task 4          |
| Strategy agent: pipeline stats                                           | Task 4          |
| Strategy agent: generate digest (Claude Sonnet)                          | Task 4          |
| Strategy agent: update last_reviewed_at                                  | Task 4          |
| Research agent: general scan (6 queries)                                 | Task 5          |
| Research agent: targeted monitoring per strategy (LLM-generated queries) | Task 5          |
| Research agent: synthesize findings                                      | Task 5          |
| MCP tools (4)                                                            | Task 6          |
| Monday cron jobs                                                         | Task 7          |
| RUNBOOK update                                                           | Task 7          |

**No gaps found.**

**Type consistency check:**

- `save_research_finding(run_date: str, ...)` — used as string in both `research_agent.py` and `marketing_db.py`. Consistent.
- `get_all_strategies(status=None)` — called as `get_all_strategies()` and `get_all_strategies(status="active")`. Both forms handled. Consistent.
- `save_digest(week_date: str, content: str)` — called in `strategy_agent.py`. Consistent.
- `update_strategy_reviewed(strategy_id: int)` — called in `strategy_agent.py` with `s["id"]`. Consistent.
- `get_recent_research(days=14, strategy_slug=None)` — called in `strategy_agent.py` as `get_recent_research(days=7)` and in MCP tool as `get_recent_research(days=days, strategy_slug=slug)`. Consistent.
