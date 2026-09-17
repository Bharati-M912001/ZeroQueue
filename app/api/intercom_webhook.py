"""POST /api/webhooks/intercom - receives Intercom events.

==========================================================================
THE WEBHOOK FLOW, STEP BY STEP (read this top to bottom once and you own it)
==========================================================================

A "webhook" just means: when a customer writes in the Intercom Messenger,
Intercom turns around and POSTs that event to OUR server at this URL.
Then we answer. The full journey of one customer message:

  1. Customer types "Where is my order?" in the Messenger.
  2. Intercom POSTs a JSON event to https://<your-ngrok-url>/api/webhooks/intercom
     (you tell Intercom this URL once, in its webhook settings).
  3. We verify the event REALLY came from Intercom (HMAC signature check),
     so strangers cannot fake customer messages.
  4. We answer HTTP 200 IMMEDIATELY ("accepted") - Intercom requires a fast
     reply or it retries and eventually disables the webhook. The slow work
     (retrieval, LLM, replying) happens AFTER, in a background task.
  5. In the background we:
       a. ignore our own bot/admin replies (otherwise the bot would answer
          its own messages forever - "loop prevention"),
       b. dedupe: if Intercom sends the same event id twice, we process it
          only once ("idempotency"),
       c. strip the HTML from the customer's text,
       d. if the customer attached a file, download it and read it with OCR,
       e. run the shared pipeline (retrieve -> confidence -> answer/handoff),
       f. post the answer back into the same conversation via the Intercom
          API, or hand the conversation to the human team.
  6. The customer sees the answer in the Messenger. Done.

Run it locally with ngrok: `ngrok http 8000`, then paste the https URL it
prints + /api/webhooks/intercom into Intercom's webhook settings. The full
checklist with screenshots-of-text is in docs/intercom-setup.md.
==========================================================================
"""
import hashlib
import hmac
import json
import logging
import re

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from app import config
from app.adapters import intercom
from models import database as db
from app.services import attachment_service, pipeline

log = logging.getLogger("zeroqueue.webhook")
router = APIRouter()


def _verify_signature(raw_body: bytes, header: str) -> bool:
    """Intercom signs every webhook with HMAC-SHA1 using the webhook secret.
    We recompute the signature and compare - only Intercom knows the secret,
    so a match proves the event is genuine."""
    digest = hmac.new(config.INTERCOM_WEBHOOK_SECRET.encode(),
                      raw_body, hashlib.sha1).hexdigest()
    expected = f"sha1={digest}"
    return hmac.compare_digest(expected, header or "")


def _already_processed(event_id: str) -> bool:
    """Idempotency guard: one Intercom event id is processed at most once."""
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT event_id FROM processed_events WHERE event_id=?",
            (event_id,)).fetchone()
        if row:
            return True
        conn.execute("INSERT INTO processed_events (event_id, received_at)"
                     " VALUES (?,?)", (event_id, db.now()))
        return False


@router.post("/api/webhooks/intercom")
async def receive_intercom_event(request: Request, background_tasks: BackgroundTasks):
    """The front door. Fast checks only, then 200 OK. Never do slow work here."""
    raw = await request.body()

    # Step 3: signature check (skipped only when no secret is configured,
    # i.e. early local testing - never in the deployed demo).
    if config.INTERCOM_WEBHOOK_SECRET:
        if not _verify_signature(raw, request.headers.get("X-Hub-Signature", "")):
            return JSONResponse({"status": "invalid_signature"}, status_code=401)

    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return JSONResponse({"status": "bad_json"}, status_code=400)

    # Step 4 + 5b: dedupe, then acknowledge immediately.
    event_id = str(payload.get("id") or payload.get("item", {}).get("id") or "")
    if event_id and _already_processed(event_id):
        return {"status": "duplicate_ignored"}

    # The real work continues in the background AFTER this 200 is sent.
    background_tasks.add_task(_process_event_safely, payload)
    return {"status": "accepted"}


def _process_event_safely(payload: dict) -> None:
    """Run the worker and make any failure LOUD. A background task that
    raises would otherwise vanish into the server log with no context -
    the most common causes are MOCK_MODE still on (replies only logged),
    a wrong/expired INTERCOM_ACCESS_TOKEN, or a bad INTERCOM_ADMIN_ID."""
    try:
        process_event(payload)
    except Exception:
        log.exception(
            "webhook processing FAILED - check MOCK_MODE=false, the new app's "
            "INTERCOM_ACCESS_TOKEN, and INTERCOM_ADMIN_ID")


def process_event(payload: dict) -> None:
    """Background worker: normalize -> pipeline -> reply/assign via Intercom.

    This is where every slow step lives. Intercom already got its 200."""
    topic = payload.get("topic", "")
    item = payload.get("data", {}).get("item", payload.get("item", {}))
    conversation_id = str(item.get("id", ""))
    if not conversation_id:
        log.warning("webhook event without conversation id; ignored (topic=%s)", topic)
        return

    # Step 5a: loop prevention - never react to OUR OWN side of the
    # conversation, or the bot would answer its own messages forever.
    # Intercom author types: "user" and "lead" are CUSTOMERS (an anonymous
    # Messenger visitor is a "lead" until identified); "admin", "bot" and
    # "team" are OUR side. Ignoring "lead" here would silently drop every
    # real customer who is not logged in - that was the no-reply bug.
    author = (item.get("conversation_message", {}) or {}).get("author", {}) \
        or item.get("author", {})
    author_type = author.get("type", "user")
    log.info("event %s on conversation %s, author type %s",
             topic, conversation_id, author_type)
    if author_type in ("admin", "bot", "team"):
        log.info("ignoring %s-authored event (loop prevention)", author_type)
        return

    # Step 5c: latest customer text; Intercom bodies are HTML like <p>hi</p>.
    raw_text = (item.get("conversation_message", {}) or {}).get("body") \
        or item.get("body", "")
    message = re.sub(r"<[^>]+>", " ", raw_text or "").strip()
    log.info("customer text on %s: %.80s", conversation_id, message or "(empty)")

    convo_pk = pipeline.get_or_create_conversation(intercom_id=conversation_id)

    # Step 5d: attachments. A customer can send an image/video/invoice in
    # the Messenger; Intercom puts download URLs on the message. We fetch
    # the first one and read it with the same OCR used by the web chat.
    attachment_text, attachment_note = "", ""
    attachment_urls = (item.get("conversation_message", {}) or {}).get("attachment_urls") \
        or item.get("attachment_urls") or []
    if attachment_urls:
        try:
            log.info("downloading attachment for %s", conversation_id)
            data = intercom.download_attachment(attachment_urls[0])
            filename = attachment_urls[0].rsplit("/", 1)[-1].split("?")[0] or "attachment"
            if data:
                attachment_text, attachment_note = attachment_service.save_and_extract(
                    convo_pk, filename, data)
                log.info("attachment read: %s", attachment_note)
        except Exception as exc:  # a bad attachment must never kill the reply
            log.warning("attachment handling failed: %s", exc)

    if not message and not attachment_text:
        log.info("nothing to answer on %s (empty message, no readable "
                 "attachment); stopping", conversation_id)
        return
    if not message:
        message = "(customer sent an attachment)"

    with db.get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO messages (conversation_id,"
            " intercom_event_id, author_type, text, created_at)"
            " VALUES (?,?,?,?,?)",
            (convo_pk, str(item.get("id")), "customer", message, db.now()))

    # Step 5e: the shared pipeline - same code the built-in chat uses.
    log.info("running pipeline for %s", conversation_id)
    result = pipeline.run_pipeline(convo_pk, message, attachment_text)

    # Step 5f: post the outcome back into Intercom.
    log.info("pipeline result for %s: %s", conversation_id, result.status)
    if attachment_note:
        intercom.reply(conversation_id, f"(I read your attachment: {attachment_note})")
    if result.status == "answered":
        intercom.reply(conversation_id, result.answer_text)
    elif result.status == "handoff" and result.handoff_reason:
        intercom.reply(conversation_id, result.answer_text)          # acknowledgement
        intercom.add_note(conversation_id,                           # internal summary
                          f"Handoff: {result.handoff_reason}. "
                          "See retrieval trace for sources already checked.")
        intercom.assign(conversation_id)                             # human owns it now
    log.info("reply posted to conversation %s (check the Messenger)", conversation_id)
