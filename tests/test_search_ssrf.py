"""H-4 / L-1 regression: SSRF guard for fetch_page and Overpass query escaping."""
import pytest

from src.tools.search import _is_safe_public_url, _build_overpass_query, _escape_overpass


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/",
    "http://127.0.0.1:8000/admin",
    "http://169.254.169.254/latest/meta-data/",   # cloud metadata
    "http://10.0.0.5/",
    "http://192.168.1.1/",
    "http://172.16.0.1/",
    "http://[::1]/",                                # IPv6 loopback
    "http://0.0.0.0/",
    "ftp://example.com/",                           # disallowed scheme
    "file:///etc/passwd",                           # disallowed scheme
    "gopher://8.8.8.8/",                            # disallowed scheme
    "not-a-url",
    "",
])
def test_unsafe_urls_blocked(url):
    assert _is_safe_public_url(url) is False


@pytest.mark.parametrize("url", [
    "http://8.8.8.8/",          # public IPv4 literal — no DNS needed
    "https://1.1.1.1/path",
])
def test_public_urls_allowed(url):
    assert _is_safe_public_url(url) is True


def test_overpass_escaping_neutralizes_quotes():
    assert _escape_overpass('Mün"chen') == 'Mün\\"chen'
    assert _escape_overpass("a\\b") == "a\\\\b"


def test_overpass_query_no_raw_quote_injection():
    # A city name with an embedded quote must not produce an unescaped break-out.
    q = _build_overpass_query('X"]; out; //', [("amenity", "gallery")], "DE")
    assert '"X\\"]; out; //"' in q
