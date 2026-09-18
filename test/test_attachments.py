"""The attachment feature: text invoices feed the answer, bad files get
honest errors, and the OCR note is always truthful."""


def _post_file(client, session_id, message, filename, content, ctype):
    return client.post(
        "/api/chat",
        data={"session_id": session_id, "message": message},
        files={"file": (filename, content, ctype)},
    )


def test_text_invoice_feeds_the_answer(client):
    # A .txt "invoice" needs no OCR dependencies, so this test runs anywhere.
    invoice = (b"Nivara Botanics - Order NB-1042\nItem: Rosehip Serum\n"
               b"Status: Delivered\nAmount: Rs 1,299\n")
    resp = _post_file(client, "attach-1", "What is the returns policy for this order?",
                      "invoice.txt", invoice, "text/plain")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "answered"
    assert body["attachment_note"] is not None
    assert "invoice.txt" in body["attachment_note"]

    # The extracted text was stored and merged into the recorded query.
    from models import database as db
    with db.get_conn() as conn:
        att = conn.execute(
            "SELECT extracted_text FROM attachments ORDER BY id DESC LIMIT 1"
        ).fetchone()
        run = conn.execute(
            "SELECT query FROM retrieval_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert "NB-1042" in att["extracted_text"]
    assert "Attachment text (OCR)" in run["query"]
    assert "NB-1042" in run["query"]


def test_attachment_only_message_is_accepted(client):
    # No typed text at all: the file itself is the question.
    resp = _post_file(client, "attach-2", "", "note.txt",
                      b"When will my refund arrive?", "text/plain")
    assert resp.status_code == 200
    assert resp.json()["status"] in ("answered", "handoff")


def test_unsupported_file_type_gets_clear_error(client):
    resp = _post_file(client, "attach-3", "hi", "archive.zip",
                      b"PK\x03\x04", "application/zip")
    assert resp.status_code == 400
    assert "Unsupported file type" in resp.json()["detail"]


def test_empty_message_without_file_gets_clear_error(client):
    resp = client.post("/api/chat", data={"session_id": "attach-4", "message": ""})
    assert resp.status_code == 400


def test_invoice_attachment_does_not_hijack_retrieval(client):
    # Regression: a payment/GST-heavy invoice attached to "where is my
    # order?" must still retrieve the Orders FAQ, not the payments doc.
    invoice = (b"Nivara Botanics Tax Invoice\nOrder: NB-1042\n"
               b"GST No 29ABCDE1234F1Z5\nItem Rosehip Renewal Serum\n"
               b"Amount Rs 1,299\nPayment UPI\nShipping fee Rs 0\n"
               b"COD fee Rs 0\nStatus Delivered\nDate 12 Sep 2026\n")
    resp = _post_file(client, "attach-5", "where is my order?",
                      "File_1.txt", invoice, "text/plain")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "answered"
    assert "Orders And Order Status Faq" in body["citations"][0]["label"]


def test_llm_failure_falls_back_to_passage_quote(monkeypatch):
    """A Groq outage or retired model must never kill a live answer."""
    from app.services import answer_service, moss_service
    from app import config
    monkeypatch.setattr(config, "MOCK_MODE", False)
    monkeypatch.setattr(config, "GROQ_API_KEY", "gsk_fake")

    def boom(query, passages):
        raise RuntimeError("groq 404")
    monkeypatch.setattr(answer_service.llm, "grounded_answer", boom)

    passages = [moss_service.Passage(
        source_key="faq", title="Faq", section="Shipping",
        text="Orders ship in 3 days.", score=1.0, safe_url="")]
    text, citations = answer_service.build_answer("when does it ship?", passages)
    assert "Orders ship in 3 days." in text
    assert citations


def test_llm_sources_line_is_not_duplicated(monkeypatch):
    """The model ends with its own Sources: line; we append ours. One only."""
    from app.services import answer_service, moss_service
    from app import config
    monkeypatch.setattr(config, "MOCK_MODE", False)
    monkeypatch.setattr(config, "GROQ_API_KEY", "gsk_fake")
    monkeypatch.setattr(
        answer_service.llm, "grounded_answer",
        lambda q, ps: "Orders ship in 3 days.\n\nSources: [1] Faq - Shipping")

    passages = [moss_service.Passage(
        source_key="faq", title="Faq", section="Shipping",
        text="Orders ship in 3 days.", score=1.0, safe_url="")]
    text, _ = answer_service.build_answer("when does it ship?", passages)
    assert text.lower().count("sources:") == 1
    assert "Orders ship in 3 days." in text
