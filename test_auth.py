"""
test_auth.py - society signup, login and /api/me.
"""


def test_society_signup_creates_society_and_admin(client):
    response = client.post(
        "/api/societies",
        json={
            "society_name": "Green Park",
            "city": "Mumbai",
            "admin_full_name": "Ravi S",
            "admin_username": "ravi",
            "admin_password": "secret123",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["society"]["name"] == "Green Park"
    assert body["society"]["city"] == "Mumbai"
    assert body["society"]["retention_days"] == 90
    assert body["society"]["qr_token"]  # generated, never empty

    assert body["user"]["username"] == "ravi"
    assert body["user"]["full_name"] == "Ravi S"
    assert body["user"]["role"] == "admin"
    assert body["user"]["society_id"] == body["society"]["id"]
    # The password hash must never be sent to the browser.
    assert "password_hash" not in body["user"]


def test_signup_rejects_username_that_is_taken(client, society):
    response = client.post(
        "/api/societies",
        json={
            "society_name": "Other Heights",
            "city": "Pune",
            "admin_full_name": "Someone",
            "admin_username": "admin1",
            "admin_password": "another123",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Username already taken"


def test_login_returns_a_token_and_the_user(client, society):
    response = client.post(
        "/api/login", json={"username": "admin1", "password": "admin123"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert body["user"]["username"] == "admin1"
    assert body["user"]["role"] == "admin"


def test_login_with_wrong_password_is_rejected(client, society):
    response = client.post(
        "/api/login", json={"username": "admin1", "password": "wrong"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


def test_me_returns_the_logged_in_user(client, admin_headers):
    response = client.get("/api/me", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["username"] == "admin1"


def test_me_without_a_token_is_rejected(client):
    response = client.get("/api/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not logged in"


def test_me_with_a_made_up_token_is_rejected(client):
    response = client.get(
        "/api/me", headers={"Authorization": "Bearer not-a-real-token"}
    )

    assert response.status_code == 401
