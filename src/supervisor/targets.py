"""
Research targets: the city + industry pairs the research agent will investigate.

Edit this list to add new cities or industries. The supervisor runs the
research agent once per target per invocation.

Format: {"city": str, "industry": str, "country": str (ISO 3166-1 alpha-2)}
"""

INDUSTRIES = [
    "gallery",
    "restaurant",
    "hotel",
    "cafe",
    "interior designer",
    "coworking space",
    "corporate office",
    "concept store",
]

# All cities within ~300km of Klosterlechfeld with population 25k+
CITIES = [
    # --- Bavaria: immediate area ---
    {"city": "Augsburg",                    "country": "DE"},
    {"city": "Königsbrunn",                 "country": "DE"},
    {"city": "Pfaffenhofen an der Ilm",     "country": "DE"},
    {"city": "Olching",                     "country": "DE"},
    {"city": "Friedberg",                   "country": "DE"},
    {"city": "Germering",                   "country": "DE"},
    {"city": "Fürstenfeldbruck",            "country": "DE"},
    {"city": "Dachau",                      "country": "DE"},
    {"city": "Landsberg am Lech",           "country": "DE"},

    # --- Bavaria: wider ring ---
    {"city": "Munich",                      "country": "DE"},
    {"city": "Kaufbeuren",                  "country": "DE"},
    {"city": "Erding",                      "country": "DE"},
    {"city": "Memmingen",                   "country": "DE"},
    {"city": "Kempten",                     "country": "DE"},
    {"city": "Garmisch-Partenkirchen",      "country": "DE"},
    {"city": "Wangen im Allgäu",            "country": "DE"},
    {"city": "Landshut",                    "country": "DE"},
    {"city": "Rosenheim",                   "country": "DE"},
    {"city": "Ingolstadt",                  "country": "DE"},
    {"city": "Lindau",                      "country": "DE"},

    # --- Baden-Württemberg: Ulm area ---
    {"city": "Ulm",                         "country": "DE"},
    {"city": "Neu-Ulm",                     "country": "DE"},
    {"city": "Ehingen",                     "country": "DE"},
    {"city": "Biberach an der Riss",        "country": "DE"},
    {"city": "Heidenheim an der Brenz",     "country": "DE"},
    {"city": "Geislingen an der Steige",    "country": "DE"},

    # --- Baden-Württemberg: Swabian Alb / northeast ---
    {"city": "Aalen",                       "country": "DE"},
    {"city": "Schwäbisch Gmünd",            "country": "DE"},
    {"city": "Schwäbisch Hall",             "country": "DE"},
    {"city": "Crailsheim",                  "country": "DE"},
    {"city": "Öhringen",                    "country": "DE"},
    {"city": "Neckarsulm",                  "country": "DE"},
    {"city": "Göppingen",                   "country": "DE"},

    # --- Baden-Württemberg: Stuttgart metro ---
    {"city": "Stuttgart",                   "country": "DE"},
    {"city": "Esslingen am Neckar",         "country": "DE"},
    {"city": "Ludwigsburg",                 "country": "DE"},
    {"city": "Tübingen",                    "country": "DE"},
    {"city": "Reutlingen",                  "country": "DE"},
    {"city": "Sindelfingen",                "country": "DE"},
    {"city": "Böblingen",                   "country": "DE"},
    {"city": "Leonberg",                    "country": "DE"},
    {"city": "Waiblingen",                  "country": "DE"},
    {"city": "Schorndorf",                  "country": "DE"},
    {"city": "Fellbach",                    "country": "DE"},
    {"city": "Bietigheim-Bissingen",        "country": "DE"},
    {"city": "Kirchheim unter Teck",        "country": "DE"},
    {"city": "Nürtingen",                   "country": "DE"},
    {"city": "Herrenberg",                  "country": "DE"},
    {"city": "Albstadt",                    "country": "DE"},
    {"city": "Balingen",                    "country": "DE"},
    {"city": "Tuttlingen",                  "country": "DE"},

    # --- Baden-Württemberg: Lake Constance ---
    {"city": "Friedrichshafen",             "country": "DE"},
    {"city": "Ravensburg",                  "country": "DE"},
    {"city": "Konstanz",                    "country": "DE"},
    {"city": "Singen",                      "country": "DE"},
    {"city": "Radolfzell am Bodensee",      "country": "DE"},

    # --- Baden-Württemberg: Karlsruhe / Rhine area ---
    {"city": "Karlsruhe",                   "country": "DE"},
    {"city": "Rastatt",                     "country": "DE"},
    {"city": "Bruchsal",                    "country": "DE"},
    {"city": "Ettlingen",                   "country": "DE"},
    {"city": "Offenburg",                   "country": "DE"},
    {"city": "Kehl",                        "country": "DE"},
    {"city": "Bühl",                        "country": "DE"},
    {"city": "Achern",                      "country": "DE"},
    {"city": "Lörrach",                     "country": "DE"},
    {"city": "Weil am Rhein",               "country": "DE"},
    {"city": "Rheinfelden",                 "country": "DE"},
    {"city": "Emmendingen",                 "country": "DE"},

    # --- Baden-Württemberg: Heidelberg / Kraichgau ---
    {"city": "Heidelberg",                  "country": "DE"},
    {"city": "Weinheim",                    "country": "DE"},
    {"city": "Sinsheim",                    "country": "DE"},
    {"city": "Bretten",                     "country": "DE"},
    {"city": "Pforzheim",                   "country": "DE"},

    # --- Austria ---
    {"city": "Innsbruck",                   "country": "AT"},
    {"city": "Salzburg",                    "country": "AT"},
    {"city": "Bregenz",                     "country": "AT"},
    {"city": "Dornbirn",                    "country": "AT"},
    {"city": "Feldkirch",                   "country": "AT"},

    # --- Switzerland ---
    {"city": "Zurich",                      "country": "CH"},
    {"city": "Winterthur",                  "country": "CH"},
    {"city": "St. Gallen",                  "country": "CH"},
    {"city": "Basel",                       "country": "CH"},
]

# Expand to one entry per city/industry combination
RESEARCH_TARGETS: list[dict] = [
    {"city": c["city"], "industry": industry, "country": c["country"]}
    for c in CITIES
    for industry in INDUSTRIES
]
