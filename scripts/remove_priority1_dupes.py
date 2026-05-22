"""
Remove Priority 1 duplicates: same name (>=90% similar), same city.

Rules:
  - Prefer 'contacted' status when choosing which entry to keep.
  - If winner is 'contacted' and a loser has 'dropped'/'not_interested',
    update winner's status to that negative value before soft-deleting the loser.
  - Ties (same status or neither contacted): keep the lowest ID.
  - Soft-delete losers (sets deleted_at = now()).
  - Builds connected components so 3-way+ duplicates are handled as a group.

Usage:
  uv run python3 scripts/remove_priority1_dupes.py          # dry run
  uv run python3 scripts/remove_priority1_dupes.py --execute
"""
import argparse
import difflib
import sys
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

DB_URL = "postgresql://artcrm_admindude:aw4e0rfeA1!Q@localhost:5432/artcrm"
THRESHOLD = 0.90
NEGATIVE_STATUSES = {"dropped", "not_interested"}

STATUS_RANK = {
    "contacted":        5,
    "accepted":         5,
    "on_hold":          4,
    "lead_unverified":  3,
    "cold":             3,
    "candidate":        3,
    "dropped":          2,
    "not_interested":   2,
    "dormant":          1,
}


def normalize(name: str) -> str:
    return name.lower().strip()


def union_find_groups(pairs: list[tuple]) -> list[list]:
    """Build connected components from (id_a, id_b) pairs using union-find."""
    parent: dict[int, int] = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    for a, b in pairs:
        union(a, b)

    groups: dict[int, list[int]] = {}
    for node in parent:
        root = find(node)
        groups.setdefault(root, []).append(node)

    return list(groups.values())


def pick_winner(group_contacts: list[dict]) -> tuple[dict, list[dict]]:
    """Return (winner, losers). Winner = highest status rank, lowest ID on tie."""
    def sort_key(c):
        rank = STATUS_RANK.get(c["status"] or "", 0)
        return (-rank, c["id"])

    sorted_contacts = sorted(group_contacts, key=sort_key)
    return sorted_contacts[0], sorted_contacts[1:]


def status_override(winner: dict, losers: list[dict]) -> str | None:
    """If winner is 'contacted' and any loser is negative, return that status."""
    if (winner["status"] or "") == "contacted":
        for loser in losers:
            if (loser["status"] or "") in NEGATIVE_STATUSES:
                return loser["status"]
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Apply changes (default: dry run)")
    args = parser.parse_args()
    dry_run = not args.execute

    if dry_run:
        print("DRY RUN — no changes will be made. Pass --execute to apply.\n")

    conn = psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, city, country, status, email FROM contacts WHERE deleted_at IS NULL ORDER BY name"
    )
    contacts = list(cur.fetchall())
    contact_by_id = {c["id"]: c for c in contacts}

    # Find all same-city pairs at >= 90% name similarity
    same_city_pairs: list[tuple[int, int]] = []
    n = len(contacts)
    for i in range(n):
        a = contacts[i]
        na = normalize(a["name"])
        city_a = (a["city"] or "").lower().strip()
        for j in range(i + 1, n):
            b = contacts[j]
            nb = normalize(b["name"])
            city_b = (b["city"] or "").lower().strip()
            if not city_a or not city_b or city_a != city_b:
                continue
            sm = difflib.SequenceMatcher(None, na, nb)
            if sm.quick_ratio() >= THRESHOLD and sm.ratio() >= THRESHOLD:
                same_city_pairs.append((a["id"], b["id"]))

    groups = union_find_groups(same_city_pairs)
    groups = [g for g in groups if len(g) > 1]

    print(f"Found {len(groups)} duplicate group(s) (Priority 1 — same city):\n")

    updates: list[tuple[int, str]] = []     # (id, new_status)
    deletes: list[int] = []                 # ids to soft-delete

    for group_ids in sorted(groups):
        group_contacts = [contact_by_id[gid] for gid in group_ids]
        winner, losers = pick_winner(group_contacts)
        override = status_override(winner, losers)

        print(f"  GROUP — {winner['name']} / {winner['city']}")
        print(f"    KEEP   id={winner['id']:>5}  status={winner['status']:<15}  email={winner['email'] or ''}")
        for loser in losers:
            print(f"    DELETE id={loser['id']:>5}  status={loser['status']:<15}  email={loser['email'] or ''}")
        if override:
            print(f"    STATUS UPDATE: {winner['status']} → {override}  (loser was '{override}')")
            updates.append((winner["id"], override))
        deletes.extend(l["id"] for l in losers)
        print()

    print(f"Plan: {len(updates)} status update(s), {len(deletes)} soft-delete(s)")

    if dry_run:
        print("\nRe-run with --execute to apply.")
        conn.close()
        return

    # Execute
    now = datetime.now(timezone.utc)
    for contact_id, new_status in updates:
        cur.execute(
            "UPDATE contacts SET status = %s, updated_at = %s WHERE id = %s",
            (new_status, now, contact_id),
        )
        print(f"  Updated id={contact_id} status → {new_status}")

    for contact_id in deletes:
        cur.execute(
            "UPDATE contacts SET deleted_at = %s, updated_at = %s WHERE id = %s",
            (now, now, contact_id),
        )
        print(f"  Soft-deleted id={contact_id}")

    conn.commit()
    conn.close()
    print(f"\nDone — {len(updates)} update(s), {len(deletes)} soft-delete(s) applied.")


if __name__ == "__main__":
    main()
