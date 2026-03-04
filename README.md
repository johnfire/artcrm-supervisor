# artcrm-supervisor

Orchestrates the ArtCRM agent system. Runs alongside `theo-hits-the-road` against the same PostgreSQL database — it does not modify any existing tables.

## What this is

- LangGraph supervisor that coordinates research, scout, outreach, and follow-up agents
- FastAPI + lightweight browser UI for the approval queue and activity feed
- Concrete tool implementations that inject into each agent
- Mission configuration that defines what the agents are working toward

## Setup

```bash
cp .env.example .env
# fill in .env

uv sync
uv run python scripts/migrate.py   # adds agent tables to shared DB
uv run python -m src.api.main      # start the UI at http://127.0.0.1:8000
```

## Reconfiguring for a different domain

Edit `src/config.py`. Replace `ART_MISSION` with a new `Mission(...)` and point `ACTIVE_MISSION` at it. Nothing else changes.

## Structure

```
src/
  mission.py          Mission dataclass
  config.py           Art mission + all env config
  db/                 DB connection + migrations
  api/                FastAPI app + routers
  ui/                 Jinja2 templates + CSS
  tools/              Concrete tool implementations (added Phase 1+)
  supervisor/         LangGraph supervisor graph (added Phase 5)
```

## Support

If you find this useful, a small donation helps keep projects like this going:
[Donate via PayPal](https://paypal.me/christopherrehm001)
