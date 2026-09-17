"""Push the knowledge base into Moss (Phase 1 of the real build).

Today this script shows you exactly WHAT would be indexed: every headed
section of every file in knowledge/. When the Moss SDK is wired in
app/adapters/moss.py, the last line does the real indexing - nothing else
in the app changes.

Run from the repo root:
    python scripts/index_knowledge.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import moss_service

sections = moss_service._load_sections()
print(f"Knowledge base: {len(sections)} sections "
      f"from {len(list(moss_service.KNOWLEDGE_DIR.glob('*.md')))} files\n")
for s in sections[:10]:
    print(f"  {s.source_key}  ({len(s.text)} chars)")
if len(sections) > 10:
    print(f"  ... and {len(sections) - 10} more")

print("\nTo index these into Moss, wire app/adapters/moss.py first, then add:")
print("    from app.adapters import moss")
print("    moss.index_documents()")
