"""
Scan level definitions for the research agent.

Each level maps to a fixed set of Google Maps search terms.
The research agent runs all terms for a given city + level combination.

Level 1 — galleries, cafes, interior designers, coworking spaces  (always run first)
Level 2 — gift shops, esoteric/wellness shops, concept stores
Level 3 — independent restaurants
Level 4 — corporate offices and headquarters
Level 5 — hotels
"""

SCAN_LEVELS: dict[int, dict] = {
    1: {
        "label": "Galleries, Cafes, Interior Designers, Coworking",
        "maps_terms": [
            "Kunstgalerie",
            "Galerie",
            "Café",
            "Kaffeehaus",
            "Innenarchitekt",
            "Raumausstatter",
            "Coworking Space",
        ],
    },
    2: {
        "label": "Gift Shops, Esoteric, Concept Stores",
        "maps_terms": [
            "Geschenkeladen",
            "Esoterikladen",
            "Kristallladen",
            "Yoga Studio",
            "Concept Store",
            "Designladen",
            "Boutique",
        ],
    },
    3: {
        "label": "Independent Restaurants",
        "maps_terms": [
            "Restaurant",
            "Gasthaus",
            "Bistro",
            "Weinrestaurant",
            "Gasthof",
        ],
    },
    4: {
        "label": "Corporate Offices & Headquarters",
        "maps_terms": [
            "Firmensitz",
            "Hauptverwaltung",
            "Bürogebäude",
            "Unternehmensberatung",
            "Technologieunternehmen",
        ],
    },
    5: {
        "label": "Hotels",
        "maps_terms": [
            "Hotel",
            "Boutique Hotel",
            "Design Hotel",
            "Landhotel",
            "Stadthotel",
        ],
    },
}
