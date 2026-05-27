# ArtCRM Supervisor — VPS Deployment Plan

**Date:** 2026-05-27
**Status:** draft — not yet implemented

## Goal

Deploy artcrm-supervisor to the VPS (82.165.32.162) so the full pipeline can be triggered and monitored from anywhere — phone, tablet, or any browser. Also serve a spectator login as a live marketing demo of the system.

---

## User Roles

### Admin (Christopher)

- Trigger research scans (city + level)
- Run the full pipeline (enrich → scout → outreach → followup)
- Review and approve/reject email drafts
- View all contacts, activity log, city registry
- Full write access

### Spectator (public demo login)

- Read-only access to contacts, activity log, approval queue, city registry
- Can see the system working in real time
- Cannot trigger anything
- Marketing tool — show potential users/clients how the system works

---

## Architecture Changes for VPS

### What stays the same

- FastAPI web UI (already exists)
- LangGraph agents and supervisor graph
- PostgreSQL database
- All pipeline logic

### What changes

**Email:** Replace Proton Bridge (desktop app, local only) with a VPS mail server (Postfix + Dovecot). SMTP for sending, IMAP for reading replies. The email tool in `src/tools/email.py` just needs new host/port env vars — no code changes beyond that.

**Process management:** Pipeline runs are long-running Python processes. On VPS these need to be managed — options are `systemd` services or running inside Docker with a task queue. Simplest first approach: trigger via the web UI, run as a background subprocess, stream logs to the activity table.

**Auth:** Add a proper login system to the FastAPI UI. Two accounts: admin and spectator. Session-based (cookie) or JWT. The spectator role gets read-only route protection.

**Deployment:** Docker Compose alongside the existing stacks (notes-world, art-platform). Same VPS, different port/subdomain.

---

## Email Server Plan

Install Postfix (SMTP) + Dovecot (IMAP) on the VPS.

DNS records needed on christopherrehm.de (or whichever domain):

- **MX record** — points to the VPS IP
- **SPF record** — TXT record listing the VPS IP as authorised sender
- **DKIM** — public key TXT record (private key lives on VPS, signs outgoing mail)
- **DMARC** — TXT record defining policy for failed checks

Once set up, update `.env` on VPS:

```
PROTON_SMTP_HOST=127.0.0.1   →   SMTP_HOST=localhost
PROTON_SMTP_PORT=1025        →   SMTP_PORT=587
PROTON_IMAP_HOST=127.0.0.1   →   IMAP_HOST=localhost
PROTON_IMAP_PORT=1143        →   IMAP_PORT=993
```

---

## Subdomain

Suggest: `crm.christopherrehm.de` — consistent with the existing pattern.

Apache on VPS proxies to the FastAPI container. Certbot handles SSL (same as other apps).

---

## Open Questions

1. Which domain for outgoing email — `christopher.rehm.63@protonmail.com` (personal) or `contact@christopherrehm.de` (domain email via new mail server)?
2. Spectator login — shared single password, or invite-based accounts?
3. Should the spectator view show real contact data (names, emails) or anonymised data?

---

## Implementation Order

1. Set up VPS mail server (Postfix + Dovecot + DNS records)
2. Add auth (admin + spectator) to FastAPI UI
3. Add pipeline trigger endpoints to UI (city scan form, run pipeline button)
4. Dockerise and deploy to VPS under `crm.christopherrehm.de`
5. Test full pipeline end-to-end from mobile browser
