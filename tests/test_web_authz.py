"""H-1 regression: spectator (read-only) role must not reach mutating web routes.

The web UI mounts every router behind require_login (admin OR spectator); the fix adds
require_admin to each mutating POST so a spectator can view but not act. These tests
drive the real dependency chain by stubbing get_role to control the session role.
"""
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

import src.api.auth as auth_mod
from src.api.main import app

# https base_url so the now-Secure session middleware path behaves; auth is stubbed below.
client = TestClient(app, base_url="https://testserver")

# Every mutating web POST that must be admin-only.
MUTATING_POSTS = [
    "/approvals/1/approve",
    "/approvals/1/reject",
    "/approvals/1/hold",
    "/approvals/1/delete",
    "/approvals/1/edit",
    "/drafts/1/approve",
    "/drafts/1/reject",
    "/contacts/1/edit",
    "/contacts/1/delete",
    "/contacts/1/unflag",
    "/marketing/observations",
    "/marketing/strategy/1/save",
]


def test_spectator_blocked_from_every_mutation(monkeypatch):
    monkeypatch.setattr(auth_mod, "get_role", lambda request: "spectator")
    for path in MUTATING_POSTS:
        resp = client.post(path, data={}, follow_redirects=False)
        assert resp.status_code == 403, f"spectator should be 403 on {path}, got {resp.status_code}"


def test_unauthenticated_blocked_from_mutation(monkeypatch):
    monkeypatch.setattr(auth_mod, "get_role", lambda request: None)
    resp = client.post("/contacts/1/unflag", data={}, follow_redirects=False)
    # require_login raises a 307 redirect to /login for anonymous users.
    assert resp.status_code in (307, 401, 403)


def test_admin_passes_authz_on_mutation(monkeypatch):
    monkeypatch.setattr(auth_mod, "get_role", lambda request: "admin")
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    with patch("src.api.routers.contacts.db", return_value=mock_conn):
        resp = client.post("/contacts/1/unflag", data={}, follow_redirects=False)
    # Admin clears authz: should redirect (303), never 403.
    assert resp.status_code != 403
    assert resp.status_code == 303
