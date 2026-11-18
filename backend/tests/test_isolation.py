"""
Person 4 — society data-isolation test.

The single most important rule in the contract:

    every backend route gets society_id from get_current_user(request) and
    NEVER trusts a society_id sent by the browser, and every SQL query filters
    WHERE society_id = ?

This file creates two separate societies (A and B) and proves they cannot see,
edit or delete each other's flats, staff, entries or QR check-ins.

Run it from the society-gate folder:

    pip install pytest httpx
    pytest backend/tests -v
"""

import pathlib
import sys
import uuid

import pytest

# Let "backend" be importable whichever folder pytest is started from.
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

pytest.importorskip("httpx", reason="pip install httpx (needed by FastAPI's TestClient)")

try:
    from fastapi.testclient import TestClient
    from backend.main import app
except ModuleNotFoundError as exc:  # backend/ not written yet
    pytest.skip(f"Backend is not importable yet: {exc}", allow_module_level=True)


@pytest.fixture(scope="module")
def client():
    # "with" runs FastAPI's startup event, which creates the tables.
    with TestClient(app) as test_client:
        yield test_client


# --------------------------------------------------------------------------
# Small helpers (kept local so this file runs on its own)
# --------------------------------------------------------------------------

def unique(prefix):
    return prefix + "_" + uuid.uuid4().hex[:8]


def as_list(body, key):
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        return body.get(key, [])
    return []


def create_society(client, city):
    """Creates a fresh society + admin login. Returns (headers, society_row)."""
    username = unique("admin")
    response = client.post("/api/societies", json={
        "name": unique("Society"),
        "city": city,
        "full_name": "Admin " + city,
        "username": username,
        "password": "testpass123",
    })
    assert response.status_code in (200, 201), response.text

    body = response.json()
    society = (body.get("society", body) if isinstance(body, dict) else body)

    login = client.post("/api/login", json={"username": username, "password": "testpass123"})
    assert login.status_code == 200, login.text
    token = login.json().get("token") or login.json().get("access_token")

    return {"Authorization": f"Bearer {token}"}, society


def make_flat(client, headers, wing, number):
    response = client.post("/api/flats", json={"wing": wing, "number": number}, headers=headers)
    assert response.status_code in (200, 201), response.text
    flats = as_list(client.get("/api/flats", headers=headers).json(), "flats")
    return [f for f in flats if f["wing"] == wing and f["number"] == number][0]


def make_entry(client, headers, flat_id, visitor_name):
    response = client.post("/api/entries", json={
        "entry_type": "visitor",
        "flat_id": flat_id,
        "visitor_name": visitor_name,
        "visitor_phone": "9000000000",
        "note": "isolation test",
    }, headers=headers)
    assert response.status_code in (200, 201), response.text
    return response.json()


# --------------------------------------------------------------------------
# The test
# --------------------------------------------------------------------------

def test_two_societies_never_see_each_other(client):
    headers_a, society_a = create_society(client, "Pune")
    headers_b, society_b = create_society(client, "Mumbai")

    assert society_a["id"] != society_b["id"]
    assert society_a["qr_token"] != society_b["qr_token"]

    # Each admin's /api/me points at their own society.
    me_a = client.get("/api/me", headers=headers_a).json()
    me_b = client.get("/api/me", headers=headers_b).json()
    assert me_a["society_id"] == society_a["id"]
    assert me_b["society_id"] == society_b["id"]

    # ---- Flats -----------------------------------------------------------
    flat_a = make_flat(client, headers_a, "A", "777")
    flat_b = make_flat(client, headers_b, "B", "999")

    flats_a = as_list(client.get("/api/flats", headers=headers_a).json(), "flats")
    flats_b = as_list(client.get("/api/flats", headers=headers_b).json(), "flats")

    assert any(f["id"] == flat_a["id"] for f in flats_a)
    assert not any(f["id"] == flat_b["id"] for f in flats_a), "society A can see a flat of society B"
    assert any(f["id"] == flat_b["id"] for f in flats_b)
    assert not any(f["id"] == flat_a["id"] for f in flats_b), "society B can see a flat of society A"

    # ---- A spoofed society_id in the request body must be ignored ---------
    response = client.post("/api/flats", json={
        "wing": "Z",
        "number": "001",
        "society_id": society_b["id"],  # <-- the browser must not be able to choose this
    }, headers=headers_a)
    if response.status_code in (200, 201):
        leaked = [f for f in as_list(client.get("/api/flats", headers=headers_b).json(), "flats")
                  if f["number"] == "001"]
        assert leaked == [], "a flat sent with a foreign society_id landed in the other society"

    # ---- Staff -----------------------------------------------------------
    response = client.post("/api/staff", json={
        "name": "MaidOfA",
        "role": "maid",
        "verification_status": "verified",
        "flat_ids": [flat_a["id"]],
    }, headers=headers_a)
    assert response.status_code in (200, 201), response.text
    staff_a = response.json()

    staff_b = as_list(client.get("/api/staff", headers=headers_b).json(), "staff")
    assert not any(person["id"] == staff_a["id"] for person in staff_b), \
        "society B can list a staff member of society A"

    # B must not be able to read or edit A's staff member.
    assert client.get(f"/api/staff/{staff_a['id']}", headers=headers_b).status_code in (403, 404)
    response = client.patch(f"/api/staff/{staff_a['id']}",
                            json={"verification_status": "not_done"}, headers=headers_b)
    assert response.status_code in (403, 404), "society B could edit staff of society A"

    still_verified = client.get(f"/api/staff/{staff_a['id']}", headers=headers_a).json()
    assert still_verified["verification_status"] == "verified", "B's PATCH changed A's staff row"

    # ---- Entries ---------------------------------------------------------
    entry_a = make_entry(client, headers_a, flat_a["id"], "VisitorOfA")

    entries_b = as_list(client.get("/api/entries", params={"search": "VisitorOfA"},
                                   headers=headers_b).json(), "entries")
    assert entries_b == [], "society B can see an entry of society A"

    entries_a = as_list(client.get("/api/entries", params={"search": "VisitorOfA"},
                                   headers=headers_a).json(), "entries")
    assert any(e["id"] == entry_a["id"] for e in entries_a)

    inside_b = as_list(client.get("/api/entries/inside", headers=headers_b).json(), "entries")
    assert not any(e["id"] == entry_a["id"] for e in inside_b), "B's 'inside' list leaks A's visitor"

    # ---- A guard of one society cannot reach the other's data ------------
    guard_username = unique("guard")
    response = client.post("/api/users", json={
        "full_name": "GuardOfA",
        "username": guard_username,
        "password": "guardpass123",
        "role": "guard",
    }, headers=headers_a)
    assert response.status_code in (200, 201), response.text

    login = client.post("/api/login", json={"username": guard_username, "password": "guardpass123"})
    guard_a = {"Authorization": f"Bearer {login.json()['token']}"}

    assert client.get("/api/me", headers=guard_a).json()["society_id"] == society_a["id"]

    guard_entries = as_list(client.get("/api/entries", headers=guard_a).json(), "entries")
    assert all(e["flat"]["label"] != "B-999" for e in guard_entries), \
        "a guard of society A sees flats of society B"

    # ---- QR check-in writes into the right society only ------------------
    response = client.post(f"/api/checkin/{society_a['qr_token']}", json={
        "visitor_name": "QrVisitorOfA",
        "visitor_phone": None,
        "flat_id": flat_a["id"],
        "entry_type": "delivery",
    })
    assert response.status_code in (200, 201), response.text

    assert as_list(client.get("/api/entries", params={"search": "QrVisitorOfA"},
                             headers=headers_b).json(), "entries") == [], \
        "a QR check-in for A appeared in B's log"

    # ---- Delete everything only touches the admin's own society ----------
    response = client.post("/api/admin/delete-everything", headers=headers_b)
    assert response.status_code == 200, response.text

    assert as_list(client.get("/api/entries", headers=headers_b).json(), "entries") == []

    surviving = as_list(client.get("/api/entries", params={"search": "VisitorOfA"},
                                   headers=headers_a).json(), "entries")
    assert any(e["id"] == entry_a["id"] for e in surviving), \
        "society B's delete-everything deleted society A's entries"

    # ---- Purge old entries is also per society ---------------------------
    response = client.post("/api/admin/purge-old", headers=headers_b)
    assert response.status_code == 200, response.text


def test_private_routes_reject_anonymous_calls(client):
    """No token at all must never return data."""
    for path in ("/api/me", "/api/flats", "/api/users", "/api/staff", "/api/entries"):
        assert client.get(path).status_code == 401, path

    response = client.post("/api/flats", json={"wing": "A", "number": "1"})
    assert response.status_code == 401, "an anonymous request could add a flat"
