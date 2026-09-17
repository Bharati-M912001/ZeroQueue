"""Evidence-based confidence. The LLM never decides its own certainty.

Rules (simple on purpose, tuned during Phase 1 testing):
- no passage at all            -> low
- best passage score < 0.35    -> low  (weak evidence)
- best passage score >= 0.60   -> high
- otherwise                    -> medium
"""
from typing import List
from app.services.moss_service import Passage

HIGH = 0.60
LOW = 0.35


def band(passages: List[Passage]) -> str:
    if not passages:
        return "low"
    best = max(p.score for p in passages)
    if best < LOW:
        return "low"
    if best >= HIGH:
        return "high"
    return "medium"
