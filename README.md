# ArtCRM Supervisor

An autonomous AI agent system that finds art venues, researches them, drafts outreach emails, and manages follow-ups — all without a traditional interface. You talk to Claude, Claude talks to the system.

Built by Christopher Rehm as a practical tool for selling and displaying original artwork across Bavaria, Austria, and Switzerland. Designed to be repurposed for any industry where relationship-driven outreach matters.

---

## What It Does

The system runs a full outreach pipeline autonomously:

```
Research → Enrich → Scout → Outreach → Follow-up
```

1. **Research** — Searches the web and OpenStreetMap for venues (galleries, hotels, coworking spaces, interior designers, concept stores, etc.) across a queue of 82 cities and counting. Processes 3 cities per day automatically.

2. **Enrich** — For every contact missing a website or email, searches the web and uses an LLM to extract contact details. Runs automatically on every pipeline invocation.

3. **Scout** — Scores each new contact 0–100 for mission fit. Contacts above the threshold are promoted to outreach. Below it, they're dropped with a reason saved so you can review.

4. **Outreach** — Drafts a personalised first-contact email for each venue ready to be contacted. Each draft goes into an approval queue — you review and send, or reject.

5. **Follow-up** — Reads the inbox, classifies replies (interested / rejected / opt-out), and drafts follow-up emails for contacts that haven't responded in 90+ days.

All of this runs on a schedule. You approve emails and adjust strategy through conversation with Claude — no dashboard required.

---

## Architecture

### Agent packages

Each agent is an independent Python package built on LangGraph. They accept tools via Python Protocols — no direct database or API imports. This makes them testable in isolation and reusable in other contexts.

| Package                   | What it does                                                       |
| ------------------------- | ------------------------------------------------------------------ |
| `artcrm-research-agent`   | Generates search queries, runs geo + web search, extracts contacts |
| `artcrm-enrichment-agent` | Finds missing websites and emails for existing contacts            |
| `artcrm-scout-agent`      | Scores candidates for mission fit, promotes or drops               |
| `artcrm-outreach-agent`   | Drafts first-contact emails, queues for approval                   |
| `artcrm-followup-agent`   | Processes inbox replies, sends follow-ups to overdue contacts      |

### Supervisor

A LangGraph `StateGraph` that chains all five agents in sequence. Uses a PostgreSQL checkpointer so a crash mid-run resumes from where it left off.

### Tools

Concrete implementations injected into agents at runtime:

- `db.py` — all PostgreSQL operations
- `search.py` — Overpass geo search + DuckDuckGo web search
- `email.py` — Proton Bridge SMTP send + IMAP read
- `llm.py` — LLM factory (DeepSeek for research/scout, Claude for outreach/followup)

### Web UI

FastAPI + Jinja2. Read-only views for reviewing what the agents are doing:

- `/approvals/` — email drafts awaiting your review
- `/contacts/` — full contact database with sort, filter, search, and pagination
- `/people/` — personal contacts (friends, collectors) kept separate from the business pipeline
- `/activity/` — agent run log
- `/research/` — research queue showing which cities have been covered and when

### MCP Server

A FastMCP server exposes the database and agent tools to Claude directly. This is the primary interface — most operations happen through conversation, not the web UI.

---

## The Mission System

The entire system is driven by a `Mission` object defined in `src/config.py`:

```python
ART_MISSION = Mission(
    goal="Find venues across Germany and Bavaria that display and sell original artwork...",
    identity="Christopher Rehm, watercolor and oil painter based in Klosterlechfeld, Bavaria",
    targets="galleries, hotel lobbies, restaurants, corporate offices, cafes, coworking spaces",
    fit_criteria="open to original artwork, contemporary or traditional style welcome...",
    outreach_style="personal, artist-direct, warm but professional...",
    language_default="de",
)
```

Every agent prompt is built from this object. To repurpose the system for a different domain — a photographer, a musician, a web developer — replace the mission and nothing else changes.

---

## Research Queue

Rather than running all research targets in one go, the system maintains a `research_queue` table in the database. Each run picks the 3 cities researched longest ago (or never) and runs all 8 industries for each. At 3 cities per day the full queue of 82 cities completes in ~27 days, then cycles again — useful since new venues open regularly.

Current target industries per city:
`gallery`, `restaurant`, `hotel`, `cafe`, `interior designer`, `coworking space`, `corporate office`, `concept store`

Current cities: 82 across Germany (Bavaria, Baden-Württemberg), Austria (Tyrol, Vorarlberg, Salzburg), and Switzerland.

---

## LLM Strategy

- **DeepSeek** (`deepseek-chat`) — research, enrichment, scouting. High volume, low cost.
- **Claude** (`claude-sonnet`) — outreach drafts and follow-up emails. Quality matters when a human reads it.

---

## Setup

### Prerequisites

- PostgreSQL with an `artcrm` database
- `uv` package manager
- Proton Bridge running locally (for email send/receive)
- DeepSeek API key
- Anthropic API key

### Install

```bash
git clone https://github.com/your-username/artcrm-supervisor
cd artcrm-supervisor
cp .env.example .env
# fill in .env
uv sync --extra agents
```

### Configure `.env`

```
DATABASE_URL=postgresql://user:password@localhost/artcrm
DEEPSEEK_API_KEY=your_key
ANTHROPIC_API_KEY=your_key

PROTON_IMAP_HOST=127.0.0.1
PROTON_IMAP_PORT=1143
PROTON_SMTP_HOST=127.0.0.1
PROTON_SMTP_PORT=1025
PROTON_EMAIL=your@proton.me
PROTON_PASSWORD=bridge_app_password

SCOUT_THRESHOLD=75   # minimum fit score for outreach (0-100)
HOST=127.0.0.1
PORT=8000
```

### Run migrations

```bash
uv run python scripts/migrate.py
```

Creates the agent tables (`agent_runs`, `approval_queue`, `consent_log`, `inbox_messages`, `research_queue`, `people`) in your existing database. Does not modify existing tables.

### Start the UI

```bash
uv run python -m src.api.main
# http://127.0.0.1:8000
```

### Run the pipeline

```bash
uv run python -m src.supervisor.run
```

### Schedule daily runs (cron)

```cron
0 7 * * * cd /home/christopher/programming/artcrm-supervisor && /home/christopher/.local/bin/uv run python -m src.supervisor.run >> /home/christopher/logs/supervisor.log 2>&1
```

---

## Contact Status Flow

```
candidate   — found by research agent, not yet scored
    ↓
cold        — scored ≥ threshold by scout, ready for outreach
    ↓
contacted   — first email sent and approved
    ↓
meeting     — positive reply, meeting scheduled (set manually)
    ↓
accepted    — venue agreed to display/sell work
    ↓
dormant     — opted out or gone quiet for a long time
dropped     — scored below threshold or disqualified (reason saved in notes)
```

---

## Scout Threshold

Controls the minimum fit score for a contact to be promoted to outreach:

```
SCOUT_THRESHOLD=75   # best venues only (default)
SCOUT_THRESHOLD=60   # more volume
SCOUT_THRESHOLD=50   # cast a wide net
```

Dropped contacts are kept in the database with the scout's reasoning in the `notes` field. Visible at `/contacts/?status=dropped`.

---

## Repurposing for Another Industry

1. Edit `src/config.py` — write a new `Mission(...)` and set `ACTIVE_MISSION` to it
2. Edit `src/supervisor/targets.py` — update the `CITIES` list and `INDUSTRIES` for your domain
3. Nothing else changes — all agents pick up the new mission automatically

Example missions that would work out of the box:

- Freelance photographer seeking corporate clients
- Music act seeking venue bookings
- Web studio seeking SME clients
- Artisan / craftsperson seeking retail stockists

---

## File Structure

```
artcrm-supervisor/
  src/
    mission.py              Mission dataclass
    config.py               Active mission + env config
    db/
      connection.py         db() context manager
      migrations/           SQL migration files
    tools/
      db.py                 All database operations
      search.py             Geo search + web search
      email.py              Proton Bridge SMTP/IMAP
      llm.py                LLM factory
    supervisor/
      targets.py            City + industry lists
      graph.py              LangGraph supervisor graph
      run.py                Entry point
    mcp/
      server.py             FastMCP server
    api/
      routers/              FastAPI route handlers
    ui/
      templates/            Jinja2 + HTMX templates
      static/style.css
  scripts/
    migrate.py              Run all DB migrations
    import_contacts_leads.py  One-time spreadsheet import
    import_studies.py       Import pre-existing research markdown files
  tests/
  RUNBOOK.md                Detailed operational guide
  .env.example
```

---

## Related Packages

These live as sibling directories and are installed as editable packages:

- `artcrm-research-agent`
- `artcrm-enrichment-agent`
- `artcrm-scout-agent`
- `artcrm-outreach-agent`
- `artcrm-followup-agent`

---

## Licence

Free to use, study, and modify for personal or commercial projects.

**Not licensed for resale.** You may not sell this software, offer it as a hosted service, or incorporate it into a product sold to others without explicit written permission from the author.

---

## Support

If you find this useful, a small donation helps keep projects like this going:
[Donate via PayPal](https://paypal.me/christopherrehm001)
