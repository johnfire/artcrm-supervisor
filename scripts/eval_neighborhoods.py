"""
Show neighborhood distribution for a city and optionally assign tiers.

Usage:
    uv run python scripts/eval_neighborhoods.py --city Augsburg
    uv run python scripts/eval_neighborhoods.py --city Augsburg --set-tier "Maximilianstraße=wealthy"
    uv run python scripts/eval_neighborhoods.py --city Augsburg --set-tier "Lechhausen=poor"
"""
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

VALID_TIERS = {"poor", "normal", "wealthy"}


def main():
    parser = argparse.ArgumentParser(description="Evaluate and rate neighborhoods in a city")
    parser.add_argument("--city", required=True)
    parser.add_argument(
        "--set-tier",
        metavar="NEIGHBORHOOD=TIER",
        action="append",
        default=[],
        help="Assign a tier: --set-tier 'Maximilianstraße=wealthy' (repeatable)",
    )
    args = parser.parse_args()

    from src.db.connection import db

    # Apply any tier assignments first
    for assignment in args.set_tier:
        if "=" not in assignment:
            logger.error("Invalid format: %s (expected NEIGHBORHOOD=TIER)", assignment)
            continue
        neighborhood, tier = assignment.split("=", 1)
        neighborhood = neighborhood.strip()
        tier = tier.strip().lower()
        if tier not in VALID_TIERS:
            logger.error("Invalid tier '%s' — must be one of: %s", tier, ", ".join(VALID_TIERS))
            continue
        with db() as conn:
            cur = conn.cursor()
            # Upsert into neighborhood_tiers table
            cur.execute(
                """
                INSERT INTO neighborhood_tiers (city, neighborhood, tier)
                VALUES (%s, %s, %s)
                ON CONFLICT (lower(city), lower(neighborhood))
                DO UPDATE SET tier = EXCLUDED.tier, updated_at = NOW()
                """,
                (args.city, neighborhood, tier),
            )
            # Propagate to contacts
            cur.execute(
                """
                UPDATE contacts SET neighborhood_tier = %s
                WHERE lower(city) = lower(%s) AND lower(neighborhood) = lower(%s)
                  AND deleted_at IS NULL
                """,
                (tier, args.city, neighborhood),
            )
            conn.commit()
            logger.info("Set %s / %s → %s (%d contacts updated)",
                        args.city, neighborhood, tier, cur.rowcount)

    # Print current state
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                COALESCE(c.neighborhood, '(none)') AS neighborhood,
                COALESCE(nt.tier, '—') AS tier,
                COUNT(*) AS contacts,
                SUM(CASE WHEN c.status = 'cold' THEN 1 ELSE 0 END) AS cold
            FROM contacts c
            LEFT JOIN neighborhood_tiers nt
                ON lower(c.city) = lower(nt.city)
               AND lower(c.neighborhood) = lower(nt.neighborhood)
            WHERE lower(c.city) = lower(%s) AND c.deleted_at IS NULL
            GROUP BY c.neighborhood, nt.tier
            ORDER BY contacts DESC
            """,
            (args.city,),
        )
        rows = cur.fetchall()

    print(f"\nNeighborhood report — {args.city}")
    print(f"{'Neighborhood':<35} {'Tier':<10} {'Total':>7} {'Cold':>7}")
    print("-" * 62)
    for r in rows:
        print(f"{r['neighborhood']:<35} {r['tier']:<10} {r['contacts']:>7} {r['cold']:>7}")
    print()


if __name__ == "__main__":
    main()
