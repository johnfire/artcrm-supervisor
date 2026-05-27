# Architecture

**Last Updated:** 2026-05-26
**Status:** current
**Read when:** understanding how the system works, adding agents, modifying the pipeline

## Summary

ArtCRM Supervisor is an autonomous AI agent system that finds art venues, scores them for fit, drafts outreach emails, and manages follow-ups. The primary interface is conversation with Claude — no dashboard required. Five LangGraph agents are chained by a supervisor graph. Tools (DB, search, email, LLM) are injected via Python Protocols so agents are testable in isolation.

## Pipeline

```
Research → Enrich → Scout → Outreach → Follow-up
```

| Agent      | Package                   | What it does                                                            |
| ---------- | ------------------------- | ----------------------------------------------------------------------- |
| Research   | `artcrm-research-agent`   | Google Maps + web search + page fetch, extracts and saves contacts      |
| Enrichment | `artcrm-enrichment-agent` | Finds missing websites/emails for existing contacts                     |
| Scout      | `artcrm-scout-agent`      | Scores candidates 0–100 for mission fit, promotes or drops              |
| Outreach   | `artcrm-outreach-agent`   | Drafts first-contact emails, queues for approval                        |
| Follow-up  | `artcrm-followup-agent`   | Reads inbox, classifies replies, drafts follow-ups for overdue contacts |

Each agent is an independent Python package built on LangGraph. They live as sibling directories and are installed as editable packages into the supervisor's virtualenv.

## Supervisor

A LangGraph `StateGraph` in `src/supervisor/graph.py` chains all five agents in sequence. Each agent can also be run standalone for targeted scans or testing.

## Tools (injected via Protocol)

| Module                | Purpose                                                                       |
| --------------------- | ----------------------------------------------------------------------------- |
| `src/tools/db.py`     | All PostgreSQL operations                                                     |
| `src/tools/search.py` | Google Maps Places API, DuckDuckGo web search, page fetch (HTML → plain text) |
| `src/tools/email.py`  | Proton Bridge SMTP send + IMAP read                                           |
| `src/tools/llm.py`    | LLM factory (configurable cheap model + Claude Sonnet for quality tasks)      |

## Mission System

Everything is driven by a `Mission` object in `src/config.py`:

```python
ART_MISSION = Mission(
    goal="Find venues across Germany and Bavaria...",
    identity="Christopher Rehm, watercolor and oil painter...",
    targets="galleries, hotel lobbies, restaurants, corporate offices...",
    fit_criteria="Strong fit: galleries showing regional emerging artists...",
    outreach_style="personal, artist-direct, warm but professional...",
    language_default="de",
)
```

Every agent prompt is built from this object. To repurpose for a different vertical: replace `Mission(...)` in `config.py` and update scan terms in `src/supervisor/targets.py`. Nothing else changes.

## LLM Strategy

| Task                           | Model                                          | Reason                              |
| ------------------------------ | ---------------------------------------------- | ----------------------------------- |
| Research, enrichment, scouting | `CHEAP_LLM` env var (default: `deepseek-chat`) | High volume, cost-sensitive         |
| Outreach drafts, follow-ups    | Claude Sonnet 4.6                              | Quality matters, human will read it |

Set `CHEAP_LLM=claude-haiku` in `.env` to switch to Claude Haiku 4.5.

## Web UI

FastAPI + Jinja2 + HTMX. Read-only review interface at `http://127.0.0.1:8000`:

- `/approvals/` — email drafts awaiting review
- `/contacts/` — full contact DB with sort, filter, search, pagination
- `/people/` — personal contacts (friends, collectors), separate from business pipeline
- `/activity/` — agent run log
- `/research/` — city registry showing scan levels run and contacts found per city

## MCP Server

FastMCP server in `src/mcp/server.py`. Exposes DB and agent tools to Claude directly. Primary interface for most operations — talk to Claude, Claude runs the pipeline.

## File Structure

```
src/
  mission.py          Mission dataclass
  config.py           Active mission + env config
  db/
    connection.py     db() context manager
    migrations/       SQL migration files (001–004)
  tools/
    db.py, search.py, email.py, llm.py
  supervisor/
    targets.py        Scan level definitions (Google Maps terms per level)
    graph.py          LangGraph supervisor graph
    run.py            Full pipeline entry point
    run_research.py   Standalone research runner
  mcp/server.py       FastMCP server
  api/routers/        FastAPI route handlers
  ui/templates/       Jinja2 + HTMX templates
scripts/
  migrate.py          Run all DB migrations
  import_contacts_leads.py
  import_studies.py
```
