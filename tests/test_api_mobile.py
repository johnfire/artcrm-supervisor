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
