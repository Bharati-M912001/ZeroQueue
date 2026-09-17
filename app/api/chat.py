"""Built-in chat endpoints: the ZeroQueue web page talks to these.

The page sends multipart/form-data (because a message can carry an
attachment). The same pipeline that powers the Intercom webhook answers
here - only the channel differs. This is also the hard fallback: if
Intercom ever fails, this chat IS the product.
"""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from models.schemas import ChatResponse, HandoffRequest, TraceResponse
from app.services import attachment_service, pipeline

router = APIRouter()

AI_PAUSED_REPLY = ("A human teammate already has this conversation and will "
                   "reply here. There is nothing more you need to do.")


@router.post("/api/chat", response_model=ChatResponse)
async def chat(session_id: str = Form(...),
               message: str = Form(""),
               file: UploadFile = File(default=None)):
    """One customer message (plus an optional image/video/invoice file)."""
    convo_pk = pipeline.get_or_create_conversation(session_id=session_id)

    # Read the attachment first: its text becomes part of the question.
    attachment_text, attachment_note = "", None
    if file is not None and file.filename:
        data = await file.read()
        try:
            attachment_text, attachment_note = attachment_service.save_and_extract(
                convo_pk, file.filename, data, file.content_type or "")
        except attachment_service.UnsupportedFileError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    if not message.strip() and not attachment_text:
        raise HTTPException(
            status_code=400,
            detail="Send a message, or attach a file with readable text in it.")

    result = pipeline.run_pipeline(convo_pk, message, attachment_text)
    return ChatResponse(
        answer=result.answer_text,
        status=result.status,
        citations=result.citations,
        trace=result.trace or TraceResponse(state="empty"),
        attachment_note=attachment_note,
    )


@router.post("/api/handoff", response_model=ChatResponse)
def request_handoff(req: HandoffRequest):
    """Explicit 'Talk to a human' button in the chat."""
    convo_pk = pipeline.get_or_create_conversation(session_id=req.session_id)
    pipeline.record_handoff(convo_pk, req.reason, "(handoff button)", [])
    return ChatResponse(
        answer=("Thanks - I have asked a human teammate to take over. They "
                "can see this conversation and will reply here shortly."),
        status="handoff",
        citations=[],
        trace=pipeline.latest_trace_for_conversation(convo_pk),
    )
