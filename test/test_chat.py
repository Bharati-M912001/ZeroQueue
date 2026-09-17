"""Built-in chat: grounded answer with citations, trace fields, handoff."""


def _post(client, session_id, message, files=None):
    data = {"session_id": session_id, "message": message}
    return client.post("/api/chat", data=data, files=files)


def test_chat_answers_with_citations_and_trace(client):
    resp = _post(client, "test-session-1", "How long does shipping take?")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "answered"
    assert "Sources:" in body["answer"]
    assert len(body["citations"]) >= 1
    trace = body["trace"]
    assert trace["state"] == "answered"
    assert trace["retrieval_ms"] is not None
    assert trace["total_ms"] is not None
    assert trace["source_count"] >= 1


def test_escalation_phrase_hands_off_and_pauses_ai(client):
    resp = _post(client, "test-session-2", "That did not help. I want to talk to a human.")
    body = resp.json()
    assert body["status"] == "handoff"
    assert body["trace"]["state"] == "escalated"
    assert body["trace"]["handoff_reason"] == "customer_requested_human"

    # AI stays paused afterwards: no new answer is generated.
    follow = _post(client, "test-session-2", "Are you still there?")
    assert follow.json()["status"] == "handoff"
    assert "human teammate already has" in follow.json()["answer"]


def test_no_reliable_answer_hands_off_without_inventing(client):
    resp = _post(client, "test-session-3",
                 "Can you recommend a good birthday gift for my uncle?")
    body = resp.json()
    assert body["status"] == "handoff"
    assert "do not have a reliable answer" in body["answer"]
    assert body["citations"] == []


def test_handoff_button_endpoint(client):
    resp = client.post("/api/handoff", json={
        "session_id": "test-session-4", "reason": "customer_requested_human"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "handoff"


def test_trace_endpoint_reflects_latest_run(client):
    _post(client, "test-session-5", "What is the returns policy?")
    trace = client.get("/api/trace/test-session-5").json()
    assert trace["state"] == "answered"
    assert trace["source_count"] >= 1
    assert trace["sources"][0]["label"].startswith("[1]")


def test_unknown_session_trace_is_empty(client):
    assert client.get("/api/trace/nope").json()["state"] == "empty"
