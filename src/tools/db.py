"""
All database operations used as injected tools in the agents.
Every function uses parameterised queries — no string interpolation on user data.
"""
import json
import logging
from datetime import date, datetime, timezone

from src.db.connection import db

logger = logging.getLogger(__name__)


def _serialize_row(row: dict) -> dict:
    """Convert datetime/date objects to ISO strings so rows are JSON-safe."""
    return {
        k: v.isoformat() if isinstance(v, (datetime, date)) else v
        for k, v in row.items()
    }


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

def save_contact(
    name: str,
    city: str,
    *,
    country: str = "DE",
    type: str = "",
    website: str = "",
    email: str = "",
    phone: str = "",
    notes: str = "",
) -> int:
    """
    Insert a new contact with status='candidate'.
    Deduplication key is (name, city) — returns existing contact's id if duplicate.
    Returns contact id, or 0 on error.
    """
    with db() as conn:
        cur = conn.cursor()
        # Check for duplicate
        cur.execute(
            "SELECT id FROM contacts WHERE lower(name) = lower(%s) AND lower(city) = lower(%s)",
            (name, city),
        )
        existing = cur.fetchone()
        if existing:
            logger.debug("save_contact: duplicate skipped — %s / %s", name, city)
            return existing["id"]

        cur.execute(
            """
            INSERT INTO contacts (name, city, country, type, website, email, phone, notes, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'candidate')
            RETURNING id
            """,
            (name, city, country, type or None, website or None, email or None, phone or None, notes or None),
        )
        contact_id = cur.fetchone()["id"]
        ensure_consent_log(contact_id, conn=conn)
        logger.info("save_contact: created id=%d  %s / %s", contact_id, name, city)
        return contact_id


def get_candidates(limit: int = 50) -> list[dict]:
    """Return contacts with status='candidate'."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM contacts WHERE status = 'candidate' ORDER BY created_at ASC LIMIT %s",
            (limit,),
        )
        return [_serialize_row(dict(r)) for r in cur.fetchall()]


def get_cold_contacts(limit: int = 20) -> list[dict]:
    """Return contacts with status='cold' ready for first outreach."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM contacts WHERE status = 'cold' ORDER BY created_at ASC LIMIT %s",
            (limit,),
        )
        return [_serialize_row(dict(r)) for r in cur.fetchall()]


def update_contact(contact_id: int, status: str, fit_score: int, notes: str = "") -> None:
    """Update a contact's status and fit_score. Appends notes if provided."""
    with db() as conn:
        cur = conn.cursor()
        if notes:
            cur.execute(
                """
                UPDATE contacts
                SET status = %s, fit_score = %s,
                    notes = CASE WHEN notes IS NULL THEN %s ELSE notes || E'\n' || %s END,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (status, fit_score, notes, notes, contact_id),
            )
        else:
            cur.execute(
                "UPDATE contacts SET status = %s, fit_score = %s, updated_at = NOW() WHERE id = %s",
                (status, fit_score, contact_id),
            )


def get_contacts_needing_enrichment(limit: int = 50) -> list[dict]:
    """Return contacts missing both website and email, any status."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT * FROM contacts
            WHERE (website IS NULL OR website = '')
              AND (email IS NULL OR email = '')
            ORDER BY created_at ASC
            LIMIT %s
            """,
            (limit,),
        )
        return [_serialize_row(dict(r)) for r in cur.fetchall()]


def update_contact_details(contact_id: int, **kwargs) -> None:
    """Update arbitrary contact fields (website, email, phone). Ignores unknown keys."""
    allowed = {"website", "email", "phone"}
    fields = {k: v for k, v in kwargs.items() if k in allowed and v}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [contact_id]
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE contacts SET {set_clause}, updated_at = NOW() WHERE id = %s",
            values,
        )


def match_contact_by_email(from_email: str) -> dict | None:
    """Find a contact by email address. Returns None if not found."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM contacts WHERE lower(email) = lower(%s) LIMIT 1",
            (from_email,),
        )
        row = cur.fetchone()
        return _serialize_row(dict(row)) if row else None


# ---------------------------------------------------------------------------
# GDPR / Compliance
# ---------------------------------------------------------------------------

def ensure_consent_log(contact_id: int, *, conn=None) -> None:
    """
    Create a consent_log entry for a contact if one doesn't exist.
    Can receive an existing connection (when called within save_contact's transaction).
    """
    def _insert(c):
        cur = c.cursor()
        cur.execute(
            "SELECT id FROM consent_log WHERE contact_id = %s LIMIT 1",
            (contact_id,),
        )
        if not cur.fetchone():
            cur.execute(
                """
                INSERT INTO consent_log (contact_id, legal_basis, first_contact_date)
                VALUES (%s, 'legitimate_interest', NOW())
                """,
                (contact_id,),
            )

    if conn:
        _insert(conn)
    else:
        with db() as c:
            _insert(c)


def check_compliance(contact_id: int) -> bool:
    """
    Returns True if outreach to this contact is permitted.
    Blocked if: opt_out is set, erasure_requested is set, or contact has been erased.
    """
    with db() as conn:
        cur = conn.cursor()
        # Check consent_log
        cur.execute(
            """
            SELECT opt_out, erasure_requested
            FROM consent_log WHERE contact_id = %s
            ORDER BY created_at DESC LIMIT 1
            """,
            (contact_id,),
        )
        row = cur.fetchone()
        if row and (row["opt_out"] or row["erasure_requested"]):
            return False
        # Check contact not erased
        cur.execute("SELECT name FROM contacts WHERE id = %s", (contact_id,))
        contact = cur.fetchone()
        if not contact or contact["name"] == "[removed]":
            return False
        return True


def set_opt_out(contact_id: int) -> None:
    """Record opt-out in consent_log and update contact status to 'dormant'."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO consent_log (contact_id, legal_basis, opt_out, opt_out_date)
            VALUES (%s, 'legitimate_interest', TRUE, NOW())
            """,
            (contact_id,),
        )
        cur.execute(
            "UPDATE contacts SET status = 'dormant', updated_at = NOW() WHERE id = %s",
            (contact_id,),
        )
        logger.info("set_opt_out: contact_id=%d opted out", contact_id)


# ---------------------------------------------------------------------------
# Approval queue
# ---------------------------------------------------------------------------

def queue_for_approval(contact_id: int, run_id: int, subject: str, body: str) -> int:
    """Insert an email draft into the approval queue. Returns queue item id."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO approval_queue (contact_id, agent_run_id, draft_subject, draft_body)
            VALUES (%s, %s, %s, %s) RETURNING id
            """,
            (contact_id, run_id or None, subject, body),
        )
        return cur.fetchone()["id"]


# ---------------------------------------------------------------------------
# Interactions
# ---------------------------------------------------------------------------

def log_interaction(
    contact_id: int,
    method: str,
    direction: str,
    summary: str,
    outcome: str,
) -> None:
    """Log a contact interaction and update the contact's updated_at timestamp."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO interactions
                (contact_id, interaction_date, method, direction, summary, outcome)
            VALUES (%s, CURRENT_DATE, %s, %s, %s, %s)
            """,
            (contact_id, method, direction, summary, outcome),
        )
        cur.execute(
            "UPDATE contacts SET updated_at = NOW() WHERE id = %s",
            (contact_id,),
        )


def get_overdue_contacts(days: int = 90) -> list[dict]:
    """
    Return contacts with status='contacted' that haven't had an interaction
    in `days` days, or whose next_action_date is in the past.
    """
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                c.*,
                EXTRACT(DAY FROM NOW() - MAX(i.interaction_date))::int AS days_since_contact,
                (
                    SELECT summary FROM interactions
                    WHERE contact_id = c.id
                    ORDER BY interaction_date DESC LIMIT 1
                ) AS last_subject
            FROM contacts c
            LEFT JOIN interactions i ON i.contact_id = c.id
            WHERE c.status = 'contacted'
            GROUP BY c.id
            HAVING
                MAX(i.interaction_date) < CURRENT_DATE - INTERVAL '%s days'
                OR MAX(i.interaction_date) IS NULL
            ORDER BY MAX(i.interaction_date) ASC NULLS FIRST
            LIMIT 30
            """,
            (days,),
        )
        return [_serialize_row(dict(r)) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Inbox messages
# ---------------------------------------------------------------------------

def save_inbox_message(
    message_id: str,
    from_email: str,
    subject: str,
    body: str,
    received_at: datetime,
) -> int:
    """Cache an inbox message from IMAP. Returns id, or 0 if duplicate."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM inbox_messages WHERE message_id = %s",
            (message_id,),
        )
        if cur.fetchone():
            return 0
        cur.execute(
            """
            INSERT INTO inbox_messages (message_id, from_email, subject, body, received_at)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
            """,
            (message_id, from_email, subject, body, received_at),
        )
        return cur.fetchone()["id"]


def get_unprocessed_inbox() -> list[dict]:
    """Return inbox messages not yet processed by the follow-up agent."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM inbox_messages WHERE processed = FALSE ORDER BY received_at ASC"
        )
        return [dict(r) for r in cur.fetchall()]


def mark_message_processed(inbox_message_id: int, contact_id: int | None) -> None:
    """Mark an inbox message as processed, linking it to a contact if matched."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE inbox_messages
            SET processed = TRUE, matched_contact_id = %s
            WHERE id = %s
            """,
            (contact_id, inbox_message_id),
        )


# ---------------------------------------------------------------------------
# Research queue
# ---------------------------------------------------------------------------

def get_next_research_targets(cities_per_run: int = 3) -> list[dict]:
    """
    Return the next batch of research targets — all industries for the next
    N cities that haven't been researched yet (or were researched longest ago).
    """
    with db() as conn:
        cur = conn.cursor()
        # Pick the next N cities ordered by last_run_at ASC NULLS FIRST
        cur.execute(
            """
            SELECT DISTINCT city, country,
                   MIN(COALESCE(last_run_at, '1970-01-01')) AS oldest
            FROM research_queue
            GROUP BY city, country
            ORDER BY oldest ASC
            LIMIT %s
            """,
            (cities_per_run,),
        )
        cities = [(r["city"], r["country"]) for r in cur.fetchall()]

        if not cities:
            return []

        targets = []
        for city, country in cities:
            cur.execute(
                "SELECT city, industry, country FROM research_queue WHERE city = %s AND country = %s",
                (city, country),
            )
            targets.extend([dict(r) for r in cur.fetchall()])
        return targets


def mark_research_target_done(city: str, industry: str) -> None:
    """Record that a city/industry combo was just researched."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE research_queue
            SET last_run_at = NOW(), run_count = run_count + 1
            WHERE city = %s AND industry = %s
            """,
            (city, industry),
        )


# ---------------------------------------------------------------------------
# Agent run logging
# ---------------------------------------------------------------------------

def start_run(agent_name: str, input_data: dict) -> int:
    """Insert a new agent_run record. Returns run_id."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO agent_runs (agent_name, status, input_json)
            VALUES (%s, 'running', %s) RETURNING id
            """,
            (agent_name, json.dumps(input_data, default=str)),
        )
        return cur.fetchone()["id"]


def finish_run(run_id: int, status: str, summary: str, output_data: dict) -> None:
    """Update an agent_run record with completion details."""
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE agent_runs
            SET status = %s, summary = %s, output_json = %s, finished_at = NOW()
            WHERE id = %s
            """,
            (status, summary, json.dumps(output_data, default=str), run_id),
        )
