import os
from dotenv import load_dotenv
from src.mission import Mission

load_dotenv()

# --- Database ---
DATABASE_URL: str = os.environ["DATABASE_URL"]

# --- AI backends ---
DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# --- Google Maps ---
GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY", "")

# --- Proton Bridge (IMAP + SMTP) ---
PROTON_IMAP_HOST: str = os.getenv("PROTON_IMAP_HOST", "127.0.0.1")
PROTON_IMAP_PORT: int = int(os.getenv("PROTON_IMAP_PORT", "1143"))
PROTON_SMTP_HOST: str = os.getenv("PROTON_SMTP_HOST", "127.0.0.1")
PROTON_SMTP_PORT: int = int(os.getenv("PROTON_SMTP_PORT", "1025"))
PROTON_EMAIL: str = os.getenv("PROTON_EMAIL", "")
PROTON_PASSWORD: str = os.getenv("PROTON_PASSWORD", "")

# --- App ---
HOST: str = os.getenv("HOST", "127.0.0.1")
PORT: int = int(os.getenv("PORT", "8000"))

# --- Scout threshold ---
# Contacts scoring below this are dropped. Start high, lower when you need more volume.
SCOUT_THRESHOLD: int = int(os.getenv("SCOUT_THRESHOLD", "75"))

# --- Email ---
# Set EMAIL_ENABLED=false to disable all outgoing email (approvals will be marked approved_unsent)
EMAIL_ENABLED: bool = os.getenv("EMAIL_ENABLED", "true").lower() == "true"

# --- LLM backend for cheap/high-volume tasks (research, enrichment, scouting) ---
# Options: deepseek-chat, claude-haiku
CHEAP_LLM: str = os.getenv("CHEAP_LLM", "deepseek-chat")

# --- Mission ---
# To repurpose for a different domain, replace ART_MISSION with your own
# and update ACTIVE_MISSION to point to it. Nothing else changes.

ART_MISSION = Mission(
    goal=(
        "Find venues across Germany and Bavaria that display and sell original artwork, "
        "build relationships with them, and secure exhibition or sales opportunities."
    ),
    identity="Christopher Rehm, watercolor and oil painter based in Klosterlechfeld, Bavaria",
    targets=(
        "galleries, hotel lobbies, restaurants, corporate offices, cafes, "
        "cultural centres, museums, coworking spaces"
    ),
    fit_criteria=(
        "Strong fit: galleries showing regional, emerging, or mid-career artists; "
        "venues that sell work on consignment or display art for atmosphere (hotels, restaurants, offices, cafes); "
        "interior designers who source original art for clients; "
        "coworking spaces and concept stores with a design-conscious aesthetic. "
        "Weak fit: galleries that exclusively represent internationally established or blue-chip artists; "
        "venues with no visible interest in art or decor; "
        "purely commercial or chain businesses with no cultural angle. "
        "Style: contemporary or traditional both welcome, regional landscapes and figurative work a strong fit."
    ),
    outreach_style=(
        "personal, artist-direct, warm but professional. "
        "Not commercial or templated — each message should feel handwritten."
    ),
    language_default="de",
)

ACTIVE_MISSION: Mission = ART_MISSION
