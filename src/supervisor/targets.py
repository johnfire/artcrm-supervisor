"""
Research targets: the city + industry pairs the research agent will investigate.

Edit this list to add new cities or industries. The supervisor runs the
research agent once per target per invocation.

Format: {"city": str, "industry": str, "country": str (ISO 3166-1 alpha-2)}
"""

RESEARCH_TARGETS: list[dict] = [
    {"city": "Augsburg",        "industry": "gallery",    "country": "DE"},
    {"city": "Augsburg",        "industry": "restaurant", "country": "DE"},
    {"city": "Augsburg",        "industry": "hotel",      "country": "DE"},
    {"city": "Munich",          "industry": "gallery",    "country": "DE"},
    {"city": "Munich",          "industry": "cafe",       "country": "DE"},
    {"city": "Nuremberg",       "industry": "gallery",    "country": "DE"},
    {"city": "Ingolstadt",      "industry": "gallery",    "country": "DE"},
    {"city": "Landsberg",       "industry": "gallery",    "country": "DE"},
]
