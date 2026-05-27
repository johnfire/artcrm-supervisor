# Database

**Last Updated:** 2026-05-26
**Status:** current
**Read when:** schema questions, contact status flow, migrations, adding tables

## Summary

PostgreSQL, `artcrm` database. Shared with `theo-hits-the-road` (the original CRM) — supervisor adds 4 tables on top of the existing schema. Raw SQL migrations in `src/db/migrations/`. No ORM.

## Tables

### From theo-hits-the-road (do not modify)

| Table           | Contents                                                                 |
| --------------- | ------------------------------------------------------------------------ |
| `contacts`      | All venue contacts — name, address, email, website, status, notes, score |
| `interactions`  | Log of all interactions with a contact                                   |
| `shows`         | Art show/exhibition records                                              |
| `lookup_values` | Enum values (statuses, types, etc.)                                      |

### Added by artcrm-supervisor

| Table            | Contents                                                                                 |
| ---------------- | ---------------------------------------------------------------------------------------- |
| `agent_runs`     | Log of every agent execution — agent name, city, level, start/end time, contacts found   |
| `consent_log`    | GDPR consent tracking                                                                    |
| `approval_queue` | Email drafts awaiting review — contact_id, subject, body, status                         |
| `inbox_messages` | Inbox messages read by follow-up agent — message_id, from, subject, body, classification |
| `ignored_chains` | Business names that should never be saved as contacts (chains, franchises)               |

## Contact Status Flow

```
candidate   — found by research agent, not yet scored
    ↓
cold        — scored ≥ threshold by scout, ready for outreach
    ↓
contacted   — first email sent and approved
    ↓
meeting     — positive reply, meeting scheduled (set manually)
    ↓
accepted    — venue agreed to display/sell work

dropped     — scored below threshold or disqualified (reason in notes)
dormant     — opted out or gone quiet for a long time
on_hold     — paused (approve flow also works from this status)
```

## Migrations

Location: `src/db/migrations/` — numbered SQL files (001–004+).

```bash
uv run python scripts/migrate.py
```

Safe to re-run. Does not modify existing tables, only creates missing ones.

## City Registry

Tracks research scan state per city:

- Which scan levels have been run
- Date of last scan per level
- Number of contacts found per level
- Re-run status

Visible in the web UI at `/research/`. Currently covers ~82 cities across Bavaria, Baden-Württemberg, Austria (Tyrol, Vorarlberg, Salzburg), and Switzerland.
