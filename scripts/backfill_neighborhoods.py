"""
Backfill neighborhood for contacts that have none.

Looks up each contact by name+city via Google Places and extracts
the sublocality/neighborhood from addressComponents.

Usage:
    uv run python scripts/backfill_neighborhoods.py --city Augsburg
    uv run python scripts/backfill_neighborhoods.py --city Augsburg --dry-run
    uv run python scripts/backfill_neighborhoods.py  # all cities
"""
import argparse
import logging
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def lookup_neighborhood(name: str, city: str) -> str:
    """Query Google Places for a venue and return its neighborhood, or '' if not found."""
    from src.tools.search import google_maps_search
    results = google_maps_search(name, city)
    for r in results:
        n = r.get("neighborhood", "")
        if n:
            return n
    return ""


def main():
    parser = argparse.ArgumentParser(description="Backfill neighborhood field for contacts")
    parser.add_argument("--city", default=None, help="Limit to a specific city")
    parser.add_argument("--limit", type=int, default=200, help="Max contacts to process")
    parser.add_argument("--dry-run", action="store_true", help="Print results without updating DB")
    args = parser.parse_args()

    import psycopg2
    import psycopg2.extras
    from src.db.connection import db

    with db() as conn:
        cur = conn.cursor()
        q = "SELECT id, name, city FROM contacts WHERE neighborhood IS NULL AND deleted_at IS NULL"
        params: list = []
        if args.city:
            q += " AND lower(city) = lower(%s)"
            params.append(args.city)
        q += " ORDER BY id ASC LIMIT %s"
        params.append(args.limit)
        cur.execute(q, params)
        contacts = cur.fetchall()

    logger.info("Backfilling %d contacts", len(contacts))
    updated = 0
    not_found = 0

    for row in contacts:
        contact_id, name, city = row["id"], row["name"], row["city"]
        neighborhood = lookup_neighborhood(name, city)
        if neighborhood:
            logger.info("  [%d] %s / %s → %s", contact_id, name, city, neighborhood)
            if not args.dry_run:
                with db() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "UPDATE contacts SET neighborhood = %s WHERE id = %s",
                        (neighborhood, contact_id),
                    )
                    conn.commit()
            updated += 1
        else:
            logger.debug("  [%d] %s / %s → not found", contact_id, name, city)
            not_found += 1
        time.sleep(0.1)  # stay within Places API rate limits

    label = "(dry run) " if args.dry_run else ""
    logger.info("%sComplete — %d updated, %d not found", label, updated, not_found)


if __name__ == "__main__":
    main()
