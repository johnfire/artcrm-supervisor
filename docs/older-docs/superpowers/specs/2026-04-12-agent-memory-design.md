# Agent Memory Design

**Date:** 2026-04-12  
**Status:** Approved

## Problem

The artcrm-supervisor agents run independently and forget everything between runs. The outreach agent drafts emails without knowing which styles have gotten warm replies. The research agent scans a city and discards its observations. There is no shared intelligence layer across the pipeline.

The goal is to give agents two types of memory:

1. **Outreach quality loop** — automatic learning from email outcomes, silently improving draft quality over time
2. **Marketing observations** — a shared city/venue intelligence layer, writable by both agents and the human

---

## Architecture

### Memory Store: Open Brain

All synthesized learnings and observations are stored in Open Brain with `project="artcrm"`. Open Brain handles embeddings and semantic search — no vector DB to manage. Four topic hints are registered at setup to guide classification:

| Hint              | Category | Covers                                                    |
| ----------------- | -------- | --------------------------------------------------------- |
| `artcrm-outreach` | projects | Email tone, length, subject lines, response rates         |
| `artcrm-city`     | projects | City-level notes, venue responsiveness, seasonal patterns |
| `artcrm-venue`    | projects | Venue type patterns (galleries, hotels, cafes, etc.)      |
| `artcrm-seasonal` | projects | Time-of-year observations, plein air season, events       |

### Raw Signal Store: DB

One new table tracks the structured outcome signal needed for analysis:

```sql
CREATE TABLE outreach_outcomes (
    id                   SERIAL PRIMARY KEY,
    contact_id           INTEGER NOT NULL REFERENCES contacts(id),
    sent_interaction_id  INTEGER NOT NULL REFERENCES interactions(id),
    reply_interaction_id INTEGER NOT NULL REFERENCES interactions(id),
    warm                 BOOLEAN NOT NULL,
    word_count           INTEGER,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

`warm=true` means the reply was classified as interested/positive by the followup agent. `word_count` is the word count of the sent email body.

---

## Agent Changes

### 1. Followup Agent (new write)

When the followup agent classifies an inbound reply as warm (`outcome IN ('interested', 'warm_reply')`), it:

1. Looks up the most recent outbound `interactions` row for that contact
2. Writes a row to `outreach_outcomes` linking the sent email to the warm reply
3. Includes `word_count` of the sent email body

This is the only change to the followup agent — one DB write after warm classification. Cold/neutral replies are not recorded (absence of a row = not warm).

### 2. Outreach Agent (new read)

Before drafting each email, the agent:

1. Calls `search_thoughts("outreach email tone {venue_type} {city}", project="artcrm")` — top 3 results
2. If results exist, injects them as a brief style note at the top of the system prompt:

```
Recent learnings from past outreach:
- [learning 1]
- [learning 2]
...
Draft the email with these patterns in mind.
```

If Open Brain returns nothing (early stage, no learnings yet), the prompt is unchanged. No structural change to the agent.

### 3. Research Agent (new write)

After completing a city scan, writes a brief observation to Open Brain:

```python
capture_thought(
    f"artcrm city scan: {city} level {level}. Found {n} venues. "
    f"Best lead types: {top_types}. Notes: {summary}",
    project="artcrm"
)
```

This is low-effort signal that accumulates passively. The research agent does not read from Open Brain.

### 4. New: Weekly Learnings Job (`run_outreach_analysis.py`)

Runs Monday at 7:30am (after marketing research at 6am and strategy digest at 7am). Outreach is run manually, so learnings will always be fresh when triggered.

Steps:

1. Reads `outreach_outcomes` for the last 90 days — both warm and cold rows
2. Fetches the full body of each linked sent email from `interactions`
3. Sends both sets to Claude Sonnet with a prompt: "What patterns distinguish emails that received warm replies from those that did not? Consider tone, length, subject line style, personalization, and opening. Be specific and concise."
4. Writes the synthesis to Open Brain: `capture_thought(synthesis, project="artcrm")`
5. Skips if fewer than 5 warm outcomes exist (not enough signal yet)

The job does not modify any existing agent or table — it only reads `outreach_outcomes` + `interactions` and writes to Open Brain.

---

## UI: Observations Section

The marketing page (`/marketing/`) gets a new "Observations" section below the digest.

**Display:** Shows the 20 most recent `artcrm` thoughts from Open Brain — a live feed of agent and human observations. Each card shows: content, author tag (agent name or "you"), date, auto-extracted topics as badges.

**Add form:**

```
[ What did you notice? _________________________ ] [Add]
```

Submitting calls `capture_thought(content, project="artcrm")` directly. No intermediate DB table — Open Brain is the store.

**Filtering:** A simple topic filter (city, venue, outreach, seasonal) using `search_thoughts` with a topic prefix.

The strategy agent's existing `generate_digest` call already has access to Open Brain via `search_thoughts` — observations flow into the weekly digest automatically without extra wiring.

---

## Setup Migration

A one-time setup script (`scripts/setup_memory.py`) handles:

1. `CREATE TABLE outreach_outcomes ...` (idempotent)
2. Register 4 topic hints in Open Brain via `add_topic_hint`

---

## What Does Not Change

- No changes to the scout agent — it already writes drop reasons to contact notes
- No changes to the enrichment agent — its output is structural (email/website), not observational
- No changes to the marketing research/strategy agents — they benefit from observations automatically via the digest
- The followup agent's classification logic is unchanged — only a write is added after warm detection

---

## Success Criteria

- After 4 weeks of use, `outreach_outcomes` has at least 10 warm rows
- The weekly analysis job produces at least one synthesized learning in Open Brain
- The outreach agent's prompt includes at least one injected learning on the next run
- Human observations added via the UI appear in the next weekly digest
- The marketing page Observations section shows a non-empty feed within one week of deployment

---

## Scope Explicitly Excluded

- No changes to email sending logic
- No A/B testing framework
- No automatic prompt rewriting — learnings are advisory, injected as style notes only
- No retrieval for scout, enrichment, or followup agents (Phase 1 scope)
