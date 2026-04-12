"""
One-time setup for the agent memory system.

Registers topic hints in Open Brain to guide thought classification.

Run once after deploying:
    uv run python scripts/setup_memory.py
"""
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TOPIC_HINTS = [
    {
        "topic": "artcrm-outreach",
        "description": "Email tone, word count, subject lines, response rates for art CRM outreach",
        "category": "projects",
    },
    {
        "topic": "artcrm-city",
        "description": "City-level notes for art CRM: venue density, responsiveness, regional patterns",
        "category": "projects",
    },
    {
        "topic": "artcrm-venue",
        "description": "Venue type patterns for art CRM: galleries, hotels, cafes, coworking spaces",
        "category": "projects",
    },
    {
        "topic": "artcrm-seasonal",
        "description": "Seasonal observations for art CRM: plein air season, events, time-of-year patterns",
        "category": "projects",
    },
]


def main():
    from src.tools.memory import _run_tool

    for hint in TOPIC_HINTS:
        result = _run_tool("add_topic_hint", hint)
        logger.info("Registered topic hint '%s': %s", hint["topic"], result[:80] if result else "ok")

    logger.info("Setup complete.")


if __name__ == "__main__":
    main()
