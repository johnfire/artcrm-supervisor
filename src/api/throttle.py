"""Login throttling + constant-time password comparison (M-4).

Both auth endpoints validate a single shared password, so brute force is the whole
attack surface. This adds a small, dependency-free per-client sliding-window limiter
and a constant-time comparison helper. In-memory is sufficient for this single-tenant
CRM (worst case, each worker process throttles independently).
"""
import hmac
import threading
import time
from collections import defaultdict

from fastapi import HTTPException, Request

_MAX_FAILURES = 5          # allowed failures within the window before lockout
_WINDOW_SECONDS = 300      # sliding window / lockout duration

_lock = threading.Lock()
_failures: dict[str, list[float]] = defaultdict(list)


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _prune(key: str, now: float) -> None:
    cutoff = now - _WINDOW_SECONDS
    kept = [stamp for stamp in _failures[key] if stamp > cutoff]
    if kept:
        _failures[key] = kept
    else:
        _failures.pop(key, None)


def enforce_rate_limit(request: Request) -> str:
    """Raise 429 if the client has too many recent failed attempts. Returns the key."""
    key = _client_key(request)
    now = time.monotonic()
    with _lock:
        _prune(key, now)
        attempts = _failures.get(key, [])
        if len(attempts) >= _MAX_FAILURES:
            retry_after = max(1, int(_WINDOW_SECONDS - (now - attempts[0])))
            raise HTTPException(
                status_code=429,
                detail="Too many failed attempts. Try again later.",
                headers={"Retry-After": str(retry_after)},
            )
    return key


def record_failure(key: str) -> None:
    now = time.monotonic()
    with _lock:
        _failures[key].append(now)
        _prune(key, now)


def record_success(key: str) -> None:
    with _lock:
        _failures.pop(key, None)


def passwords_match(supplied: str, expected: str) -> bool:
    """Constant-time comparison; always False when no password is configured."""
    if not expected:
        return False
    return hmac.compare_digest(supplied, expected)
