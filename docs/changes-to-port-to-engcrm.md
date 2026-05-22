# Changes to Port to engcrm

Summary of all code and architecture changes made to artcrm-supervisor that should be replicated in the engcrm project.

---

## 1. `ignored_chains` table

**What:** A database table of business names that should never be saved as contacts — mass-market chains, franchises, etc.

**Migration to create:**

```sql
CREATE TABLE IF NOT EXISTS ignored_chains (
    id         SERIAL PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    reason     TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Grant access to the app user:

```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON ignored_chains TO <app_db_user>;
GRANT USAGE, SELECT ON SEQUENCE ignored_chains_id_seq TO <app_db_user>;
```

---

## 2. Chain filtering in `save_contact` (`src/tools/db.py`)

**What:** Before saving any contact, check if the name matches a known ignored chain. If it does, skip silently and return 0.

**Add these three helpers before `save_contact`:**

```python
import difflib

def _load_ignored_chains(cur) -> list[str]:
    cur.execute("SELECT name FROM ignored_chains")
    return [r["name"] for r in cur.fetchall()]


def _normalize_for_chain_match(name: str) -> str:
    import re
    return re.sub(r"[\s\-_/&'\".,;:!?]+", " ", name.lower()).strip()


def _is_ignored_chain(name: str, chains: list[str], threshold: float = 0.90) -> bool:
    n = _normalize_for_chain_match(name)
    for chain in chains:
        c = _normalize_for_chain_match(chain)
        if n == c or n.startswith(c + " "):
            return True
        sm = difflib.SequenceMatcher(None, n, c)
        if sm.quick_ratio() >= threshold and sm.ratio() >= threshold:
            return True
    return False
```

**Add at the top of `save_contact`, before the duplicate check:**

```python
chains = _load_ignored_chains(cur)
if _is_ignored_chain(name, chains):
    logger.info("save_contact: ignored chain skipped — %s / %s", name, city)
    return 0
```

**Also add a public getter function** (used by the research agent):

```python
def get_ignored_chains() -> list[str]:
    """Return all chain names from the ignored_chains table."""
    with db() as conn:
        cur = conn.cursor()
        return _load_ignored_chains(cur)
```

Export it from `src/tools/__init__.py`.

---

## 3. Email deduplication in `save_contact`

**What:** Use email as a primary dedup key. If an active contact already has the same email, skip saving the new candidate instead of creating a duplicate.

**Add this block in `save_contact`, after the chain check and before the name+city duplicate check:**

```python
if email:
    cur.execute(
        "SELECT id FROM contacts WHERE lower(email) = lower(%s) AND deleted_at IS NULL",
        (email,),
    )
    existing = cur.fetchone()
    if existing:
        logger.info("save_contact: email duplicate skipped — %s (%s)", name, email)
        return existing["id"]
```

**Why:** Email is a more reliable dedup key than name+city. Two entries with the same email are always the same business. This prevents duplicates even when the agent finds the same contact from a different search query or city variation.

---

## 4. Research agent: chain filtering before save

**What:** Load the ignored chains list once at the start of each research run and filter extracted contacts before calling `save_contact`. Avoids unnecessary DB round-trips.

**In `artcrm_research_agent/protocols.py`, add:**

```python
class ChainsFetcher(Protocol):
    """Return the list of ignored chain names from the database."""
    def __call__(self) -> list[str]: ...
```

**In `artcrm_research_agent/graph.py`, add these helpers (with the other module-level functions):**

```python
def _normalize_chain(name: str) -> str:
    return re.sub(r"[\s\-_/&'\".,;:!?]+", " ", name.lower()).strip()


def _is_ignored_chain(name: str, chains: list[str], threshold: float = 0.90) -> bool:
    import difflib
    n = _normalize_chain(name)
    for chain in chains:
        c = _normalize_chain(chain)
        if n == c or n.startswith(c + " "):
            return True
        sm = difflib.SequenceMatcher(None, n, c)
        if sm.quick_ratio() >= threshold and sm.ratio() >= threshold:
            return True
    return False
```

**Add `fetch_chains` parameter to `_ResearchAgent.__init__` and `create_research_agent`:**

```python
fetch_chains: ChainsFetcher | None = None,
```

**In `invoke`, load chains once after `start_run`:**

```python
ignored_chains = self._fetch_chains() if self._fetch_chains else []
```

**After the LLM extracts contacts, filter before saving:**

```python
if ignored_chains:
    before = len(contacts)
    contacts = [c for c in contacts if not _is_ignored_chain(c.get("name", ""), ignored_chains)]
    skipped = before - len(contacts)
    if skipped:
        logger.info("research: skipped %d ignored chain(s) in %s", skipped, city)
```

**In `src/supervisor/run_research.py`, pass `get_ignored_chains` when creating the agent:**

```python
from src.tools import get_ignored_chains
...
agent = create_research_agent(
    ...
    fetch_chains=get_ignored_chains,
)
```

---

## 5. Research agent: fetch email from website at save time

**What:** After the LLM extracts contacts, for every contact that has a website but no email, fetch that page and extract the email with a regex. This means contacts are saved with an email from the start, making enrichment unnecessary for most cases.

**Add this method to `_ResearchAgent` (before `_save_contacts`):**

```python
def _fetch_missing_emails(self, contacts: list[dict], city: str) -> list[dict]:
    import re
    email_re = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
    noise_domains = {
        "example.com", "sentry.io", "wixpress.com", "squarespace.com",
        "wordpress.com", "shopify.com", "amazonaws.com", "googletagmanager.com",
    }
    found = 0
    for contact in contacts:
        if contact.get("email") or not contact.get("website"):
            continue
        try:
            text = self._fetch_page(contact["website"])
            if not text:
                continue
            for match in email_re.finditer(text):
                email = match.group(0).lower()
                domain = email.split("@")[1]
                if domain not in noise_domains:
                    contact["email"] = email
                    found += 1
                    logger.info("research: email found for %s — %s", contact.get("name", ""), email)
                    break
        except Exception:
            pass
    if found:
        logger.info("research: fetched emails for %d contact(s) in %s", found, city)
    return contacts
```

**Call it in `invoke` after chain filtering and before `_save_contacts`:**

```python
contacts = self._fetch_missing_emails(contacts, city)
```

---

## 6. Remove enrichment from the automatic supervisor pipeline

**What:** The enrichment agent no longer runs automatically. Since research now fetches emails at discovery time, enrichment is only needed manually (e.g. to backfill old contacts). Keep `run_enrichment.py` intact for manual use.

**In `src/supervisor/graph.py`:**

- Remove `from artcrm_enrichment_agent import create_enrichment_agent`
- Remove `get_contacts_needing_enrichment, update_contact_details` from tool imports
- Remove `enrichment_summary` from `SupervisorState`
- Remove `enrichment_agent` from `_build_agents()` and its return value
- Remove the `run_enrich` node function
- Remove `graph.add_node("run_enrich", run_enrich)`
- Change edge: `"run_research" → "run_enrich" → "run_scout"` becomes `"run_research" → "run_scout"`
- Remove enrichment line from `generate_report`
- Update the docstring to reflect the new pipeline order

**New pipeline order:**

```
research → scout → outreach → followup
```

---

## 7. Duplicate-finding script threshold

**File:** `scripts/find_duplicates.py`

Set `THRESHOLD = 0.85` (was 0.90). At 85% you catch real duplicates that differ only by punctuation, accents, or "e.V." suffixes, without generating too much noise. Below 85% produces too many false positives.

---

## Notes

- The enrichment agent (`run_enrichment.py`) still exists and works — run it manually when you want to backfill emails on older contacts or contacts where the website fetch failed during research.
- The `ignored_chains` table is the single source of truth for what to skip. Add new chains there via SQL `INSERT` and they are automatically picked up on the next research run — no code changes needed.
- The `_is_ignored_chain` function uses a prefix match so "Brand - CityName" patterns are caught by a "Brand" entry in the table.
