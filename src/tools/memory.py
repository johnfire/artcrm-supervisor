"""
Open Brain memory wrapper.

Provides two functions used by agents and the supervisor:
  capture_thought(content) — write an observation or learning to Open Brain
  search_artcrm_thoughts(query) — semantic search over artcrm-tagged thoughts

Both are no-ops when OPEN_BRAIN_URL / OPEN_BRAIN_TOKEN are not configured,
so tests and dev environments don't need the service available.
"""
import asyncio
import logging
import re

logger = logging.getLogger(__name__)


def _get_config() -> tuple[str, str]:
    from src.config import OPEN_BRAIN_URL, OPEN_BRAIN_TOKEN
    return OPEN_BRAIN_URL, OPEN_BRAIN_TOKEN


# Module-level references patched in tests
OPEN_BRAIN_URL: str = ""
OPEN_BRAIN_TOKEN: str = ""


def _load_config() -> None:
    global OPEN_BRAIN_URL, OPEN_BRAIN_TOKEN
    url, token = _get_config()
    OPEN_BRAIN_URL = url
    OPEN_BRAIN_TOKEN = token


_load_config()


def _run_tool(tool_name: str, arguments: dict) -> str:
    """Call an Open Brain MCP tool synchronously. Returns empty string on failure."""
    if not OPEN_BRAIN_URL or not OPEN_BRAIN_TOKEN:
        return ""

    async def _inner() -> str:
        from mcp.client.streamable_http import streamablehttp_client
        from mcp import ClientSession
        headers = {"Authorization": f"Bearer {OPEN_BRAIN_TOKEN}"}
        async with streamablehttp_client(OPEN_BRAIN_URL, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                texts = [c.text for c in result.content if hasattr(c, "text")]
                return "\n".join(texts)

    try:
        return asyncio.run(_inner())
    except Exception as e:
        logger.warning("memory: %s failed: %s", tool_name, e)
        return ""


def capture_thought(content: str, project: str = "artcrm") -> None:
    """Write an observation or learning to Open Brain."""
    _run_tool("capture_thought", {"content": content, "project": project})


def search_artcrm_thoughts(query: str, limit: int = 5) -> list[str]:
    """
    Semantic search over artcrm thoughts in Open Brain.
    Returns a list of content strings (metadata stripped), up to `limit`.
    Returns [] when unconfigured or on error.
    """
    raw = _run_tool("search_thoughts", {"query": f"artcrm {query}", "limit": limit, "threshold": 0.45})
    if not raw:
        return []

    results = []
    _METADATA = re.compile(
        r"^(Captured:|Type:|Project:|Status:|Topics:|People:|Actions:|---)",
        re.MULTILINE,
    )
    for block in re.split(r"--- Result \d+.*---", raw):
        lines = [
            l.strip() for l in block.splitlines()
            if l.strip() and not _METADATA.match(l.strip())
            and not l.strip().startswith("Found ")
        ]
        content = " ".join(lines).strip()
        if content:
            results.append(content)

    return results[:limit]
