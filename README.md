# ArtCRM Supervisor

An autonomous AI agent system that finds art venues, researches them, drafts outreach emails, and manages follow-ups — all without a traditional interface. You talk to Claude, Claude talks to the system.

Built by Christopher Rehm as a practical tool for selling and displaying original artwork across Bavaria, Austria, and Switzerland. Designed to be repurposed for any industry where relationship-driven outreach matters.


This all works btw, youll need to download all the agents and then get api key or keys depending on the models you use. It could be adjusted to do sales resarch and out reach for any product.

---

## What It Does

The system runs a full outreach pipeline autonomously:

```
Research → Enrich → Scout → Outreach → Follow-up
```

1. **Research** — Uses Google Maps (Places API) to find every relevant venue in a city. Supplements with web search and page fetching to extract contact details. Cities are organised by scan level so you can run a quick level-1 scan first, then go deeper when needed.

2. **Enrich** — For every contact missing a website or email, searches the web and uses an LLM to fill in the gaps. Runs automatically on every pipeline invocation.

3. **Scout** — Scores each new contact 0–100 for mission fit. Contacts above the threshold are promoted to outreach. Below it, they're dropped with a reason saved so you can review. Scoring is informed by detailed notes written during research — including signals like "only shows blue-chip artists" or "actively seeks regional emerging artists".

4. **Outreach** — Drafts a personalised first-contact email for each venue ready to be contacted. Each draft goes into an approval queue — you review and send, or reject.

5. **Follow-up** — Reads the inbox, classifies replies (interested / rejected / opt-out), and drafts follow-up emails for contacts that haven't responded in 90+ days.

All of this runs on demand. You approve emails and trigger scans through conversation with Claude — no dashboard required.

---

## Architecture

### Agent packages

Each agent is an independent Python package built on LangGraph. They accept tools via Python Protocols — no direct database or API imports. This makes them testable in isolation and reusable in other contexts.

| Package                   | What it does                                                       |
| ------------------------- | ------------------------------------------------------------------ |
| `artcrm-research-agent`   | Google Maps + web search + page fetch, extracts and saves contacts |
| `artcrm-enrichment-agent` | Finds missing websites and emails for existing contacts            |
| `artcrm-scout-agent`      | Scores candidates for mission fit, promotes or drops               |
| `artcrm-outreach-agent`   | Drafts first-contact emails, queues for approval                   |
| `artcrm-followup-agent`   | Processes inbox replies, sends follow-ups to overdue contacts      |

### Supervisor

A LangGraph `StateGraph` that chains all five agents in sequence. Each agent can also be run standalone — useful for targeted scans or testing individual stages.

### Tools

Concrete implementations injected into agents at runtime:

- `db.py` — all PostgreSQL operations
- `search.py` — Google Maps Places API, DuckDuckGo web search, page fetching (HTML → plain text)
- `email.py` — Proton Bridge SMTP send + IMAP read
- `llm.py` — LLM factory (configurable: DeepSeek or Claude Haiku for research/scout, Claude Sonnet for outreach/followup)

### Web UI

FastAPI + Jinja2. Read-only views for reviewing what the agents are doing:

- `/approvals/` — email drafts awaiting your review
- `/contacts/` — full contact database with sort, filter, search, and pagination
- `/people/` — personal contacts (friends, collectors) kept separate from the business pipeline
- `/activity/` — agent run log
- `/research/` — city registry showing which scan levels have been run and how many contacts were found

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
    fit_criteria=(
        "Strong fit: galleries showing regional, emerging, or mid-career artists; "
        "venues that sell work on consignment; interior designers who source original art. "
        "Weak fit: galleries that exclusively represent blue-chip artists; chain businesses."
    ),
    outreach_style="personal, artist-direct, warm but professional...",
    language_default="de",
)
```

Every agent prompt is built from this object. To repurpose the system for a different domain — a photographer, a musician, a web developer — replace the mission and nothing else changes.

---

## Research: Scan Levels

Research is organised into five scan levels. Level 1 is always run first; the others can be run in any order once level 1 is complete. Each level has fixed Google Maps search terms so results are consistent and repeatable.

| Level | What it finds                                          |
| ----- | ------------------------------------------------------ |
| 1     | Galleries, cafes, interior designers, coworking spaces |
| 2     | Gift shops, esoteric/wellness shops, concept stores    |
| 3     | Independent restaurants                                |
| 4     | Corporate offices and headquarters                     |
| 5     | Hotels                                                 |

The city registry tracks last scan date, contacts found, and re-run status per level. Currently 82 cities across Germany (Bavaria, Baden-Württemberg), Austria (Tyrol, Vorarlberg, Salzburg), and Switzerland.

### Running a scan

```bash
# Run level 1 on a city
uv run python -m src.supervisor.run_research --city Konstanz --level 1

# Austrian city
uv run python -m src.supervisor.run_research --city Innsbruck --level 1 --country AT

# Run the full pipeline (enrich + scout + outreach + followup, no research)
uv run python -m src.supervisor.run
```

Or just tell Claude: _"Run level 1 on Stuttgart"_ — the MCP server handles it.

---

## How Research Works

For each city + level combination the research agent runs three steps:

1. **Google Maps search** — queries the Places API with fixed German-language terms for the level (e.g. `"Kunstgalerie Konstanz"`, `"Innenarchitekt Konstanz"`). Returns name, address, website, phone directly from Maps data.

2. **Web search supplement** — two DuckDuckGo queries add context and catch venues Google Maps might miss.

3. **Page fetch** — visits the top 3 URLs found, strips HTML to plain text, and feeds the content to the extraction LLM. This is what enables pulling emails, contact names, and gallery style signals (e.g. "shows emerging regional artists on consignment") from actual venue websites.

The extraction LLM writes detailed notes on each contact — gallery type, artist level, fit signals — which the scout agent uses for scoring.

---

## LLM Strategy

| Task                           | Model                 | Why                                   |
| ------------------------------ | --------------------- | ------------------------------------- |
| Research, enrichment, scouting | `CHEAP_LLM` (env var) | High volume, cost-sensitive           |
| Outreach drafts, follow-ups    | Claude Sonnet 4.6     | Quality matters when a human reads it |

`CHEAP_LLM` defaults to `deepseek-chat`. Set `CHEAP_LLM=claude-haiku` in `.env` to switch to Claude Haiku 4.5 — useful for comparing result quality.

---

## Setup

### Prerequisites

- PostgreSQL with an `artcrm` database
- `uv` package manager
- Proton Bridge running locally (for email send/receive)
- Anthropic API key
- Google Maps API key (Places API New, billing enabled)
- DeepSeek API key (optional — only needed if using DeepSeek as CHEAP_LLM)

### Install

```bash
git clone https://github.com/chrisRehm/artcrm-supervisor
cd artcrm-supervisor
cp .env.example .env
# fill in .env
uv sync --extra agents
```

### Configure `.env`

```
DATABASE_URL=postgresql://user:password@localhost/artcrm
ANTHROPIC_API_KEY=your_key
GOOGLE_MAPS_API_KEY=your_key

# Optional — only if using DeepSeek
DEEPSEEK_API_KEY=your_key

# LLM for high-volume tasks: deepseek-chat or claude-haiku
CHEAP_LLM=claude-haiku

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

Creates all tables including the city registry and scan tracking. Does not modify existing tables.

### Start the UI

```bash
uv run python -m src.api.main
# http://127.0.0.1:8000
```

### Run the pipeline

```bash
uv run python -m src.supervisor.run
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
2. Edit `src/supervisor/targets.py` — update `SCAN_LEVELS` with relevant Google Maps search terms
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
      migrations/           SQL migration files (001–004)
    tools/
      db.py                 All database operations
      search.py             Google Maps + DuckDuckGo + page fetching
      email.py              Proton Bridge SMTP/IMAP
      llm.py                LLM factory
    supervisor/
      targets.py            Scan level definitions (Google Maps terms per level)
      graph.py              LangGraph supervisor graph
      run.py                Full pipeline entry point
      run_research.py       Standalone research agent runner
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
