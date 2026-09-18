"""Builds the grounded answer from retrieved passages.

MOCK_MODE (default): no LLM call. The answer is assembled from the top
passage text with explicit citations. This keeps the system fully offline
and makes the citation contract visible.

REAL BUILD: set MOCK_MODE=false and GROQ_API_KEY; then the passages,
source ids and rules go to the Groq model (see app/adapters/llm.py and
app/prompts/support_answer.txt) and the model must answer ONLY from them.
"""
import logging
import re
from typing import List, Tuple

from app import config
from app.adapters import llm
from models.schemas import Citation
from app.services.moss_service import Passage

log = logging.getLogger("zeroqueue.answer")

# The LLM is told to end its answer with its own "Sources:" line, and we
# append the canonical citation line ourselves - strip the model's line
# first or the customer sees "Sources: ... Sources: ..." (the duplication
# spotted in the Sep 18 live test).
_SOURCES_TAIL = re.compile(r"\s*sources\s*:.*\Z", re.IGNORECASE | re.DOTALL)


def make_citations(passages: List[Passage]) -> List[Citation]:
    """At most 3 citations, labelled like: [1] Faq - Shipping Times."""
    out = []
    for i, p in enumerate(passages[:3], start=1):
        out.append(Citation(label=f"[{i}] {p.title} - {p.section}",
                            url=p.safe_url or None))
    return out


def _quote_passage(passages: List[Passage]) -> str:
    """Quote the strongest passage directly. Honest and deterministic."""
    top = passages[0]
    body = " ".join(top.text.split())[:400]
    return (f"Based on our {top.title.lower()} ({top.section}): {body}\n\n"
            f"Next step: if this does not solve it, say \"human\" and "
            f"a teammate will take over.")


def build_answer(query: str, passages: List[Passage]) -> Tuple[str, List[Citation]]:
    citations = make_citations(passages)
    if not config.MOCK_MODE and config.GROQ_API_KEY:
        # Real path: grounded generation constrained to the passages.
        # If the LLM call fails (outage, retired model, bad key), fall back
        # to quoting the passage - a live demo must never die on a 404.
        try:
            text = llm.grounded_answer(query, passages)
            text = _SOURCES_TAIL.sub("", text).rstrip()
        except Exception:
            log.exception("Groq answer failed - falling back to passage quote")
            text = _quote_passage(passages)
    else:
        # Mock path: quote the strongest passage directly, which is exactly
        # what the first live demo needs.
        text = _quote_passage(passages)
    source_line = "  ".join(c.label for c in citations)
    return f"{text}\n\nSources: {source_line}", citations
