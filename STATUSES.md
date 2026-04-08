# Contact Statuses

## Pipeline Statuses (automated flow)

| Status      | Description                                                                            |
| ----------- | -------------------------------------------------------------------------------------- |
| `candidate` | Freshly discovered by the research agent. Not yet evaluated — no scoring, no outreach. |
| `cold`      | Scored by the scout agent as a good fit. Ready for first-contact outreach.             |
| `contacted` | First outreach email has been sent. Waiting for a response.                            |

## Positive Progression

| Status             | Description                                                                                                |
| ------------------ | ---------------------------------------------------------------------------------------------------------- |
| `meeting`          | A meeting has been arranged or confirmed.                                                                  |
| `accepted`         | Contact has agreed to display or purchase work. Active relationship.                                       |
| `networking_visit` | Responded positively but no current exhibition opportunity. Flagged to revisit in person at a future date. |

## Inactive / Stalled

| Status    | Description                                                                                                     |
| --------- | --------------------------------------------------------------------------------------------------------------- |
| `dormant` | Was active at some point but has gone quiet. No interaction within the dormancy threshold (default: 12 months). |
| `on_hold` | Manually parked — not ready to proceed but not dropped. Revisit later.                                          |
| `maybe`   | Ambiguous fit or unclear response. Needs manual review before deciding next step.                               |

## Dead Ends

| Status           | Description                                                                                           |
| ---------------- | ----------------------------------------------------------------------------------------------------- |
| `dropped`        | Decided not to pursue — wrong fit, no response after multiple attempts, or venue closed.              |
| `do_not_contact` | Opted out or explicitly asked not to be contacted. Blocked from all outreach by the compliance check. |
| `closed`         | Relationship ended after a completed engagement.                                                      |

## Data Quality

| Status            | Description                                                                                                                                                                           |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `lead_unverified` | Imported or auto-discovered but not yet validated — website, name, or contact details may be incomplete or wrong. Needs enrichment or manual check before entering the main pipeline. |

---

## Flow

```
candidate → (scout scores) → cold → (outreach sent) → contacted
                                                           ↓
                                        meeting → accepted / networking_visit
                                                           ↓
                                        dormant / on_hold / dropped / do_not_contact
```
