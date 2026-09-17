"""The shared answer pipeline used by BOTH the Intercom webhook worker
and the built-in /api/chat endpoint. Only the channel adapter differs -
which is exactly the fallback strategy: if Intercom ever fails, the
built-in chat keeps the whole product working with zero changes here.

The flow for every customer message, in order:
  1. If a human already owns the conversation, the AI stays silent.
  2. Retrieve matching knowledge-base passages (Moss seam).
  3. Measure confidence from the evidence (never from the LLM).
  4. Either hand off to a human, or build a grounded, cited answer.
"""
import logging
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional

from models import database as db
from models.schemas import Citation, TraceResponse
from app.services import answer_service, confidence, escalation, moss_service

log = logging.getLogger("zeroqueue.pipeline")


@dataclass
class PipelineResult:
    status: str                       # answered | handoff | error
    answer_text: str = ""
    citations: List[Citation] = field(default_factory=list)
    handoff_reason: Optional[str] = None
    trace: Optional[TraceResponse] = None


def get_or_create_conversation(session_id=None, intercom_id=None) -> int:
    """Return the internal conversation id, creating the row if needed."""
    with db.get_conn() as conn:
        row = None
        if intercom_id:
            row = conn.execute(
                "SELECT * FROM conversations WHERE intercom_conversation_id=?",
                (intercom_id,)).fetchone()
        if row is None and session_id:
            row = conn.execute(
                "SELECT * FROM conversations WHERE session_id=?",
                (session_id,)).fetchone()
        if row:
            return row["id"]
        cur = conn.execute(
            "INSERT INTO conversations (intercom_conversation_id, session_id,"
            " status, created_at, updated_at) VALUES (?,?,?,?,?)",
            (intercom_id, session_id, "ai_active", db.now(), db.now()))
        return cur.lastrowid


def _conversation_status(conversation_id: int) -> str:
    with db.get_conn() as conn:
        row = conn.execute("SELECT status FROM conversations WHERE id=?",
                           (conversation_id,)).fetchone()
        return row["status"] if row else "ai_active"


def _record_run(conversation_id: int, query: str, retrieval_ms, total_ms,
                band: str, status: str, passages, error_code=None) -> int:
    """Persist one retrieval run + its sources, and return the run id."""
    with db.get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO retrieval_runs (conversation_id, query, retrieval_ms,"
            " total_ms, confidence, status, error_code, created_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (conversation_id, query, retrieval_ms, total_ms, band, status,
             error_code, db.now()))
        run_id = cur.lastrowid
        for rank, p in enumerate(passages[:3], start=1):
            conn.execute(
                "INSERT INTO sources (retrieval_run_id, source_key, title,"
                " section, safe_url, score, rank) VALUES (?,?,?,?,?,?,?)",
                (run_id, p.source_key, p.title, p.section, p.safe_url or None,
                 p.score, rank))
        conn.execute(
            "UPDATE conversations SET last_customer_text=?, updated_at=?"
            " WHERE id=?", (query, db.now(), conversation_id))
        return run_id


def _set_status(conversation_id: int, status: str) -> None:
    with db.get_conn() as conn:
        conn.execute("UPDATE conversations SET status=?, updated_at=? WHERE id=?",
                     (status, db.now(), conversation_id))


def record_handoff(conversation_id: int, reason: str, query: str,
                   passages) -> None:
    source_titles = ", ".join(f"{p.title} - {p.section}" for p in passages[:3]) or "none"
    summary = (f"Customer asked: {query[:200]}. Confidence low or human "
               f"requested. Sources already checked: {source_titles}. "
               f"Suggested next step: read the transcript and reply.")
    with db.get_conn() as conn:
        conn.execute(
            "INSERT INTO handoffs (conversation_id, reason, issue_type,"
            " summary, assigned_to, created_at) VALUES (?,?,?,?,?,?)",
            (conversation_id, reason, "support", summary, None, db.now()))
    _set_status(conversation_id, "handoff")


def run_pipeline(conversation_id: int, message: str,
                 attachment_text: str = "") -> PipelineResult:
    """Retrieve -> confidence -> answer or hand off. Channel-neutral.

    `attachment_text` is whatever OCR/parsing read out of the customer's
    uploaded image, video, or invoice. It is merged into the query so the
    retrieval and the answer can use order numbers, product names, or
    error text the customer SHOWED instead of typed.

    total_ms starts here (right after the webhook was already acknowledged,
    or when /api/chat received the message) and stops after the answer is
    built and recorded. retrieval_ms measures ONLY the Moss search inside.
    """
    total_start = time.perf_counter()

    # If a human already owns this conversation, the AI stays silent.
    if _conversation_status(conversation_id) == "handoff":
        return PipelineResult(
            status="handoff",
            answer_text=("A human teammate already has this conversation and "
                         "will reply here. There is nothing more you need to do."),
            trace=latest_trace_for_conversation(conversation_id))

    # Merge the typed message with whatever the attachment told us.
    query = message.strip()
    if attachment_text.strip():
        query = (query + "\n\nAttachment text (OCR):\n" + attachment_text.strip()).strip()
    if not query:
        query = "(customer sent an attachment with no readable text)"

    # 1. Retrieve (local stub today, real Moss tomorrow - same signature).
    #    The typed message drives retrieval; the attachment text gets its
    #    own search and the two are merged, so invoice words can add
    #    relevant passages but never drown out the actual question.
    retrieval = moss_service.search(message.strip() or query)
    if attachment_text.strip():
        att_retrieval = moss_service.search(attachment_text.strip())
        retrieval = _merge_retrievals(retrieval, att_retrieval,
                                      attachment_text=attachment_text)
    passages = retrieval.passages

    # 2. Evidence-based confidence + escalation decision (never the LLM's).
    band = confidence.band(passages)
    reason = escalation.decide(message, band)

    if reason:
        record_handoff(conversation_id, reason, query, passages)
        ack = ("Thanks for your patience - I am handing this to a human "
               "teammate now. They can see this conversation and will reply "
               "here shortly.")
        if reason != "customer_requested_human":
            ack = ("I do not have a reliable answer for that in our support "
                   "knowledge base, so I will not guess. " + ack)
        _record_run(conversation_id, query, retrieval.retrieval_ms,
                    _elapsed(total_start), band, "escalated", passages)
        return PipelineResult(status="handoff", answer_text=ack,
                              handoff_reason=reason,
                              trace=latest_trace_for_conversation(conversation_id))

    # 3. Grounded answer with citations.
    answer_text, citations = answer_service.build_answer(query, passages)
    _record_run(conversation_id, query, retrieval.retrieval_ms,
                _elapsed(total_start), band, "answered", passages)
    return PipelineResult(status="answered", answer_text=answer_text,
                          citations=citations,
                          trace=latest_trace_for_conversation(conversation_id))



# The typed question is always the boss of retrieval. Passages found via
# the attachment text are discounted so invoice wording (payment terms,
# GST lines, fees) can never outrank what the customer actually ASKED.
ATTACHMENT_WEIGHT = 0.5

# Order-id shapes worth hunting in the knowledge base, e.g. NB-1042 or
# #48213. When a passage mentions the exact id from the customer's
# invoice, that is strong evidence - boost it.
_ORDER_ID = re.compile(r"\b[A-Z]{2,}-\d{3,}\b|\b#\d{3,}\b")


def _merge_retrievals(primary, secondary, top_k: int = 3,
                      attachment_text: str = ""):
    """Combine two retrieval results. The customer's typed message
    (primary) keeps full weight; attachment passages (secondary) are
    discounted to ATTACHMENT_WEIGHT so they can add context but not take
    over. Passages mentioning an exact order id from the attachment get
    a boost. Times add up (both are real retrieval work)."""
    ids = _ORDER_ID.findall(attachment_text)
    best = {}
    for p in primary.passages:
        best[p.source_key] = p
    for p in secondary.passages:
        p.score = round(p.score * ATTACHMENT_WEIGHT, 3)
        if p.source_key not in best or p.score > best[p.source_key].score:
            best[p.source_key] = p
    for p in best.values():
        if ids and any(i in p.text for i in ids):
            p.score = min(1.0, round(p.score + 0.3, 3))
    merged = sorted(best.values(), key=lambda p: p.score, reverse=True)[:top_k]
    return moss_service.RetrievalResult(
        passages=merged,
        retrieval_ms=round(primary.retrieval_ms + secondary.retrieval_ms, 1))


def _elapsed(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 1)


def latest_trace_for_conversation(conversation_id: int) -> TraceResponse:
    """Build the safe, customer-visible trace for the newest run."""
    with db.get_conn() as conn:
        run = conn.execute(
            "SELECT * FROM retrieval_runs WHERE conversation_id=?"
            " ORDER BY id DESC LIMIT 1", (conversation_id,)).fetchone()
        if not run:
            return TraceResponse(state="empty")
        sources = conn.execute(
            "SELECT title, section, safe_url FROM sources"
            " WHERE retrieval_run_id=? ORDER BY rank", (run["id"],)).fetchall()
    state = {"answered": "answered", "escalated": "escalated"}.get(run["status"], "error")
    handoff_reason = None
    if state == "escalated":
        with db.get_conn() as conn:
            h = conn.execute(
                "SELECT reason FROM handoffs WHERE conversation_id=?"
                " ORDER BY id DESC LIMIT 1", (conversation_id,)).fetchone()
            handoff_reason = h["reason"] if h else None
    return TraceResponse(
        state=state,
        retrieval_ms=run["retrieval_ms"],
        total_ms=run["total_ms"],
        source_count=len(sources),
        sources=[Citation(label=f"[{i+1}] {s['title']} - {s['section']}",
                          url=s["safe_url"]) for i, s in enumerate(sources)],
        confidence_band=run["confidence"],
        handoff_reason=handoff_reason,
    )
