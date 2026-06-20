# artcrm-supervisor

Autonomous AI agent system for art venue outreach. Finds venues, scores them for fit, drafts emails, manages follow-ups. Primary interface is conversation with Claude via MCP. Five LangGraph agents chained by a supervisor graph.

## Run

```bash
# Full pipeline (enrich + scout + outreach + followup)
uv run python -m src.supervisor.run

# Research a city
uv run python -m src.supervisor.run_research --city München --level 1

# Web UI (http://127.0.0.1:8000)
uv run python -m src.api.main

# DB migrations
uv run python scripts/migrate.py
```

## Tests

```bash
uv run pytest
```

## Agent Packages (sibling dirs, installed as editable)

- `../artcrm-research-agent`
- `../artcrm-enrichment-agent`
- `../artcrm-scout-agent`
- `../artcrm-outreach-agent`
- `../artcrm-followup-agent`

## Doc Index

Read only the doc relevant to the current task.

| File                         | Domain             | Read when...                                                          |
| ---------------------------- | ------------------ | --------------------------------------------------------------------- |
| `docs/architecture.md`       | Architecture       | understanding the pipeline, agents, mission system, LLM strategy      |
| `docs/setup.md`              | Setup & Operations | install, env vars, running the pipeline, scan levels, scout threshold |
| `docs/database.md`           | Database           | schema, contact status flow, migrations, city registry                |
| `docs/apis.md`               | APIs & MCP         | external API keys, LLM config, MCP server setup                       |
| `docs/AGENTS.md`             | Agents             | detailed agent behaviour, how to operate them manually                |
| `docs/STATUSES.md`           | Statuses           | contact status reference                                              |
| `docs/IMPROVEMENT-IDEAS.md`  | Ideas              | future improvement ideas from real-world usage                        |
| `docs/ai-tools-audit.md`     | AI Tools           | roles of humans vs AI in the system                                   |
| `docs/markets-strategy.md`   | Strategy           | Bavarian art markets strategy                                         |
| `docs/plein-air-strategy.md` | Strategy           | plein air painting strategy and legal framework                       |
| `docs/open-brain-guide.md`   | Open Brain         | connecting to Open Brain from Python agents                           |
| `docs/RUNBOOK.md`            | Operations         | detailed end-to-end setup, operation, and testing runbook            |
| `docs/dns-records-to-add.md` | Deployment         | DNS records to add in Ionos for the VPS deployment                   |
| `docs/vps-deployment-plan.md` | Deployment        | plan for deploying the supervisor to the VPS (draft)                 |
| `docs/vps-email-server-plan.md` | Deployment      | plan for the Postfix + Dovecot VPS email server (draft)             |
