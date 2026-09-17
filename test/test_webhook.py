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


def test_bad_signature_rejected(client, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "INTERCOM_WEBHOOK_SECRET", "test-secret")
    resp = client.post("/api/webhooks/intercom",
                       content=json.dumps(_event("e4")),
                       headers={"X-Hub-Signature": "sha1=wrong"})
    assert resp.status_code == 401
