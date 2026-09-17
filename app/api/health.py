"""GET /health - status without secrets. The page header uses it for the
online/degraded/offline pill."""
from fastapi import APIRouter

from app import config
from models import database as db

router = APIRouter()


@router.get("/health")
def health():
    try:
        with db.get_conn() as conn:
            conn.execute("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "service": "zeroqueue-backend",
        "status": "ok" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
        "mock_mode": config.MOCK_MODE,          # safe to expose: it is not a secret
        "ocr_provider": config.OCR_PROVIDER,
        "intercom_configured": bool(config.INTERCOM_ACCESS_TOKEN),
        "llm_configured": bool(config.GROQ_API_KEY),
    }
