"""
LangGraph supervisor that orchestrates all four agents in sequence.
Uses a PostgreSQL checkpointer so runs survive crashes and can be resumed.

Run order per invocation:
  1. research_agent — once per target in RESEARCH_TARGETS
  2. scout_agent    — scores all candidates
  3. outreach_agent — drafts first-contact emails for cold contacts
  4. followup_agent — processes inbox + sends follow-ups to overdue contacts

Each agent handles the "nothing to do" case gracefully, so the supervisor
always runs to completion even when there is no work.
"""
import logging
from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver

from src.config import DATABASE_URL, ACTIVE_MISSION, SCOUT_THRESHOLD
from src.supervisor.targets import RESEARCH_TARGETS
from src.tools import (
    save_contact, get_candidates, get_cold_contacts, update_contact,
    check_compliance, queue_for_approval, log_interaction, set_opt_out,
    get_overdue_contacts, get_unprocessed_inbox, mark_message_processed,
    match_contact_by_email, save_inbox_message,
    start_run, finish_run,
    web_search, geo_search,
    send_email, read_inbox,
    get_llm,
)

from artcrm_research_agent import create_research_agent
from artcrm_scout_agent import create_scout_agent
from artcrm_outreach_agent import create_outreach_agent
from artcrm_followup_agent import create_followup_agent

logger = logging.getLogger(__name__)


class SupervisorState(TypedDict):
    run_id: int
    research_summaries: list[str]
    scout_summary: str
    outreach_summary: str
    followup_summary: str
    errors: list[str]
    summary: str


def _build_agents():
    """Instantiate all four agents with concrete tools and the active mission."""
    research_llm = get_llm("deepseek-chat")
    scout_llm = get_llm("deepseek-chat")
    outreach_llm = get_llm("deepseek-reasoner")
    followup_llm = get_llm("deepseek-reasoner")

    research = create_research_agent(
        llm=research_llm,
        web_search=web_search,
        geo_search=geo_search,
        save_contact=save_contact,
        start_run=start_run,
        finish_run=finish_run,
        mission=ACTIVE_MISSION,
    )

    scout = create_scout_agent(
        llm=scout_llm,
        fetch_candidates=get_candidates,
        update_contact=update_contact,
        start_run=start_run,
        finish_run=finish_run,
        mission=ACTIVE_MISSION,
        threshold=SCOUT_THRESHOLD,
    )

    outreach = create_outreach_agent(
        llm=outreach_llm,
        fetch_ready_contacts=get_cold_contacts,
        check_compliance=check_compliance,
        queue_for_approval=queue_for_approval,
        start_run=start_run,
        finish_run=finish_run,
        mission=ACTIVE_MISSION,
    )

    followup = create_followup_agent(
        llm=followup_llm,
        fetch_inbox=read_inbox,
        match_contact=match_contact_by_email,
        log_interaction=log_interaction,
        set_opt_out=set_opt_out,
        mark_message_processed=mark_message_processed,
        fetch_overdue=get_overdue_contacts,
        send_email=send_email,
        start_run=start_run,
        finish_run=finish_run,
        mission=ACTIVE_MISSION,
    )

    return research, scout, outreach, followup


def create_supervisor():
    """
    Build and compile the supervisor graph with a PostgreSQL checkpointer.
    Returns the compiled graph.
    """
    research_agent, scout_agent, outreach_agent, followup_agent = _build_agents()

    def init(state: SupervisorState) -> dict:
        run_id = start_run("supervisor", {"targets": len(RESEARCH_TARGETS)})
        logger.info("supervisor: starting run_id=%d, %d research targets", run_id, len(RESEARCH_TARGETS))
        return {
            "run_id": run_id,
            "research_summaries": [],
            "scout_summary": "",
            "outreach_summary": "",
            "followup_summary": "",
            "errors": [],
            "summary": "",
        }

    def run_research(state: SupervisorState) -> dict:
        summaries = []
        for target in RESEARCH_TARGETS:
            try:
                result = research_agent.invoke({
                    "city": target["city"],
                    "industry": target["industry"],
                    "country": target.get("country", "DE"),
                })
                summaries.append(result.get("summary", ""))
                logger.info("research: %s", result.get("summary", ""))
            except Exception as e:
                msg = f"research failed for {target['city']}/{target['industry']}: {e}"
                logger.error(msg)
                summaries.append(msg)
        return {"research_summaries": summaries}

    def run_scout(state: SupervisorState) -> dict:
        try:
            result = scout_agent.invoke({"limit": 100})
            logger.info("scout: %s", result.get("summary", ""))
            return {"scout_summary": result.get("summary", "")}
        except Exception as e:
            msg = f"scout failed: {e}"
            logger.error(msg)
            return {"scout_summary": msg, "errors": state["errors"] + [msg]}

    def run_outreach(state: SupervisorState) -> dict:
        try:
            result = outreach_agent.invoke({"limit": 1})
            logger.info("outreach: %s", result.get("summary", ""))
            return {"outreach_summary": result.get("summary", "")}
        except Exception as e:
            msg = f"outreach failed: {e}"
            logger.error(msg)
            return {"outreach_summary": msg, "errors": state["errors"] + [msg]}

    def run_followup(state: SupervisorState) -> dict:
        try:
            result = followup_agent.invoke({})
            logger.info("followup: %s", result.get("summary", ""))
            return {"followup_summary": result.get("summary", "")}
        except Exception as e:
            msg = f"followup failed: {e}"
            logger.error(msg)
            return {"followup_summary": msg, "errors": state["errors"] + [msg]}

    def generate_report(state: SupervisorState) -> dict:
        lines = [
            f"Supervisor run completed — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "Research:",
        ]
        for s in state.get("research_summaries", []):
            lines.append(f"  {s}")
        lines += [
            "",
            f"Scout:    {state.get('scout_summary', '—')}",
            f"Outreach: {state.get('outreach_summary', '—')}",
            f"Followup: {state.get('followup_summary', '—')}",
        ]
        errs = state.get("errors", [])
        if errs:
            lines.append(f"\nErrors ({len(errs)}):")
            for e in errs:
                lines.append(f"  {e}")

        summary = "\n".join(lines)
        status = "failed" if errs and not state.get("scout_summary") else "completed"
        finish_run(state.get("run_id", 0), status, summary[:500], {})
        return {"summary": summary}

    graph = StateGraph(SupervisorState)
    graph.add_node("init", init)
    graph.add_node("run_research", run_research)
    graph.add_node("run_scout", run_scout)
    graph.add_node("run_outreach", run_outreach)
    graph.add_node("run_followup", run_followup)
    graph.add_node("generate_report", generate_report)

    graph.set_entry_point("init")
    graph.add_edge("init", "run_research")
    graph.add_edge("run_research", "run_scout")
    graph.add_edge("run_scout", "run_outreach")
    graph.add_edge("run_outreach", "run_followup")
    graph.add_edge("run_followup", "generate_report")
    graph.add_edge("generate_report", END)

    checkpointer = PostgresSaver.from_conn_string(DATABASE_URL)
    checkpointer.setup()  # creates LangGraph checkpoint tables if not present

    return graph.compile(checkpointer=checkpointer)
