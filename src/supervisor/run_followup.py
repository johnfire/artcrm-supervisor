"""
Run the followup agent standalone — reads inbox and queues overdue nudges.

Usage:
    uv run python -m src.supervisor.run_followup
    uv run python -m src.supervisor.run_followup --overdue-days 60
"""
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run the followup agent standalone")
    parser.add_argument("--overdue-days", type=int, default=90,
                        help="Days without reply before a contact is considered overdue (default: 90)")
    args = parser.parse_args()

    from src.config import ACTIVE_MISSION
    from src.tools import (
        read_inbox, match_contact_by_email, log_interaction, set_opt_out,
        mark_bad_email, set_visit_when_nearby, save_inbox_classification,
        get_overdue_contacts, queue_for_approval,
        start_run, finish_run, get_llm,
    )
    from artcrm_followup_agent import create_followup_agent

    agent = create_followup_agent(
        llm=get_llm("claude"),
        fetch_inbox=read_inbox,
        match_contact=match_contact_by_email,
        log_interaction=log_interaction,
        set_opt_out=set_opt_out,
        handle_bounce=mark_bad_email,
        set_visit_when_nearby=set_visit_when_nearby,
        save_inbox_classification=save_inbox_classification,
        fetch_overdue=get_overdue_contacts,
        queue_for_approval=queue_for_approval,
        start_run=start_run,
        finish_run=finish_run,
        mission=ACTIVE_MISSION,
        overdue_days=args.overdue_days,
    )

    logger.info("followup: running (overdue_days=%d)", args.overdue_days)
    result = agent.invoke({})
    logger.info("Done: %s", result.get("summary", ""))


if __name__ == "__main__":
    main()
