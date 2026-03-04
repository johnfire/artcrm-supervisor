"""
Concrete tool implementations injected into agents at runtime.
Each function satisfies a Protocol defined in the relevant agent repo.
"""
from .db import (
    save_contact,
    get_candidates,
    get_cold_contacts,
    update_contact,
    check_compliance,
    ensure_consent_log,
    queue_for_approval,
    log_interaction,
    set_opt_out,
    get_overdue_contacts,
    save_inbox_message,
    get_unprocessed_inbox,
    mark_message_processed,
    match_contact_by_email,
    start_run,
    finish_run,
)
from .search import web_search, geo_search
from .email import send_email, read_inbox
from .llm import get_llm

__all__ = [
    "save_contact", "get_candidates", "get_cold_contacts", "update_contact",
    "check_compliance", "ensure_consent_log", "queue_for_approval",
    "log_interaction", "set_opt_out", "get_overdue_contacts",
    "save_inbox_message", "get_unprocessed_inbox", "mark_message_processed",
    "match_contact_by_email", "start_run", "finish_run",
    "web_search", "geo_search",
    "send_email", "read_inbox",
    "get_llm",
]
