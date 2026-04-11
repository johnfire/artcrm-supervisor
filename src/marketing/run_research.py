# src/marketing/run_research.py
"""
Entry point for the marketing research agent.

Usage:
    uv run python -m src.marketing.run_research
"""
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    from src.config import CHEAP_LLM
    from src.tools.llm import get_llm
    from src.marketing.research_agent import run

    logger.info("Marketing research agent starting")
    llm = get_llm(CHEAP_LLM)
    count = run(llm)
    logger.info("Research agent complete — %d findings saved", count)


if __name__ == "__main__":
    main()
