# ZeroQueue file guide (plain English)

Read this before the demo so you can defend every part of the code.

## What happens when a customer sends a message (the request lifecycle)

1. **The page** (`src/web/components/ChatPanel.tsx`) sends the message -
   and the file, if one is attached - as one form to `POST /api/chat`.
   (In production the same message arrives from Intercom instead - see
   the big comment at the top of `app/api/intercom_webhook.py`.)
2. **The door** (`app/api/chat.py`) finds-or-creates the conversation,
   and if a file came in, hands it to the attachment service FIRST.
3. **The attachment service** (`app/services/attachment_service.py`)
   saves the file into `uploads/` and asks the OCR adapter to read it.
4. **The OCR adapter** (`app/adapters/ocr.py`) picks the right free
   reader: direct read for .txt, pypdf for digital PDFs, PyMuPDF +
   Tesseract for scanned PDFs, Tesseract for images, OpenCV + Tesseract
   for videos. It always returns an honest note about what it did.
5. **The pipeline** (`app/services/pipeline.py`) merges the typed message
   with the extracted attachment text, then:
   - asks the retrieval service for matching knowledge-base passages,
   - measures confidence from the evidence (never asks the LLM),
   - either hands off to a human or builds a cited answer.
6. **The retrieval seam** (`app/services/moss_service.py`) today does
   local keyword matching over `knowledge/`. The real Moss SDK replaces
   the inside of this one function (`app/adapters/moss.py`) - the timing
   wrapper and every caller stay untouched.
7. **The answer service** (`app/services/answer_service.py`) either
   quotes the strongest passage (mock mode, offline) or asks Groq to
   write the answer using ONLY the retrieved passages.
8. Everything is recorded in SQLite (`models/database.py`): the run, its
   retrieval time, its sources, the attachment text. The Trace strip on
   the page reads exactly this - so the numbers judges see are real
   measurements, not claims.

## The three rules the whole design follows

- **Never guess.** Low evidence -> hand to a human, with a summary.
- **Citations or it didn't happen.** Every answer names its sources.
- **One seam per external service.** Intercom, Groq, Moss, OCR each live
  in exactly one adapter file. You can swap any of them without touching
  the rest.
