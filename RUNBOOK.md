# ArtCRM Agent System — Runbook

How to set up, run, and test the full system.

---

## Repos

| Repo | Purpose | Status |
|---|---|---|
| `theo-hits-the-road` | Original CRM, CLI, PostgreSQL schema | Untouched — always works |
| `artcrm-supervisor` | Orchestrator, FastAPI UI, tool implementations | Phase 0 done |
| `artcrm-research-agent` | Researches cities/industries for new contacts | Phase 1 done |
| `artcrm-scout-agent` | Scores candidates for mission fit | Phase 2 done |
| `artcrm-outreach-agent` | Drafts first-contact emails, queues for approval | Phase 3 done |
| `artcrm-followup-agent` | Monitors inbox, classifies replies, drafts follow-ups | Phase 4 — TODO |
| Supervisor wiring + PostgreSQL checkpointer | Phase 5 — TODO |
| UI polish | Phase 6 — TODO |

All repos live at `/home/christopher/programming/`.

---

## Prerequisites

- PostgreSQL running with the `artcrm` database (same one used by `theo-hits-the-road`)
- `uv` installed (`~/.local/bin/uv`)
- Proton Bridge running locally (for Phases 3+ when email is actually sent)
- DeepSeek and/or Anthropic API keys

---

## First-Time Setup

### 1. Set up artcrm-supervisor

```bash
cd ~/programming/artcrm-supervisor
cp .env.example .env
# Edit .env — fill in DATABASE_URL, API keys, Proton Bridge credentials
uv sync
uv run python scripts/migrate.py   # adds 4 new tables to the shared DB
```

### 2. Install agent packages for local development

The supervisor needs the agent packages installed. During development, install
them as editable local packages so changes to agent repos are reflected immediately:

```bash
cd ~/programming/artcrm-supervisor
uv add --editable ../artcrm-research-agent
uv add --editable ../artcrm-scout-agent
uv add --editable ../artcrm-outreach-agent
# Phase 4, when built:
# uv add --editable ../artcrm-followup-agent
```

When agents are published to GitHub, replace with:
```bash
uv add git+https://github.com/you/artcrm-research-agent
```

### 3. Start the UI

```bash
cd ~/programming/artcrm-supervisor
uv run python -m src.api.main
# Opens at http://127.0.0.1:8000
```

Two pages:
- `/approvals/` — email drafts waiting for your approval (approve / edit+approve / reject)
- `/activity/` — log of all agent runs with status and summary

---

## Running the Original CRM (theo-hits-the-road)

Nothing changes here. It still works independently:

```bash
cd ~/programming/theo-hits-the-road
source venv/bin/activate
python main.py          # interactive menu
scripts/crm --help      # CLI
pytest                  # run its own tests
```

The agent system shares the same PostgreSQL database. Both systems can run at the same time.

---

## Running Agents Manually (Phase 5 will automate this)

Until the supervisor is wired (Phase 5), agents can be invoked directly from Python.
This is also how you test end-to-end with real tools before the supervisor is ready.

Example — run the research agent against the real database:

```python
# from artcrm-supervisor directory
# uv run python -c "..."

from src.config import ACTIVE_MISSION
from src.tools.db import save_contact, start_run, finish_run   # (these will exist after Phase 5)
from src.tools.search import web_search, geo_search
from artcrm_research_agent import create_research_agent

agent = create_research_agent(
    llm=...,                    # your ChatOpenAI or ChatAnthropic instance
    web_search=web_search,
    geo_search=geo_search,
    save_contact=save_contact,
    start_run=start_run,
    finish_run=finish_run,
    mission=ACTIVE_MISSION,
)

result = agent.invoke({"city": "Augsburg", "industry": "gallery"})
print(result["summary"])
```

The concrete tool implementations (`src/tools/`) are built in Phase 5.

---

## Testing

### Philosophy

Each agent repo has its own test suite that runs with **zero external dependencies** —
no real LLM, no database, no network. Every test uses dummy implementations of the
Protocol interfaces. This means:

- Tests run in milliseconds
- Tests are deterministic (no flaky API calls)
- Every edge case is testable by controlling what the dummies return
- The real tool implementations are tested separately (integration tests, Phase 5)

### Running tests

Each agent repo is tested independently:

```bash
cd ~/programming/artcrm-research-agent && uv run pytest -v
cd ~/programming/artcrm-scout-agent    && uv run pytest -v
cd ~/programming/artcrm-outreach-agent && uv run pytest -v
# Phase 4:
# cd ~/programming/artcrm-followup-agent && uv run pytest -v
```

To run everything at once:

```bash
for repo in artcrm-research-agent artcrm-scout-agent artcrm-outreach-agent; do
    echo "=== $repo ==="
    cd ~/programming/$repo && uv run pytest -v
done
```

### What each test suite covers

**research agent** (4 tests):
- Saves contacts when search returns results
- Handles empty search results gracefully
- Handles LLM returning invalid JSON (records error, doesn't crash)
- Handles LLM wrapping JSON in markdown code fences

**scout agent** (4 tests):
- Promotes contacts with score >= 60
- Drops contacts with score < 60
- Handles empty candidate list
- Continues processing batch when one contact's scoring fails

**outreach agent** (4 tests):
- Queues email for approval when contact passes compliance check
- Blocks contact with opt-out flag (nothing queued, nothing sent)
- Handles LLM returning invalid JSON for email draft
- Handles empty contact list

### Writing new tests

The pattern for every test is the same:

```python
# 1. Create a DummyMission dataclass
# 2. Create a FakeLLM that returns controlled responses
# 3. Create dummy tool functions (closures that record what was called)
# 4. Build the agent with create_X_agent(llm=fake, tools=dummies, mission=dummy)
# 5. Call agent.invoke({...}) and assert on the result

def test_something():
    queued = []

    def queue_for_approval(contact_id, run_id, subject, body):
        queued.append(subject)
        return 1

    agent = create_outreach_agent(
        llm=FakeLLM(['{"subject": "Hi", "body": "Hello"}']),
        fetch_ready_contacts=lambda limit: [{"id": 1, "name": "Gallery X", ...}],
        check_compliance=lambda contact_id: True,
        queue_for_approval=queue_for_approval,
        start_run=lambda name, data: 1,
        finish_run=lambda *a: None,
        mission=DummyMission(),
    )

    result = agent.invoke({"limit": 1})
    assert result["queued_count"] == 1
    assert queued[0] == "Hi"
```

### Integration tests (Phase 5)

Once the supervisor's concrete tool implementations exist (`src/tools/`), we add
integration tests that run against a real test database. These are kept separate
from the unit tests and require `TEST_DATABASE_URL` in `.env`:

```bash
cd ~/programming/artcrm-supervisor
uv run pytest tests/integration/ -v
```

Integration tests will cover:
- `save_contact()` correctly writes to PostgreSQL
- `check_compliance()` correctly reads consent_log
- `queue_for_approval()` inserts into approval_queue
- Full agent run against test DB (research → scout → outreach pipeline)

---

## Changing the Mission

To repurpose the entire agent system for a different domain, edit one file:

```python
# artcrm-supervisor/src/config.py

SOFTWARE_MISSION = Mission(
    goal="Find SMEs in Germany that need web development or internal tooling",
    identity="Acme Web Dev, full-stack agency based in Munich",
    targets="retail businesses, clinics, tradespeople, SMEs with outdated web presence",
    fit_criteria="10-100 employees, no recent digital investment, growing sector",
    outreach_style="professional, ROI-focused, concrete value proposition",
    language_default="de",
)

ACTIVE_MISSION: Mission = SOFTWARE_MISSION  # <- change this line
```

The four agent repos are untouched. All prompts, all logic, all graph structure
stays the same. Only the context injected into the LLM changes.

---

## Contact Flow (end to end)

```
research_agent runs
  → new contacts written to DB with status=candidate

scout_agent runs
  → candidates scored, promoted to status=cold or dropped

outreach_agent runs
  → cold contacts drafted, inserted into approval_queue
  → UI shows drafts at /approvals/

You review in browser
  → approve / edit+approve / reject

[Phase 5] Supervisor picks up approved items
  → sends via Proton Bridge SMTP
  → logs interaction in DB
  → updates contact status to status=contacted

[Phase 4] followup_agent runs
  → reads IMAP inbox via Proton Bridge
  → classifies replies (interested / rejected / opt-out)
  → drafts follow-ups for non-replies
  → auto-logs interactions
  → daily report visible at /activity/
```
