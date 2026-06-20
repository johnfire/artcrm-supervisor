# ArtCRM Supervisor — API Audit

**Date:** 2026-04-11  
**Project:** artcrm-supervisor

---

## 1. AI APIs

### Providers

| Provider  | Key Env Var         | SDK                                    |
| --------- | ------------------- | -------------------------------------- |
| Anthropic | `ANTHROPIC_API_KEY` | `langchain-anthropic`, `anthropic`     |
| DeepSeek  | `DEEPSEEK_API_KEY`  | `langchain-openai` (OpenAI-compatible) |

DeepSeek is accessed via `https://api.deepseek.com` using the OpenAI SDK with a custom `base_url`.

### Model Assignments by Agent

| Agent                              | Model                          | Provider  | Role                      |
| ---------------------------------- | ------------------------------ | --------- | ------------------------- |
| `supervisor/run_research.py`       | `CHEAP_LLM` → claude-haiku-4-5 | Anthropic | City venue research       |
| `supervisor/run_enrichment.py`     | deepseek-chat                  | DeepSeek  | Contact data enrichment   |
| `supervisor/run_scout.py`          | deepseek-chat                  | DeepSeek  | Contact scoring/filtering |
| `supervisor/run_requeue_unsent.py` | deepseek-chat                  | DeepSeek  | Requeue logic             |
| `supervisor/run_outreach.py`       | claude-sonnet-4-6              | Anthropic | Email drafting            |
| `supervisor/run_followup.py`       | claude-sonnet-4-6              | Anthropic | Follow-up email drafting  |
| `marketing/run_research.py`        | `CHEAP_LLM` → claude-haiku-4-5 | Anthropic | Marketing research scans  |
| `marketing/run_strategy.py`        | claude-sonnet-4-6              | Anthropic | Strategy synthesis        |

### Model Configuration

The `CHEAP_LLM` env var controls which model handles high-volume, routine tasks (research, enrichment, scouting). Currently set to `claude-haiku` in `.env`. The default fallback in code is `deepseek-chat`.

Writing tasks (outreach, followup, marketing strategy) are hardcoded to `claude-sonnet-4-6` and are not configurable via env.

The `deepseek-reasoner` (R1) model is supported in the LLM factory (`src/tools/llm.py`) but not used by any agent currently.

Agents in `run_enrichment.py`, `run_scout.py`, and `run_requeue_unsent.py` hardcode `deepseek-chat` directly — they bypass `CHEAP_LLM` entirely.

---

## 2. Non-AI APIs

### Google Places API (New)

| Property    | Value                                                               |
| ----------- | ------------------------------------------------------------------- |
| Key env var | `GOOGLE_MAPS_API_KEY`                                               |
| Endpoint    | `https://places.googleapis.com/v1/places:searchText`                |
| Used by     | `src/tools/search.py` → `google_maps_search()`                      |
| Purpose     | Venue discovery by city — up to 60 results per query (3 pages × 20) |
| Cost        | Pay-per-query (Google Maps Platform billing)                        |

### Brave Search API

| Property    | Value                                            |
| ----------- | ------------------------------------------------ |
| Key env var | `BRAVE_SEARCH_API_KEY`                           |
| Endpoint    | `https://api.search.brave.com/res/v1/web/search` |
| Used by     | `src/tools/search.py` → `web_search()`           |
| Purpose     | Web search during research and enrichment runs   |
| Cost        | Subscription-based                               |

### Google Custom Search API

| Property     | Value                                                            |
| ------------ | ---------------------------------------------------------------- |
| Key env vars | `GOOGLE_SEARCH_API_KEY`, `GOOGLE_SEARCH_CX`                      |
| Used by      | Configured in `src/config.py` — not actively called by any agent |
| Purpose      | Originally intended as web search backend; replaced by Brave     |
| Limit        | 100 queries/day on free tier                                     |

> **Note:** Keys are present in `.env` and `config.py` but `web_search()` uses Brave exclusively. Google Custom Search appears to be a legacy holdover.

### OpenStreetMap Overpass API

| Property    | Value                                     |
| ----------- | ----------------------------------------- |
| Key env var | None (no key required)                    |
| Endpoint    | `https://overpass-api.de/api/interpreter` |
| Used by     | `src/tools/search.py` → `geo_search()`    |
| Purpose     | Secondary geo venue lookup using OSM tags |
| Cost        | Free                                      |

### Proton Bridge (IMAP/SMTP)

| Property    | Value                                                     |
| ----------- | --------------------------------------------------------- |
| Credentials | `PROTON_EMAIL`, `PROTON_PASSWORD`                         |
| SMTP        | `127.0.0.1:1025`                                          |
| IMAP        | `127.0.0.1:1143`                                          |
| Purpose     | Send and receive emails via local Proton Bridge daemon    |
| Notes       | Not a remote API — requires Proton Bridge running locally |

### PostgreSQL

| Property | Value                                                          |
| -------- | -------------------------------------------------------------- |
| Env var  | `DATABASE_URL`                                                 |
| Purpose  | Primary application database (contacts, runs, approvals, etc.) |
| Notes    | Local instance — not a remote API                              |

---

## 3. Open Brain (Session Memory)

Open Brain is a custom-built persistent memory service used by Claude Code across all sessions. It is **not integrated into artcrm-supervisor's application code** — it is used only by Claude during interactive sessions to recall context and capture decisions.

### Architecture

```
Claude Code (Claude AI)
    |
    | MCP tools
    v
Open Brain MCP Server
    |
    +---> Supabase Postgres   (memory_units table — structured records)
    |     qaonmvqhlvrrvfkqcjbf.supabase.co
    |
    +---> Supabase pgvector   (content store — semantic search)
    |
    +---> Supabase Edge Fn    (ingest-thought — write endpoint)
    |
    +---> OpenRouter API      (embeddings + AI formation layer)
```

### Memory Tiers

| Tier           | Scope       | Volatility               | Purpose                                |
| -------------- | ----------- | ------------------------ | -------------------------------------- |
| 1 — Working    | Per-project | Volatile (~14 day decay) | Active task state, in-flight decisions |
| 2 — User Model | Global      | Stable                   | Identity, preferences, work style      |
| 3 — Archive    | Global      | Permanent                | Completed projects, resolved decisions |
| Content Store  | Global      | Immutable                | Uploaded documents (vector search)     |

### MCP Tools Available

`capture_thought`, `search_thoughts`, `list_thoughts`, `list_topic_hints`, `add_topic_hint`, `get_artifacts`, `push_artifact`, `complete_artifact`, `thought_stats`

### Credentials

| Component        | Details                            |
| ---------------- | ---------------------------------- |
| Supabase project | `qaonmvqhlvrrvfkqcjbf.supabase.co` |
| Ingest endpoint  | `.../functions/v1/ingest-thought`  |
| AI embeddings    | OpenRouter (`sk-or-v1-...`)        |
| MCP access key   | Stored in Open Brain config        |

### Connection to artcrm-supervisor

None. Open Brain is global infrastructure. The artcrm-supervisor agents do not read from or write to Open Brain. It is used exclusively by Claude Code during interactive sessions.

---

_Generated 2026-04-11_
