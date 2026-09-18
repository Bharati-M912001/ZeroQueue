"""Webhook contract: immediate 200, idempotency, loop prevention."""
import json


def _event(event_id, author_type="user", text="How long does shipping take?"):
    return {
        "id": event_id,
        "topic": "conversation.user.replied",
        "data": {"item": {
            "id": f"convo-{event_id}",
            "conversation_message": {
                "author": {"type": author_type},
                "body": f"<p>{text}</p>",
            },
        }},
    }


def test_webhook_accepts_immediately(client):
    resp = client.post("/api/webhooks/intercom", content=json.dumps(_event("e1")))
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"


def test_duplicate_event_is_ignored(client):
    first = client.post("/api/webhooks/intercom", content=json.dumps(_event("e2")))
    second = client.post("/api/webhooks/intercom", content=json.dumps(_event("e2")))
    assert first.json()["status"] == "accepted"
    assert second.json()["status"] == "duplicate_ignored"


def test_admin_author_does_not_retrigger(client):
    # An admin/bot reply arriving as a webhook must NOT produce another AI
    # reply (loop prevention). It is accepted but no run is recorded.
    resp = client.post("/api/webhooks/intercom",
                       content=json.dumps(_event("e3", author_type="admin")))
    assert resp.json()["status"] == "accepted"
    from models import database as db
    with db.get_conn() as conn:
        runs = conn.execute(
            "SELECT COUNT(*) AS n FROM retrieval_runs r"
            " JOIN conversations c ON c.id=r.conversation_id"
            " WHERE c.intercom_conversation_id='convo-e3'").fetchone()
    assert runs["n"] == 0


def test_lead_author_is_answered(client):
    # Anonymous Messenger visitors arrive as author type "lead". They are
    # customers, not admins - the event must be processed (a run recorded).
    resp = client.post("/api/webhooks/intercom",
                       content=json.dumps(_event("e5", author_type="lead")))
    assert resp.json()["status"] == "accepted"
    from models import database as db
    with db.get_conn() as conn:
        runs = conn.execute(
            "SELECT COUNT(*) AS n FROM retrieval_runs r"
            " JOIN conversations c ON c.id=r.conversation_id"
            " WHERE c.intercom_conversation_id='convo-e5'").fetchone()
    assert runs["n"] == 1


def _created_event(event_id, text):
    # Real Intercom shape for conversation.user.created: text in item.source.
    return {
        "id": event_id,
        "topic": "conversation.user.created",
        "data": {"item": {
            "id": f"convo-{event_id}",
            "source": {
                "body": f"<p>{text}</p>",
                "author": {"type": "user"},
                "attachments": [],
            },
        }},
    }


def _replied_event(event_id, text, author_type="user"):
    # Real Intercom shape for conversation.user.replied: the new message is
    # the LAST entry of item.conversation_parts.conversation_parts.
    return {
        "id": event_id,
        "topic": "conversation.user.replied",
        "data": {"item": {
            "id": f"convo-{event_id}",
            "conversation_parts": {"conversation_parts": [
                {"part_type": "comment", "body": "<p>hi</p>",
                 "author": {"type": "user"}},
                {"part_type": "comment", "body": f"<p>{text}</p>",
                 "author": {"type": author_type}},
            ]},
        }},
    }


def _runs_for(client, convo):
    from models import database as db
    with db.get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) AS n FROM retrieval_runs r"
            " JOIN conversations c ON c.id=r.conversation_id"
            f" WHERE c.intercom_conversation_id='{convo}'").fetchone()["n"]


def test_created_event_reads_item_source(client):
    resp = client.post("/api/webhooks/intercom",
                       content=json.dumps(_created_event("e6", "[Image] Where is my order?")))
    assert resp.json()["status"] == "accepted"
    assert _runs_for(client, "convo-e6") == 1


def test_created_event_with_bot_autoreply_still_answered(client):
    # Intercom Operator can auto-post right after the visitor writes; the
    # created payload then ends with a BOT part. The visitor's message in
    # item.source must still be the one we answer.
    event = {
        "id": "e9",
        "topic": "conversation.user.created",
        "data": {"item": {
            "id": "convo-e9",
            "source": {"body": "<p>Where is my order?</p>",
                       "author": {"type": "user"}, "attachments": []},
            "conversation_parts": {"conversation_parts": [
                {"part_type": "comment", "body": "<p>Where is my order?</p>",
                 "author": {"type": "user"}},
                {"part_type": "comment", "body": "<p>Hi! I'm the Operator.</p>",
                 "author": {"type": "bot"}},
            ]},
        }},
    }
    resp = client.post("/api/webhooks/intercom", content=json.dumps(event))
    assert resp.json()["status"] == "accepted"
    assert _runs_for(client, "convo-e9") == 1


def test_replied_event_reads_last_conversation_part(client):
    resp = client.post("/api/webhooks/intercom",
                       content=json.dumps(_replied_event("e7", "What is the returns policy?")))
    assert resp.json()["status"] == "accepted"
    assert _runs_for(client, "convo-e7") == 1


def test_admin_part_in_replied_event_is_ignored(client):
    resp = client.post("/api/webhooks/intercom",
                       content=json.dumps(_replied_event("e8", "admin reply", "admin")))
    assert resp.json()["status"] == "accepted"
    assert _runs_for(client, "convo-e8") == 0


def test_bad_signature_rejected(client, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "INTERCOM_WEBHOOK_SECRET", "test-secret")
    resp = client.post("/api/webhooks/intercom",
                       content=json.dumps(_event("e4")),
                       headers={"X-Hub-Signature": "sha1=wrong"})
    assert resp.status_code == 401
