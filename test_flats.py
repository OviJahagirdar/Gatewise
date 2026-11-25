"""
test_flats.py - adding, listing, searching and CSV-importing flats.
"""


def test_create_flat_with_a_wing(client, admin_headers):
    response = client.post(
        "/api/flats", json={"wing": "A", "number": "101"}, headers=admin_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["wing"] == "A"
    assert body["number"] == "101"
    assert body["label"] == "A-101"


def test_create_flat_without_a_wing(client, admin_headers):
    response = client.post(
        "/api/flats", json={"number": "301"}, headers=admin_headers
    )

    assert response.status_code == 200
    assert response.json()["label"] == "301"


def test_list_flats_requires_login(client):
    response = client.get("/api/flats")

    assert response.status_code == 401


def test_search_filters_the_list(client, admin_headers):
    client.post("/api/flats", json={"wing": "A", "number": "101"}, headers=admin_headers)
    client.post("/api/flats", json={"wing": "B", "number": "201"}, headers=admin_headers)

    response = client.get("/api/flats?search=B", headers=admin_headers)

    assert response.status_code == 200
    assert [flat["label"] for flat in response.json()] == ["B-201"]


def test_guard_cannot_create_a_flat(client, guard_headers):
    response = client.post(
        "/api/flats", json={"wing": "A", "number": "101"}, headers=guard_headers
    )

    assert response.status_code == 403


def test_flats_are_separated_by_society(client, admin_headers):
    client.post("/api/flats", json={"wing": "A", "number": "101"}, headers=admin_headers)

    client.post(
        "/api/societies",
        json={
            "society_name": "Second Society",
            "city": "Delhi",
            "admin_full_name": "Second Admin",
            "admin_username": "admin2",
            "admin_password": "admin123",
        },
    )
    second_login = client.post(
        "/api/login", json={"username": "admin2", "password": "admin123"}
    ).json()
    second_headers = {"Authorization": f"Bearer {second_login['token']}"}

    response = client.get("/api/flats", headers=second_headers)

    assert response.json() == []


def test_csv_upload_counts_created_and_skipped(client, admin_headers):
    csv_text = "wing,number\nA,101\nA,102\n,301\n"

    first = client.post(
        "/api/flats/upload-csv",
        files={"file": ("flats.csv", csv_text, "text/csv")},
        headers=admin_headers,
    )
    assert first.status_code == 200
    assert first.json() == {"created": 3, "skipped": 0}

    # Uploading the same file again must not create duplicates.
    second = client.post(
        "/api/flats/upload-csv",
        files={"file": ("flats.csv", csv_text, "text/csv")},
        headers=admin_headers,
    )
    assert second.json() == {"created": 0, "skipped": 3}


def test_csv_upload_skips_rows_without_a_number(client, admin_headers):
    csv_text = "wing,number\nA,101\n,\n"

    response = client.post(
        "/api/flats/upload-csv",
        files={"file": ("flats.csv", csv_text, "text/csv")},
        headers=admin_headers,
    )

    assert response.json() == {"created": 1, "skipped": 1}
