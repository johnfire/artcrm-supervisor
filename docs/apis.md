# External APIs & MCP Server

**Last Updated:** 2026-05-26
**Status:** current
**Read when:** API key issues, adding new integrations, MCP server config, LLM selection

## External APIs

### Anthropic (Claude)

| Env var  | `ANTHROPIC_API_KEY`                                 |
| -------- | --------------------------------------------------- |
| SDK      | `langchain-anthropic`, `anthropic`                  |
| Used for | Outreach drafts, follow-up emails (quality matters) |
| Model    | Claude Sonnet 4.6                                   |

### DeepSeek (optional)

| Env var  | `DEEPSEEK_API_KEY`                                           |
| -------- | ------------------------------------------------------------ |
| SDK      | `langchain-openai` (OpenAI-compatible)                       |
| Used for | Research, enrichment, scouting (high volume, cost-sensitive) |
| Model    | `deepseek-chat`                                              |

Set `CHEAP_LLM=deepseek-chat` in `.env` to use DeepSeek, or `CHEAP_LLM=claude-haiku` to use Claude Haiku 4.5 instead.

### Google Maps (Places API New)

| Env var  | `GOOGLE_MAPS_API_KEY`                                 |
| -------- | ----------------------------------------------------- |
| Billing  | Required — Places API New has per-request cost        |
| Used for | Research agent — finding venues by city + search term |

### Proton Bridge (Email)

| Env vars | `PROTON_IMAP_HOST`, `PROTON_IMAP_PORT`, `PROTON_SMTP_HOST`, `PROTON_SMTP_PORT`, `PROTON_EMAIL`, `PROTON_PASSWORD` |
| -------- | ----------------------------------------------------------------------------------------------------------------- |
| Requires | Proton Bridge running locally                                                                                     |
| Used for | Outreach agent (SMTP send), follow-up agent (IMAP read)                                                           |

IMAP reads by date window (14 days) rather than UNSEEN flag — ensures emails opened in Proton Mail directly are still processed.

### DuckDuckGo (Web Search)

No API key required. Used by research agent to supplement Google Maps results and catch venues Maps might miss.

## MCP Server

FastMCP server in `src/mcp/server.py`. The primary interface for operating the system.

**Start:**

```bash
uv run python -m src.mcp.server
```

Or configure in Claude Code's `.mcp.json` / `settings.json` to have it start automatically.

**What it exposes:** DB operations (read/write contacts, approvals, interactions) + agent runners (trigger research, run pipeline). Ask Claude to do something and it calls the right tool.
