"""
Auto-rate neighborhoods as wealthy, poor, or normal using web search + Claude.

For each unrated neighborhood in a city, searches the web for socioeconomic info
and asks Claude to classify it. Writes results to neighborhood_tiers and propagates
to contacts.

Usage:
    uv run python scripts/rate_neighborhoods.py --city Augsburg
    uv run python scripts/rate_neighborhoods.py --city Augsburg --dry-run
"""
import argparse
import logging
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = """\
You are classifying a city neighborhood by its socioeconomic character for the purpose of art sales outreach.

Neighborhood: {neighborhood}
City: {city}
Country: Germany

Web search results:
{search_text}

Classify this neighborhood as exactly one of:
- wealthy: above-average income, high-end shops, affluent residents
- poor: below-average income, socially deprived area
- normal: average/mixed, neither notably wealthy nor poor

Reply with a single word: wealthy, poor, or normal.
If there is insufficient information to determine, reply: normal
"""


def search_neighborhood(neighborhood: str, city: str) -> str:
    """Run a web search for neighborhood socioeconomic info."""
    from src.tools.search import web_search
    query = f"{neighborhood} {city} Stadtteil Kaufkraft sozial wohlhabend"
    try:
        results = web_search(query, max_results=5)
        snippets = []
        for r in results:
            title = r.get("title", "")
            snippet = r.get("snippet", "")
            if title or snippet:
                snippets.append(f"{title}: {snippet}")
        return "\n".join(snippets[:5]) if snippets else "(no results)"
    except Exception as e:
        logger.warning("search failed for %s: %s", neighborhood, e)
        return "(search failed)"


def classify_neighborhood(neighborhood: str, city: str, search_text: str) -> str:
    """Ask Claude to classify the neighborhood tier."""
    from src.tools.llm import get_llm
    from langchain_core.messages import HumanMessage

    llm = get_llm("claude")
    prompt = CLASSIFICATION_PROMPT.format(
        neighborhood=neighborhood,
        city=city,
        search_text=search_text,
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    tier = response.content.strip().lower().split()[0]
    if tier not in ("wealthy", "poor", "normal"):
        tier = "normal"
    return tier


def main():
    parser = argparse.ArgumentParser(description="Auto-rate neighborhoods using web search + Claude")
    parser.add_argument("--city", required=True)
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing to DB")
    parser.add_argument("--rerate", action="store_true", help="Re-rate neighborhoods that already have a tier")
    args = parser.parse_args()

    from src.db.connection import db

    # Fetch distinct neighborhoods needing a tier
    with db() as conn:
        cur = conn.cursor()
        if args.rerate:
            cur.execute(
                """
                SELECT DISTINCT c.neighborhood
                FROM contacts c
                WHERE lower(c.city) = lower(%s)
                  AND c.neighborhood IS NOT NULL
                  AND c.deleted_at IS NULL
                ORDER BY c.neighborhood
                """,
                (args.city,),
            )
        else:
            cur.execute(
                """
                SELECT DISTINCT c.neighborhood
                FROM contacts c
                LEFT JOIN neighborhood_tiers nt
                    ON lower(c.city) = lower(nt.city)
                   AND lower(c.neighborhood) = lower(nt.neighborhood)
                WHERE lower(c.city) = lower(%s)
                  AND c.neighborhood IS NOT NULL
                  AND c.deleted_at IS NULL
                  AND nt.tier IS NULL
                ORDER BY c.neighborhood
                """,
                (args.city,),
            )
        neighborhoods = [r["neighborhood"] for r in cur.fetchall()]

    logger.info("Rating %d neighborhoods in %s", len(neighborhoods), args.city)

    for neighborhood in neighborhoods:
        search_text = search_neighborhood(neighborhood, args.city)
        tier = classify_neighborhood(neighborhood, args.city, search_text)
        logger.info("  %s → %s", neighborhood, tier)

        if not args.dry_run:
            with db() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO neighborhood_tiers (city, neighborhood, tier)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (lower(city), lower(neighborhood))
                    DO UPDATE SET tier = EXCLUDED.tier, updated_at = NOW()
                    """,
                    (args.city, neighborhood, tier),
                )
                cur.execute(
                    """
                    UPDATE contacts SET neighborhood_tier = %s
                    WHERE lower(city) = lower(%s)
                      AND lower(neighborhood) = lower(%s)
                      AND deleted_at IS NULL
                    """,
                    (tier, args.city, neighborhood),
                )
                conn.commit()

        time.sleep(0.5)

    logger.info("Done.")


if __name__ == "__main__":
    main()
