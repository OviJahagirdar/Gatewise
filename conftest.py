"""
conftest.py - shared pytest fixtures.

Every test gets a brand new, empty database in a temporary folder, so the
tests never touch app.db and never depend on each other.

The trick: core/config.py reads SOCIETY_DB_PATH every time it opens a
connection, so setting that variable here is enough to redirect the whole app.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Put backend/ on the import path so "app.main" can be imported from anywhere.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import init_db  # noqa: E402
from app.main import app  # noqa: E402

SOCIETY_BODY = {
    "society_name": "Test Heights",
    "city": "Pune",
    "admin_full_name": "Asha K",
    "admin_username": "admin1",
    "admin_password": "admin123",
}

GUARD_BODY = {
    "username": "guard1",
    "password": "guard123",
    "full_name": "Ramu Guard",
    "role": "guard",
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A test client whose database lives in a temporary folder."""
    monkeypatch.setenv("SOCIETY_DB_PATH", str(tmp_path / "test.db"))
    init_db()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def society(client):
    """Create one society with an admin and return the response body."""
    response = client.post("/api/societies", json=SOCIETY_BODY)
    assert response.status_code == 200
    return response.json()


def login_headers(client, username: str, password: str) -> dict:
    """Log in and wrap the token in the header every protected route expects."""
    response = client.post(
        "/api/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture()
def admin_headers(client, society):
    return login_headers(client, "admin1", "admin123")


@pytest.fixture()
def guard_headers(client, society, admin_headers):
    response = client.post("/api/users", json=GUARD_BODY, headers=admin_headers)
    assert response.status_code == 200
    return login_headers(client, "guard1", "guard123")
