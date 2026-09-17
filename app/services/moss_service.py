"""Retrieval service: the Moss seam.

`search()` is the ONE function the rest of the app calls for retrieval.
Right now it keyword-matches the local files in /knowledge so the whole
system runs offline with no credentials.

FOR THE REAL BUILD: keep this function signature and replace the body
with Moss index/search calls (see app/adapters/moss.py). The timing
wrapper (retrieval_ms) stays exactly where it is: start the clock
immediately before the Moss search call, stop it immediately after.
Nothing else in the app changes.
"""
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"

# Words that carry no retrieval signal.
_STOP = {"the", "a", "an", "is", "it", "my", "i", "do", "to", "of", "and",
         "or", "for", "on", "in", "me", "can", "what", "how", "does", "are",
         "was", "were", "will", "would", "should", "could", "get", "got",
         "where", "when", "who", "whom", "whose", "which", "why",
         "this", "that", "these", "those", "there", "here",
         "their", "them", "they", "we", "you", "your", "yours",
         "he", "she", "his", "her", "its", "am", "be", "been", "being",
         "have", "has", "had", "did", "doing", "tell", "say", "says",
         "please", "want", "need", "know", "about"}


@dataclass
class Passage:
    source_key: str      # stable id, e.g. "06-returns...md#returns-window"
    title: str           # document title
    section: str         # heading of the passage
    text: str            # passage text shown to the answer service
    safe_url: str = ""   # only set if the document is intentionally public
    score: float = 0.0   # 0..1 evidence strength (drives confidence)


@dataclass
class RetrievalResult:
    passages: List[Passage] = field(default_factory=list)
    retrieval_ms: float = 0.0


def _tokenize(text: str) -> List[str]:
    # Naive stemming: drop a trailing "s" so "take" matches "takes" and
    # "return" matches "returns". The real Moss adapter replaces all of this.
    out = []
    for tok in re.findall(r"[a-z0-9]+", text.lower()):
        if tok in _STOP:
            continue
        out.append(tok[:-1] if len(tok) > 3 and tok.endswith("s") else tok)
    return out


def _load_sections() -> List[Passage]:
    """Split every knowledge/*.md file into passages.

    Files with "## Heading" structure become one passage per heading.
    Files written as flat paragraphs (most of the Nivara corpus) become
    one passage per paragraph - otherwise the whole file would be a single
    blob and retrieval could only match it as one giant chunk.
    """
    sections: List[Passage] = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        title = path.stem.replace("_", " ").replace("-", " ", 1).strip()
        title = title.lstrip("0123456789 ").replace("-", " ").title()
        current_heading, buf = "Overview", []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                if buf:
                    sections.append(Passage(
                        source_key=f"{path.name}#{_slug(current_heading)}",
                        title=title, section=current_heading,
                        text="\n".join(buf).strip()))
                current_heading, buf = line[3:].strip(), []
            elif not line.startswith("# "):
                buf.append(line)
        if buf:
            sections.append(Passage(
                source_key=f"{path.name}#{_slug(current_heading)}",
                title=title, section=current_heading,
                text="\n".join(buf).strip()))
        # Flat file (no ## headings): split the single blob into paragraphs.
        flat = [s for s in sections if s.source_key.startswith(f"{path.name}#")]
        if len(flat) == 1 and "## " not in path.read_text(encoding="utf-8"):
            sections = [s for s in sections if s is not flat[0]]
            paragraphs = [par.strip() for par in flat[0].text.split("\n\n") if par.strip()]
            for i, par in enumerate(paragraphs, start=1):
                # Label the passage by its opening words so citations and
                # the trace read like a human wrote them.
                lead = " ".join(par.split())[:48].strip()
                section = lead + ("..." if len(" ".join(par.split())) > 48 else "")
                sections.append(Passage(
                    source_key=f"{path.name}#p{i}",
                    title=title, section=section, text=par))
    return sections


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def search(query: str, top_k: int = 3) -> RetrievalResult:
    """Return the top passages for a question plus the retrieval time.

    STUB SCORING: share of query keywords found in the section text.
    Replace this scoring block with the real Moss search call; keep the
    perf_counter lines wrapped tightly around that call.
    """
    start = time.perf_counter()                       # <- clock starts here
    query_terms = set(_tokenize(query))
    scored: List[Passage] = []
    for passage in _load_sections():
        body_terms = set(_tokenize(passage.title + " " + passage.section + " " + passage.text))
        if not query_terms:
            continue
        score = len(query_terms & body_terms) / len(query_terms)
        if score > 0:
            # Title bonus: a passage from a document whose TITLE matches the
            # question ("Orders and Order Status FAQ" for "where is my
            # order?") beats a passage that merely mentions the word in
            # passing. Generic words like "order" appear in almost every
            # policy doc, so this bonus is what puts the right document
            # on top. Score may exceed 1.0 - that is fine, it is only a
            # ranking number (confidence thresholds still work).
            title_hits = len(query_terms & set(_tokenize(passage.title)))
            score += 0.2 * (title_hits / len(query_terms))
            passage.score = round(score, 3)
            scored.append(passage)
    scored.sort(key=lambda p: p.score, reverse=True)
    top = scored[:top_k]
    retrieval_ms = (time.perf_counter() - start) * 1000  # <- clock stops here
    return RetrievalResult(passages=top, retrieval_ms=round(retrieval_ms, 1))
