"""
Web and geographic search tools.
geo_search uses the Overpass API (OpenStreetMap) — no API key required.
google_maps_search uses Google Places API (New) — requires GOOGLE_MAPS_API_KEY.
web_search uses Google Custom Search API — requires GOOGLE_SEARCH_API_KEY + GOOGLE_SEARCH_CX.
  Daily limit: 100 queries (free tier). Counter resets at midnight.
"""
import logging
import httpx

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_TIMEOUT = (10, 60)  # (connect, read)

GOOGLE_PLACES_URL = "https://places.googleapis.com/v1/places:searchText"

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


def google_maps_search(query: str, city: str, country: str = "DE") -> list[dict]:
    """
    Search for venues using Google Places API (New).
    Paginates up to 3 pages (max 60 results) using nextPageToken.
    Returns list of dicts with: name, address, city, country, website, phone.
    Falls back to empty list if API key is missing or request fails.
    """
    from src.config import GOOGLE_MAPS_API_KEY
    if not GOOGLE_MAPS_API_KEY:
        logger.warning("google_maps_search: GOOGLE_MAPS_API_KEY not set")
        return []

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.websiteUri,places.nationalPhoneNumber,places.internationalPhoneNumber,nextPageToken",
    }

    results = []
    page_token = None
    max_pages = 3

    for page in range(max_pages):
        payload = {
            "textQuery": f"{query} {city}",
            "languageCode": "de",
            "regionCode": country,
            "maxResultCount": 20,
        }
        if page_token:
            payload["pageToken"] = page_token

        try:
            resp = httpx.post(GOOGLE_PLACES_URL, json=payload, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            places = data.get("places", [])
            page_token = data.get("nextPageToken")
        except Exception as e:
            logger.warning("google_maps_search failed for '%s' in %s (page %d): %s", query, city, page + 1, e)
            break

        for p in places:
            name = p.get("displayName", {}).get("text", "")
            if not name:
                continue
            results.append({
                "name": name,
                "address": p.get("formattedAddress", ""),
                "city": city,
                "country": country,
                "website": p.get("websiteUri", ""),
                "phone": p.get("nationalPhoneNumber", "") or p.get("internationalPhoneNumber", ""),
                "email": "",
            })

        if not page_token:
            break

    logger.info("google_maps_search: %d results for '%s' in %s", len(results), query, city)
    return results


def fetch_page(url: str, max_chars: int = 3000) -> str:
    """
    Fetch a web page and return its plain text content (HTML stripped).
    Returns empty string on any failure.
    """
    try:
        resp = httpx.get(url, timeout=10, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"
        })
        resp.raise_for_status()
        html = resp.text
        # Remove script and style blocks entirely
        import re
        html = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
        # Strip remaining HTML tags
        text = re.sub(r'<[^>]+>', ' ', html)
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:max_chars]
    except Exception as e:
        logger.debug("fetch_page failed for %s: %s", url, e)
        return ""


BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


def web_search(query: str, max_results: int = 8) -> list[dict]:
    """
    Search the web using Brave Search API.
    Returns list of dicts with: title, url, snippet.
    """
    from src.config import BRAVE_SEARCH_API_KEY
    if not BRAVE_SEARCH_API_KEY:
        logger.warning("web_search: BRAVE_SEARCH_API_KEY not set")
        return []
    try:
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": BRAVE_SEARCH_API_KEY,
        }
        params = {"q": query, "count": min(max_results, 20)}
        resp = httpx.get(BRAVE_SEARCH_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        items = resp.json().get("web", {}).get("results", [])
        results = [{"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("description", "")} for r in items]
        logger.info("web_search: %d results for '%s'", len(results), query)
        return results
    except Exception as e:
        logger.warning("web_search failed for '%s': %s", query, e)
        return []
