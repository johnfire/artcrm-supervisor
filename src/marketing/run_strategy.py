# src/marketing/run_strategy.py
"""
Entry point for the marketing strategy agent.

Usage:
    uv run python -m src.marketing.run_strategy
"""
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    from src.tools.llm import get_llm
    from src.marketing.strategy_agent import run

    logger.info("Marketing strategy agent starting")
    llm = get_llm("claude")
    digest = run(llm)
    logger.info("Digest generated (%d chars)", len(digest))
    print("\n" + "=" * 60)
    print(digest)
    print("=" * 60)


if __name__ == "__main__":
    main()
