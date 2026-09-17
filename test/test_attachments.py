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
