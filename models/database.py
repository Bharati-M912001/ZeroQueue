"""SQLite storage for ZeroQueue.

One small file-based database (zeroqueue.db), created automatically on
startup. Tables: conversations, messages, retrieval_runs, sources,
handoffs - plus processed_events for webhook deduplication (idempotency)
and attachments for the OCR feature.
"""
import sqlite3
import time
from contextlib import contextmanager

from app.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    intercom_conversation_id TEXT UNIQUE,   -- set in the Intercom path
    session_id TEXT UNIQUE,                 -- anonymous id from the web page
    status TEXT NOT NULL DEFAULT 'ai_active', -- ai_active | handoff | closed
    last_customer_text TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    intercom_event_id TEXT UNIQUE,          -- UNIQUE = webhook dedupe guard
    author_type TEXT NOT NULL,              -- customer | bot | admin
    text TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS retrieval_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    query TEXT NOT NULL,
    retrieval_ms REAL,                      -- Moss-only time
    total_ms REAL,                          -- whole answer pipeline time
    confidence TEXT,                        -- high | medium | low
    status TEXT NOT NULL,                   -- answered | escalated | error
    error_code TEXT,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    retrieval_run_id INTEGER NOT NULL,
    source_key TEXT NOT NULL,
    title TEXT NOT NULL,
    section TEXT,
    safe_url TEXT,                          -- only intentionally public links
    score REAL,
    rank INTEGER
);
CREATE TABLE IF NOT EXISTS handoffs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    issue_type TEXT,
    summary TEXT,
    assigned_to TEXT,
    created_at REAL NOT NULL
);
-- Webhook idempotency: each Intercom event id is processed at most once.
CREATE TABLE IF NOT EXISTS processed_events (
    event_id TEXT PRIMARY KEY,
    received_at REAL NOT NULL
);
-- Customer uploads (image / video / invoice) and what OCR read out of them.
CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    content_type TEXT,
    extracted_text TEXT,                    -- what OCR/parsing read
    note TEXT,                              -- honest status line about the read
    created_at REAL NOT NULL
);
"""


@contextmanager
def get_conn():
    """Open a connection that dict-ifies rows and always closes."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def now() -> float:
    return time.time()
