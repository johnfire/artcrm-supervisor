"""
Web and geographic search tools.
geo_search uses the Overpass API (OpenStreetMap) — no API key required.
web_search uses DuckDuckGo — no API key required.
"""
import logging
import httpx
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_TIMEOUT = (10, 60)  # (connect, read)

# Maps industry names to OpenStreetMap tag queries.
# Each entry is a list of (key, value) pairs tried in a single union query.
INDUSTRY_OSM_TAGS: dict[str, list[tuple[str, str]]] = {
    "gallery":     [("amenity", "gallery"), ("tourism", "gallery"), ("shop", "art")],
    "restaurant":  [("amenity", "restaurant")],
    "hotel":       [("tourism", "hotel")],
    "cafe":        [("amenity", "cafe")],
    "museum":      [("tourism", "museum")],
    "office":      [("office", "company"), ("office", "yes")],
    "coworking":   [("amenity", "coworking_space")],
    "bar":         [("amenity", "bar")],
}


def _build_overpass_query(city: str, tags: list[tuple[str, str]], country: str = "DE") -> str:
    area_filter = f'area["name"="{city}"]["ISO3166-2"~"^{country}"]->.a;'
    node_clauses = "\n".join(
        f'  node["{k}"="{v}"](area.a);' for k, v in tags
    )
    return f"""
[out:json][timeout:30];
{area_filter}
(
{node_clauses}
);
out center tags;
""".strip()


def geo_search(query: str, city: str, country: str = "DE") -> list[dict]:
    """
    Search for venues in a city using OpenStreetMap's Overpass API.
    `query` is used to determine the OSM tag set (matched by keyword).
    Returns list of dicts with: name, address, city, country, website, phone.
    """
    # Match query to tag set — fall back to generic text search tags
    industry_key = next(
        (k for k in INDUSTRY_OSM_TAGS if k in query.lower()),
        None,
    )
    tags = INDUSTRY_OSM_TAGS.get(industry_key, [("name", "*")])

    overpass_q = _build_overpass_query(city, tags, country)
    try:
        resp = httpx.post(
            OVERPASS_URL,
            data={"data": overpass_q},
            timeout=OVERPASS_TIMEOUT,
            verify=True,
        )
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
    except Exception as e:
        logger.warning("geo_search failed for %s/%s: %s", city, query, e)
        return []

    results = []
    for el in elements:
        tags_data = el.get("tags", {})
        name = tags_data.get("name", "")
        if not name:
            continue
        results.append({
            "name": name,
            "address": " ".join(filter(None, [
                tags_data.get("addr:street", ""),
                tags_data.get("addr:housenumber", ""),
            ])),
            "city": city,
            "country": country,
            "website": tags_data.get("website", tags_data.get("contact:website", "")),
            "phone": tags_data.get("phone", tags_data.get("contact:phone", "")),
            "email": tags_data.get("email", tags_data.get("contact:email", "")),
        })

    logger.info("geo_search: %d results for '%s' in %s", len(results), query, city)
    return results


def web_search(query: str, max_results: int = 8) -> list[dict]:
    """
    Search the web using DuckDuckGo. No API key required.
    Returns list of dicts with: title, url, snippet.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        logger.info("web_search: %d results for '%s'", len(results), query)
        return [{"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")} for r in results]
    except Exception as e:
        logger.warning("web_search failed for '%s': %s", query, e)
        return []
