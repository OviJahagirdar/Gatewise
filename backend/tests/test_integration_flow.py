"""
Person 4 — end-to-end integration test of the whole app.

This walks the exact journey a demo walks by hand:

    create a society -> log in -> add a flat -> add a guard login
    -> register a staff member -> the guard logs a visitor -> the guard marks the exit
    -> the committee sees it in /api/entries -> the CSV export contains it
    -> a visitor checks in through the QR link -> that entry shows up too
    -> a bad QR token is rejected -> purge old entries -> delete everything

Every test run starts by creating its OWN society through POST /api/societies,
so it never needs to delete app.db and never touches the demo data.

Run it from the society-gate folder:

    pip install pytest httpx
    pytest backend/tests -v
"""

import datetime
import json
import pathlib
import sys
import uuid

import pytest

# Let "backend" be importable whichever folder pytest is started from.
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# FastAPI's TestClient needs httpx, which is not always installed.
pytest.importorskip("httpx", reason="pip install httpx (needed by FastAPI's TestClient)")

try:
    from fastapi.testclient import TestClient
    from backend.main import app
except ModuleNotFoundError as exc:  # backend/ not written yet
    pytest.skip(f"Backend is not importable yet: {exc}", allow_module_level=True)


@pytest.fixture(scope="module")
def client():
    # "with" matters: it runs FastAPI's startup event, which creates the tables.
    with TestClient(app) as test_client:
        yield test_client


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def unique(prefix):
    """A different username/society name on every run, so re-runs never clash."""
    return prefix + "_" + uuid.uuid4().hex[:8]


def as_list(body, key):
    """The backend may answer with a plain list or with {key: [...]}."""
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        return body.get(key, [])
    return []


def create_society(client, city="Pune"):
    """Creates a fresh society + admin login. Returns (token, society_row)."""
    username = unique("admin")
    response = client.post("/api/societies", json={
        "name": unique("Society"),
        "city": city,
        "full_name": "Test Admin",
        "username": username,
        "password": "testpass123",
    })
    assert response.status_code in (200, 201), response.text

    body = response.json()
    society = (body.get("society", body) if isinstance(body, dict) else body)
    assert isinstance(society, dict), society

    login = client.post("/api/login", json={"username": username, "password": "testpass123"})
    assert login.status_code == 200, login.text

    payload = login.json()
    token = payload.get("token") or payload.get("access_token")
    assert token, "the login response has no token field"

    return token, society


def headers_for(token):
    return {"Authorization": f"Bearer {token}"}


def add_flat(client, headers, wing, number):
    response = client.post("/api/flats", json={"wing": wing, "number": number}, headers=headers)
    assert response.status_code in (200, 201), response.text

    flats = as_list(client.get("/api/flats", headers=headers).json(), "flats")
    matches = [f for f in flats if f["wing"] == wing and f["number"] == number]
    assert matches, f"flat {wing}-{number} was created but is missing from GET /api/flats"

    flat = matches[0]
    assert flat["label"] == f"{wing}-{number}", flat
    return flat


# --------------------------------------------------------------------------
# The journey
# --------------------------------------------------------------------------

def test_full_journey_from_society_to_csv_to_qr_checkin(client):
    # ---- 1. A new society + its committee login -------------------------
    admin_token, society = create_society(client)
    admin = headers_for(admin_token)

    assert society.get("id"), society
    assert society.get("qr_token"), "the society row must include qr_token (the QR link needs it)"
    qr_token = society["qr_token"]

    me = client.get("/api/me", headers=admin).json()
    assert me["role"] == "admin"
    assert me["society_id"] == society["id"]
    assert me["full_name"] == "Test Admin"

    # Nothing works without a token.
    assert client.get("/api/flats").status_code == 401

    # ---- 2. The admin adds a flat --------------------------------------
    flat = add_flat(client, admin, "A", "101")

    # ---- 3. The admin adds a guard login and the guard logs in ---------
    guard_username = unique("guard")
    response = client.post("/api/users", json={
        "full_name": "Ramu Guard",
        "username": guard_username,
        "password": "guardpass123",
        "role": "guard",
    }, headers=admin)
    assert response.status_code in (200, 201), response.text

    guards = as_list(client.get("/api/users", headers=admin).json(), "users")
    assert any(u["username"] == guard_username and u["role"] == "guard" for u in guards)

    login = client.post("/api/login", json={"username": guard_username, "password": "guardpass123"})
    assert login.status_code == 200, login.text
    guard = headers_for(login.json()["token"])

    # ---- 4. Staff registry: register, search, edit ---------------------
    response = client.post("/api/staff", json={
        "name": "Sunita",
        "role": "maid",
        "verification_status": "verified",
        "flat_ids": [flat["id"]],
    }, headers=admin)
    assert response.status_code in (200, 201), response.text

    staff = response.json()
    staff_id = staff["id"]
    assert staff["name"] == "Sunita"
    assert staff["verification_status"] == "verified"
    assert "flats" in staff, "the staff JSON must include the flats list"
    assert staff["is_active"] is True

    found = as_list(client.get("/api/staff", params={"search": "Sunita"}, headers=admin).json(), "staff")
    assert any(person["id"] == staff_id for person in found), "the search did not find the new staff member"

    response = client.patch(f"/api/staff/{staff_id}",
                            json={"verification_status": "pending"}, headers=admin)
    assert response.status_code == 200, response.text

    refreshed = client.get(f"/api/staff/{staff_id}", headers=admin).json()
    assert refreshed["verification_status"] == "pending"

    # ---- 5. The guard logs a visitor -----------------------------------
    response = client.post("/api/entries", json={
        "entry_type": "visitor",
        "flat_id": flat["id"],
        "visitor_name": "Rahul",
        "visitor_phone": "9876543210",
        "note": "Guest",
    }, headers=guard)
    assert response.status_code in (200, 201), response.text

    entry = response.json()
    entry_id = entry["id"]
    assert entry["entry_type"] == "visitor"
    assert entry["source"] == "guard"
    assert entry["flat"]["label"] == "A-101"
    assert entry["visitor_name"] == "Rahul"
    assert entry["exit_time"] is None
    assert entry.get("logged_by"), "the entry should say which guard logged it"

    inside = as_list(client.get("/api/entries/inside", headers=guard).json(), "entries")
    assert any(e["id"] == entry_id for e in inside), "a fresh visitor should be listed as inside"

    # ---- 6. The guard marks the exit -----------------------------------
    response = client.post(f"/api/entries/{entry_id}/exit", headers=guard)
    assert response.status_code == 200, response.text

    entries = as_list(client.get("/api/entries", params={"search": "Rahul"}, headers=admin).json(), "entries")
    stored = [e for e in entries if e["id"] == entry_id]
    assert stored, "the entry disappeared from GET /api/entries"
    assert stored[0]["exit_time"], "the exit time was not saved"

    inside = as_list(client.get("/api/entries/inside", headers=guard).json(), "entries")
    assert not any(e["id"] == entry_id for e in inside), "someone who exited is still listed as inside"

    # ---- 7. The committee sees it, filtered ----------------------------
    today = datetime.date.today().isoformat()
    params = {"date_from": today, "date_to": today, "entry_type": "visitor", "search": "Rahul"}
    entries = as_list(client.get("/api/entries", params=params, headers=admin).json(), "entries")
    assert any(e["id"] == entry_id for e in entries), "today's visitor is missing from the filtered log"

    # ---- 8. CSV export contains the row ---------------------------------
    response = client.get("/api/entries/export-csv", params=params, headers=admin)
    assert response.status_code == 200, response.text
    assert "text/csv" in response.headers.get("content-type", ""), response.headers
    csv_text = response.text
    assert "Rahul" in csv_text and "A-101" in csv_text, csv_text[:400]

    # ---- 9. QR check-in, with no login at all ---------------------------
    response = client.get(f"/api/checkin/{qr_token}")
    assert response.status_code == 200, response.text

    public_page = response.json()
    assert society["name"] in json.dumps(public_page), "the check-in page does not know the society name"
    public_flats = as_list(public_page, "flats")
    assert any(f["id"] == flat["id"] for f in public_flats), "the QR page is missing the flat list"

    response = client.post(f"/api/checkin/{qr_token}", json={
        "visitor_name": "Neha",
        "visitor_phone": None,
        "flat_id": flat["id"],
        "entry_type": "delivery",
    })
    assert response.status_code in (200, 201), response.text

    qr_entries = as_list(client.get("/api/entries", params={"search": "Neha"}, headers=admin).json(), "entries")
    assert qr_entries, "the QR check-in never appeared in the committee log"
    assert qr_entries[0]["source"] == "qr"
    assert qr_entries[0]["flat"]["label"] == "A-101"
    qr_entry_id = qr_entries[0]["id"]

    # ---- 10. A wrong QR token is rejected ------------------------------
    assert client.get("/api/checkin/this-token-does-not-exist").status_code == 404

    # ---- 11. Purge old entries (today's entries are inside retention) --
    response = client.post("/api/admin/purge-old", headers=admin)
    assert response.status_code == 200, response.text

    still_there = as_list(client.get("/api/entries", headers=admin).json(), "entries")
    assert any(e["id"] == qr_entry_id for e in still_there), "purging deleted today's entries"

    # ---- 12. Delete everything -----------------------------------------
    response = client.post("/api/admin/delete-everything", headers=admin)
    assert response.status_code == 200, response.text
    assert as_list(client.get("/api/entries", headers=admin).json(), "entries") == [], \
        "delete-everything did not empty the log"

    # ---- 13. A guard is not allowed to wipe the log ---------------------
    response = client.post("/api/admin/delete-everything", headers=guard)
    assert response.status_code == 403, "a guard must not be able to delete all entries"


def test_csv_export_needs_a_login(client):
    """Export is not a public file: without a token it must be refused."""
    assert client.get("/api/entries/export-csv").status_code == 401
