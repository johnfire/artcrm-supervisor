import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
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


def _get_token(password="testpass") -> str:
    with patch.dict("os.environ", {"ADMIN_PASSWORD": password}):
        resp = client.post("/api/auth/token", json={"password": password})
    return resp.json()["token"]


def test_push_register_requires_auth():
    resp = client.post("/api/push/register", json={"token": "ExponentPushToken[abc]"})
    assert resp.status_code in (401, 403)


def test_approvals_list_requires_auth():
    resp = client.get("/api/approvals")
    assert resp.status_code in (401, 403)


def test_approvals_list_returns_list():
    token = _get_token()
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.fetchall.return_value = []
    with patch("src.api.routers.api_approvals.db", return_value=mock_conn):
        resp = client.get("/api/approvals", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_push_register_success():
    token = _get_token()
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    with patch("src.api.routers.api_push.db", return_value=mock_conn):
        resp = client.post(
            "/api/push/register",
            json={"token": "ExponentPushToken[testtoken123]"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 204


def test_inbox_list_requires_auth():
    resp = client.get("/api/inbox")
    assert resp.status_code in (401, 403)


def test_inbox_list_returns_list():
    token = _get_token()
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.fetchall.return_value = []
    with patch("src.api.routers.api_inbox.db", return_value=mock_conn):
        resp = client.get("/api/inbox", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_contacts_list_requires_auth():
    resp = client.get("/api/contacts")
    assert resp.status_code in (401, 403)


def test_contacts_list_returns_list():
    token = _get_token()
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.fetchall.return_value = []
    with patch("src.api.routers.api_contacts.db", return_value=mock_conn):
        resp = client.get("/api/contacts", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
