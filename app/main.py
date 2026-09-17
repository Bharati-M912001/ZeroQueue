"""ZeroQueue FastAPI entrypoint. Run it from the repo root with:
    uvicorn app.main:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.api import chat, health, intercom_webhook, trace
from models import database as db

app = FastAPI(title="ZeroQueue backend", version="1.0.0")

# Allow the Next.js page (localhost:3000 in dev) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    db.init_db()
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


app.include_router(health.router)
app.include_router(intercom_webhook.router)
app.include_router(trace.router)
app.include_router(chat.router)
