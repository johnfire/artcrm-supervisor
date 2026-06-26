"""Tests for the full-CRUD mobile API endpoints (contacts / approvals / marketing).

Focus: the authz gates (spectator is read-only → 403 on every mutation) and the
approve-now-actually-sends fix. DB access is mocked, matching test_api_mobile.py.
"""
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def _admin_token() -> str:
    with patch.dict("os.environ", {"ADMIN_PASSWORD": "testpass"}):
        return client.post("/api/auth/token", json={"password": "testpass"}).json()["token"]


def _spectator_token() -> str:
    with patch.dict("os.environ", {"SPECTATOR_PASSWORD": "specpass"}):
        return client.post("/api/auth/token", json={"password": "specpass"}).json()["token"]


def _mock_db(fetchone=None, fetchall=None, rowcount=1) -> MagicMock:
    conn = MagicMock()
    conn.__enter__ = lambda s: s
    conn.__exit__ = MagicMock(return_value=False)
    cur = conn.cursor.return_value
    cur.fetchone.return_value = fetchone
    cur.fetchall.return_value = fetchall or []
    cur.rowcount = rowcount
    return conn


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── authz: spectator (read-only) must be blocked from every mutation ──────────

def test_spectator_cannot_create_contact():
    resp = client.post("/api/contacts", json={"name": "X", "city": "Y"}, headers=_auth(_spectator_token()))
    assert resp.status_code == 403


def test_spectator_cannot_update_contact():
    resp = client.put("/api/contacts/1", json={"status": "cold"}, headers=_auth(_spectator_token()))
    assert resp.status_code == 403


def test_spectator_cannot_delete_contact():
    resp = client.delete("/api/contacts/1", headers=_auth(_spectator_token()))
    assert resp.status_code == 403


def test_spectator_cannot_log_interaction():
    resp = client.post("/api/contacts/1/interactions", json={"method": "visit"}, headers=_auth(_spectator_token()))
    assert resp.status_code == 403


def test_spectator_cannot_approve():
    resp = client.post("/api/approvals/1/approve", headers=_auth(_spectator_token()))
    assert resp.status_code == 403


def test_spectator_cannot_delete_approval():
    resp = client.delete("/api/approvals/1", headers=_auth(_spectator_token()))
    assert resp.status_code == 403


def test_spectator_cannot_add_observation():
    resp = client.post("/api/marketing/observations", json={"content": "x"}, headers=_auth(_spectator_token()))
    assert resp.status_code == 403


def test_mutations_require_auth():
    assert client.post("/api/contacts", json={"name": "X", "city": "Y"}).status_code in (401, 403)
    assert client.delete("/api/contacts/1").status_code in (401, 403)
    assert client.put("/api/marketing/strategy/1", json={"content": "x"}).status_code in (401, 403)


# ── contacts CRUD behavior ───────────────────────────────────────────────────

def test_create_contact_requires_name_and_city():
    resp = client.post("/api/contacts", json={"name": " ", "city": ""}, headers=_auth(_admin_token()))
    assert resp.status_code == 422


def test_create_contact_rejects_bad_status():
    resp = client.post(
        "/api/contacts",
        json={"name": "Galerie", "city": "Munich", "status": "bogus"},
        headers=_auth(_admin_token()),
    )
    assert resp.status_code == 422


def test_create_contact_success():
    with patch("src.tools.db.save_contact", return_value=77) as save:
        resp = client.post(
            "/api/contacts",
            json={"name": "Galerie Nord", "city": "Munich", "type": "gallery"},
            headers=_auth(_admin_token()),
        )
    assert resp.status_code == 201
    assert resp.json() == {"id": 77}
    save.assert_called_once()


def test_update_contact_no_fields_is_422():
    resp = client.put("/api/contacts/1", json={}, headers=_auth(_admin_token()))
    assert resp.status_code == 422


def test_update_contact_success():
    with patch("src.api.routers.api_contacts.db", return_value=_mock_db(rowcount=1)):
        resp = client.put("/api/contacts/1", json={"status": "cold", "notes": "hi"}, headers=_auth(_admin_token()))
    assert resp.status_code == 204


def test_update_contact_missing_is_404():
    with patch("src.api.routers.api_contacts.db", return_value=_mock_db(rowcount=0)):
        resp = client.put("/api/contacts/999", json={"city": "Berlin"}, headers=_auth(_admin_token()))
    assert resp.status_code == 404


def test_log_interaction_rejects_bad_method():
    resp = client.post("/api/contacts/1/interactions", json={"method": "telepathy"}, headers=_auth(_admin_token()))
    assert resp.status_code == 422


def test_log_interaction_success():
    with patch("src.api.routers.api_contacts.db", return_value=_mock_db(fetchone={"?column?": 1})), \
         patch("src.tools.db.log_interaction") as logger_fn:
        resp = client.post(
            "/api/contacts/1/interactions",
            json={"method": "visit", "summary": "dropped off portfolio", "outcome": "warm"},
            headers=_auth(_admin_token()),
        )
    assert resp.status_code == 201
    logger_fn.assert_called_once()


# ── approvals: approve must actually send (the fixed bug) ─────────────────────

def test_approve_sends_email():
    draft = {"draft_subject": "Hallo", "draft_body": "...", "contact_id": 5, "email": "v@gallery.de"}
    with patch("src.api.routers.api_approvals.db", return_value=_mock_db(fetchone=draft)), \
         patch("src.api.routers.api_approvals.send_and_log", return_value=(True, "sent")) as sender:
        resp = client.post("/api/approvals/1/approve", headers=_auth(_admin_token()))
    assert resp.status_code == 200
    assert resp.json()["sent"] is True
    sender.assert_called_once()


def test_edit_and_send_sends_email():
    draft = {"draft_subject": "old", "draft_body": "old", "contact_id": 5, "email": "v@gallery.de"}
    with patch("src.api.routers.api_approvals.db", return_value=_mock_db(fetchone=draft)), \
         patch("src.api.routers.api_approvals.send_and_log", return_value=(True, "sent")) as sender:
        resp = client.post(
            "/api/approvals/1/edit",
            json={"subject": "new", "body": "new body"},
            headers=_auth(_admin_token()),
        )
    assert resp.status_code == 200
    sender.assert_called_once()
    # the edited subject/body are what get sent
    _, kwargs = sender.call_args
    assert kwargs["subject"] == "new" and kwargs["body"] == "new body"


def test_approve_missing_is_404():
    with patch("src.api.routers.api_approvals.db", return_value=_mock_db(fetchone=None)):
        resp = client.post("/api/approvals/999/approve", headers=_auth(_admin_token()))
    assert resp.status_code == 404


def test_approvals_list_rejects_bad_status():
    resp = client.get("/api/approvals?status=bogus", headers=_auth(_admin_token()))
    assert resp.status_code == 422


# ── marketing ────────────────────────────────────────────────────────────────

def test_add_observation_requires_content():
    resp = client.post("/api/marketing/observations", json={"content": "   "}, headers=_auth(_admin_token()))
    assert resp.status_code == 422


def test_add_observation_success():
    with patch("src.api.routers.api_marketing.capture_thought") as capture:
        resp = client.post(
            "/api/marketing/observations",
            json={"content": "Gallery X is hiring a curator"},
            headers=_auth(_admin_token()),
        )
    assert resp.status_code == 201
    capture.assert_called_once()
