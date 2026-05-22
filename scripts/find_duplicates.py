"""
Find contacts whose names are >= 85% similar to another contact (THRESHOLD = 0.85).
Categorizes pairs to help prioritize review:
  [SAME CITY]  - same name + same city       → almost certainly a true duplicate
  [SAME EMAIL] - same email address           → same business, different city entries
  [DIFF CITY]  - different cities             → could be chain/franchise (legitimate)
"""
import difflib
import psycopg2
import psycopg2.extras

DB_URL = "postgresql://artcrm_admindude:aw4e0rfeA1!Q@localhost:5432/artcrm"
THRESHOLD = 0.85


def normalize(name: str) -> str:
    return name.lower().strip()


def main():
    conn = psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, city, country, status, email FROM contacts WHERE deleted_at IS NULL ORDER BY name"
    )
    contacts = list(cur.fetchall())
    conn.close()

    print(f"Loaded {len(contacts)} contacts\n")

    pairs = []
    n = len(contacts)
    for i in range(n):
        a = contacts[i]
        na = normalize(a["name"])
        for j in range(i + 1, n):
            b = contacts[j]
            nb = normalize(b["name"])
            sm = difflib.SequenceMatcher(None, na, nb)
            if sm.quick_ratio() >= THRESHOLD and sm.ratio() >= THRESHOLD:
                pairs.append((sm.ratio(), a, b))

    if not pairs:
        print("No potential duplicates found at 90% threshold.")
        return

    pairs.sort(key=lambda x: x[0], reverse=True)

    # Categorize
    same_city = []
    same_email = []
    diff_city = []

    for ratio, a, b in pairs:
        city_a = (a["city"] or "").lower().strip()
        city_b = (b["city"] or "").lower().strip()
        email_a = (a["email"] or "").lower().strip()
        email_b = (b["email"] or "").lower().strip()

        if city_a and city_b and city_a == city_b:
            same_city.append((ratio, a, b))
        elif email_a and email_b and email_a == email_b:
            same_email.append((ratio, a, b))
        else:
            diff_city.append((ratio, a, b))

    def print_section(title, section_pairs, tag):
        print(f"\n{'='*80}")
        print(f"  {title}  ({len(section_pairs)} pairs)")
        print(f"{'='*80}")
        if not section_pairs:
            print("  (none)")
            return
        header = f"{'SIM':>5}  {'TAG':<12}  {'ID':>5}  {'NAME':<40}  {'CITY':<22}  {'STATUS':<15}  EMAIL"
        print(header)
        print("-" * 140)
        for ratio, a, b in section_pairs:
            sim_pct = f"{ratio:.0%}"
            for contact in (a, b):
                print(
                    f"{sim_pct:>5}  {tag:<12}  {contact['id']:>5}  "
                    f"{contact['name']:<40}  {contact['city'] or '':<22}  "
                    f"{contact['status'] or '':<15}  {contact['email'] or ''}"
                )
            print()

    print_section("PRIORITY 1 — Same name, same city (true duplicates)", same_city, "[SAME CITY]")
    print_section("PRIORITY 2 — Same name, same email (same biz, wrong city)", same_email, "[SAME EMAIL]")
    print_section("PRIORITY 3 — Same name, different city (possible chain/franchise)", diff_city, "[DIFF CITY]")

    print(f"\n\nSUMMARY")
    print(f"  Total pairs:    {len(pairs)}")
    print(f"  Same city:      {len(same_city)}  ← likely safe to delete one")
    print(f"  Same email:     {len(same_email)}  ← review, probably duplicates")
    print(f"  Different city: {len(diff_city)}  ← review carefully (could be chains)")


if __name__ == "__main__":
    main()
