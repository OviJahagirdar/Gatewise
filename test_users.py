"""
test_users.py - creating and listing logins, and keeping societies apart.
"""


def test_admin_can_create_a_guard(client, admin_headers):
    response = client.post(
        "/api/users",
        json={
            "username": "guard2",
            "password": "guard123",
            "full_name": "New Guard",
            "role": "guard",
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "guard2"
    assert body["role"] == "guard"


def test_admin_lists_only_its_own_society_users(client, admin_headers, guard_headers):
    response = client.get("/api/users", headers=admin_headers)

    assert response.status_code == 200
    usernames = {user["username"] for user in response.json()}
    assert usernames == {"admin1", "guard1"}


def test_duplicate_username_is_rejected(client, admin_headers):
    response = client.post(
        "/api/users",
        json={
            "username": "admin1",
            "password": "x",
            "full_name": "Copy Cat",
            "role": "guard",
        },
        headers=admin_headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Username already taken"


def test_guard_cannot_list_users(client, guard_headers):
    response = client.get("/api/users", headers=guard_headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Admins only"


def test_guard_cannot_create_users(client, guard_headers):
    response = client.post(
        "/api/users",
        json={"username": "x", "password": "x", "full_name": "X", "role": "guard"},
        headers=guard_headers,
    )

    assert response.status_code == 403


def test_users_are_separated_by_society(client, admin_headers):
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

    response = client.get("/api/users", headers=second_headers)

    assert [user["username"] for user in response.json()] == ["admin2"]
