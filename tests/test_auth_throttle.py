"""M-4 regression: login throttling + constant-time comparison."""
import pytest

from src.api import throttle


@pytest.fixture(autouse=True)
def _clean_throttle_state():
    throttle._failures.clear()
    yield
    throttle._failures.clear()


class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    def __init__(self, host="1.2.3.4"):
        self.client = _FakeClient(host)


def test_lockout_after_max_failures():
    req = _FakeRequest()
    key = throttle.enforce_rate_limit(req)          # first attempt allowed
    for _ in range(throttle._MAX_FAILURES):
        throttle.record_failure(key)
    with pytest.raises(throttle.HTTPException) as exc:
        throttle.enforce_rate_limit(req)
    assert exc.value.status_code == 429
    assert "Retry-After" in exc.value.headers


def test_success_clears_failures():
    req = _FakeRequest("5.6.7.8")
    key = throttle.enforce_rate_limit(req)
    for _ in range(throttle._MAX_FAILURES):
        throttle.record_failure(key)
    throttle.record_success(key)
    # Cleared — no lockout on the next attempt.
    assert throttle.enforce_rate_limit(req) == key


def test_passwords_match_constant_time_and_empty():
    assert throttle.passwords_match("secret", "secret") is True
    assert throttle.passwords_match("secret", "nope") is False
    # Never authenticate against an unset (empty) password.
    assert throttle.passwords_match("", "") is False
    assert throttle.passwords_match("anything", "") is False


def test_failures_are_per_client():
    req_a = _FakeRequest("10.0.0.1")
    req_b = _FakeRequest("10.0.0.2")
    key_a = throttle.enforce_rate_limit(req_a)
    for _ in range(throttle._MAX_FAILURES):
        throttle.record_failure(key_a)
    # Client A is locked, client B is unaffected.
    with pytest.raises(throttle.HTTPException):
        throttle.enforce_rate_limit(req_a)
    assert throttle.enforce_rate_limit(req_b) == "10.0.0.2"
