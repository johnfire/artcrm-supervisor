# Setup & Operations

**Last Updated:** 2026-05-26
**Status:** current
**Read when:** first-time setup, running the pipeline, starting the UI, running research on a city

## Prerequisites

- PostgreSQL running with the `artcrm` database
- `uv` installed (`~/.local/bin/uv`)
- Proton Bridge running locally (required for email send/receive)
- Anthropic API key
- Google Maps API key (Places API New, billing enabled)
- DeepSeek API key (optional — only if using DeepSeek as `CHEAP_LLM`)

## Install

```bash
cd ~/ppp2/artcrm/artcrm-supervisor
cp .env.example .env
# fill in .env
uv sync --extra agents
```

## `.env` Keys

```
DATABASE_URL=postgresql://user:password@localhost/artcrm
ANTHROPIC_API_KEY=your_key
GOOGLE_MAPS_API_KEY=your_key

DEEPSEEK_API_KEY=your_key       # only if CHEAP_LLM=deepseek-chat
CHEAP_LLM=claude-haiku          # or deepseek-chat

PROTON_IMAP_HOST=127.0.0.1
PROTON_IMAP_PORT=1143
PROTON_SMTP_HOST=127.0.0.1
PROTON_SMTP_PORT=1025
PROTON_EMAIL=your@proton.me
PROTON_PASSWORD=bridge_app_password

SCOUT_THRESHOLD=75              # min fit score for outreach (0–100)
HOST=127.0.0.1
PORT=8000
```

## Run DB Migrations

```bash
uv run python scripts/migrate.py
```

Creates all tables. Safe to re-run — does not modify existing tables.

## Start the Web UI

```bash
uv run python -m src.api.main
# http://127.0.0.1:8000
```

## Run the Full Pipeline

```bash
uv run python -m src.supervisor.run
```

Runs enrich → scout → outreach → follow-up. Does not run research (research is always triggered per city).

## Run Research on a City

```bash
# Level 1 scan (always run first)
uv run python -m src.supervisor.run_research --city Konstanz --level 1

# Austrian city
uv run python -m src.supervisor.run_research --city Innsbruck --level 1 --country AT

# Or just tell Claude: "Run level 1 on Stuttgart"
```

## Scan Levels

| Level | What it finds                                          |
| ----- | ------------------------------------------------------ |
| 1     | Galleries, cafes, interior designers, coworking spaces |
| 2     | Gift shops, esoteric/wellness shops, concept stores    |
| 3     | Independent restaurants                                |
| 4     | Corporate offices and headquarters                     |
| 5     | Hotels                                                 |

Always run level 1 first. Others can follow in any order.

## Scout Threshold

Controls minimum fit score for a contact to be promoted to outreach:

```
SCOUT_THRESHOLD=75   # best venues only (default)
SCOUT_THRESHOLD=60   # more volume
SCOUT_THRESHOLD=50   # cast a wide net
```

Dropped contacts are kept in DB with scout reasoning in `notes`. Visible at `/contacts/?status=dropped`.

## Agent Packages — If Reinstall Needed

```bash
uv add --editable ../artcrm-research-agent
uv add --editable ../artcrm-enrichment-agent
uv add --editable ../artcrm-scout-agent
uv add --editable ../artcrm-outreach-agent
uv add --editable ../artcrm-followup-agent
```
