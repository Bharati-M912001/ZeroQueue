# ZeroQueue

AI customer support that answers in seconds - grounded in your knowledge
base, with citations, real latency measurements, and a clean handoff to a
human when it does not know. Customers can also **attach an image, a
video, or an invoice** to their message; ZeroQueue reads it with OCR and
uses what it finds (order numbers, products, error text) in the answer.

Built for the YC Fall 2026 x Moss Zero-Latency Builder Sprint.
Runs on your laptop with zero accounts and zero cost (mock mode).

---

## What works out of the box

- The ZeroQueue web page: one simple chat screen with an **Attach** button
  and the **Moss Trace** strip (retrieval ms, total ms, sources, confidence).
- Grounded answers from the 18-file Nivara Botanics knowledge base in
  `knowledge/`, every answer ending in a `Sources:` line.
- Attachment reading: txt/PDF invoices with zero setup; images, scanned
  PDFs, and videos with the free Tesseract install (see
  `docs/ocr-and-attachments.md`).
- Human handoff: say "human", or ask something the knowledge base cannot
  answer - the bot stops, summarizes, and hands off instead of guessing.
- The Intercom webhook endpoint (signature check, immediate 200, dedupe,
  loop prevention), carried over from the live-verified earlier build.
- 14 passing automated tests, all offline.

What is still a seam (by design): real Moss retrieval plugs into ONE
function (`app/adapters/moss.py`); Groq writes the final wording when you
turn mock mode off. Nothing else in the app changes when you do either.

## Websites and accounts you will need (all free)

| What | Where | When you need it |
|---|---|---|
| Python packages | pip (in your `GenAI` conda env) | setup |
| Node.js LTS | https://nodejs.org | setup, for the web page |
| Tesseract OCR | https://github.com/UB-Mannheim/tesseract/wiki | image/scanned-PDF/video OCR |
| Groq API key | https://console.groq.com -> API Keys | real LLM answers (mock mode off) |
| ngrok | https://ngrok.com | letting Intercom reach your laptop |
| Intercom | https://app.intercom.io | the production Messenger channel |
| Moss | per the hackathon docs | real retrieval (Phase 1) |

## Setup (Windows, one command at a time)

Open a terminal in the `zeroqueue` folder (where this README is), then:

```
scripts\setup.bat
```

That creates your `.env`, installs the Python packages into the `GenAI`
conda env, and installs the web page packages. If `conda` is not
recognized in a fresh terminal, open "Anaconda Prompt" instead.

## Run it (two terminals, keep both open)

Terminal 1 - the backend:

```
scripts\run_backend.bat
```

Check: open http://localhost:8000/health - you should see `"status": "ok"`.

Terminal 2 - the web page:

```
scripts\run_web.bat
```

Open http://localhost:3000.

## Try the demo (5 minutes)

1. Ask **"How long does shipping take?"** - watch the cited answer and
   the Moss Trace numbers fill in.
2. Click **Attach**, pick `docs\samples\invoice-sample.txt`, and ask
   **"Can I return this order?"** - the answer uses the policy AND the
   invoice. The chat shows an honest note about what was read.
3. Ask **"Can you recommend a birthday gift for my uncle?"** - the bot
   refuses to guess and hands off to a human. The Trace switches to
   "escalated" with the reason.
4. Send anything else - the bot stays paused because a human owns the
   conversation now. That is the intended behavior.

## Run the tests

```
scripts\run_tests.bat
```

14 tests, all offline: webhook (fast 200, dedupe, loop prevention, bad
signature rejected), chat (citations, escalation, trace), and the
attachment feature (invoice text feeds the answer, bad file types get
clear errors).

## Understand the code (do this before the demo)

1. `docs/folder-map.md` - what every folder is for.
2. `docs/file-guide.md` - the request lifecycle in plain English: what
   happens from "customer hits Send" to "answer with citations".
3. The big comment at the top of `app/api/intercom_webhook.py` - the
   webhook flow, step by step. Read it once and the webhook is yours.

## Connect the real services (when ready)

- **Groq**: paste your free key into `.env` (GROQ_API_KEY) and set
  MOCK_MODE=false. Answers are now written by the LLM using ONLY the
  retrieved passages.
- **Intercom**: `docs/intercom-setup.md`. Use the NEW rotated token -
  the old one was exposed in chat on Sep 16; revoke it in Intercom and
  never send tokens through chat. The webhook URL Intercom needs is
  `https://<your-ngrok-url>/api/webhooks/intercom`.
- **Moss**: `python scripts\index_knowledge.py` previews the sections;
  wire the SDK in `app/adapters/moss.py` per the hackathon docs.

## The one-.env rule

There is exactly ONE `.env`, at the repo root. The backend reads it; the
web page reads its NEXT_PUBLIC_* values from the same file
(`src/web/next.config.js`). `.env` is git-ignored - never commit it,
never paste keys into chat.

## Rules that keep you safe

- Real keys go ONLY in `.env`. If a key ever leaks, rotate it at the
  provider and replace it in `.env`.
- `uploads/` and `zeroqueue.db` are git-ignored runtime data.
- `POST /api/demo/reset` (via `python scripts\reset_demo.py`) wipes demo
  state between rehearsal runs.
