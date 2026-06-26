import os
import threading
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
import psycopg2.pool

from src.config import DATABASE_URL

# Connection pool (anti-fragility): previously every request opened a fresh
# psycopg2 connection, so under DB pressure or a connection-limit hit ALL requests
# failed together with no backpressure. A bounded pool reuses connections and caps
# concurrency. The pool is created lazily on first use (not at import) so a missing
# DB doesn't break module import / health checks.
_POOL_MIN = int(os.getenv("DB_POOL_MIN", "1"))
_POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))

_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = psycopg2.pool.ThreadedConnectionPool(
                    _POOL_MIN, _POOL_MAX, dsn=DATABASE_URL,
                    cursor_factory=psycopg2.extras.RealDictCursor,
                )
    return _pool


def get_connection():
    """Borrow a pooled connection. Prefer the db() context manager, which returns it."""
    return _get_pool().getconn()


@contextmanager
def db():
    """Context manager for a pooled connection with auto-commit on success.

    The connection is returned to the pool on exit. If it broke mid-request it is
    discarded (closed) instead of poisoning the pool.
    """
    pool = _get_pool()
    conn = pool.getconn()
    broken = False
    try:
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            broken = True
        raise
    finally:
        pool.putconn(conn, close=broken or conn.closed != 0)
