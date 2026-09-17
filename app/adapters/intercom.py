"""Intercom adapter: every Intercom API call lives in this one file.

MOCK_MODE (default): functions log what they WOULD send and return a fake
success, so the whole webhook pipeline runs with no Intercom account.

REAL BUILD: set MOCK_MODE=false and INTERCOM_ACCESS_TOKEN (the ROTATED
token - the old one was exposed in chat on Sep 16). The API version and
bodies below match Intercom API v2.11 as verified during the live spike.
"""
import logging
from typing import Any, Dict

import httpx

from app import config

log = logging.getLogger("zeroqueue.intercom")
logging.basicConfig(level=logging.INFO)


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {config.INTERCOM_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "Intercom-Version": "2.11",
    }


def _live() -> bool:
    return not config.MOCK_MODE and bool(config.INTERCOM_ACCESS_TOKEN)


def reply(conversation_id: str, text: str) -> Dict[str, Any]:
    """Post the bot answer into the same customer conversation."""
    if not _live():
        log.info("[MOCK] would reply to conversation %s: %.120s", conversation_id, text)
        return {"mock": True}
    resp = httpx.post(
        f"{config.INTERCOM_API_BASE}/conversations/{conversation_id}/reply",
        headers=_headers(),
        json={"message_type": "comment",
              "type": "admin",
              "admin_id": config.INTERCOM_ADMIN_ID,
              "body": text},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def add_note(conversation_id: str, note: str) -> Dict[str, Any]:
    """Attach the internal handoff summary (teammates see it, customer does not)."""
    if not _live():
        log.info("[MOCK] would add note to %s: %.120s", conversation_id, note)
        return {"mock": True}
    resp = httpx.post(
        f"{config.INTERCOM_API_BASE}/conversations/{conversation_id}/reply",
        headers=_headers(),
        json={"message_type": "note",
              "type": "admin",
              "admin_id": config.INTERCOM_ADMIN_ID,
              "body": note},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def assign(conversation_id: str) -> Dict[str, Any]:
    """Assign the conversation to the human team."""
    if not _live():
        log.info("[MOCK] would assign conversation %s to team %s",
                 conversation_id, config.INTERCOM_TEAM_ID)
        return {"mock": True}
    resp = httpx.post(
        f"{config.INTERCOM_API_BASE}/conversations/{conversation_id}",
        headers=_headers(),
        json={"assignee_id": config.INTERCOM_TEAM_ID, "type": "team"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def download_attachment(url: str) -> bytes:
    """Download a customer attachment that arrived with a Messenger message.
    Intercom attachment URLs need the same Bearer token as the API."""
    if not _live():
        log.info("[MOCK] would download attachment %s", url)
        return b""
    resp = httpx.get(url, headers=_headers(), timeout=60, follow_redirects=True)
    resp.raise_for_status()
    return resp.content
