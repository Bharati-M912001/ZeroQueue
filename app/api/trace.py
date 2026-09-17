"""GET /api/trace/{session_id} - the safe Moss Trace subset for the page.

Also POST /api/demo/reset to clear demo state (protected by DEMO_RESET_SECRET).
"""
from fastapi import APIRouter, Header, HTTPException

from app import config
from models import database as db
from models.schemas import TraceResponse
from app.services import pipeline

router = APIRouter()


@router.get("/api/trace/{session_id}", response_model=TraceResponse)
def get_trace(session_id: str):
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM conversations WHERE session_id=?", (session_id,)
        ).fetchone()
    if not row:
        return TraceResponse(state="empty")
    return pipeline.latest_trace_for_conversation(row["id"])


@router.post("/api/demo/reset")
def demo_reset(x_demo_secret: str = Header(default="")):
    """Development/demo only: wipe all state so the demo can be re-run.
    Requires the DEMO_RESET_SECRET header so strangers cannot reset it."""
    if not config.DEMO_RESET_SECRET or x_demo_secret != config.DEMO_RESET_SECRET:
        raise HTTPException(status_code=403, detail="invalid demo secret")
    with db.get_conn() as conn:
        for table in ("sources", "retrieval_runs", "messages", "handoffs",
                      "conversations", "processed_events", "attachments"):
            conn.execute(f"DELETE FROM {table}")
    return {"status": "reset"}
