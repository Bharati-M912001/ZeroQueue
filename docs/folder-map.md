# ZeroQueue folder map

```
zeroqueue/
  .env                  <- YOUR secrets (you create it from .env.example; never commit)
  .env.example          <- the template, safe to commit
  requirements.txt      <- Python packages for the backend
  conftest.py           <- makes `pytest` work from the repo root (ignore it)
  README.md             <- start here

  app/                  <- the FastAPI backend (all the Python that runs the product)
    main.py             <- entrypoint: builds the app, plugs in the routes
    config.py           <- reads the ONE root .env; every setting lives here
    api/                <- HTTP endpoints (the "doors" into the backend)
      chat.py           <- POST /api/chat (message + optional attachment), /api/handoff
      intercom_webhook.py <- POST /api/webhooks/intercom (read the big comment!)
      trace.py          <- GET /api/trace/{session}, POST /api/demo/reset
      health.py         <- GET /health
    services/           <- the business logic (what the product actually DOES)
      pipeline.py       <- retrieve -> confidence -> answer/handoff (shared by all channels)
      moss_service.py   <- retrieval seam: local stub today, real Moss tomorrow
      answer_service.py <- builds the grounded, cited answer
      confidence.py     <- evidence-based confidence (never the LLM's opinion)
      escalation.py     <- when to stop and hand to a human
      attachment_service.py <- saves uploads and routes them to OCR
    adapters/           <- every external service, one file each
      intercom.py       <- reply / note / assign / download attachments
      llm.py            <- Groq: grounded answers + vision OCR
      moss.py           <- Moss SDK placeholder (Phase 1 wiring point)
      ocr.py            <- how text is pulled out of images / videos / PDFs
    prompts/
      support_answer.txt <- the LLM's rules (answer ONLY from the passages)

  models/               <- data layer
    database.py         <- SQLite schema + connection helper
    schemas.py          <- pydantic request/response shapes

  src/web/              <- the web page (Next.js)
    app/page.tsx        <- the one screen
    components/ChatPanel.tsx <- messages, input, attach button
    components/TraceCard.tsx <- the Moss Trace strip
    lib/session.ts      <- anonymous session id
    next.config.js      <- loads NEXT_PUBLIC_* from the root .env (single .env rule)

  test/                 <- automated tests (run: pytest test -q)
    test_webhook.py     <- webhook: 200 fast, dedupe, loop prevention, signature
    test_chat.py        <- answers with citations, escalation, trace
    test_attachments.py <- the OCR/attachment feature

  scripts/              <- helper commands
    setup.bat           <- one-time install (Windows)
    run_backend.bat     <- start the API
    run_web.bat         <- start the page
    run_tests.bat       <- run the tests
    reset_demo.py       <- wipe demo state
    index_knowledge.py  <- preview/push the knowledge base into Moss
    make_sample_invoice_image.py <- create a fake invoice image for OCR demos

  docs/                 <- plain-English documentation
    folder-map.md       <- this file
    file-guide.md       <- what each important file does, in words
    intercom-setup.md   <- connect the real Intercom Messenger
    ocr-and-attachments.md <- install Tesseract, how the feature works
    troubleshooting.md  <- fixes for the errors you will actually hit
    samples/            <- demo files to attach in the chat

  knowledge/            <- the Nivara Botanics knowledge base (18 files, frozen v1)

  uploads/              <- customer attachments land here at runtime (git-ignored)
```
