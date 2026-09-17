"""OCR adapter: the ONLY file that knows HOW text is pulled out of a file.

Routing by kind:
- document (.txt/.md)  -> read the file directly. No dependencies.
- document (.pdf)      -> pypdf reads the text layer; if the PDF is a
                          scan (no text layer), PyMuPDF renders each page
                          to an image and Tesseract OCRs it.
- image                -> Tesseract OCR locally (default, free), or the
                          free Groq vision model when OCR_PROVIDER=groq
                          and MOCK_MODE=false.
- video                -> OpenCV samples up to 5 frames, Tesseract OCRs
                          each frame, duplicate lines are removed.

How Tesseract is run (this matters on Windows):
We call the tesseract PROGRAM directly (`tesseract <image> stdout`) and
capture its output. We deliberately do NOT use the pytesseract library:
pytesseract juggles temporary files behind the scenes, and on Windows
that regularly fails with "[WinError 5] Access is denied" even when
Tesseract itself is installed correctly. Calling the program directly
with the image path - exactly like you would in a terminal - avoids that
whole class of bugs.

Every failure path returns an honest note instead of crashing, so the
chat keeps working and tells the customer (and you) exactly what is
missing or misconfigured.
"""
import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from app import config


def extract_text(path: Path, kind: str, original_name: str = "") -> Tuple[str, str]:
    """Return (extracted_text, note). `note` always tells the truth about
    what happened, including "could not read this because ..."."""
    name = original_name or path.name
    try:
        if kind == "document":
            return _extract_document(path, name)
        if kind == "image":
            return _extract_image(path, name)
        if kind == "video":
            return _extract_video(path, name)
    except Exception as exc:  # never let a bad file break the chat
        return "", f"Could not read {name}: {exc}"
    return "", f"Unsupported attachment kind '{kind}' for {name}."


# ---------------------------------------------------------------- documents

def _extract_document(path: Path, name: str) -> Tuple[str, str]:
    if path.suffix.lower() in (".txt", ".md"):
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        return text, f"Read {_line_count(text)} lines of text from {name}."

    # PDF: first try the embedded text layer (digital invoices have one).
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    except ImportError:
        return "", ("pypdf is not installed. Run: pip install pypdf "
                    "(see requirements.txt).")
    if text:
        return text, f"Read the text layer of {name} ({_line_count(text)} lines)."

    # Scanned PDF: render pages to images and OCR them.
    return _ocr_scanned_pdf(path, name)


def _ocr_scanned_pdf(path: Path, name: str) -> Tuple[str, str]:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return "", (f"{name} looks like a scanned PDF (no text layer) and "
                    "PyMuPDF is not installed to render it. Run: "
                    "pip install PyMuPDF")
    doc = fitz.open(str(path))
    chunks: List[str] = []
    for page in doc:
        pix = page.get_pixmap(dpi=200)
        img_path = path.with_suffix(f".page{page.number}.png")
        pix.save(str(img_path))
        page_text, _ = _ocr_image_file(img_path)
        if page_text:
            chunks.append(page_text)
        img_path.unlink(missing_ok=True)
    text = "\n".join(chunks).strip()
    if text:
        return text, f"OCR read {_line_count(text)} lines from scanned PDF {name}."
    return "", (f"OCR found no readable text in {name}. If Tesseract is not "
                "installed yet, see docs/ocr-and-attachments.md.")


# ------------------------------------------------------------------- images

def _extract_image(path: Path, name: str) -> Tuple[str, str]:
    if config.OCR_PROVIDER == "groq" and not config.MOCK_MODE:
        from app.adapters import llm
        try:
            text = llm.vision_extract(path).strip()
            if text:
                return text, f"Groq vision read {_line_count(text)} lines from {name}."
        except Exception as exc:
            return "", (f"Groq vision could not read {name} ({exc}). "
                        "Set OCR_PROVIDER=tesseract to use local OCR instead.")
        return "", f"Groq vision found no readable text in {name}."
    return _ocr_image_file(path, name)


def _find_tesseract() -> Tuple[Optional[str], str]:
    """Locate the tesseract executable. Returns (path or None, how-we-looked).

    Search order:
    1. TESSERACT_CMD from .env - you may point it at the exe OR at the
       install folder; a folder is completed to <folder>/tesseract.exe.
    2. `tesseract` on the PATH (the installer offers this as a checkbox).
    3. The standard Windows install locations.
    4. Standard Linux/macOS locations (for non-Windows development).
    """
    candidates: List[Path] = []
    if config.TESSERACT_CMD:
        cmd = config.TESSERACT_CMD.strip().strip('"').strip("'")
        p = Path(cmd)
        # On Windows, allow pointing at the install FOLDER too: complete
        # any path that does not end in .exe to <path>/tesseract.exe.
        if os.name == "nt" and p.suffix.lower() != ".exe":
            p = p / "tesseract.exe"
        candidates.append(p)
    on_path = shutil.which("tesseract")
    if on_path:
        candidates.append(Path(on_path))
    if os.name == "nt":
        for env_var in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
            base = os.environ.get(env_var)
            if base:
                candidates.append(Path(base) / "Tesseract-OCR" / "tesseract.exe")
    else:
        candidates += [Path("/usr/bin/tesseract"), Path("/usr/local/bin/tesseract")]
    for c in candidates:
        if c.is_file():
            return str(c), f"found at {c}"
    return None, "not found in TESSERACT_CMD, PATH, or the standard install folder"


def _run_tesseract(exe: str, image_path: Path) -> str:
    """Run `tesseract <image> stdout` and return what it reads. This is the
    same command you can type in a terminal yourself - no temp-file magic."""
    proc = subprocess.run(
        [exe, str(image_path), "stdout"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "tesseract failed").strip()[:200])
    return proc.stdout.strip()


def _ocr_image_file(path: Path, name: str = "") -> Tuple[str, str]:
    """Local Tesseract OCR. Free, offline, no account needed."""
    label = name or path.name
    exe, how = _find_tesseract()
    if not exe:
        return "", ("Tesseract is not installed on this machine, so the "
                    "image could not be read. It is a free 2-minute install "
                    "- see docs/ocr-and-attachments.md.")
    try:
        text = _run_tesseract(exe, path)
    except PermissionError:
        return "", ("Windows refused to run Tesseract (Access is denied). "
                    "Check TESSERACT_CMD in .env: it must point to "
                    "tesseract.exe or its folder, e.g. "
                    "C:\\Program Files\\Tesseract-OCR\\tesseract.exe")
    except FileNotFoundError:
        return "", ("Tesseract was found but would not start. Re-check "
                    "TESSERACT_CMD in .env or reinstall Tesseract "
                    "(docs/ocr-and-attachments.md).")
    except subprocess.TimeoutExpired:
        return "", f"Tesseract took too long reading {label} and was stopped."
    except OSError as exc:
        return "", f"Tesseract could not be run ({exc}). Check TESSERACT_CMD in .env."
    if text:
        return text, f"OCR read {_line_count(text)} lines from {label}."
    return "", f"OCR ran on {label} but found no readable text."


# ------------------------------------------------------------------- videos

def _extract_video(path: Path, name: str, max_frames: int = 5) -> Tuple[str, str]:
    """Sample a few frames and OCR them. Simple on purpose: enough for a
    customer filming a damaged item, a screen, or a paper invoice."""
    try:
        import cv2
    except ImportError:
        return "", ("OpenCV is not installed, so video cannot be read. Run: "
                    "pip install opencv-python-headless")
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return "", f"Could not open video {name}."
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    step = max(frame_count // (max_frames + 1), 1)
    texts: List[str] = []
    for i in range(1, max_frames + 1):
        cap.set(cv2.CAP_PROP_POS_FRAMES, min(i * step, frame_count - 1))
        ok, frame = cap.read()
        if not ok:
            continue
        tmp = path.with_suffix(f".frame{i}.png")
        cv2.imwrite(str(tmp), frame)
        frame_text, _ = _ocr_image_file(tmp)
        if frame_text:
            texts.append(frame_text)
        tmp.unlink(missing_ok=True)
    cap.release()
    text = _dedupe_lines("\n".join(texts))
    if text:
        return text, f"OCR read {_line_count(text)} unique lines from video {name}."
    return "", (f"OCR found no readable text in the sampled frames of {name}. "
                "If Tesseract is missing, see docs/ocr-and-attachments.md.")


# ------------------------------------------------------------------ helpers

def _line_count(text: str) -> int:
    return len([ln for ln in text.splitlines() if ln.strip()]) if text else 0


def _dedupe_lines(text: str) -> str:
    seen, out = set(), []
    for line in text.splitlines():
        key = " ".join(line.split()).lower()
        if key and key not in seen:
            seen.add(key)
            out.append(line.strip())
    return "\n".join(out)
