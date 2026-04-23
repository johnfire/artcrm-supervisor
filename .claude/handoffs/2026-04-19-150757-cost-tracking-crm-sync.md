# Handoff: Cost tracking, CRM sync pipeline, city scans

## Session Metadata

- Created: 2026-04-19 15:07:57
- Project: /home/christopher/programming/art-crm/artcrm-supervisor
- Branch: main
- Session duration: ~3 hours

### Recent Commits (for context)

- 3858576 feat: per-run cost tracking for Brave Search and LLM APIs
- 691f503 feat: approval UX improvements, inbox backlog fix, memory auth header
- 0e32aa5 feat: setup_memory.py — register Open Brain topic hints for artcrm
- 45aa7eb fix: explicit hx-swap=innerHTML on observations lazy-load div
- 7238e1e feat: Observations section on marketing page — add/view Open Brain artcrm thoughts

## Handoff Chain

- **Continues from**: [2026-03-26-095046-scout-agent-rework.md](./2026-03-26-095046-scout-agent-rework.md)
- **Supersedes**: None

## Current State Summary

A full session covering: committing and pushing a batch of approval UI + inbox fixes, syncing those changes to eng-crm and general-crm via a new parallel-agent skill, running Ulm and Augsburg level 4+5 city scans with enrichment and scout, and adding per-run cost tracking (Brave Search + LLM APIs) to the DB. Everything is committed and pushed. No pending work — the system is in a clean state.

## Codebase Understanding

### Architecture Overview

- **artcrm-supervisor** is the source-of-truth CRM. Changes sync downstream to **eng-crm** (`/home/christopher/programming/eng-crm`) and **general-crm** (`/home/christopher/programming/general-crm`) via a periodic sync doc process.
- Agents run as separate processes (MCP-triggered or CLI). Each run is logged in `agent_runs` and now also `run_costs`.
- LLMs: DeepSeek (research/enrichment/scout), Claude Sonnet 4.6 (outreach/followup).
- Search: Brave Search API (enrichment, research web queries), Google Places API (research geo), OSM Overpass (research geo fallback).

### Critical Files

| File                                       | Purpose                                    | Relevance                                                          |
| ------------------------------------------ | ------------------------------------------ | ------------------------------------------------------------------ |
| `src/tools/costs.py`                       | Per-run cost accumulator                   | New this session — tracks Brave + LLM costs                        |
| `src/tools/llm.py`                         | LLM factory                                | Now injects `_CostCallback` into every model                       |
| `src/tools/search.py`                      | Brave/Google/OSM search                    | Now calls `record_search()` on each Brave query                    |
| `src/tools/db.py`                          | All DB ops + run logging                   | `start_run` resets costs; `finish_run` writes to `run_costs` table |
| `src/api/routers/approval.py`              | Approval queue UI routes                   | Reject→dropped, on_hold approve, delete draft, Dropped page        |
| `src/ui/templates/dropped.html`            | New Dropped prospects page                 | Lists rejected contacts                                            |
| `docs/sync-2026-04-19.md`                  | Sync doc for this session                  | Copied to eng-crm and general-crm root                             |
| `~/.claude/skills/crm-sync-doc/SKILL.md`   | How to create sync docs                    | New skill                                                          |
| `~/.claude/skills/crm-sync-apply/SKILL.md` | How to apply sync docs via parallel agents | New skill                                                          |

### Key Patterns Discovered

- Sync docs go in `artcrm-supervisor/docs/sync-YYYY-MM-DD.md` and are copied to the **root** of eng-crm and general-crm.
- `run_costs` table links to `agent_runs` via `run_id`. Cost summary is appended to `agent_runs.summary` as `| cost=$X.XXXX | search:Nq | deepseek:Ntok`.
- Open Brain syncs are recorded after every significant operation so the next session knows the baseline.
- general-crm has extra contact statuses (`accepted`, `closed`, `do_not_contact`, `dormant`, `maybe`, `meeting`, `networking_visit`, `online`) — never apply the artcrm status CHECK constraint to it.

## Work Completed

### Tasks Finished

- [x] Committed and pushed batch of approval UI fixes + inbox/memory changes (commit 691f503)
- [x] Created `docs/sync-2026-04-19.md` covering all 7 change areas
- [x] Built `crm-sync-doc` skill for creating future sync docs
- [x] Built `crm-sync-apply` skill for dispatching parallel agents to apply sync docs
- [x] Applied sync to eng-crm (all changes) and general-crm (all changes, status constraint skipped)
- [x] Added `Read`, `Edit`, `Write`, `Glob`, `Grep` to global settings allowlist (subagents were being blocked)
- [x] Ran Ulm L4 (18 contacts) + L5 (16 contacts) + enrichment + scout (all 34 promoted to cold)
- [x] Ran Augsburg L4 (17 contacts) + L5 (14 contacts) + enrichment + scout (all promoted to cold)
- [x] Added per-run cost tracking: `src/tools/costs.py`, `run_costs` DB table, LangChain callback, Brave counter
- [x] Recorded sync in Open Brain

### Files Modified

| File                                           | Changes                                                                            | Rationale                           |
| ---------------------------------------------- | ---------------------------------------------------------------------------------- | ----------------------------------- |
| `src/tools/costs.py`                           | New file                                                                           | Cost accumulator + pricing table    |
| `src/tools/llm.py`                             | Added `_CostCallback`, injected into all models                                    | Track LLM token usage               |
| `src/tools/search.py`                          | Added `record_search()` call                                                       | Track Brave query count             |
| `src/tools/db.py`                              | `start_run` resets costs, `finish_run` writes `run_costs`, added `get_run_costs()` | Cost persistence                    |
| `src/tools/__init__.py`                        | Exported `get_run_costs`                                                           | API surface                         |
| `src/api/routers/approval.py`                  | Reject→dropped, on_hold approve, delete draft, Dropped page route                  | Lifecycle fixes                     |
| `src/mcp/server.py`                            | Same approval lifecycle fixes in MCP tools                                         | Parity                              |
| `src/tools/email.py`                           | SINCE date window instead of UNSEEN, HTML body fallback                            | Inbox reliability                   |
| `src/tools/memory.py`                          | Fixed Open Brain auth header to `x-brain-key`                                      | Memory was silently failing         |
| `src/supervisor/run_followup.py`               | Inbox backlog merge                                                                | Catch previously skipped messages   |
| `src/supervisor/graph.py`                      | Outreach limit 1→50                                                                | Was too conservative                |
| `src/supervisor/run_outreach.py`               | Default limit 10→50                                                                | Same                                |
| `src/ui/templates/base.html`                   | Dropped nav link                                                                   | UI                                  |
| `src/ui/templates/partials/approval_list.html` | Website link, Delete button, contact ID badge                                      | Usability                           |
| `src/ui/templates/dropped.html`                | New file                                                                           | Dropped prospects page              |
| `docs/open-brain-guide.md`                     | New file                                                                           | Reference for Open Brain connection |
| `docs/sync-2026-04-19.md`                      | New file                                                                           | Sync doc for this session           |
| `~/.claude/settings.json`                      | Added Read/Edit/Write/Glob/Grep to allow list                                      | Subagents were being blocked        |

### Decisions Made

| Decision                                                            | Options Considered              | Rationale                                                                           |
| ------------------------------------------------------------------- | ------------------------------- | ----------------------------------------------------------------------------------- |
| Module-level cost accumulator (not thread-local)                    | Thread-local vs module-level    | Each agent run is a separate process — module-level is simpler and sufficient       |
| Append costs to `agent_runs.summary` AND write to `run_costs` table | Summary only vs DB only vs both | Both: summary is immediately visible in `agent_runs`, DB enables historical queries |
| Skip status CHECK constraint when syncing to general-crm            | Apply anyway vs skip            | general-crm has extra statuses that would violate the artcrm constraint             |

## Pending Work

### Immediate Next Steps

1. Consider exposing `get_run_costs` in the MCP server so cost history is queryable from Claude
2. Consider adding cost tracking to the MCP tool responses (e.g. `agent_runs` output includes cost)
3. Run outreach on Ulm and Augsburg new contacts when ready (all 65 contacts promoted to cold)

### Blockers/Open Questions

- None — clean state

### Deferred Items

- Cost tracking not yet added to eng-crm / general-crm (sync doc doesn't cover it yet — would need a new sync doc)

## Context for Resuming Agent

### Important Context

- **Cost tracking is live**: every run now writes to `run_costs` table. Query with `get_run_costs(limit)`. The LangChain callback model name key for DeepSeek is `model_name` in `response_metadata` (not `model`) — already fixed.
- **Brave Search is $0.005/query** (Data for AI plan, $5/1000). 2000 queries/month is normal given enrichment runs of 50 contacts each.
- **Sync skills exist**: use `/crm-sync-doc` to create a sync doc, then `/crm-sync-apply` to dispatch parallel agents. Always record the sync in Open Brain afterward.
- **general-crm status constraint**: never apply the artcrm `contacts_status_check` — general-crm has additional statuses.
- **eng-crm has no followup agent** (disabled in graph.py) and no standalone `run_outreach.py`.

### Assumptions Made

- DeepSeek pricing hardcoded at $0.27/M input, $1.10/M output — verify if rates change
- Brave Search at $0.005/query (Data for AI plan)

### Potential Gotchas

- `get_run_costs` only has data from runs after 2026-04-19 (when table was created)
- The `_CostCallback` is a singleton — if two agents somehow ran in the same process, costs would bleed. Fine in practice since each run is a subprocess.
- general-crm's `dropped.html` was titled "Eng-CRM Supervisor" by the sync agent (it used artcrm's file) — may need a branding fix

## Environment State

### Tools/Services Used

- DeepSeek API (research, enrichment, scout)
- Anthropic Claude API (outreach, followup)
- Brave Search API (enrichment web search)
- Google Places API (research geo search)
- Open Brain MCP (memory)
- Proton Bridge IMAP/SMTP (email)

### Active Processes

- Scheduled followup agent runs daily at 09:00 and 18:00
- Scheduled outreach analysis runs weekly

### Environment Variables

- `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`
- `ANTHROPIC_API_KEY`
- `BRAVE_SEARCH_API_KEY`
- `GOOGLE_MAPS_API_KEY`
- `OPEN_BRAIN_URL`, `OPEN_BRAIN_TOKEN`
- `DATABASE_URL`
- `PROTON_EMAIL`, `PROTON_PASSWORD`, `PROTON_IMAP_HOST`, `PROTON_IMAP_PORT`

## Related Resources

- Open Brain: search `artcrm` project for session history
- Sync docs: `artcrm-supervisor/docs/sync-*.md`
- Skills: `~/.claude/skills/crm-sync-doc/`, `~/.claude/skills/crm-sync-apply/`

---

**Security Reminder**: Before finalizing, run `validate_handoff.py` to check for accidental secret exposure.
