# ArtCRM — Improvement Ideas

These ideas emerged from reflecting on real-world usage of the system — going out, meeting people,
and thinking about what a full sales pipeline actually feels like in practice.

---

## 1. Capture Friction (after a visit)

The moment right after a real-world interaction is the highest-value moment in the whole pipeline.
If logging it is even slightly annoying, it gets skipped or delayed — and detail is lost.

**Ideas:**

- Mobile-optimized quick-add form: name, venue, one-line impression, next step — done in 30 seconds
- Voice-to-note via phone: speak a quick summary, transcribe and attach to the contact
- Natural language entry: "I visited Galerie X in Lindau, spoke with Maria, she was interested, wants me to follow up in May" — parsed and saved directly to the DB
- Telegram integration: send a message from your phone and it updates the contact record

---

## 2. Pre-Visit Briefing

Before walking into a venue, it would help to have a one-pager:

- Fit score and why
- Previous interactions (what was sent, when, any response)
- City market context for that area
- Any notes you've added
- Their website / social media links

Could be a single URL per contact that renders cleanly on mobile.

---

## 3. Relationship Quality Signals

A CRM tracks events (emails sent, visits logged) but not the soft stuff:

- Was the conversation warm or polite-but-uninterested?
- Did they ask you to come back?
- Did you leave prints behind?
- Gut feeling about fit

These signals live in your head. If there's a low-friction way to capture them
(even just a 1–5 warmth rating + one free-text line), the outreach and follow-up
agents could use them to prioritize and personalize.

---

## 4. What the System Can't Currently See

Gaps in the system's picture of each relationship:

- Face-to-face conversations (content, tone, outcome)
- Physical materials left behind (prints, postcards, portfolio)
- Verbal commitments ("call me in spring", "send me a price list")
- Whether someone recognized your name from a previous email

Bridging these gaps doesn't require anything complex — just a richer notes field
and a habit of logging after each visit.

---

## 5. The 448 No-Email Problem

448 contacts were enriched but no email was found. In practice, visiting these venues
will often yield a business card, a name, or a direct email that no search engine knows.

**Ideas:**

- Manual quick-entry flow: scan a business card or type what you got
- "Visited — got email" button in the UI that opens a focused edit form
- Contact form outreach: for venues with no email but a working website, draft a
  contact-form message instead of email

---

## 6. Pipeline Visibility

As the pipeline grows, it gets harder to answer "what should I do today?"

**Ideas:**

- A daily digest: X contacts ready for outreach, Y follow-ups overdue, Z venues near you worth visiting
- A map view: show all contacts by city/region so you can plan visit routes efficiently
- A "warm contacts" view: everyone in meeting/networking_visit/accepted status in one place

---

## 7. After the Sale / Relationship Maintenance

The system currently focuses on acquiring new contacts. But maintaining active relationships
(accepted, meeting, networking_visit) is equally important.

**Ideas:**

- Periodic check-in reminders for active contacts
- Log artwork placed at each venue (piece name, date, consignment terms)
- Track revenue or interest level per venue over time
- Anniversary or seasonal touchpoints ("it's been 6 months, worth a visit?")

---

## 8. System-Level Improvements

Smaller things that would improve day-to-day use:

- **Bulk status update**: select multiple contacts, change status in one action
- **Duplicate detection**: the research agent sometimes finds the same venue twice
- **Confidence scoring on enriched emails**: flag guessed vs. confirmed emails
- **Search**: full-text search across all contacts and notes in the UI
- **Export**: CSV or PDF of a filtered contact list for offline use or sharing

---

## Priority Thinking

Not everything here is equal. A rough cut:

| Idea                              | Value  | Effort |
| --------------------------------- | ------ | ------ |
| Pre-visit briefing page           | High   | Low    |
| Post-visit quick capture (mobile) | High   | Medium |
| Warmth/gut-feeling rating         | High   | Low    |
| Daily digest / what to do today   | High   | Medium |
| Map view                          | Medium | Medium |
| Business card scan                | Medium | High   |
| Artwork placement tracking        | Medium | Medium |
| Bulk status update                | Medium | Low    |
| Duplicate detection               | Medium | Medium |

---

_Generated 2026-04-08 during a working session on the ArtCRM pipeline._
