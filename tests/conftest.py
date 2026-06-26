"""
Set dummy environment variables before any src.* imports so that
config.py doesn't raise KeyError when DATABASE_URL etc. are absent.
All DB calls in tests are mocked — these values are never used.
"""
import os

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("PROTON_EMAIL", "test@test.com")
os.environ.setdefault("PROTON_PASSWORD", "test")
os.environ.setdefault("DEEPSEEK_API_KEY", "test")
os.environ.setdefault("ANTHROPIC_API_KEY", "test")
# JWT_SECRET / SESSION_SECRET are now required (no insecure default) — supply test
# values long enough (>=32 bytes) to avoid the HS256 short-key warning.
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-long-enough-for-hs256-algorithm")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-long-enough-for-signing")
