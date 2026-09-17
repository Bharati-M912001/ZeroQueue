"""Pytest helper: makes `app` and `models` importable when running `pytest`
from the repo root. You never need to edit this file."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
