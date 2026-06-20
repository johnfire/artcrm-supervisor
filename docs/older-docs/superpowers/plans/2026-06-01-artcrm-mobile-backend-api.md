# ArtCRM Mobile Backend API — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add JWT auth, push notification endpoints, and JSON API routes to artcrm-supervisor so the React Native mobile app can connect.

**Architecture:** New `/api/*` routes sit alongside the existing web routes in the same FastAPI app. JWT auth is added as a separate dependency (`jwt_auth.py`) without touching the existing session-based auth. Push notifications call the Expo Push API via httpx (already in deps).

**Tech Stack:** FastAPI, PyJWT, httpx, psycopg2, Expo Push API

---

## File Map

| Action | Path                                    | Responsibility                                   |
| ------ | --------------------------------------- | ------------------------------------------------ |
| Create | `src/db/migrations/017_push_tokens.sql` | push_tokens table                                |
| Create | `src/api/jwt_auth.py`                   | JWT encode/decode + `require_jwt` dependency     |
| Create | `src/api/push.py`                       | Send push via Expo Push API, load tokens from DB |
| Create | `src/api/routers/api_auth.py`           | `POST /api/auth/token`                           |
| Create | `src/api/routers/api_approvals.py`      | GET list, approve, reject                        |
| Create | `src/api/routers/api_inbox.py`          | GET list, classify                               |
| Create | `src/api/routers/api_contacts.py`       | GET list, GET detail                             |
| Create | `src/api/routers/api_activity.py`       | GET list                                         |
| Create | `src/api/routers/api_marketing.py`      | GET observations, strategies, digests            |
| Create | `src/api/routers/api_research.py`       | POST run (background)                            |
| Create | `src/api/routers/api_push.py`           | POST register push token                         |
| Modify | `pyproject.toml`                        | add PyJWT                                        |
| Modify | `src/config.py`                         | add JWT_SECRET                                   |
| Modify | `src/api/main.py`                       | add CORS, register new routers                   |
| Modify | `src/tools/db.py`                       | call push on new approval queued                 |
| Test   | `tests/test_api_jwt.py`                 | JWT encode/decode unit tests                     |
| Test   | `tests/test_api_mobile.py`              | API route integration tests                      |

---

## Task 1: Add PyJWT dependency

**Files:**

- Modify: `pyproject.toml`

- [ ] **Step 1: Add PyJWT to dependencies**

In `pyproject.toml`, add `"PyJWT>=2.8.0"` to the `dependencies` list:

```toml
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "psycopg2-binary>=2.9.9",
    "python-dotenv>=1.0.0",
    "jinja2>=3.1.4",
    "python-multipart>=0.0.12",
    "httpx>=0.28.0",
    "itsdangerous>=2.2.0",
    "mcp[cli]>=1.0.0",
    "mistune>=3.0.0",
    "PyJWT>=2.8.0",
    ...
]
```

- [ ] **Step 2: Sync deps**

```bash
uv sync
```

Expected: PyJWT installed, no errors.

- [ ] **Step 3: Verify import works**

```bash
uv run python -c "import jwt; print(jwt.__version__)"
```

Expected: version string printed (e.g. `2.8.0`).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add PyJWT dependency for mobile API"
```

---

## Task 2: Add JWT_SECRET to config

**Files:**

- Modify: `src/config.py`

- [ ] **Step 1: Add JWT_SECRET**

In `src/config.py`, add after the `OPEN_BRAIN_TOKEN` line:

```python
# --- Mobile API ---
JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")
```

- [ ] **Step 2: Add to VPS .env**

```bash
ssh chris@82.165.32.162 "openssl rand -hex 32"
```

Copy the output, then:

```bash
ssh chris@82.165.32.162 "echo 'JWT_SECRET=<paste-output-here>' | sudo tee -a /opt/artcrm/artcrm-supervisor/.env"
```

- [ ] **Step 3: Commit**

```bash
git add src/config.py
git commit -m "feat: add JWT_SECRET config for mobile API"
```

---

## Task 3: Create jwt_auth.py

**Files:**

- Create: `src/api/jwt_auth.py`
- Create: `tests/test_api_jwt.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_api_jwt.py`:

```python
import pytest
from src.api.jwt_auth import create_token, decode_token, ALGORITHM
import jwt

SECRET = "test-secret"


def test_create_token_returns_string():
    token = create_token("admin", SECRET)
    assert isinstance(token, str)
    assert len(token) > 20


def test_decode_token_returns_role():
    token = create_token("admin", SECRET)
    role = decode_token(token, SECRET)
    assert role == "admin"


def test_decode_token_spectator():
    token = create_token("spectator", SECRET)
    assert decode_token(token, SECRET) == "spectator"


def test_decode_expired_token_raises():
    from datetime import datetime, timedelta, timezone
    payload = {"sub": "admin", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)}
    expired = jwt.encode(payload, SECRET, algorithm=ALGORITHM)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(expired, SECRET)


def test_decode_invalid_token_raises():
    with pytest.raises(jwt.InvalidTokenError):
        decode_token("not.a.token", SECRET)
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/test_api_jwt.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.api.jwt_auth'`

- [ ] **Step 3: Create jwt_auth.py**

Create `src/api/jwt_auth.py`:

```python
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config import JWT_SECRET

ALGORITHM = "HS256"
TOKEN_EXPIRY_HOURS = 24

_bearer = HTTPBearer()


def create_token(role: str, secret: str = JWT_SECRET) -> str:
    payload = {
        "sub": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRY_HOURS),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_token(token: str, secret: str = JWT_SECRET) -> str:
    payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
    return payload["sub"]


def require_jwt(credentials: HTTPAuthorizationCredentials = Security(_bearer)) -> str:
    try:
        return decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_api_jwt.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/api/jwt_auth.py tests/test_api_jwt.py
git commit -m "feat: add JWT auth helpers for mobile API"
```

---

## Task 4: Add CORS and register API prefix in main.py

**Files:**

- Modify: `src/api/main.py`

- [ ] **Step 1: Add CORS middleware**

In `src/api/main.py`, add after the `SessionMiddleware` line:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
```

- [ ] **Step 2: Verify app still starts**

```bash
uv run python -m src.api.main
```

Expected: `Uvicorn running on http://127.0.0.1:8000` — no errors.

- [ ] **Step 3: Commit**

```bash
git add src/api/main.py
git commit -m "feat: add CORS middleware for mobile API clients"
```

---

## Task 5: Create the auth token endpoint

**Files:**

- Create: `src/api/routers/api_auth.py`
- Create: `tests/test_api_mobile.py` (initial file)

- [ ] **Step 1: Write failing test**

Create `tests/test_api_mobile.py`:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from src.api.main import app

client = TestClient(app)


def test_auth_token_admin_success():
    with patch.dict("os.environ", {"ADMIN_PASSWORD": "testpass"}):
        resp = client.post("/api/auth/token", json={"password": "testpass"})
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["role"] == "admin"


def test_auth_token_wrong_password():
    with patch.dict("os.environ", {"ADMIN_PASSWORD": "testpass"}):
        resp = client.post("/api/auth/token", json={"password": "wrong"})
    assert resp.status_code == 401


def test_auth_token_spectator():
    with patch.dict("os.environ", {"SPECTATOR_PASSWORD": "specpass"}):
        resp = client.post("/api/auth/token", json={"password": "specpass"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "spectator"
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/test_api_mobile.py::test_auth_token_admin_success -v
```

Expected: `404 Not Found` (route doesn't exist yet).

- [ ] **Step 3: Create api_auth.py**

Create `src/api/routers/api_auth.py`:

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os

from src.api.jwt_auth import create_token

router = APIRouter(prefix="/api/auth", tags=["mobile-auth"])

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
SPECTATOR_PASSWORD = os.environ.get("SPECTATOR_PASSWORD", "")


class TokenRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    token: str
    role: str


@router.post("/token", response_model=TokenResponse)
def get_token(body: TokenRequest) -> TokenResponse:
    if ADMIN_PASSWORD and body.password == ADMIN_PASSWORD:
        return TokenResponse(token=create_token("admin"), role="admin")
    if SPECTATOR_PASSWORD and body.password == SPECTATOR_PASSWORD:
        return TokenResponse(token=create_token("spectator"), role="spectator")
    raise HTTPException(status_code=401, detail="Invalid password")
```

- [ ] **Step 4: Register router in main.py**

In `src/api/main.py`, add at the top of the imports block:

```python
from src.api.routers import api_auth
```

And after `app.include_router(auth.router)`:

```python
app.include_router(api_auth.router)
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_api_mobile.py -v
```

Expected: all 3 auth tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/api/routers/api_auth.py src/api/main.py tests/test_api_mobile.py
git commit -m "feat: add JWT token endpoint for mobile auth"
```

---

## Task 6: Push tokens migration and registration endpoint

**Files:**

- Create: `src/db/migrations/017_push_tokens.sql`
- Create: `src/api/routers/api_push.py`

- [ ] **Step 1: Create migration**

Create `src/db/migrations/017_push_tokens.sql`:

```sql
CREATE TABLE IF NOT EXISTS push_tokens (
    id SERIAL PRIMARY KEY,
    token TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

- [ ] **Step 2: Run migration locally**

```bash
uv run python scripts/migrate.py
```

Expected: migration runs, table created, no errors.

- [ ] **Step 3: Create push registration endpoint**

Create `src/api/routers/api_push.py`:

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.jwt_auth import require_jwt
from src.db.connection import db

router = APIRouter(prefix="/api/push", tags=["mobile-push"])


class PushTokenRequest(BaseModel):
    token: str


@router.post("/register", status_code=204)
def register_push_token(body: PushTokenRequest, _role: str = Depends(require_jwt)) -> None:
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO push_tokens (token, updated_at)
            VALUES (%s, NOW())
            ON CONFLICT (token) DO UPDATE SET updated_at = NOW()
            """,
            [body.token],
        )
```

- [ ] **Step 4: Register router in main.py**

Add to imports in `src/api/main.py`:

```python
from src.api.routers import api_auth, api_push
```

Add after `app.include_router(api_auth.router)`:

```python
app.include_router(api_push.router)
```

- [ ] **Step 5: Add test**

In `tests/test_api_mobile.py`, add:

```python
def _get_token(password="testpass") -> str:
    with patch.dict("os.environ", {"ADMIN_PASSWORD": password}):
        resp = client.post("/api/auth/token", json={"password": password})
    return resp.json()["token"]


def test_push_register_requires_auth():
    resp = client.post("/api/push/register", json={"token": "ExponentPushToken[abc]"})
    assert resp.status_code == 403


def test_push_register_success():
    token = _get_token()
    resp = client.post(
        "/api/push/register",
        json={"token": "ExponentPushToken[testtoken123]"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/test_api_mobile.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 7: Run migration on VPS**

```bash
ssh chris@82.165.32.162 "sudo docker exec artcrm-app uv run python scripts/migrate.py"
```

Expected: migration applied, no errors.

- [ ] **Step 8: Commit**

```bash
git add src/db/migrations/017_push_tokens.sql src/api/routers/api_push.py src/api/main.py tests/test_api_mobile.py
git commit -m "feat: add push token registration endpoint"
```

---

## Task 7: Create push notification sender

**Files:**

- Create: `src/api/push.py`

- [ ] **Step 1: Create push.py**

Create `src/api/push.py`:

```python
import logging
import httpx
from src.db.connection import db

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/exponent-push-notification-service/push/send"


def _get_all_tokens() -> list[str]:
    with db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT token FROM push_tokens")
        return [row["token"] for row in cur.fetchall()]


def send_push_to_all(title: str, body: str, data: dict | None = None) -> None:
    tokens = _get_all_tokens()
    if not tokens:
        return
    messages = [
        {"to": t, "title": title, "body": body, **({"data": data} if data else {})}
        for t in tokens
    ]
    try:
        with httpx.Client(timeout=5) as client:
            client.post(EXPO_PUSH_URL, json=messages)
    except Exception as e:
        logger.warning("push notification failed: %s", e)
```

- [ ] **Step 2: Commit**

```bash
git add src/api/push.py
git commit -m "feat: add Expo push notification sender"
```

---

## Task 8: Approvals API route

**Files:**

- Create: `src/api/routers/api_approvals.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_api_mobile.py`:

```python
def test_approvals_list_requires_auth():
    resp = client.get("/api/approvals")
    assert resp.status_code == 403


def test_approvals_list_returns_list():
    token = _get_token()
    resp = client.get("/api/approvals", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_api_mobile.py::test_approvals_list_requires_auth -v
```

Expected: `404 Not Found`

- [ ] **Step 3: Create api_approvals.py**

Create `src/api/routers/api_approvals.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.jwt_auth import require_jwt
from src.db.connection import db

router = APIRouter(prefix="/api/approvals", tags=["mobile-approvals"])


def _fetch_pending(conn) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT aq.id, aq.draft_subject, aq.draft_body, aq.created_at,
               c.id AS contact_id, c.name, c.city, c.email, c.website
        FROM approval_queue aq
        JOIN contacts c ON c.id = aq.contact_id
        WHERE aq.status = 'pending'
        ORDER BY aq.created_at ASC
        """
    )
    rows = []
    for row in cur.fetchall():
        r = dict(row)
        r["created_at"] = r["created_at"].isoformat() if r["created_at"] else None
        rows.append(r)
    return rows


@router.get("")
def list_approvals(_role: str = Depends(require_jwt)) -> list[dict]:
    with db() as conn:
        return _fetch_pending(conn)


class RejectBody(BaseModel):
    reason: str = ""


@router.post("/{approval_id}/approve", status_code=204)
def approve(approval_id: int, role: str = Depends(require_jwt)) -> None:
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE approval_queue SET status='approved', reviewed_at=NOW() WHERE id=%s AND status='pending'",
            [approval_id],
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Approval not found or already reviewed")


@router.post("/{approval_id}/reject", status_code=204)
def reject(approval_id: int, body: RejectBody, role: str = Depends(require_jwt)) -> None:
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE approval_queue
            SET status='rejected', reviewed_at=NOW(), reviewer_note=%s
            WHERE id=%s AND status='pending'
            """,
            [body.reason or None, approval_id],
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Approval not found or already reviewed")
```

- [ ] **Step 4: Register router in main.py**

Add to imports:

```python
from src.api.routers import api_auth, api_push, api_approvals
```

Add after `app.include_router(api_push.router)`:

```python
app.include_router(api_approvals.router)
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_api_mobile.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/api/routers/api_approvals.py src/api/main.py tests/test_api_mobile.py
git commit -m "feat: add mobile approvals API routes"
```

---

## Task 9: Inbox API route

**Files:**

- Create: `src/api/routers/api_inbox.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_api_mobile.py`:

```python
def test_inbox_list_requires_auth():
    resp = client.get("/api/inbox")
    assert resp.status_code == 403


def test_inbox_list_returns_list():
    token = _get_token()
    resp = client.get("/api/inbox", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
```

- [ ] **Step 2: Create api_inbox.py**

Create `src/api/routers/api_inbox.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.jwt_auth import require_jwt
from src.db.connection import db

router = APIRouter(prefix="/api/inbox", tags=["mobile-inbox"])

VALID_CLASSIFICATIONS = {
    "interested", "warm", "not_interested", "opt_out",
    "bounced", "auto_reply", "unclassified",
}


@router.get("")
def list_inbox(_role: str = Depends(require_jwt)) -> list[dict]:
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT i.id, i.from_email, i.subject, i.body,
                   i.received_at, i.classification,
                   c.id AS contact_id, c.name AS contact_name, c.city
            FROM inbox_messages i
            LEFT JOIN contacts c ON c.id = i.matched_contact_id
            WHERE i.processed = TRUE
              AND i.received_at >= NOW() - INTERVAL '30 days'
            ORDER BY i.received_at DESC
            LIMIT 200
            """
        )
        rows = []
        for row in cur.fetchall():
            r = dict(row)
            r["received_at"] = r["received_at"].isoformat() if r["received_at"] else None
            rows.append(r)
        return rows


class ClassifyBody(BaseModel):
    classification: str


@router.post("/{message_id}/classify", status_code=204)
def classify(message_id: int, body: ClassifyBody, role: str = Depends(require_jwt)) -> None:
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    if body.classification not in VALID_CLASSIFICATIONS:
        raise HTTPException(status_code=422, detail=f"Invalid classification. Valid: {VALID_CLASSIFICATIONS}")
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE inbox_messages SET classification=%s WHERE id=%s",
            [body.classification, message_id],
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Message not found")
```

- [ ] **Step 3: Register router, run tests, commit**

In `src/api/main.py` imports:

```python
from src.api.routers import api_auth, api_push, api_approvals, api_inbox
```

Add: `app.include_router(api_inbox.router)`

```bash
uv run pytest tests/test_api_mobile.py -v
git add src/api/routers/api_inbox.py src/api/main.py tests/test_api_mobile.py
git commit -m "feat: add mobile inbox API routes"
```

---

## Task 10: Contacts API route

**Files:**

- Create: `src/api/routers/api_contacts.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_api_mobile.py`:

```python
def test_contacts_list_requires_auth():
    resp = client.get("/api/contacts")
    assert resp.status_code == 403


def test_contacts_list_returns_list():
    token = _get_token()
    resp = client.get("/api/contacts", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
```

- [ ] **Step 2: Create api_contacts.py**

Create `src/api/routers/api_contacts.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.jwt_auth import require_jwt
from src.db.connection import db

router = APIRouter(prefix="/api/contacts", tags=["mobile-contacts"])


def _serialize(row: dict) -> dict:
    r = dict(row)
    for key in ("created_at", "updated_at", "last_contact", "enriched_at"):
        if key in r and r[key] is not None:
            r[key] = r[key].isoformat()
    return r


@router.get("")
def list_contacts(
    search: str = Query(""),
    status: str = Query(""),
    page: int = Query(1, ge=1),
    _role: str = Depends(require_jwt),
) -> list[dict]:
    with db() as conn:
        cur = conn.cursor()
        params: list = []
        where = ["c.deleted_at IS NULL"]
        if search:
            where.append("(c.name ILIKE %s OR c.city ILIKE %s OR c.type ILIKE %s)")
            params += [f"%{search}%", f"%{search}%", f"%{search}%"]
        if status:
            where.append("c.status = %s")
            params.append(status)
        where_clause = " AND ".join(where)
        offset = (page - 1) * 50
        cur.execute(
            f"""
            SELECT c.id, c.name, c.city, c.country, c.type, c.status,
                   c.email, c.website, c.fit_score, c.flagged,
                   MAX(i.interaction_date) AS last_contact
            FROM contacts c
            LEFT JOIN interactions i ON i.contact_id = c.id
            WHERE {where_clause}
            GROUP BY c.id
            ORDER BY c.name ASC
            LIMIT 50 OFFSET %s
            """,
            params + [offset],
        )
        return [_serialize(dict(row)) for row in cur.fetchall()]


@router.get("/{contact_id}")
def get_contact(contact_id: int, _role: str = Depends(require_jwt)) -> dict:
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT c.*, MAX(i.interaction_date) AS last_contact
            FROM contacts c
            LEFT JOIN interactions i ON i.contact_id = c.id
            WHERE c.id = %s AND c.deleted_at IS NULL
            GROUP BY c.id
            """,
            [contact_id],
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Contact not found")
        contact = _serialize(dict(row))

        cur.execute(
            """
            SELECT interaction_type, interaction_date, notes
            FROM interactions
            WHERE contact_id = %s
            ORDER BY interaction_date DESC
            LIMIT 20
            """,
            [contact_id],
        )
        contact["interactions"] = [
            {**dict(r), "interaction_date": r["interaction_date"].isoformat() if r["interaction_date"] else None}
            for r in cur.fetchall()
        ]
        return contact
```

- [ ] **Step 3: Register, test, commit**

Add to `src/api/main.py` imports and registrations:

```python
from src.api.routers import api_auth, api_push, api_approvals, api_inbox, api_contacts
```

Add: `app.include_router(api_contacts.router)`

```bash
uv run pytest tests/test_api_mobile.py -v
git add src/api/routers/api_contacts.py src/api/main.py tests/test_api_mobile.py
git commit -m "feat: add mobile contacts API routes"
```

---

## Task 11: Activity API route

**Files:**

- Create: `src/api/routers/api_activity.py`

- [ ] **Step 1: Create api_activity.py**

Create `src/api/routers/api_activity.py`:

```python
from fastapi import APIRouter, Depends

from src.api.jwt_auth import require_jwt
from src.db.connection import db

router = APIRouter(prefix="/api/activity", tags=["mobile-activity"])


@router.get("")
def list_activity(_role: str = Depends(require_jwt)) -> list[dict]:
    with db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, agent_name, status, summary, started_at, finished_at
            FROM agent_runs
            ORDER BY started_at DESC
            LIMIT 50
            """
        )
        rows = []
        for row in cur.fetchall():
            r = dict(row)
            r["started_at"] = r["started_at"].isoformat() if r["started_at"] else None
            r["finished_at"] = r["finished_at"].isoformat() if r["finished_at"] else None
            rows.append(r)
        return rows
```

- [ ] **Step 2: Register, commit**

Add to `src/api/main.py`:

```python
from src.api.routers import api_auth, api_push, api_approvals, api_inbox, api_contacts, api_activity
```

Add: `app.include_router(api_activity.router)`

```bash
git add src/api/routers/api_activity.py src/api/main.py
git commit -m "feat: add mobile activity API route"
```

---

## Task 12: Marketing API route

**Files:**

- Create: `src/api/routers/api_marketing.py`

- [ ] **Step 1: Create api_marketing.py**

Create `src/api/routers/api_marketing.py`:

```python
from fastapi import APIRouter, Depends

from src.api.jwt_auth import require_jwt
from src.tools.marketing_db import (
    get_recent_research,
    get_all_strategies,
    get_digest_archive,
)

router = APIRouter(prefix="/api/marketing", tags=["mobile-marketing"])


@router.get("/observations")
def observations(_role: str = Depends(require_jwt)) -> list[dict]:
    return get_recent_research(days=60)


@router.get("/strategies")
def strategies(_role: str = Depends(require_jwt)) -> list[dict]:
    return get_all_strategies()


@router.get("/digests")
def digests(_role: str = Depends(require_jwt)) -> list[dict]:
    return get_digest_archive(limit=12)
```

- [ ] **Step 2: Register, commit**

Add to `src/api/main.py`:

```python
from src.api.routers import (
    api_auth, api_push, api_approvals, api_inbox,
    api_contacts, api_activity, api_marketing,
)
```

Add: `app.include_router(api_marketing.router)`

```bash
git add src/api/routers/api_marketing.py src/api/main.py
git commit -m "feat: add mobile marketing API routes"
```

---

## Task 13: Research run API route

**Files:**

- Create: `src/api/routers/api_research.py`

- [ ] **Step 1: Create api_research.py**

Create `src/api/routers/api_research.py`:

```python
import subprocess
import sys
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from src.api.jwt_auth import require_jwt

router = APIRouter(prefix="/api/research", tags=["mobile-research"])


class ResearchRequest(BaseModel):
    city: str
    level: int
    country: str = "DE"


def _run_research(city: str, level: int, country: str) -> None:
    subprocess.Popen(
        [sys.executable, "-m", "src.supervisor.run_research",
         "--city", city, "--level", str(level), "--country", country],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


@router.post("/run", status_code=202)
def run_research(
    body: ResearchRequest,
    background_tasks: BackgroundTasks,
    role: str = Depends(require_jwt),
) -> dict:
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    if body.level not in range(1, 6):
        raise HTTPException(status_code=422, detail="Level must be 1-5")
    background_tasks.add_task(_run_research, body.city, body.level, body.country)
    return {"status": "queued", "city": body.city, "level": body.level}
```

- [ ] **Step 2: Register, commit**

Add to `src/api/main.py`:

```python
from src.api.routers import (
    api_auth, api_push, api_approvals, api_inbox,
    api_contacts, api_activity, api_marketing, api_research,
)
```

Add: `app.include_router(api_research.router)`

```bash
git add src/api/routers/api_research.py src/api/main.py
git commit -m "feat: add mobile research trigger API route"
```

---

## Task 14: Wire push notifications to approval queue

**Files:**

- Modify: `src/tools/db.py`

- [ ] **Step 1: Find the queue_for_approval function**

```bash
grep -n "def queue_for_approval" src/tools/db.py
```

Note the line number. Open the function and find where it successfully inserts.

- [ ] **Step 2: Add push call after successful insert**

Find the `queue_for_approval` function in `src/tools/db.py`. After the `conn.commit()` / successful insert, add:

```python
    try:
        from src.api.push import send_push_to_all
        send_push_to_all(
            title="New approval waiting",
            body=f"{contact_name} — {subject}",
            data={"screen": "approvals"},
        )
    except Exception:
        pass  # push is non-critical
```

Replace `contact_name` and `subject` with the actual variable names used in that function (check the surrounding code).

- [ ] **Step 3: Verify tests still pass**

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add src/tools/db.py
git commit -m "feat: send push notification when approval is queued"
```

---

## Task 15: SSL + Nginx on VPS

- [ ] **Step 1: Install certbot and nginx on VPS**

```bash
ssh chris@82.165.32.162 "sudo apt-get install -y nginx certbot python3-certbot-nginx"
```

- [ ] **Step 2: Create nginx config for crm.christopherrehm.de**

```bash
ssh chris@82.165.32.162 "sudo tee /etc/nginx/sites-available/artcrm <<'EOF'
server {
    listen 80;
    server_name crm.christopherrehm.de;

    location / {
        proxy_pass http://127.0.0.1:8084;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF"
```

- [ ] **Step 3: Enable site and get SSL cert**

```bash
ssh chris@82.165.32.162 "sudo ln -sf /etc/nginx/sites-available/artcrm /etc/nginx/sites-enabled/artcrm && sudo nginx -t && sudo systemctl reload nginx"
ssh chris@82.165.32.162 "sudo certbot --nginx -d crm.christopherrehm.de --non-interactive --agree-tos -m christopher.rehm.63@protonmail.com"
```

Expected: certbot issues cert, nginx reloaded with HTTPS.

- [ ] **Step 4: Verify**

```bash
curl -s https://crm.christopherrehm.de/login | grep -i "artcrm\|login"
```

Expected: HTML containing login page content.

- [ ] **Step 5: Rebuild and redeploy Docker container**

```bash
ssh chris@82.165.32.162 "sudo -u claude git -C /opt/artcrm/artcrm-supervisor pull origin main"
ssh chris@82.165.32.162 "cd /opt/artcrm/artcrm-supervisor && sudo docker compose build --no-cache app && sudo docker compose up -d app"
```

- [ ] **Step 6: Run migration on VPS**

```bash
ssh chris@82.165.32.162 "sudo docker exec artcrm-app uv run python scripts/migrate.py"
```

- [ ] **Step 7: Test the live API**

```bash
curl -s -X POST https://crm.christopherrehm.de/api/auth/token \
  -H "Content-Type: application/json" \
  -d '{"password":"<ADMIN_PASSWORD>"}' | python3 -m json.tool
```

Expected: JSON with `token` and `role`.

---

## Task 16: Final test run and push

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 2: Push to GitHub**

```bash
git push
```

- [ ] **Step 3: Close issue #2 reference**

The backend is now complete. The mobile app plan picks up from here.
