"""Shared send-and-log for approved outreach drafts.

Single source of truth used by the web approval/drafts routers and the mobile
JSON API so "approve" behaves identically everywhere: send the email, log the
interaction, and advance the contact to 'contacted'. Returns (success, status)
where status is the approval_queue status to persist ('sent' maps to the
caller's approved/edited status; 'approved_unsent' means the send failed).
"""
import logging

from src.db.connection import db

logger = logging.getLogger(__name__)


def send_and_log(item_id: int, contact_id: int, to_email: str, subject: str, body: str) -> tuple[bool, str]:
    """Attempt to send an approved email and record the interaction.

    Never raises — returns (False, error) on failure so the caller can still
    record a terminal review state instead of leaving the draft pending.
    """
    try:
        from src.tools.email import send_email
        from src.tools.db import log_interaction
        success = send_email(to_email=to_email, subject=subject, body=body)
        log_interaction(
            contact_id=contact_id,
            method="email",
            direction="outbound",
            summary=subject,
            outcome="no_reply",
        )
        with db() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE contacts SET status = 'contacted', last_emailed_at = NOW(), updated_at = NOW() "
                "WHERE id = %s AND status IN ('cold', 'on_hold')",
                (contact_id,),
            )
        return success, "sent" if success else "approved_unsent"
    except Exception as exc:
        logger.error("send_and_log: item_id=%d error=%s", item_id, exc)
        return False, str(exc)
