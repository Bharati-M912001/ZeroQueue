"""Central configuration.

Every secret or environment-specific value is read here, from environment
variables. ZeroQueue has exactly ONE .env file, at the repo root. For local
runs we load it by hand (no extra package): each line is KEY=VALUE.
`.env` is listed in .gitignore so it is never committed. Real keys live
only in `.env` or in the deployment platform's secret settings - never in
code, never in chat.
"""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]   # the zeroqueue/ folder


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines, # comments. Existing env wins."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(REPO_ROOT / ".env")

APP_NAME = "ZeroQueue"
APP_ENV = os.environ.get("APP_ENV", "development")

# MOCK_MODE=true (default) means: no external paid API calls are made.
# Intercom and Groq adapters log what they *would* send instead.
# Local OCR still runs for real in mock mode (it needs no account).
MOCK_MODE = os.environ.get("MOCK_MODE", "true").strip().lower() == "true"

# Spike supports SQLite only. DATABASE_URL looks like: sqlite:///./zeroqueue.db
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./zeroqueue.db")
DB_PATH = DATABASE_URL.replace("sqlite:///", "")

# Which websites may call this API (the Next.js page origin).
CORS_ORIGINS = [o.strip() for o in os.environ.get(
    "CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]

# Protects POST /api/demo/reset so strangers cannot wipe the demo state.
DEMO_RESET_SECRET = os.environ.get("DEMO_RESET_SECRET", "dev-reset-secret")

# --- Attachments / OCR ---
UPLOAD_DIR = REPO_ROOT / "uploads"
MAX_UPLOAD_MB = float(os.environ.get("MAX_UPLOAD_MB", "15"))
OCR_PROVIDER = os.environ.get("OCR_PROVIDER", "tesseract").strip().lower()
TESSERACT_CMD = os.environ.get("TESSERACT_CMD", "").strip()

# --- Intercom (leave blank in mock mode) ---
# Use the ROTATED token here - the old one was exposed in chat on Sep 16.
INTERCOM_ACCESS_TOKEN = os.environ.get("INTERCOM_ACCESS_TOKEN", "")
INTERCOM_WEBHOOK_SECRET = os.environ.get("INTERCOM_WEBHOOK_SECRET", "")
INTERCOM_API_BASE = os.environ.get("INTERCOM_API_BASE", "https://api.intercom.io")
INTERCOM_ADMIN_ID = os.environ.get("INTERCOM_ADMIN_ID", "")  # bot author id for replies
INTERCOM_TEAM_ID = os.environ.get("INTERCOM_TEAM_ID", "")    # default team for handoff

# --- Moss (real retrieval goes in adapters/moss.py; stub works without it) ---
MOSS_API_KEY = os.environ.get("MOSS_API_KEY", "")
MOSS_INDEX_NAME = os.environ.get("MOSS_INDEX_NAME", "")

# --- LLM (Groq free tier; only used when MOCK_MODE=false) ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
# Groq shut down llama-3.1-8b-instant on 2026-08-16; openai/gpt-oss-20b is
# their free-tier replacement. If this 404s again, pick a current model at
# https://console.groq.com/docs/models and set GROQ_MODEL in .env.
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_VISION_MODEL = os.environ.get(
    "GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
