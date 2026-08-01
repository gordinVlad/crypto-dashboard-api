"""
Tests for cryptocurrency listing/detail/refresh/history and the watchlist,
using a mocked CoinGecko client so tests don't depend on network access.
"""

from datetime import datetime
from unittest.mock import patch

MOCK_MARKETS = [
    {
        "id": "bitcoin",
        "symbol": "btc",
        "name": "Bitcoin",
        "image": "https://example.com/btc.png",
        "current_price": 65000.0,
        "market_cap": 1280000000000.0,
        "price_change_percentage_24h": 2.5,
    },
    {
        "id": "ethereum",
        "symbol": "eth",
        "name": "Ethereum",
        "image": "https://example.com/eth.png",
        "current_price": 3400.0,
        "market_cap": 410000000000.0,
        "price_change_percentage_24h": -1.2,
    },
]

MOCK_HISTORY = [
    (datetime(2026, 7, 20, 0, 0, 0), 64000.0),
    (datetime(2026, 7, 21, 0, 0, 0), 64500.0),
    (datetime(2026, 7, 22, 0, 0, 0), 65000.0),
]


def _register_and_login(client, email="watchlist_user@example.com"):
    client.post(
        "/api/auth/register", json={"email": email, "password": "supersecret123"}
    )
    response = client.post(
        "/api/auth/login", data={"username": email, "password": "supersecret123"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_refresh_populates_cryptocurrencies(client):
    with patch(
        "app.api.routes.cryptocurrencies.coingecko_client.get_markets",
        return_value=MOCK_MARKETS,
    ):
        response = client.post("/api/cryptocurrencies/refresh")
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 2

    list_response = client.get("/api/cryptocurrencies")
    assert list_response.status_code == 200
    coins = list_response.json()
    assert len(coins) == 2
    symbols = {c["symbol"] for c in coins}
    assert symbols == {"BTC", "ETH"}


def test_get_cryptocurrency_detail_and_404(client):
    with patch(
        "app.api.routes.cryptocurrencies.coingecko_client.get_markets",
        return_value=MOCK_MARKETS,
    ):
        client.post("/api/cryptocurrencies/refresh")

    coin_id = client.get("/api/cryptocurrencies").json()[0]["id"]
    detail = client.get(f"/api/cryptocurrencies/{coin_id}")
    assert detail.status_code == 200

    missing = client.get("/api/cryptocurrencies/999999")
    assert missing.status_code == 404


def test_history_fetches_from_provider_when_empty(client):
    with patch(
        "app.api.routes.cryptocurrencies.coingecko_client.get_markets",
        return_value=MOCK_MARKETS,
    ):
        client.post("/api/cryptocurrencies/refresh")
    coin_id = client.get("/api/cryptocurrencies").json()[0]["id"]

    with patch(
        "app.api.routes.cryptocurrencies.coingecko_client.get_market_chart",
        return_value=MOCK_HISTORY,
    ) as mocked_chart:
        response = client.get(f"/api/cryptocurrencies/{coin_id}/history")
        assert response.status_code == 200
        data = response.json()
        assert len(data["points"]) == 3
        mocked_chart.assert_called_once()

        # Calling again should use the locally stored history and NOT hit
        # the external provider a second time.
        mocked_chart.reset_mock()
        response_2 = client.get(f"/api/cryptocurrencies/{coin_id}/history")
        assert response_2.status_code == 200
        mocked_chart.assert_not_called()


def test_watchlist_add_get_remove_flow(client):
    headers = _register_and_login(client)

    with patch(
        "app.api.routes.cryptocurrencies.coingecko_client.get_markets",
        return_value=MOCK_MARKETS,
    ):
        client.post("/api/cryptocurrencies/refresh")
    coin_id = client.get("/api/cryptocurrencies").json()[0]["id"]

    add_response = client.post(
        "/api/watchlist", json={"cryptocurrency_id": coin_id}, headers=headers
    )
    assert add_response.status_code == 201
    item_id = add_response.json()["id"]

    duplicate_response = client.post(
        "/api/watchlist", json={"cryptocurrency_id": coin_id}, headers=headers
    )
    assert duplicate_response.status_code == 409

    list_response = client.get("/api/watchlist", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["cryptocurrency"]["is_in_watchlist"] is True

    delete_response = client.delete(f"/api/watchlist/{item_id}", headers=headers)
    assert delete_response.status_code == 204

    list_after_delete = client.get("/api/watchlist", headers=headers)
    assert list_after_delete.json() == []


def test_watchlist_add_unknown_coin_returns_404(client):
    headers = _register_and_login(client, email="unknown_coin_user@example.com")
    response = client.post(
        "/api/watchlist", json={"cryptocurrency_id": 999999}, headers=headers
    )
    assert response.status_code == 404
