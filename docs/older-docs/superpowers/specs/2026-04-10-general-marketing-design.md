# General Marketing Agent System — Design Spec

_artcrm-supervisor — April 2026_

---

## Problem

The existing artcrm pipeline automates one marketing strategy: find venues, email them. But Christopher runs multiple parallel marketing strategies (plein air visibility, art markets, email outreach, and more to come). These strategies live as markdown documents with no automation, no monitoring, and no coordination. There is no place to see the full picture.

This spec defines a general-marketing layer that sits above the existing pipeline and manages all strategies.

---

## Goals

1. Track 5–10 heterogeneous marketing strategies in one place
2. Run weekly web research — general art marketing landscape + targeted monitoring per strategy
3. Generate a weekly digest (every Monday) covering open action items, research findings, and pipeline signals
4. Surface the digest at `/marketing` in the existing UI
5. Allow conversational access via MCP tools from Claude Code

---

## Non-Goals

- Replacing or modifying the existing outreach pipeline
- Automating the execution of any strategy (the agents research and summarize; Christopher acts)
- A mobile app or push notifications (Telegram can be added later)

---

## Architecture

Two new agents added to artcrm-supervisor. Both follow the existing pattern: LangGraph `StateGraph`, tool-agnostic (dependencies injected by supervisor), no direct imports from the repo.

```
Monday 6:00am → Marketing Research Agent
                       ↓ writes to marketing_research
Monday 7:00am → Marketing Strategy Agent
                       ↓ reads marketing_research + strategy docs + pipeline DB
                       ↓ writes to marketing_digests

/marketing page ← reads marketing_digests + marketing_strategies
MCP tools       ← read marketing_digests + marketing_research + strategy docs
```

The existing outreach pipeline is unchanged. The marketing agents are an independent, additive layer.

---

## Data Layer

Three new tables in the existing PostgreSQL database.

### `marketing_strategies`

One row per strategy. The structured tracking layer that sits alongside the markdown doc.

| Column             | Type        | Notes                                                            |
| ------------------ | ----------- | ---------------------------------------------------------------- |
| `id`               | serial PK   |                                                                  |
| `name`             | text        | Human-readable name, e.g. "Plein Air Visibility"                 |
| `slug`             | text unique | e.g. `plein-air`, `markets`, `email-outreach`                    |
| `doc_path`         | text        | Relative path to the markdown file, e.g. `plein-air-strategy.md` |
| `status`           | text        | `active`, `on_hold`, `paused`                                    |
| `priority`         | int         | 1–5, 1 = highest                                                 |
| `last_reviewed_at` | timestamptz | Updated by strategy agent each Monday run                        |
| `next_action_due`  | date        | Optional; manually set or inferred from doc                      |
| `notes`            | text        | Free-text, agent-writable                                        |
| `created_at`       | timestamptz |                                                                  |

Seeded at migration time with three strategies:

- `plein-air-strategy.md` → slug `plein-air`, status `active`, priority 2
- `markets-strategy.md` → slug `markets`, status `active`, priority 2
- `AGENTS.md` → slug `email-outreach`, status `active`, priority 1, notes `"Automated pipeline — monitored via pipeline DB stats, not action item checkboxes"`

The email-outreach row has no `[ ]` checkboxes to parse. The strategy agent uses pipeline DB stats (contacts by status, response rates, overdue follow-ups) in place of action items for this strategy.

New strategies: write the markdown doc, insert a row.

### `marketing_research`

Research findings from the research agent. One row per finding.

| Column        | Type            | Notes                                                   |
| ------------- | --------------- | ------------------------------------------------------- |
| `id`          | serial PK       |                                                         |
| `strategy_id` | int FK nullable | NULL = general finding, not strategy-specific           |
| `run_date`    | date            | Monday the research ran                                 |
| `topic`       | text            | Short label, e.g. "Kunst & Design Markt Augsburg dates" |
| `summary`     | text            | LLM-synthesized 2–4 sentence summary                    |
| `source_url`  | text            | Primary source URL if applicable                        |
| `created_at`  | timestamptz     |                                                         |

### `marketing_digests`

Weekly digest output, stored as markdown.

| Column       | Type        | Notes                         |
| ------------ | ----------- | ----------------------------- |
| `id`         | serial PK   |                               |
| `week_date`  | date        | The Monday this digest covers |
| `content`    | text        | Full markdown digest          |
| `created_at` | timestamptz |                               |

One row per week. Re-running the strategy agent on the same Monday overwrites the existing row for that week.

---

## Agent 1: Marketing Research Agent

**Package:** `artcrm-marketing-research-agent`  
**Schedule:** Monday 6:00am  
**LLM:** `CHEAP_LLM` (deepseek-chat or claude-haiku)

### Steps

1. **general_scan** — runs 5–8 DuckDuckGo searches on broad art marketing topics:
   - What's working for painters selling online in Europe right now
   - Art marketing strategies for emerging artists
   - Plein air marketing and visibility approaches
   - Selling original art in Germany / Bavaria
   - Social media for fine art painters

   LLM synthesizes results into 3–5 findings. Each saved to `marketing_research` with `strategy_id = NULL`.

2. **targeted_monitoring** — reads all `active` strategies from `marketing_strategies`. For each, loads the markdown doc and passes it to the LLM with the prompt: "Given this strategy document, identify 1–3 specific things worth searching the web for this week — specific websites to check, deadlines mentioned, topics to monitor." The LLM returns a short list of search queries; the agent runs them. Examples of what it will produce:
   - `plein-air`: Munich Fußgängerzone permit system changes, Augsburg Ordnungsamt plein air rules
   - `markets`: kunst-designmarkt.at Augsburg dates, Bavarian art fair calendar
   - `email-outreach`: new gallery openings in target cities (Augsburg, Landsberg, Konstanz, etc.)

   Findings saved with `strategy_id` set to the relevant strategy.

### Output

Rows in `marketing_research` for this Monday's `run_date`.

---

## Agent 2: Marketing Strategy Agent

**Package:** `artcrm-marketing-strategy-agent`  
**Schedule:** Monday 7:00am (after research agent)  
**LLM:** Claude Sonnet

### Steps

1. **review_strategies** — for each active strategy:
   - Reads the markdown doc
   - Parses all `- [ ]` checkboxes → open action items
   - Checks `last_reviewed_at` — flags as neglected if >3 weeks since last review
   - Checks `next_action_due` — flags if overdue

2. **read_pipeline** — reads from the existing contacts/interactions tables:
   - Count of contacts by status (cold, contacted, accepted, etc.)
   - Contacts with `status=contacted` and no interaction in 60+ days
   - Recent outreach response rate (last 30 days)

   Surfaces anything that's marketing-relevant (e.g. "48 cold contacts uncontacted for 3+ weeks").

3. **read_research** — reads this week's `marketing_research` rows (today's `run_date`).

4. **generate_digest** — LLM writes a structured weekly digest in markdown. Sections:
   - **Focus this week** — 2–3 concrete recommended actions, highest priority first
   - **Open action items** — by strategy, all unchecked `[ ]` items from docs
   - **Research findings** — what the research agent found, general + per-strategy
   - **Pipeline signals** — anything notable from the outreach pipeline
   - **Strategies on hold** — brief note on anything paused/on-hold with why

   Stored in `marketing_digests` for this Monday.

5. **update_strategies** — sets `last_reviewed_at = now()` on all active strategies.

### Output

One row in `marketing_digests`. Updated `last_reviewed_at` on all active strategies.

---

## UI: `/marketing` Page

New page in the existing FastAPI UI. Same visual style as `/approvals` and `/inbox`.

**Layout (top to bottom):**

1. **This week's digest** — latest `marketing_digests` entry rendered as markdown. Prominent, full-width.
2. **Strategies** — table of all `marketing_strategies` rows: name, status (badge), priority, last reviewed date. Strategy name links to the raw markdown doc file.
3. **Digest archive** — collapsible section, past digests listed by week date. Click to expand any past digest.

No write operations from the UI — the page is read-only. Strategy docs are edited directly as markdown files.

---

## MCP Tools

Four new read-only tools added to the existing FastMCP server.

| Tool                        | Arguments                       | Returns                                                    |
| --------------------------- | ------------------------------- | ---------------------------------------------------------- |
| `marketing_digest_latest`   | —                               | Latest digest content as markdown                          |
| `marketing_strategy_list`   | —                               | All strategies with status, priority, last_reviewed        |
| `marketing_action_items`    | —                               | All open `[ ]` checkboxes parsed from active strategy docs |
| `marketing_research_recent` | `days=14`, `strategy_slug=None` | Recent research findings, optionally filtered by strategy  |

These are the conversational interface. When asked "what should I work on this week?" in Claude Code, these tools give the context to answer without re-running any agents.

---

## Cron Schedule

Added to the existing cron configuration:

```
0 6 * * 1  cd ~/programming/art-crm/artcrm-supervisor && uv run python -m src.marketing.run_research >> ~/logs/marketing-research.log 2>&1
0 7 * * 1  cd ~/programming/art-crm/artcrm-supervisor && uv run python -m src.marketing.run_strategy >> ~/logs/marketing-strategy.log 2>&1
```

Both run only on Monday (`* * 1`). Logs go to `~/logs/` per project convention.

Manual re-run at any time:

```bash
uv run python -m src.marketing.run_research
uv run python -m src.marketing.run_strategy
```

---

## Implementation Stages

### Stage 1 — Foundation

- DB migration: 3 new tables
- Seed `marketing_strategies` with 2 existing docs
- `/marketing` page: static layout, shows strategies table, placeholder where digest will go
- No agents yet

**Deliverable:** The page exists. Strategies are visible.

### Stage 2 — Strategy Agent

- Implement `artcrm-marketing-strategy-agent`
- Parses strategy docs for action items
- Reads pipeline data
- Generates and stores weekly digest
- `/marketing` page shows real digest content

**Deliverable:** Every Monday, a real digest appears on the page.

### Stage 3 — Research Agent

- Implement `artcrm-marketing-research-agent`
- General scan + targeted monitoring per strategy
- Research findings stored in DB
- Strategy agent digest gains a research section

**Deliverable:** Digest includes "what the web says this week."

### Stage 4 — MCP Tools

- 4 new read tools in FastMCP server
- Conversational access from Claude Code

**Deliverable:** "What should I work on?" answerable directly in Claude Code.

### Stage 5 — Cron Automation

- Monday 6am + 7am cron jobs
- Both agents run automatically each week

**Deliverable:** Fully hands-off. Every Monday the digest appears without manual intervention.

---

## File Layout (new files only)

```
src/
  marketing/
    __init__.py
    run_research.py       ← entry point for research agent
    run_strategy.py       ← entry point for strategy agent
    research_agent/       ← mirrors existing agent package structure
      graph.py
      nodes.py
      prompts.py
      tools.py
    strategy_agent/
      graph.py
      nodes.py
      prompts.py
      tools.py
  db/
    migrations/
      0010_marketing_tables.sql   ← 3 new tables
  mcp/
    marketing.py          ← 4 new MCP tools (imported by existing mcp server)
  ui/
    templates/
      marketing.html      ← new page template
  api/
    marketing.py          ← new FastAPI router for /marketing
```

Existing files modified:

- `src/api/main.py` — register marketing router
- `src/mcp/server.py` — import and register marketing MCP tools
