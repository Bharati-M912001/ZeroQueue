"""Moss adapter: the ONLY file that should import the Moss SDK.

This is a placeholder with the intended interface. During Phase 1:
1. Install the Moss SDK per the hackathon docs.
2. Implement `index_documents()` to push knowledge/*.md sections into a
   Moss index with stable source keys (scripts/index_knowledge.py calls it).
3. Implement `search()` below and point app/services/moss_service.py at it,
   keeping the retrieval_ms timing exactly around this call.

Until then the app runs on the local stub in services/moss_service.py.
"""
from typing import List

from app import config
from app.services.moss_service import Passage


def search(query: str, top_k: int = 3) -> List[Passage]:
    raise NotImplementedError(
        "Wire the Moss SDK here (MOSS_API_KEY/MOSS_INDEX_NAME are read in "
        "app/config.py), then call this from services/moss_service.search().")


def index_documents() -> None:
    raise NotImplementedError("Push knowledge/*.md sections into Moss here.")
