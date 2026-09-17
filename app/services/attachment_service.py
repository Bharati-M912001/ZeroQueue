"""Attachment service: saves customer uploads and reads text out of them.

The customer can attach an IMAGE (png/jpg/...), a VIDEO (mp4/...) or an
INVOICE/document (pdf/txt) to their chat message. This service:
  1. saves the file into uploads/,
  2. extracts readable text (OCR for images/video frames, text parsing
     for PDFs/txt) via app/adapters/ocr.py,
  3. returns the extracted text plus an honest one-line note about what
     happened (shown in the chat and stored in the database).

Everything here is FREE: local Tesseract OCR, pypdf/PyMuPDF, OpenCV.
No paid API is ever needed for the attachment feature.
"""
import time
import uuid
from pathlib import Path
from typing import Optional, Tuple

from app import config
from app.adapters import ocr
from models import database as db

# What the customer is allowed to upload, and how we read each kind.
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".avi"}
DOC_EXTS = {".pdf", ".txt", ".md"}


class UnsupportedFileError(ValueError):
    """Raised when the upload is not an image, video, or document we read."""


def kind_for(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in DOC_EXTS:
        return "document"
    raise UnsupportedFileError(
        f"Unsupported file type '{ext or filename}'. "
        "You can attach an image (png, jpg), a video (mp4), "
        "or a document (pdf, txt).")


def save_and_extract(conversation_id: int, filename: str, data: bytes,
                     content_type: str = "") -> Tuple[str, str]:
    """Save the upload, extract its text, record it, return (text, note).

    `text` is what the answer pipeline will see (may be empty).
    `note` is a short honest status line, e.g. "Read 6 lines from
    invoice.pdf" or "Tesseract is not installed, so the image could not
    be read - see docs/ocr-and-attachments.md".
    """
    kind = kind_for(filename)  # raises UnsupportedFileError when unknown
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise UnsupportedFileError(
            f"File is too large ({len(data) // (1024 * 1024)} MB). "
            f"The limit is {config.MAX_UPLOAD_MB:.0f} MB.")

    # 1. Save under a random name so two customers never collide.
    safe_name = f"{uuid.uuid4().hex[:12]}{Path(filename).suffix.lower()}"
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored = config.UPLOAD_DIR / safe_name
    stored.write_bytes(data)

    # 2. Extract text with the free local readers.
    text, note = ocr.extract_text(stored, kind, original_name=filename)

    # 3. Record it (the trace/handoff can then show what was read).
    with db.get_conn() as conn:
        conn.execute(
            "INSERT INTO attachments (conversation_id, filename, stored_path,"
            " content_type, extracted_text, note, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (conversation_id, filename, str(stored), content_type,
             text, note, db.now()))
    return text, note
