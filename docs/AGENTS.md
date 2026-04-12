# ArtCRM Agents — How They Work

This document explains all agents in the artcrm system, how they interact, and how you can operate them manually — including directly via Claude Code.

---

## The foundation: theo-hits-the-road

`theo-hits-the-road` is the original CRM. It owns the database schema — specifically the `contacts`, `interactions`, and `shows` tables — and provides a CLI and MCP server for managing them by hand. It is never modified by the agent system and always works as a standalone fallback.

`artcrm-supervisor` adds four new tables to the same PostgreSQL database (`agent_runs`, `consent_log`, `approval_queue`, `inbox_messages`) and then automates the top of the contact funnel: finding leads, qualifying them, and initiating outreach. The two systems share data but do not depend on each other's code.

---

## Pipeline agents

### 1. Supervisor (artcrm-supervisor)

**What it is:** The orchestrator. Not really an "agent" itself — it's a LangGraph `StateGraph` that runs the five worker agents in sequence.

**Run order:**

```
research → enrich → scout → outreach → followup
```

**How it works:**

- Starts a run record in `agent_runs`
- Calls each worker agent in order, passing the active `Mission` and concrete tool implementations
- Each worker gets injected tools (DB functions, email, search) — the agents themselves have no direct imports from this repo
- Collects a summary from each worker and writes a final report to `agent_runs`
- Uses PostgreSQL as a LangGraph checkpointer: if a run crashes mid-way, it resumes from the last checkpoint when restarted within the same hour

**The human checkpoint** is the approval queue. The supervisor never sends a first-contact email on its own — it stops at drafting and waits for you to approve at `/approvals/`.

**Configuration knobs:**

- `ACTIVE_MISSION` in `src/config.py` — what the agents are working toward, including `website` for email sign-offs
- `SCAN_LEVELS` in `src/supervisor/targets.py` — Google Maps search terms per scan level
- `EMAIL_ENABLED` in `.env` — set to `false` to disable all outgoing email globally
- `PROTON_FROM_EMAIL` in `.env` — the From address on outgoing emails (can differ from the SMTP login address, e.g. an alias)

---

### 2. Research Agent (artcrm-research-agent)

**What it does:** Finds new potential contacts for a given city + level combination and saves them to the database as `status=candidate`.

**Inputs:** `city`, `country`, `level` (1–5)

**Scan levels:**

| Level | What it finds                                          |
| ----- | ------------------------------------------------------ |
| 1     | Galleries, cafes, interior designers, coworking spaces |
| 2     | Gift shops, esoteric/wellness shops, concept stores    |
| 3     | Independent restaurants                                |
| 4     | Corporate offices and headquarters                     |
| 5     | Hotels                                                 |

Level 1 must be run before any other level. Subsequent levels can be run in any order.

**Steps inside the agent:**

1. **run_maps_search** — runs fixed German-language search terms for the level against the Google Maps Places API. Returns name, address, website, phone directly from Maps data. Deduplicates by name.
2. **run_web_search** — targeted Brave Search queries per level to supplement Maps data and catch venues Maps might miss.
3. **fetch_pages** — visits the top 3 URLs found, strips HTML to plain text, feeds the content to the extraction LLM. This is how emails, contact names, and gallery style signals get extracted from actual venue websites.
4. **extract_contacts** — LLM parses all raw results into structured contact records. Writes 2–3 sentence notes per venue including fit signals. Includes ALL venues found — no filtering at this stage.
5. **save_contacts** — writes each contact to `contacts` with `status=candidate`. Deduplication key is `(name, city)` so re-runs are safe.

**LLM:** `CHEAP_LLM` env var (currently `claude-haiku`; default fallback `deepseek-chat`) — this is volume work.

**Output:** contacts in the database with `status=candidate`

**City registry:** Every city scanned is tracked in the `cities` and `city_scans` tables — what level was run, when, and how many contacts were found. Visible at `/research/`.

---

### 3. Enrichment Agent (artcrm-enrichment-agent)

**What it does:** Fills in missing contact details — website, email, phone — for contacts that came back from research without them. Runs automatically between research and scout on every pipeline invocation.

**Inputs:** `limit` (how many contacts to process per run, default 50)

**Why it exists:** The Google Maps Places API returns venue names, addresses, and often a website and phone number — but email addresses are rarely in Maps data. The enrichment agent searches the web for each contact and extracts whatever it finds from search snippets.

**Steps inside the agent:**

1. **fetch** — pulls contacts where `website` is missing OR `email` is missing, ordered by `created_at`. Skips contacts that already have both.
2. **enrich_all** — for each contact:
   - Builds a search query: `"{name} {city} website email contact"`
   - Runs it through Brave Search
   - Asks the LLM to extract website URL, email address, and phone number from the search snippets
3. **apply_results** — writes whatever was found back to the contact record. Partial updates are fine — if only an email was found, only the email gets written.

**LLM:** `deepseek-chat` (hardcoded — bypasses `CHEAP_LLM`)

**Output:** contacts updated with website/email/phone where found. No status change — enrichment doesn't promote or drop anyone.

**Note:** Enrichment doesn't fetch pages — it only reads search snippets. The research agent already fetched pages during discovery. The scout agent fetches gallery pages again during evaluation (for a fuller read).

---

### 4. Scout Agent (artcrm-scout-agent)

**What it does:** Evaluates every `candidate` contact and decides whether to pursue them.

**Inputs:** `limit` (how many candidates to process per run)

**The key insight:** Most venue types — cafes, hotels, restaurants, coworking spaces, corporate offices — are worth contacting regardless. The only venue that needs real evaluation is galleries, because a gallery that only shows Gerhard Richter is a completely different thing from one that shows emerging regional artists.

**Steps inside the agent:**

1. **fetch** — pulls all contacts where `status=candidate`
2. **split_and_promote** — separates candidates by type:
   - **Non-galleries** (cafes, hotels, restaurants, coworking, interior designers, etc.) → promoted directly to `status=cold` with no LLM call. No evaluation needed.
   - **Galleries** → sent to the research pipeline below.
3. **fetch_gallery_websites** — for each gallery, fetches the gallery website and reads up to 4000 characters of content. Galleries with no website still proceed — the LLM falls back to research notes.
4. **score_galleries** — for each gallery, the LLM reads the website content and notes and asks: does this gallery show emerging, regional, or mid-career artists? Or only blue-chip / internationally established names?
5. **apply_scores** — writes the outcome to each gallery contact:
   - `cold` — shows emerging/regional/mid-career artists, worth contacting
   - `maybe` — website unclear, too thin, or mixed signals — flagged for manual review
   - `dropped` — exclusively blue-chip or no fit

**LLM:** `deepseek-chat` (hardcoded — bypasses `CHEAP_LLM`)

**What the LLM looks for:**

- Artist names mentioned on the website (regional unknowns vs. internationally famous)
- Language like _zeitgenössisch_, _Nachwuchs_, _regional_, _auf Kommission_, _emerging_
- Exhibition history: rotating shows, open submissions, artist residencies
- Negative signals: exclusively famous artists, auction-house style, permanent collection only

**City market context:** The scout reads the city's `market_character` (tourist / mixed / upscale / unknown) from the `cities` table and passes it to the LLM. A gallery in a tourist town (Landsberg, Konstanz) gets more benefit of the doubt; galleries in upscale cities (Munich, Zurich) are held to a higher bar. Set city context with the `set_city_notes` MCP tool or via the migration seed data.

**Output:** contacts moved to `cold`, `maybe`, or `dropped`. The scout's reasoning is written into the contact's notes field.

---

### 5. Outreach Agent (artcrm-outreach-agent)

**What it does:** Researches each venue, drafts a personalized first-contact email, and puts it in the approval queue. Does not send anything.

**Inputs:** `limit` (how many cold contacts to draft for per run — default is 1 for controlled rollout)

**Steps inside the agent:**

1. **fetch** — pulls contacts where `status=cold`
2. **draft_all** — for each contact:
   - Checks GDPR compliance first (hard block if `opt_out` or `erasure_requested` is set in `consent_log`)
   - Fetches the venue's website and reads up to 3000 characters of content
   - Fetches the full interaction history for this contact
   - Asks the LLM to write a first-contact email using all of this: research notes, scout reasoning, website content, and past interactions
3. **queue_drafts** — inserts drafts into `approval_queue` with `status=pending`

**LLM:** `claude-sonnet-4-6` (hardcoded — quality matters here, this is the email a human reads)

**What the LLM is told to do:**

- Reference something specific about the venue from the notes or website — no generic openers
- Introduce Christopher briefly and naturally
- Express genuine interest in this specific space
- Propose one concrete next step (visit, call, or portfolio)
- Keep it short — 4 to 6 sentences

**Output:** rows in `approval_queue` waiting for human review at `/approvals/`

**What happens after you approve:**

- Email is sent via Proton Bridge SMTP (if `EMAIL_ENABLED=true`)
- An interaction is logged in `interactions`
- Contact moves to `status=contacted`

---

### 6. Follow-up Agent (artcrm-followup-agent)

> **Currently disabled.** The supervisor short-circuits this agent and returns immediately. All follow-up is handled manually while patterns are established.

**What it does (when enabled):** Handles everything that happens after the first email has been sent. Two work streams per run.

**Work stream 1 — Inbox replies:**

1. **fetch_inbox_messages** — reads unprocessed messages from Proton Bridge IMAP
2. **classify_replies** — for each message, finds the matching contact by email address
   - Messages with no matching contact are skipped and marked processed (no LLM call)
   - Classifies as: `interested`, `rejected`, `opt_out`, `other`
   - `opt_out`: immediately sets the flag in `consent_log` and moves contact to `status=dormant` — never contacted again
   - `interested`: drafts a warm reply and **sends it directly** (time-sensitive, bypasses approval queue)
   - `rejected` / `other`: logs the interaction, no further action
3. Marks each inbox message as processed

**Work stream 2 — Overdue contacts:**

1. **fetch_overdue_contacts** — finds contacts with `status=contacted` who haven't had an interaction in 90+ days
2. **draft_followup_emails** — drafts a brief follow-up for each, referencing the original outreach subject line
3. Puts drafts in the **approval queue** (not sent directly — human reviews first)

**LLM:** `claude-sonnet-4-6` (hardcoded)

---

## Marketing agents

These two agents run independently of the contact pipeline. They don't touch `contacts`, `approval_queue`, or email at all — they're about keeping the broader art marketing strategy current.

### 7. Marketing Research Agent

**What it does:** Runs web searches on art marketing topics and stores summarized findings in `marketing_research`. Two work streams per run.

**Work stream 1 — General scan:** Six fixed queries covering broad art marketing topics (Instagram for painters, selling at German markets, gallery open submissions, etc.). Runs every time regardless of active strategies.

**Work stream 2 — Targeted monitoring:** For each active strategy doc, asks the LLM to generate 2 search queries worth running this week — deadlines, events, specific sites to check. Runs the searches and stores findings tagged to the strategy.

**LLM:** `CHEAP_LLM` (currently `claude-haiku`) — for query generation and result summarization

**Output:** rows in `marketing_research` table, viewable via the `marketing_research_recent` MCP tool or at `/marketing/`.

**Run manually:**

```bash
uv run python -m src.marketing.run_research
```

---

### 8. Marketing Strategy Agent

**What it does:** Reads all active strategy docs, collects open action items and recent research findings, and generates a weekly markdown digest. The digest surfaces what needs attention this week.

**What it synthesizes:**

- Open `- [ ]` action items parsed directly from each strategy markdown file
- Strategies that haven't been reviewed in 3+ weeks (flagged as neglected)
- Pipeline stats: contacts by status, overdue follow-ups, pending approvals
- Research findings from the past 7 days

**Output:** a structured digest stored in `marketing_digests`, retrievable via the `marketing_digest_latest` MCP tool or at `/marketing/`.

**LLM:** `claude-sonnet-4-6` (hardcoded — this is the weekly summary you actually read)

**Run manually:**

```bash
uv run python -m src.marketing.run_strategy
```

---

## Contact status flow

```
[research_agent]
      ↓
  candidate
      ↓
[enrichment_agent]  ← fills in website/email/phone, no status change
      ↓
[scout_agent]
    ↙   ↓   ↘
  cold maybe dropped
    ↓
[outreach_agent → you approve]
      ↓
  contacted
      ↓
[followup_agent]
    ↙         ↘
(stays       dormant  ← opt-out received
contacted)
```

`maybe` contacts sit until you review them manually. Use `manual_promote` or `manual_drop` MCP tools, or review them at `/contacts/?status=maybe`.

---

## How the agents are wired together

The five pipeline worker agents are **tool-agnostic**. Each one defines its dependencies as Python Protocols (type-checked interfaces) and accepts them as constructor arguments. This means:

- The agents contain no database imports, no email imports, no config imports
- The supervisor injects concrete implementations at startup
- Tests inject fakes — no real DB, no real LLM, no real SMTP needed

The supervisor (`src/supervisor/graph.py`) is the only place that knows about the actual infrastructure.

---

## At a glance

| Agent              | Reads from DB                                            | Writes to DB                     | LLM               | Sends email             |
| ------------------ | -------------------------------------------------------- | -------------------------------- | ----------------- | ----------------------- |
| Supervisor         | —                                                        | `agent_runs`                     | —                 | —                       |
| Research           | —                                                        | `contacts` (candidate)           | CHEAP_LLM         | —                       |
| Enrichment         | `contacts` (missing website/email)                       | `contacts` (website/email/phone) | deepseek-chat     | —                       |
| Scout              | `contacts` (candidate)                                   | `contacts` (cold/maybe/dropped)  | deepseek-chat     | —                       |
| Outreach           | `contacts` (cold)                                        | `approval_queue`                 | claude-sonnet-4-6 | —                       |
| Follow-up          | `inbox_messages`, `contacts` (contacted)                 | `interactions`, `consent_log`    | claude-sonnet-4-6 | Replies only (disabled) |
| Marketing Research | `marketing_strategies`                                   | `marketing_research`             | CHEAP_LLM         | —                       |
| Marketing Strategy | `marketing_strategies`, `marketing_research`, `contacts` | `marketing_digests`              | claude-sonnet-4-6 | —                       |

**CHEAP_LLM** is currently `claude-haiku` (set in `.env`). Enrichment and Scout hardcode `deepseek-chat` directly and ignore this setting.

---

## Running manually vs. on schedule

**Full pipeline run:**

```bash
uv run python -m src.supervisor.run
```

**Research only (single city + level):**

```bash
uv run python -m src.supervisor.run_research --city Konstanz --level 1
uv run python -m src.supervisor.run_research --city Innsbruck --level 1 --country AT
```

**Individual agent (for debugging):**
Each agent package exposes a `create_*_agent()` factory. You can instantiate and invoke them directly — see the test files for examples.

**Scheduled:**

```cron
0 7 * * * cd ~/programming/artcrm-supervisor && uv run python -m src.supervisor.run >> ~/logs/supervisor.log 2>&1
```

---

## Running a single agent on request (via Claude Code)

When you ask Claude Code to run a specific agent — e.g. "run research for München level 1" — Claude runs it directly as a subprocess in the current terminal session using the same `uv run python -m src.supervisor.run_*` entry points above. One agent at a time, in the foreground, with output streamed back into the conversation.

This is different from the scheduled full pipeline run. Claude is not invoking the LangGraph supervisor — it's calling the individual agent's entry point directly. This means:

- No checkpoint recovery (short runs don't need it)
- No cross-agent dependencies — you can run enrichment on its own without running research first
- Output and errors are immediately visible in the conversation
- Claude can interpret the results, flag anomalies, and suggest next steps before you decide what to run next

Typical pattern in a session:

```
You:    run research for Regensburg level 1
Claude: [runs] uv run python -m src.supervisor.run_research --city Regensburg --level 1
        → 23 contacts saved as candidate
        → suggests running enrichment or scouting next
```

---

## Direct database access (via Claude Code)

Claude Code has a direct connection to the PostgreSQL database via `psql` and the project's `DATABASE_URL`. This is used for:

- **Inspection** — checking contact counts, pipeline status, what a specific record looks like
- **Manual corrections** — fixing a wrong status, updating a contact field that the UI doesn't expose, clearing a stuck approval
- **Bulk operations** — e.g. promoting all `maybe` contacts in a city to `cold`, resetting a bad batch
- **Debugging** — checking what an agent actually wrote, verifying that a run completed correctly

Claude does not run arbitrary destructive queries without telling you what it's about to do. For reads and targeted updates it proceeds directly. For bulk deletes or anything that touches many rows, it states the query and confirms before executing.

The DB is local PostgreSQL — there's no migration step or deployment involved. Changes take effect immediately.

**Quick access pattern Claude uses:**

```bash
psql $DATABASE_URL -c "SELECT id, name, city, status FROM contacts WHERE city='Regensburg' ORDER BY created_at DESC LIMIT 10;"
```

The `DATABASE_URL` is loaded from `.env` automatically by the project's config, and Claude reads it from there when constructing ad-hoc queries.

---

## MCP tools (manual operations from Claude Code)

The FastMCP server (`src/mcp/server.py`) exposes tools that Claude Code can call conversationally — no shell command needed.

**Contact management:**

| Tool                               | What it does                             |
| ---------------------------------- | ---------------------------------------- |
| `contacts_list`                    | List contacts, filter by status          |
| `manual_drop(contact_id, reason)`  | Set status=dropped and log the reason    |
| `manual_promote(contact_id, note)` | Set status=cold (move to outreach queue) |

**Approvals:**

| Tool                              | What it does                          |
| --------------------------------- | ------------------------------------- |
| `approval_list`                   | List pending approval queue items     |
| `approval_approve(item_id, note)` | Approve a draft — triggers email send |
| `approval_reject(item_id, note)`  | Reject a draft                        |

**Pipeline & runs:**

| Tool                        | What it does                          |
| --------------------------- | ------------------------------------- |
| `pipeline_status`           | Contact counts by status              |
| `agent_runs`                | Recent agent run history and outcomes |
| `research_status`           | Cities scanned and levels completed   |
| `run_research(city, level)` | Trigger a research run for a city     |
| `trigger_run`               | Trigger a full pipeline run           |

**City context:**

| Tool                                              | What it does                                                                        |
| ------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `set_city_notes(city, notes, character, country)` | Set market_character (tourist/mixed/upscale/unknown) and free-text notes for a city |

**Marketing:**

| Tool                                             | What it does                                              |
| ------------------------------------------------ | --------------------------------------------------------- |
| `marketing_digest_latest`                        | Retrieve the most recent weekly strategy digest           |
| `marketing_strategy_list`                        | List all active strategy docs and their review status     |
| `marketing_action_items`                         | All open `- [ ]` action items across strategy docs        |
| `marketing_research_recent(days, strategy_slug)` | Recent research findings, optionally filtered by strategy |

**City characters pre-seeded:** Landsberg, Konstanz, Friedrichshafen, Lindau, Garmisch-Partenkirchen, Rosenheim → `tourist`. Munich, Zurich, Basel → `upscale`. Augsburg, Heidelberg, Tübingen → `mixed`.
