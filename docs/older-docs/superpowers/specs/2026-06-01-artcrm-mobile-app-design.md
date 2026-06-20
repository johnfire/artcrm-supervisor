# ArtCRM Mobile App — Design Spec

**Date:** 2026-06-01
**Status:** Approved

---

## Overview

A React Native mobile app (Android-first) that mirrors the ArtCRM web UI, connecting to the existing FastAPI backend on the VPS. The app is a thin client — all business logic stays on the server. Primary value: approve email drafts, monitor inbox replies, and trigger scans from anywhere.

---

## Tech Stack

| Concern            | Choice                                     |
| ------------------ | ------------------------------------------ |
| Framework          | React Native via Expo (managed workflow)   |
| Build              | EAS Build — produces APK/AAB in the cloud  |
| Navigation         | React Navigation — Drawer navigator        |
| Auth               | JWT tokens stored in Expo SecureStore      |
| Push notifications | Expo Notifications (via Expo Push Service) |
| API client         | Axios with JWT bearer header               |
| Repo               | New standalone repo: `artcrm-mobile`       |

---

## Connectivity

- App connects to `https://crm.christopherrehm.de` over the public internet
- SSL cert required on VPS (certbot, already planned)
- No VPN required
- Auth: JWT token obtained at login (24h expiry). On expiry, app redirects to login screen — no silent refresh in v1.

---

## Navigation

Side drawer (hamburger menu, slides in from left) with 6 sections:

1. Approvals
2. Inbox
3. Contacts
4. Activity
5. Marketing
6. Research

---

## Screens

### 1. Login

- Email + password fields
- Calls `POST /api/auth/token` → receives JWT
- Token stored in SecureStore
- No biometric auth in v1

### 2. Approvals

- List of pending email drafts
- Each card shows: venue name, city, email subject, first line of body
- Actions per card: **Approve**, **Reject**, **Edit** (opens full draft body in an editable text area with a Save button; saves updated draft back to server)
- No delete button (destructive — use web UI)
- **Reject flow:** tapping Reject opens a bottom sheet with an optional free-text reason field and a Confirm Reject button. Reason is saved to contact notes.
- Tapping a card body opens the full draft text
- Badge on drawer item shows pending count
- Push notification fired when new approval arrives

### 3. Inbox

- List of inbound emails, colour-coded by classification:
  - Green: interested
  - Grey: unclassified
  - Red: not interested / opt-out
- Tap to read full message
- Tap **Classify** → bottom sheet with classification options
- Push notification fired when new inbox reply arrives

### 4. Contacts

- Searchable, filterable list (search by name/city/type)
- Filter chips: All, Cold, Contacted, Meeting, Proposal, Accepted, Rejected, Dropped
- Each row: venue name, city, type, fit score badge (colour-coded: green ≥80, yellow 60–79, grey <60)
- Tap → Contact Detail screen showing: all fields, notes, status history, emails sent/received

### 5. Activity

- Chronological list of agent runs
- Each item: agent name, status (running / completed / failed), started time, summary
- Status colour-coded: yellow=running, green=completed, red=failed
- Pull-to-refresh

### 6. Marketing

- Tabbed view: Observations | Strategies | Digests
- Read-only in v1 — no editing on mobile

### 7. Research / Scans

- City text input
- Level selector (1–5, tap to select)
- Country selector (DE default, AT available)
- **Run Scan** button → calls `POST /api/research/run`
- Result appears in Activity feed; push notification on completion

---

## Backend Additions (artcrm-supervisor)

The existing web routes and templates are untouched. New additions:

### Auth

- `POST /api/auth/token` — accepts email+password, returns JWT (24h expiry)
- JWT middleware for all `/api/*` routes

### Push Notifications

- `POST /api/push/register` — saves Expo push token to DB (new `push_tokens` table)
- Push fired on: new approval pending, new inbox message, research scan complete
- Uses Expo Push API (HTTP call from Python, no Firebase setup needed)

### JSON API routes (mirrors existing web data)

- `GET /api/approvals` — pending drafts list
- `POST /api/approvals/{id}/approve`
- `POST /api/approvals/{id}/reject` — body: `{ reason?: string }`
- `GET /api/inbox`
- `POST /api/inbox/{id}/classify` — body: `{ classification: string }`
- `GET /api/contacts` — supports `?search=&status=&page=`
- `GET /api/contacts/{id}`
- `GET /api/activity`
- `GET /api/marketing/observations`
- `GET /api/marketing/strategies`
- `GET /api/marketing/digests`
- `POST /api/research/run` — body: `{ city: string, level: int, country?: string }`

### SSL

- Certbot cert for `crm.christopherrehm.de` (already in DNS doc, needed before app can connect)
- Nginx reverse proxy in front of uvicorn on port 8084

---

## Push Notifications

- On first launch, app requests notification permission and registers Expo push token via `POST /api/push/register`
- Backend sends push when: approval created, inbox message received, research scan finishes
- Tapping a notification deep-links to the relevant screen

---

## Auth Flow

1. App launches → check SecureStore for JWT
2. If valid → go to Approvals screen
3. If missing/expired → Login screen
4. On login → `POST /api/auth/token` → store token → go to Approvals

---

## Out of Scope (v1)

- iOS build (Expo makes this easy later — same codebase)
- Offline mode
- Editing contacts on mobile
- Delete actions on mobile
- Biometric / Face ID login
- In-app email editing beyond approval edits

---

## Repository

New repo: `artcrm-mobile` (sibling to `artcrm-supervisor`)

Structure:

```
artcrm-mobile/
  app/
    (tabs)/         # drawer screens
    login.tsx
  components/
  services/
    api.ts          # axios client
    auth.ts         # JWT helpers
    notifications.ts
  constants/
  assets/
  app.json          # Expo config
  eas.json          # EAS Build config
```
