"""
ArtCRM Supervisor MCP Server

Exposes the supervisor pipeline layer as MCP tools.
Complements the art-crm MCP (in theo-hits-the-road) which handles contact/interaction/show CRUD.
This server covers what's unique to the supervisor: the approval queue, pipeline status, and agent runs.
"""
import json
import logging
import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.db.connection import db
from src.tools.db import log_interaction
from src.tools.email import send_email

logger = logging.getLogger(__name__)

server = FastMCP("artcrm-supervisor", "1.0.0")


# =============================================================================
# PIPELINE STATUS
# =============================================================================

@server.tool()
def pipeline_status() -> str:
    """Get a count of contacts at each pipeline stage: candidate, cold, contacted, dormant, dropped."""
    try:
        with db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT status, COUNT(*) AS count
                FROM contacts
                WHERE name != '[removed]'
                GROUP BY status
                ORDER BY status
            """)
            counts = {row["status"]: row["count"] for row in cur.fetchall()}

            cur.execute("SELECT COUNT(*) AS count FROM approval_queue WHERE status = 'pending'")
            pending_approvals = cur.fetchone()["count"]

        return json.dumps({
            "contacts_by_status": counts,
            "pending_approvals": pending_approvals,
        }, indent=2)
    except Exception as e:
        logger.error("pipeline_status failed: %s", e)
        return json.dumps({"error": str(e)})


# =============================================================================
# DATABASE OVERVIEW
# =============================================================================

@server.tool()
def contacts_list(status: str = "", limit: int = 200) -> str:
    """
    List contacts from the database. Optionally filter by status
    (candidate, cold, contacted, dormant, dropped).
    Returns id, name, city, email, status, fit_score, and last interaction date.
    """
    try:
        with db() as conn:
            cur = conn.cursor()
            if status:
                cur.execute("""
                    SELECT c.id, c.name, c.city, c.email, c.type, c.status, c.fit_score, c.notes,
                           MAX(i.interaction_date) AS last_contact
                    FROM contacts c
                    LEFT JOIN interactions i ON i.contact_id = c.id
                    WHERE c.status = %s AND c.name != '[removed]'
                    GROUP BY c.id
                    ORDER BY c.updated_at DESC
                    LIMIT %s
                """, (status, limit))
            else:
                cur.execute("""
                    SELECT c.id, c.name, c.city, c.email, c.type, c.status, c.fit_score, c.notes,
                           MAX(i.interaction_date) AS last_contact
                    FROM contacts c
                    LEFT JOIN interactions i ON i.contact_id = c.id
                    WHERE c.name != '[removed]'
                    GROUP BY c.id
                    ORDER BY c.status, c.updated_at DESC
                    LIMIT %s
                """, (limit,))
            rows = [dict(r) for r in cur.fetchall()]

        for r in rows:
            if r.get("last_contact"):
                r["last_contact"] = str(r["last_contact"])

        return json.dumps(rows, indent=2)
    except Exception as e:
        logger.error("contacts_list failed: %s", e)
        return json.dumps({"error": str(e)})


# =============================================================================
# APPROVAL QUEUE
# =============================================================================

@server.tool()
def approval_list() -> str:
    """List all email drafts currently pending human approval."""
    try:
        with db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    aq.id, aq.draft_subject, aq.draft_body, aq.created_at,
                    c.id AS contact_id, c.name AS contact_name, c.city, c.email
                FROM approval_queue aq
                JOIN contacts c ON c.id = aq.contact_id
                WHERE aq.status = 'pending'
                ORDER BY aq.created_at ASC
            """)
            items = [dict(row) for row in cur.fetchall()]

        for item in items:
            if item.get("created_at"):
                item["created_at"] = str(item["created_at"])

        return json.dumps(items, indent=2)
    except Exception as e:
        logger.error("approval_list failed: %s", e)
        return json.dumps({"error": str(e)})


@server.tool()
def approval_approve(item_id: int, note: str = "") -> str:
    """
    Approve a queued email draft. Sends the email via Proton Bridge SMTP,
    logs the interaction, and moves the contact to status=contacted.
    """
    try:
        with db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT aq.draft_subject, aq.draft_body, aq.contact_id, c.email, c.name
                FROM approval_queue aq
                JOIN contacts c ON c.id = aq.contact_id
                WHERE aq.id = %s AND aq.status = 'pending'
            """, (item_id,))
            row = cur.fetchone()

        if not row:
            return json.dumps({"error": f"Item {item_id} not found or already reviewed"})

        success = send_email(
            to_email=row["email"] or "",
            subject=row["draft_subject"],
            body=row["draft_body"],
        )
        final_status = "approved" if success else "approved_unsent"

        if success:
            log_interaction(
                contact_id=row["contact_id"],
                method="email",
                direction="outbound",
                summary=row["draft_subject"],
                outcome="no_reply",
            )

        with db() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE approval_queue
                SET status = %s, reviewed_at = NOW(), reviewer_note = %s
                WHERE id = %s
            """, (final_status, note or None, item_id))
            if success:
                cur.execute("""
                    UPDATE contacts SET status = 'contacted', updated_at = NOW()
                    WHERE id = %s AND status = 'cold'
                """, (row["contact_id"],))

        return json.dumps({
            "approved": True,
            "sent": success,
            "status": final_status,
            "contact": row["name"],
            "to": row["email"],
        })
    except Exception as e:
        logger.error("approval_approve failed: item_id=%d error=%s", item_id, e)
        return json.dumps({"error": str(e)})


@server.tool()
def approval_reject(item_id: int, note: str = "") -> str:
    """Reject a queued email draft. The contact stays at status=cold for the next run."""
    try:
        with db() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE approval_queue
                SET status = 'rejected', reviewed_at = NOW(), reviewer_note = %s
                WHERE id = %s AND status = 'pending'
            """, (note or None, item_id))
            if cur.rowcount == 0:
                return json.dumps({"error": f"Item {item_id} not found or already reviewed"})

        return json.dumps({"rejected": True, "item_id": item_id})
    except Exception as e:
        logger.error("approval_reject failed: item_id=%d error=%s", item_id, e)
        return json.dumps({"error": str(e)})


# =============================================================================
# AGENT RUNS
# =============================================================================

@server.tool()
def agent_runs(limit: int = 20) -> str:
    """Get recent agent run history — what ran, when, and what happened."""
    try:
        with db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, agent_name, status, summary, started_at, finished_at
                FROM agent_runs
                ORDER BY started_at DESC
                LIMIT %s
            """, (limit,))
            runs = [dict(row) for row in cur.fetchall()]

        for run in runs:
            for key in ("started_at", "finished_at"):
                if run.get(key):
                    run[key] = str(run[key])

        return json.dumps(runs, indent=2)
    except Exception as e:
        logger.error("agent_runs failed: %s", e)
        return json.dumps({"error": str(e)})


# =============================================================================
# TRIGGER RUN
# =============================================================================

@server.tool()
def trigger_run() -> str:
    """
    Kick off a full supervisor pipeline run (research → scout → outreach → followup).
    Starts in the background and returns immediately. Check agent_runs for progress.
    Requires the agents extra to be installed: uv sync --extra agents
    """
    try:
        project_root = Path(__file__).parent.parent.parent
        uv = Path.home() / ".local" / "bin" / "uv"
        cmd = [str(uv), "run", "python", "-m", "src.supervisor.run"]

        proc = subprocess.Popen(
            cmd,
            cwd=str(project_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return json.dumps({
            "triggered": True,
            "pid": proc.pid,
            "message": "Supervisor run started in background. Check agent_runs for progress.",
        })
    except Exception as e:
        logger.error("trigger_run failed: %s", e)
        return json.dumps({"error": str(e)})


# =============================================================================
# RESOURCES
# =============================================================================

@server.resource("supervisor://pipeline")
def resource_pipeline() -> str:
    """Pipeline overview: contact counts at each stage plus pending approvals."""
    try:
        with db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT status, COUNT(*) AS count
                FROM contacts
                WHERE name != '[removed]'
                GROUP BY status
                ORDER BY status
            """)
            counts = {row["status"]: row["count"] for row in cur.fetchall()}

            cur.execute("SELECT COUNT(*) AS count FROM approval_queue WHERE status = 'pending'")
            pending = cur.fetchone()["count"]

        lines = ["Pipeline status:"]
        for status, count in counts.items():
            lines.append(f"  {status}: {count}")
        lines.append(f"\nPending approvals: {pending}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


@server.resource("supervisor://queue")
def resource_queue() -> str:
    """All email drafts pending approval, one per line."""
    try:
        with db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT aq.id, aq.draft_subject, aq.created_at,
                       c.name AS contact_name, c.city, c.email
                FROM approval_queue aq
                JOIN contacts c ON c.id = aq.contact_id
                WHERE aq.status = 'pending'
                ORDER BY aq.created_at ASC
            """)
            items = cur.fetchall()

        if not items:
            return "No pending approvals."

        lines = [f"{len(items)} pending approval(s):\n"]
        for item in items:
            lines.append(
                f"  #{item['id']} | {item['contact_name']} ({item['city']}) "
                f"| {item['draft_subject']} | {str(item['created_at'])[:10]}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


# =============================================================================
# PROMPTS
# =============================================================================

@server.prompt()
def review_approvals() -> str:
    """Review the pending approval queue and decide what to approve, edit, or reject."""
    return """Review the pending email approval queue:

1. Use approval_list to see all drafts waiting for review
2. For each draft, read the subject and body carefully
3. Check the contact details — name, city, email
4. Decide:
   - Approve with approval_approve(item_id) if the draft looks good
   - Reject with approval_reject(item_id, note="reason") if it's off
   - Tell me to edit any draft before approving — I'll update it and you approve
5. After reviewing, use pipeline_status to confirm the queue is clear

Notes:
- approval_approve sends the email immediately via Proton Bridge SMTP
- Rejected drafts leave the contact at status=cold — outreach agent will redraft next run
- If Proton Bridge isn't running, the email won't send but will be marked approved_unsent
"""


@server.prompt()
def pipeline_review() -> str:
    """Check the overall health of the pipeline and decide what needs attention."""
    return """Review the state of the outreach pipeline:

1. Use pipeline_status to see how many contacts are at each stage
2. Use agent_runs(limit=10) to see what the agents did recently
3. Use approval_list to check if there are drafts waiting for you
4. Based on what you see, recommend:
   - Whether to trigger a new run (trigger_run)
   - Whether any approvals need immediate attention
   - Whether the pipeline looks healthy or has a bottleneck
"""


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    server.run()
