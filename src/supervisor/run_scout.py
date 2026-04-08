"""
Run the scout agent standalone.

Usage:
    uv run python -m src.supervisor.run_scout
    uv run python -m src.supervisor.run_scout --limit 200
    uv run python -m src.supervisor.run_scout --skip-galleries   # promote all candidates to cold, no LLM scoring
"""
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run scout agent")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--city", type=str, default=None, help="Only scout candidates in this city")
    parser.add_argument("--skip-galleries", action="store_true", help="Promote all candidates without LLM scoring")
    args = parser.parse_args()

    from src.config import ACTIVE_MISSION
    import functools
    from src.tools import (
        get_candidates, update_contact, fetch_page,
        get_city_market_context, start_run, finish_run, get_llm,
    )
    from artcrm_scout_agent import create_scout_agent
    import artcrm_scout_agent.graph as scout_graph

    if args.skip_galleries:
        scout_graph.GALLERY_TYPES = set()
        logger.info("scout: gallery scoring disabled — all candidates will be auto-promoted to cold")

    fetch_candidates = functools.partial(get_candidates, city=args.city) if args.city else get_candidates

    agent = create_scout_agent(
        llm=get_llm("deepseek"),
        fetch_candidates=fetch_candidates,
        update_contact=update_contact,
        fetch_page=fetch_page,
        fetch_city_context=get_city_market_context,
        start_run=start_run,
        finish_run=finish_run,
        mission=ACTIVE_MISSION,
    )

    logger.info("scout: running (limit=%d)", args.limit)
    result = agent.invoke({"limit": args.limit})
    logger.info("Done: %s", result.get("summary", ""))


if __name__ == "__main__":
    main()
