"""Wipe all demo state (conversations, traces, attachments) so the demo
can be re-run from a clean slate. Run from the repo root, backend ON:

    python scripts/reset_demo.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from app import config

resp = httpx.post(
    "http://localhost:8000/api/demo/reset",
    headers={"X-Demo-Secret": config.DEMO_RESET_SECRET},
    timeout=10,
)
print(resp.status_code, resp.json())
