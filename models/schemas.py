"""Request/response shapes (pydantic models) for the public API."""
from typing import List, Optional
from pydantic import BaseModel


class Citation(BaseModel):
    label: str                 # e.g. "[1] Returns Policy - Damaged items"
    url: Optional[str] = None  # only set for intentionally public links


class TraceResponse(BaseModel):
    # The safe, customer-visible subset of the latest retrieval run.
    # Never contains tokens, keys, raw webhook data, or private KB text.
    state: str                 # empty | retrieving | answered | escalated | error
    retrieval_ms: Optional[float] = None
    total_ms: Optional[float] = None
    source_count: int = 0
    sources: List[Citation] = []
    confidence_band: Optional[str] = None
    handoff_reason: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    status: str                # answered | handoff | error
    citations: List[Citation] = []
    trace: TraceResponse
    # Set when the customer attached a file: an honest one-line note about
    # what the OCR/read step did (e.g. "Read 3 lines from invoice.pdf").
    attachment_note: Optional[str] = None


class HandoffRequest(BaseModel):
    session_id: str
    reason: str = "customer_requested_human"
