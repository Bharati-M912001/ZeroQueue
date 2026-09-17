"""Test setup: use a throwaway SQLite database and force MOCK_MODE so no
external API call can ever happen during tests."""
import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='.db')}"
os.environ["MOCK_MODE"] = "true"
os.environ["INTERCOM_WEBHOOK_SECRET"] = ""  # signature tested separately

import pytest
from fastapi.testclient import TestClient

from app.main import app
from models import database as db


@pytest.fixture(scope="session")
def client():
    db.init_db()
    return TestClient(app)
