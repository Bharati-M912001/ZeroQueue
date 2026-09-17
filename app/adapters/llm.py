"""Groq LLM adapter (free tier). Only called when MOCK_MODE=false.

The prompt sends ONLY: the customer question, retrieved passages with
source ids, and the response rules. The model is instructed to answer
strictly from those passages so it cannot hallucinate policy.
"""
from pathlib import Path
from typing import List

import httpx

from app import config
from app.services.moss_service import Passage

# Windows-safe path handling: pathlib works on every OS. (Building the
# path with string splits on "/" breaks on Windows, where paths use "\".)
_PROMPT_TEMPLATE = (Path(__file__).resolve().parent.parent
                    / "prompts" / "support_answer.txt").read_text(encoding="utf-8")


def grounded_answer(query: str, passages: List[Passage]) -> str:
    blocks = "\n\n".join(
        f"[{i}] {p.title} - {p.section}\n{p.text}" for i, p in enumerate(passages, 1))
    prompt = _PROMPT_TEMPLATE.replace("{question}", query).replace("{passages}", blocks)
    resp = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
        json={"model": config.GROQ_MODEL,
              "messages": [{"role": "user", "content": prompt}],
              "temperature": 0},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def vision_extract(image_path: Path) -> str:
    """Read text out of an image with the free Groq vision model.
    Used for the attachment feature when OCR_PROVIDER=groq."""
    import base64
    mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    b64 = base64.b64encode(image_path.read_bytes()).decode()
    resp = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
        json={
            "model": config.GROQ_VISION_MODEL,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text",
                     "text": ("Extract all readable text from this image, "
                              "exactly as written. If it is an invoice or "
                              "receipt, keep line items, order numbers and "
                              "amounts. Reply with the text only.")},
                    {"type": "image_url",
                     "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }],
            "temperature": 0,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()
