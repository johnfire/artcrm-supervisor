# ArtCRM Agents — How They Work

This document explains all five agents in the artcrm system, how they interact, and how the whole thing relates to `theo-hits-the-road`.

---

## The foundation: theo-hits-the-road

`theo-hits-the-road` is the original CRM. It owns the database schema — specifically the `contacts`, `interactions`, and `shows` tables — and provides a CLI and MCP server for managing them by hand. It is never modified by the agent system and always works as a standalone fallback.

`artcrm-supervisor` adds four new tables to the same PostgreSQL database (`agent_runs`, `consent_log`, `approval_queue`, `inbox_messages`) and then automates the top of the contact funnel: finding leads, qualifying them, and initiating outreach. The two systems share data but do not depend on each other's code.

---

## The five agents

### 1. Supervisor (artcrm-supervisor)

**What it is:** The orchestrator. Not really an "agent" itself — it's a LangGraph `StateGraph` that runs the four worker agents in sequence on a schedule.

**Run order:**

```
research → scout → outreach → followup
```

**How it works:**

- Starts a run record in `agent_runs`
- Calls each worker agent in order, passing the active `Mission` and concrete tool implementations
- Each worker gets injected tools (DB functions, email, search) — the agents themselves have no direct imports from this repo
- Collects a summary from each worker and writes a final report to `agent_runs`
- Uses PostgreSQL as a LangGraph checkpointer: if a run crashes mid-way, it resumes from the last checkpoint when restarted within the same hour

**The human checkpoint** is the approval queue. The supervisor never sends a first-contact email on its own — it stops at drafting and waits for you to approve at `/approvals/`.

**Configuration knobs:**

- `ACTIVE_MISSION` in `src/config.py` — what the agents are working toward
- `RESEARCH_TARGETS` in `src/supervisor/targets.py` — which cities/industries to research
- `SCOUT_THRESHOLD` in `.env` — minimum fit score (0–100) to promote a contact

---

### 2. Research Agent (artcrm-research-agent)

**What it does:** Finds new potential contacts for a given city + industry and saves them to the database as `status=candidate`.

**Inputs:** `city`, `industry`, `country`

**Steps inside the agent:**

1. **plan_queries** — asks the LLM to generate a list of search queries based on the mission and target
2. **run_searches** — executes each query against Overpass (geo/OSM) and DuckDuckGo (web)
3. **extract_contacts** — asks the LLM to parse the raw search results into structured contact records
4. **save_contacts** — writes each contact to the `contacts` table with `status=candidate`; deduplication key is `(name, city)` so re-runs are safe

**LLM:** deepseek-chat (fast, cheap — this is volume work)

**Output:** contacts in the database with `status=candidate`

---

### 3. Scout Agent (artcrm-scout-agent)

**What it does:** Evaluates every `candidate` contact against the mission and decides whether to pursue them.

**Inputs:** `limit` (how many candidates to process per run)

**Steps inside the agent:**

1. **fetch** — pulls all contacts where `status=candidate`
2. **score_all** — for each contact, asks the LLM: "How well does this venue fit our mission? Score 0–100 and explain." Records the score and reasoning.
3. **apply_scores** — promotes contacts above `SCOUT_THRESHOLD` to `status=cold`, drops the rest to `status=dropped`. Writes the score and LLM reasoning into the contact's notes.

**LLM:** deepseek-chat

**Key behavior:** `dropped` contacts stay in the database. If you lower the threshold later and re-import candidates, the scout can re-evaluate them.

**Output:** contacts moved to either `status=cold` (ready for outreach) or `status=dropped`

---

### 4. Outreach Agent (artcrm-outreach-agent)

**What it does:** Drafts a personalized first-contact email for each `cold` contact and puts it in the approval queue. Does not send anything.

**Inputs:** `limit` (how many cold contacts to draft for per run — default is 1 for controlled rollout)

**Steps inside the agent:**

1. **fetch** — pulls contacts where `status=cold`
2. **draft_all** — for each contact:
   - Checks GDPR compliance first (hard block if `opt_out` or `erasure_requested` is set in `consent_log`)
   - Asks the LLM to write a first-contact email in the contact's preferred language, tailored to the mission and venue
3. **queue_drafts** — inserts approved drafts into `approval_queue` with `status=pending`

**LLM:** deepseek-reasoner (slower, higher quality — email quality matters here)

**Output:** rows in `approval_queue` waiting for human review at `/approvals/`

**What happens after you approve:**

- Email is sent via Proton Bridge SMTP
- An interaction is logged in `interactions`
- Contact moves to `status=contacted`

---

### 5. Follow-up Agent (artcrm-followup-agent)

**What it does:** Handles everything that happens after the first email has been sent. Two work streams per run.

**Work stream 1 — Inbox replies:**

1. **fetch_inbox_messages** — reads unprocessed messages from Proton Bridge IMAP
2. **classify_replies** — for each message, finds the matching contact by email address, then asks the LLM to classify the reply as one of: `interested`, `rejected`, `opt_out`, `other`
   - `opt_out`: immediately sets the flag in `consent_log` and moves contact to `status=dormant` — never contacted again
   - `interested`: drafts a reply and adds it to the send queue
   - `rejected` / `other`: logs the interaction, no further action
3. Marks each inbox message as processed

**Work stream 2 — Overdue contacts:**

1. **fetch_overdue_contacts** — finds contacts with `status=contacted` who haven't had an interaction in 90+ days
2. **draft_followup_emails** — drafts a brief follow-up for each, referencing the original outreach subject line

**send_all_emails** — sends everything in the queue (replies + follow-ups) directly via Proton Bridge SMTP, then logs each send as an interaction.

**LLM:** deepseek-reasoner (writing quality matters for both replies and follow-ups)

**Key difference from outreach:** the follow-up agent sends autonomously. There's no approval step. The activity feed at `/activity/` is the audit trail.

---

## Contact status flow

```
[research_agent]
      ↓
  candidate
      ↓
[scout_agent]
    ↙   ↘
  cold  dropped
    ↓
[outreach_agent → you approve]
      ↓
  contacted
      ↓
[followup_agent]
    ↙   ↘
  (stays   dormant  ← opt-out received
contacted)
```

---

## How the agents are wired together

The four worker agents are **tool-agnostic**. Each one defines its dependencies as Python Protocols (type-checked interfaces) and accepts them as constructor arguments. This means:

- The agents contain no database imports, no email imports, no config imports
- The supervisor injects concrete implementations at startup
- Tests inject fakes — no real DB, no real LLM, no real SMTP needed

The supervisor (`src/supervisor/graph.py`) is the only place that knows about the actual infrastructure.

---

## At a glance

| Agent      | Reads from DB                            | Writes to DB                  | LLM               | Sends email        |
| ---------- | ---------------------------------------- | ----------------------------- | ----------------- | ------------------ |
| Supervisor | —                                        | `agent_runs`                  | —                 | —                  |
| Research   | —                                        | `contacts` (candidate)        | deepseek-chat     | —                  |
| Scout      | `contacts` (candidate)                   | `contacts` (cold/dropped)     | deepseek-chat     | —                  |
| Outreach   | `contacts` (cold)                        | `approval_queue`              | deepseek-reasoner | —                  |
| Follow-up  | `inbox_messages`, `contacts` (contacted) | `interactions`, `consent_log` | deepseek-reasoner | Yes (autonomously) |

---

## Running manually vs. on schedule

**Full pipeline run:**

```bash
uv run python -m src.supervisor.run
```

**Individual agent (for debugging):**
Each agent package exposes a `create_*_agent()` factory. You can instantiate and invoke them directly — see the test files for examples.

**Scheduled:**

```cron
0 7 * * * cd ~/programming/artcrm-supervisor && uv run python -m src.supervisor.run >> ~/logs/supervisor.log 2>&1
```
