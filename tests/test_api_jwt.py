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
