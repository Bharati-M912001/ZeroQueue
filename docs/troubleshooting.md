# Troubleshooting (the errors you will actually hit, on Windows)

**`uvicorn` is not recognized** - the conda env is not active. Run
`conda activate GenAI` first, in the same terminal.

**`npm` is not recognized** - Node.js is not installed or the terminal is
stale. Install LTS from https://nodejs.org, then CLOSE and reopen the
terminal.

**Port already in use** - an old uvicorn/npm is still running. Find the
other terminal and press Ctrl+C. (This is why you keep two terminals open
and never reuse one for both.)

**Page says "backend offline"** - the API is not running, or it is on a
different port. Check http://localhost:8000/health in the browser.

**Attachment note says Tesseract is not installed** - see
docs/ocr-and-attachments.md. Set TESSERACT_CMD in `.env` after installing.

**`No module named 'app'` when running pytest** - run pytest from the repo
root (the folder with README.md), not from inside `test/`.

**Groq 429 errors** - the free tier daily token limit is spent. It resets
the next day; run heavy demos early. Mock mode never hits this.

**Intercom webhook silent** - ngrok stopped or the URL changed. Free ngrok
URLs change on every restart; update the Intercom webhook endpoint.

**`invalid_signature`** - INTERCOM_WEBHOOK_SECRET in `.env` does not match
the secret shown in Intercom's webhook settings.

**The bot answers itself in a loop** - it cannot; loop prevention ignores
any non-customer author. If you ever see this, the author type check in
`app/api/intercom_webhook.py` is the place to look.
