# ArtCRM Supervisor — AI Tools Audit

**Date:** 2026-04-22  
**Project:** artcrm-supervisor

---

## Roles

There are two humans and one AI in this system:

- **Christopher** (the user) — owns the business, reviews and approves outreach drafts, directs strategy
- **General Manager** (Claude Code, claude-sonnet-4-6) — interactive AI that reasons, writes code, orchestrates the pipeline on request, and captures/retrieves context via Open Brain
- **The pipeline** — everything else: a set of Python orchestration classes that execute predetermined sequences of HTTP API calls

## Overview

This document maps every AI model and AI-adjacent service used in artcrm-supervisor.

**The key architectural point:** outside of the General Manager, nothing in this system is truly "agentic." Every other so-called agent is a Python class (`_ResearchAgent`, `_OutreachAgent`, etc.) that orchestrates a fixed sequence of HTTP requests — LLM API calls to DeepSeek or Anthropic, plus search API calls to Brave/Google/OSM. The "intelligence" lives entirely in the remote APIs. There is no local inference, no running model process, and no dynamic reasoning about what to do next. The word "agent" describes the role, not the architecture.

---

## 1. Agents & AI Models

### Agent Roster

| Agent                    | Model             | Provider  | Where                                                   | Purpose                                                                        |
| ------------------------ | ----------------- | --------- | ------------------------------------------------------- | ------------------------------------------------------------------------------ |
| **General Manager**      | claude-sonnet-4-6 | Anthropic | Claude Code (interactive)                               | Strategy, code changes, pipeline orchestration on request                      |
| **Research**             | deepseek-chat     | DeepSeek  | `supervisor/run_research.py`                            | City/level scans — finds raw venue candidates via Brave + Google Places        |
| **Enrichment**           | deepseek-chat     | DeepSeek  | `supervisor/run_enrichment.py`, `run_requeue_unsent.py` | Fills missing website/email for contacts using Brave Search                    |
| **Scout**                | deepseek-chat     | DeepSeek  | `supervisor/run_scout.py`                               | Scores candidates, promotes best fits to cold contacts                         |
| **Outreach**             | claude-sonnet-4-6 | Anthropic | `supervisor/run_outreach.py`                            | Drafts cold emails — customer-facing, so premium model                         |
| **Followup**             | claude-sonnet-4-6 | Anthropic | `supervisor/run_followup.py`                            | Inbox classification + overdue follow-up drafts                                |
| **Outreach Analyst**     | claude-sonnet-4-6 | Anthropic | `supervisor/run_outreach_analysis.py`                   | Weekly: analyzes 90 days of warm/cold outcomes, writes learnings to Open Brain |
| **Marketing Researcher** | deepseek-chat     | DeepSeek  | `marketing/run_research.py`, `research_agent.py`        | 6 general + per-strategy Brave queries; synthesizes findings                   |
| **Marketing Strategist** | claude-sonnet-4-6 | Anthropic | `marketing/run_strategy.py`, `strategy_agent.py`        | Weekly digest — pipeline stats + research → structured markdown                |

### Model Configuration

The `CHEAP_LLM` env var (default: `deepseek-chat`) controls the model for high-volume, routine tasks. Writing tasks (outreach, followup, marketing strategy) are hardcoded to `claude-sonnet-4-6`.

`deepseek-reasoner` (R1) is supported in `src/tools/llm.py` but not currently used by any agent.

**Cost split logic:** DeepSeek handles volume work (research, enrichment, scouting). Claude handles anything customer-facing or requiring judgment (outreach, followup, digest).

### LLM Pricing (USD)

| Model             | Input / 1M tokens | Output / 1M tokens | Cached / 1M tokens |
| ----------------- | ----------------- | ------------------ | ------------------ |
| deepseek-chat     | $0.27             | $1.10              | $0.07              |
| deepseek-reasoner | $0.55             | $2.19              | $0.14              |
| claude-sonnet-4-6 | $3.00             | $15.00             | —                  |
| claude-haiku-4-5  | $0.80             | $4.00              | —                  |

All LLM calls are tracked via `_CostCallback` in `src/tools/llm.py` and recorded to the `run_costs` table.

---

## 2. Search APIs

| Service                    | Env Var                | Endpoint                | Used By                                  | Cost         | Purpose                                                        |
| -------------------------- | ---------------------- | ----------------------- | ---------------------------------------- | ------------ | -------------------------------------------------------------- |
| **Brave Search**           | `BRAVE_SEARCH_API_KEY` | `api.search.brave.com`  | Research, Enrichment, Marketing Research | $0.005/query | Web search for lead discovery and market research              |
| **Google Places**          | `GOOGLE_MAPS_API_KEY`  | `places.googleapis.com` | Research                                 | Pay-per-use  | Venue discovery with structured data (phone, website, address) |
| **OpenStreetMap Overpass** | None (free)            | `overpass-api.de`       | Research (fallback)                      | Free         | Free geo venue discovery alternative                           |

### Brave Search Detail

- Up to 20 results per query, 8 returned by default
- Cost tracked per-run in `run_costs` table (`brave_queries` column)
- Used in: Research (venue queries), Enrichment (website/email lookup), Marketing Research (6 general + 2 per active strategy)

### Google Places Detail

- Up to 3 pages × 20 results = 60 results per query
- Language: German by default; region from city country code
- Fields returned: displayName, formattedAddress, websiteUri, phone numbers
- Fallback: returns empty list if API key missing or request fails

---

## 3. Memory Layer — Open Brain

Open Brain is a persistent memory service used in two contexts:

### 3a. Claude Code (Interactive Sessions)

Claude Code reads from and writes to Open Brain via MCP tools during every interactive session. This is the global-manager layer — context captured here persists across all sessions.

| Operation                  | Tool              | When             |
| -------------------------- | ----------------- | ---------------- |
| Read prior context         | `search_thoughts` | Start of session |
| Capture decisions/progress | `capture_thought` | End of session   |

### 3b. Artcrm-supervisor Application Code

The supervisor agents also call Open Brain directly via `src/tools/memory.py` (HTTP MCP client):

| File                                  | Operation         | Purpose                                                    |
| ------------------------------------- | ----------------- | ---------------------------------------------------------- |
| `supervisor/run_outreach.py`          | `search_thoughts` | Fetch outreach tone/style learnings before drafting emails |
| `supervisor/run_outreach_analysis.py` | `capture_thought` | Save weekly outreach pattern analysis                      |
| `supervisor/run_research.py`          | `capture_thought` | Save city scan observations after each research run        |

**Config:** `OPEN_BRAIN_URL` + `OPEN_BRAIN_TOKEN` in `.env`. Auth header: `x-brain-key`. Timeout: 10s per call.

---

## 4. Data Flow Summary

```
[Cron / Claude Code]
        |
        v
  Research Agent (DeepSeek)
    + Brave Search
    + Google Places / OSM
        |
        v → captures city observation to Open Brain
  Enrichment Agent (DeepSeek)
    + Brave Search
        |
        v
  Scout Agent (DeepSeek)
        |
        v
  Outreach Agent (Claude Sonnet) ← fetches learnings from Open Brain
        |
        v
  Approval Queue (Human review)
        |
        v
  Followup Agent (Claude Sonnet)

[Weekly Cron]
  Marketing Research Agent (DeepSeek) + Brave Search
        |
        v
  Marketing Strategy Agent (Claude Sonnet)

[Weekly Cron]
  Outreach Analyst (Claude Sonnet) → writes patterns to Open Brain
```

---

## 5. Configured but Inactive

| Service              | Env Vars                                    | Notes                                                                      |
| -------------------- | ------------------------------------------- | -------------------------------------------------------------------------- |
| Google Custom Search | `GOOGLE_SEARCH_API_KEY`, `GOOGLE_SEARCH_CX` | Present in config, not called anywhere — legacy holdover from before Brave |
| claude-haiku-4-5     | `ANTHROPIC_API_KEY`                         | Supported in LLM factory, not assigned to any agent                        |
| deepseek-reasoner    | `DEEPSEEK_API_KEY`                          | Supported in LLM factory, not assigned to any agent                        |

---

## 6. Function Reference

All public functions in the codebase, grouped by file.

### src/tools/costs.py — Cost tracking

| Function                                                        | Description                                                         |
| --------------------------------------------------------------- | ------------------------------------------------------------------- |
| `reset_costs()`                                                 | Resets module-level cost counters to zero for a new run             |
| `record_search(n)`                                              | Records N search API queries for cost tracking                      |
| `record_llm(model, input_tokens, output_tokens, cached_tokens)` | Records token usage for an LLM request                              |
| `get_costs()`                                                   | Returns full cost breakdown dict with total USD and per-model usage |
| `format_costs()`                                                | Returns one-line cost summary string for logging                    |

### src/tools/db.py — Database access

| Function                                                                             | Description                                                                        |
| ------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| `save_contact(...)`                                                                  | Inserts a new contact (deduplicates by name+city), returns contact id              |
| `get_candidates(limit, city)`                                                        | Returns candidate/lead_unverified contacts, optionally by city                     |
| `get_cold_contacts(limit, city)`                                                     | Returns cold contacts ready for first outreach                                     |
| `update_contact(contact_id, status, fit_score, notes)`                               | Updates contact status, fit score, and notes                                       |
| `get_contacts_needing_enrichment(limit, city)`                                       | Returns contacts missing email, prioritising never-enriched                        |
| `update_contact_details(contact_id, **kwargs)`                                       | Updates arbitrary contact fields and stamps enriched_at                            |
| `match_contact_by_email(from_email)`                                                 | Finds a contact by email with domain fallback                                      |
| `ensure_consent_log(contact_id)`                                                     | Creates consent_log entry if one doesn't exist                                     |
| `check_compliance(contact_id)`                                                       | Returns True if outreach is permitted (opt-out/erasure check)                      |
| `mark_bad_email(contact_id)`                                                         | Marks email as undeliverable, sets status=bad_email                                |
| `record_warm_outcome(contact_id)`                                                    | Records that a contact sent an interested reply                                    |
| `get_outreach_outcomes(days)`                                                        | Returns outreach outcomes with email bodies for the last N days                    |
| `set_opt_out(contact_id)`                                                            | Records opt-out and sets status=do_not_contact                                     |
| `queue_for_approval(contact_id, run_id, subject, body)`                              | Inserts draft into approval queue, returns queue item id                           |
| `log_interaction(contact_id, method, direction, summary, outcome)`                   | Logs a contact interaction and updates updated_at                                  |
| `get_overdue_contacts(days)`                                                         | Returns contacted contacts with no interaction in N days                           |
| `save_inbox_message(message_id, from_email, subject, body, received_at)`             | Caches inbox message with deduplication, returns id                                |
| `get_unprocessed_inbox()`                                                            | Returns inbox messages not yet processed by followup agent                         |
| `mark_message_processed(inbox_message_id, contact_id)`                               | Marks message processed, optionally links to contact                               |
| `save_inbox_classification(inbox_message_id, contact_id, classification, reasoning)` | Persists LLM classification for an inbox message                                   |
| `set_visit_when_nearby(contact_id)`                                                  | Flags contact for a personal visit next time nearby                                |
| `get_cities(country)`                                                                | Returns all cities from master list, optionally by country                         |
| `get_city_market_context(city, country)`                                             | Returns market_character and notes for a city                                      |
| `update_city_market(city, country, character, notes)`                                | Updates market_character/notes for a city                                          |
| `add_city(city, country, region)`                                                    | Adds city to master list, or updates region if exists                              |
| `get_city_scan_status(city, country)`                                                | Returns scan records for a city across all levels                                  |
| `get_all_city_scan_status()`                                                         | Returns all cities with scan status and contact counts                             |
| `record_scan_result(city, country, level, contacts_found)`                           | Records completed scan result (create or update)                                   |
| `can_run_level(city, country, level)`                                                | Checks if a scan level can run (level 1 always allowed; others need level 1 first) |
| `get_contact_interactions(contact_id)`                                               | Returns all interactions for a contact, newest first                               |
| `start_run(agent_name, input_data)`                                                  | Inserts new agent_run with status=running, returns run_id                          |
| `finish_run(run_id, status, summary, output_data)`                                   | Updates agent_run with completion status, summary, and costs                       |
| `get_run_costs(limit)`                                                               | Returns recent run costs joined with agent_run summaries                           |

### src/tools/email.py — Email (Proton Bridge)

| Function                              | Description                                                                   |
| ------------------------------------- | ----------------------------------------------------------------------------- |
| `send_email(to_email, subject, body)` | Sends plain-text email via Proton Bridge SMTP, returns True/False             |
| `read_inbox(limit, since_days)`       | Reads recent emails via Proton Bridge IMAP, saves to DB, returns new messages |

### src/tools/llm.py — LLM factory

| Function         | Description                                                                                                  |
| ---------------- | ------------------------------------------------------------------------------------------------------------ |
| `get_llm(model)` | Returns a LangChain chat model instance for deepseek-chat, deepseek-reasoner, claude-haiku, or claude-sonnet |

### src/tools/marketing_db.py — Marketing data

| Function                                                                   | Description                                                                 |
| -------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `get_all_strategies(status)`                                               | Returns all marketing strategies, optionally filtered by status             |
| `get_strategy_by_id(strategy_id)`                                          | Returns a single strategy by id                                             |
| `get_latest_digest()`                                                      | Returns the most recent weekly digest                                       |
| `get_digest_archive(limit)`                                                | Returns the N most recent digests, newest first                             |
| `get_digest_by_id(digest_id)`                                              | Returns a single digest by id                                               |
| `save_digest(week_date, content)`                                          | Inserts or replaces the digest for a given Monday date                      |
| `save_research_finding(run_date, topic, summary, source_url, strategy_id)` | Inserts a research finding                                                  |
| `get_recent_research(days, strategy_slug)`                                 | Returns findings from the last N days, optionally by strategy               |
| `update_strategy_reviewed(strategy_id)`                                    | Sets last_reviewed_at = now() for a strategy                                |
| `get_pipeline_stats()`                                                     | Returns contact counts by status, overdue follow-ups, and pending approvals |

### src/tools/memory.py — Open Brain

| Function                               | Description                                            |
| -------------------------------------- | ------------------------------------------------------ |
| `capture_thought(content, project)`    | Writes an observation to Open Brain MCP                |
| `search_artcrm_thoughts(query, limit)` | Semantic search over artcrm-tagged Open Brain thoughts |

### src/tools/search.py — Search APIs

| Function                                   | Description                                                       |
| ------------------------------------------ | ----------------------------------------------------------------- |
| `geo_search(query, city, country)`         | OpenStreetMap Overpass venue search, returns list of results      |
| `google_maps_search(query, city, country)` | Google Places API venue search with pagination (up to 60 results) |
| `fetch_page(url, max_chars)`               | Fetches a web page and returns plain text with HTML stripped      |
| `web_search(query, max_results)`           | Brave Search API, returns list of title/url/snippet dicts         |

### src/marketing/research_agent.py

| Function   | Description                                                                |
| ---------- | -------------------------------------------------------------------------- |
| `run(llm)` | Runs general + targeted Brave search streams, returns total findings saved |

### src/marketing/strategy_agent.py

| Function   | Description                                                                                    |
| ---------- | ---------------------------------------------------------------------------------------------- |
| `run(llm)` | Generates weekly markdown digest from strategy docs, pipeline stats, and research; saves to DB |

### src/supervisor/run\_\*.py — CLI runners

| File / Function                | Description                                                               |
| ------------------------------ | ------------------------------------------------------------------------- |
| `run_research.main()`          | Runs research agent for a city + level with level validation              |
| `run_enrichment.main()`        | Runs enrichment agent to fill missing website/email, globally or by city  |
| `run_scout.main()`             | Runs scout agent to score and promote candidates                          |
| `run_outreach.main()`          | Runs outreach agent to draft cold emails, globally or by city             |
| `run_followup.main()`          | Runs followup agent for inbox classification and overdue follow-ups       |
| `run_requeue_unsent.main()`    | Enriches approved_unsent contacts and requeues drafts if email found      |
| `run_outreach_analysis.main()` | Analyzes warm/cold outcomes and writes learnings to Open Brain            |
| `run_email_audit.main()`       | Audits Sent folder against DB, optionally auto-fixes contact status       |
| `run_blocked_report.main()`    | Reports contacts blocked from outreach and why                            |
| `run_interview.main()`         | Interactive post-visit debrief — logs venue impressions and contact notes |

### src/supervisor/graph.py

| Function                          | Description                                                                   |
| --------------------------------- | ----------------------------------------------------------------------------- |
| `create_supervisor(checkpointer)` | Builds the LangGraph supervisor orchestrating all pipeline agents in sequence |

### src/mcp/server.py — MCP tools exposed to Claude Code

| Tool                                              | Description                                            |
| ------------------------------------------------- | ------------------------------------------------------ |
| `pipeline_status()`                               | Contact counts by status + pending approvals           |
| `contacts_list(status, limit)`                    | Lists contacts with optional status filter             |
| `approval_list()`                                 | All pending email drafts awaiting human approval       |
| `approval_approve(item_id, note)`                 | Approves and sends a queued draft                      |
| `approval_reject(item_id, note)`                  | Rejects draft and marks contact as dropped             |
| `approval_hold(item_id, note)`                    | Puts draft on hold, updates contact to on_hold         |
| `agent_runs(limit)`                               | Recent agent run history with timing and status        |
| `manual_drop(contact_id, reason)`                 | Manually drops a contact                               |
| `manual_promote(contact_id, note)`                | Manually promotes a contact to cold, bypassing scout   |
| `set_city_notes(city, notes, character, country)` | Updates market character and notes for a city          |
| `research_status(country, region)`                | Readable report of cities scanned and at which levels  |
| `run_research(city, level, country)`              | Triggers a background research scan                    |
| `trigger_run()`                                   | Kicks off a full supervisor pipeline run in background |
| `marketing_digest_latest()`                       | Most recent weekly marketing digest as markdown        |
| `marketing_strategy_list()`                       | All marketing strategies with status and priority      |
| `marketing_action_items()`                        | Open action items across all active strategy docs      |
| `marketing_research_recent(days, strategy_slug)`  | Recent research findings, optionally by strategy       |

### src/api/routers/ — Web UI endpoints

| Route / Function                                | Description                                |
| ----------------------------------------------- | ------------------------------------------ |
| `approval.approval_list()`                      | Pending + on-hold draft cards              |
| `approval.approve(item_id, note)`               | Approve and send a draft                   |
| `approval.reject(item_id, note)`                | Reject draft, mark contact dropped         |
| `approval.hold(item_id, note)`                  | Put draft on hold                          |
| `approval.delete_draft(item_id)`                | Delete draft from queue                    |
| `approval.dropped_list()`                       | List of rejected/dropped drafts            |
| `approval.edit_and_approve(item_id, ...)`       | Edit then approve in one action            |
| `contacts.contact_list(...)`                    | Paginated, filterable contact list         |
| `contacts.contact_detail(contact_id)`           | Full contact page with interaction history |
| `contacts.contact_edit(contact_id, ...)`        | Save edited contact fields                 |
| `contacts.delete_contact(contact_id)`           | Delete a contact                           |
| `contacts.contact_brief(contact_id)`            | Brief card with last 5 interactions        |
| `contacts.unflag_contact(contact_id)`           | Clear flagged status                       |
| `contacts.contact_print(...)`                   | Printable view matching current filters    |
| `marketing.marketing_page()`                    | Main marketing dashboard                   |
| `marketing.strategy_editor(strategy_id)`        | Strategy document editor                   |
| `marketing.strategy_save(strategy_id, content)` | Save strategy doc content                  |
| `marketing.marketing_digest(digest_id)`         | Archived digest view                       |
| `marketing.observations_list(topic)`            | Open Brain thoughts partial                |
| `marketing.add_observation(content)`            | Capture thought to Open Brain              |
| `research.research_page()`                      | City scan status across all levels         |
| `inbox.inbox_list(classification, days)`        | Processed inbox messages with filters      |
| `activity.activity_feed()`                      | Agent run history and queue stats          |
| `people.people_list(q)`                         | List of individual people contacts         |
| `drafts.drafts_list()`                          | Held drafts grouped by city                |
| `drafts.approve(item_id, note)`                 | Approve a held draft                       |
| `drafts.reject(item_id, note)`                  | Reject a held draft                        |

---

_Generated 2026-04-22_
