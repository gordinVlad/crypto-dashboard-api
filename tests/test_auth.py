"""
Tests for authentication: registration and login.
"""


def test_register_new_user(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "supersecret123"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "alice@example.com"
    assert "id" in data
    assert "hashed_password" not in data


def test_register_duplicate_email_fails(client):
    client.post(
        "/api/auth/register",
        json={"email": "bob@example.com", "password": "supersecret123"},
    )
    response = client.post(
        "/api/auth/register",
        json={"email": "bob@example.com", "password": "anotherpassword"},
    )
    assert response.status_code == 409


def test_login_success(client):
    client.post(
        "/api/auth/register",
        json={"email": "carol@example.com", "password": "supersecret123"},
    )
    response = client.post(
        "/api/auth/login",
        data={"username": "carol@example.com", "password": "supersecret123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password_fails(client):
    client.post(
        "/api/auth/register",
        json={"email": "dave@example.com", "password": "supersecret123"},
    )
    response = client.post(
        "/api/auth/login",
        data={"username": "dave@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_watchlist_requires_authentication(client):
    response = client.get("/api/watchlist")
    assert response.status_code == 401


def test_required_auth_rejects_invalid_token(client):
    response = client.get(
        "/api/watchlist",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


def test_optional_auth_ignores_invalid_token(client):
    response = client.get(
        "/api/cryptocurrencies",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 200
