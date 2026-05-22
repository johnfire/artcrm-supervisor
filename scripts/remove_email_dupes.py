"""
Remove email duplicates: groups of active contacts sharing the same email.

Rules (per user):
  1. Keep 'contacted' — highest priority
  2. Keep 'dropped' over cold/candidate/etc.
  3. Same status → keep lowest ID

Flags groups where names differ significantly (< 70% avg similarity)
as REVIEW — these are skipped in automatic mode since they may be
genuinely different businesses sharing one email address.

Usage:
  uv run python3 scripts/remove_email_dupes.py           # dry run (all groups)
  uv run python3 scripts/remove_email_dupes.py --execute  # apply changes
"""
import argparse
import difflib
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations

import psycopg2
import psycopg2.extras

DB_URL = "postgresql://artcrm_admindude:aw4e0rfeA1!Q@localhost:5432/artcrm"
NAME_SIMILARITY_THRESHOLD = 0.70  # groups below this are flagged REVIEW

STATUS_RANK = {
    "contacted":      4,
    "accepted":       4,
    "dropped":        3,
    "not_interested": 3,
    "do_not_contact": 3,
    "on_hold":        2,
    "dormant":        2,
    "lead_unverified": 1,
    "cold":           1,
    "candidate":      1,
}


def normalize(name: str) -> str:
    return name.lower().strip()


def avg_name_similarity(contacts: list[dict]) -> float:
    if len(contacts) < 2:
        return 1.0
    names = [normalize(c["name"]) for c in contacts]
    ratios = [
        difflib.SequenceMatcher(None, a, b).ratio()
        for a, b in combinations(names, 2)
    ]
    return sum(ratios) / len(ratios)


def pick_winner(contacts: list[dict]) -> tuple[dict, list[dict]]:
    def sort_key(c):
        return (-STATUS_RANK.get(c["status"] or "", 0), c["id"])
    ranked = sorted(contacts, key=sort_key)
    return ranked[0], ranked[1:]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    dry_run = not args.execute

    if dry_run:
        print("DRY RUN — pass --execute to apply.\n")

    conn = psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, city, status, email FROM contacts "
        "WHERE deleted_at IS NULL AND email IS NOT NULL AND email != '' ORDER BY id"
    )
    contacts = list(cur.fetchall())

    groups: dict[str, list[dict]] = defaultdict(list)
    for c in contacts:
        groups[c["email"].lower().strip()].append(c)

    dupe_groups = {e: g for e, g in groups.items() if len(g) > 1}
    print(f"Found {len(dupe_groups)} email groups with 2+ active contacts.\n")

    auto_groups = {}
    review_groups = {}
    for email, grp in sorted(dupe_groups.items()):
        sim = avg_name_similarity(grp)
        if sim >= NAME_SIMILARITY_THRESHOLD:
            auto_groups[email] = grp
        else:
            review_groups[email] = grp

    deletes: list[int] = []

    print(f"{'='*80}")
    print(f"  AUTO — will process ({len(auto_groups)} groups)")
    print(f"{'='*80}\n")
    for email, grp in sorted(auto_groups.items()):
        winner, losers = pick_winner(grp)
        print(f"  EMAIL: {email}")
        print(f"    KEEP   id={winner['id']:>5}  status={winner['status']:<15}  city={winner['city'] or '':<25}  {winner['name']}")
        for loser in losers:
            print(f"    DELETE id={loser['id']:>5}  status={loser['status']:<15}  city={loser['city'] or '':<25}  {loser['name']}")
        deletes.extend(l["id"] for l in losers)
        print()

    print(f"\n{'='*80}")
    print(f"  REVIEW — names too different, skipped ({len(review_groups)} groups)")
    print(f"{'='*80}\n")
    for email, grp in sorted(review_groups.items()):
        sim = avg_name_similarity(grp)
        print(f"  EMAIL: {email}  (name similarity: {sim:.0%})")
        for c in grp:
            print(f"    id={c['id']:>5}  status={c['status']:<15}  city={c['city'] or '':<25}  {c['name']}")
        print()

    print(f"\nPlan: {len(deletes)} soft-delete(s) across {len(auto_groups)} group(s). {len(review_groups)} group(s) need manual review.")

    if dry_run:
        print("\nRe-run with --execute to apply.")
        conn.close()
        return

    now = datetime.now(timezone.utc)
    for contact_id in deletes:
        cur.execute(
            "UPDATE contacts SET deleted_at = %s, updated_at = %s WHERE id = %s",
            (now, now, contact_id),
        )
        print(f"  Soft-deleted id={contact_id}")

    conn.commit()
    conn.close()
    print(f"\nDone — {len(deletes)} soft-delete(s) applied.")


if __name__ == "__main__":
    main()
