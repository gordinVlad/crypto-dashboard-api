"""
Tests for cryptocurrency listing/detail/refresh/history and the watchlist,
using a mocked CoinGecko client so tests don't depend on network access.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.services.coingecko_client import CoinGeckoError


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
    (_utcnow() - timedelta(days=8), 63000.0),
    (_utcnow() - timedelta(days=6), 64000.0),
    (_utcnow() - timedelta(days=3), 64500.0),
    (_utcnow() - timedelta(minutes=1), 65000.0),
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


def test_refresh_populates_cryptocurrencies(client, internal_api_headers):
    with patch(
        "app.api.routes.cryptocurrencies.coingecko_client.get_markets",
        return_value=MOCK_MARKETS,
    ):
        response = client.post(
            "/api/cryptocurrencies/refresh", headers=internal_api_headers
        )
    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 2

    list_response = client.get("/api/cryptocurrencies")
    assert list_response.status_code == 200
    coins = list_response.json()
    assert len(coins) == 2
    symbols = {c["symbol"] for c in coins}
    assert symbols == {"BTC", "ETH"}
    first_page = client.get("/api/cryptocurrencies?skip=0&limit=1")
    second_page = client.get("/api/cryptocurrencies?skip=1&limit=1")
    assert [coin["symbol"] for coin in first_page.json()] == ["BTC"]
    assert [coin["symbol"] for coin in second_page.json()] == ["ETH"]


def test_get_cryptocurrency_detail_and_404(client, internal_api_headers):
    with patch(
        "app.api.routes.cryptocurrencies.coingecko_client.get_markets",
        return_value=MOCK_MARKETS,
    ):
        client.post("/api/cryptocurrencies/refresh", headers=internal_api_headers)

    coin_id = client.get("/api/cryptocurrencies").json()[0]["id"]
    detail = client.get(f"/api/cryptocurrencies/{coin_id}")
    assert detail.status_code == 200

    missing = client.get("/api/cryptocurrencies/999999")
    assert missing.status_code == 404


def test_history_fetches_from_provider_when_empty(client, internal_api_headers):
    auth_headers = _register_and_login(
        client, email="history_user@example.com"
    )
    with patch(
        "app.api.routes.cryptocurrencies.coingecko_client.get_markets",
        return_value=MOCK_MARKETS,
    ):
        client.post("/api/cryptocurrencies/refresh", headers=internal_api_headers)
    coin_id = client.get("/api/cryptocurrencies").json()[0]["id"]

    with patch(
        "app.api.routes.cryptocurrencies.coingecko_client.get_market_chart",
        return_value=MOCK_HISTORY,
    ) as mocked_chart:
        response = client.get(
            f"/api/cryptocurrencies/{coin_id}/history", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["points"]) == 3
        assert all(
            datetime.fromisoformat(point["timestamp"])
            >= _utcnow() - timedelta(days=7, seconds=2)
            for point in data["points"]
        )
        mocked_chart.assert_called_once()

        # Calling again should use the locally stored history and NOT hit
        # the external provider a second time.
        mocked_chart.reset_mock()
        response_2 = client.get(
            f"/api/cryptocurrencies/{coin_id}/history", headers=auth_headers
        )
        assert response_2.status_code == 200
        mocked_chart.assert_not_called()


def test_history_refetches_when_requested_range_exceeds_cached_coverage(
    client, internal_api_headers
):
    auth_headers = _register_and_login(client, email="broad_history_user@example.com")
    with patch(
        "app.api.routes.cryptocurrencies.coingecko_client.get_markets",
        return_value=MOCK_MARKETS,
    ):
        client.post("/api/cryptocurrencies/refresh", headers=internal_api_headers)
    coin_id = client.get("/api/cryptocurrencies").json()[0]["id"]
    broad_history = [
        (_utcnow() - timedelta(days=31), 60000.0),
        (_utcnow() - timedelta(days=25), 62000.0),
        (_utcnow() - timedelta(minutes=1), 65000.0),
    ]

    with patch(
        "app.api.routes.cryptocurrencies.coingecko_client.get_market_chart",
        side_effect=[MOCK_HISTORY, broad_history],
    ) as mocked_chart:
        recent_response = client.get(
            f"/api/cryptocurrencies/{coin_id}/history?days=7",
            headers=auth_headers,
        )
        broad_response = client.get(
            f"/api/cryptocurrencies/{coin_id}/history?days=30",
            headers=auth_headers,
        )

    assert recent_response.status_code == 200
    assert broad_response.status_code == 200
    broad_points = broad_response.json()["points"]
    assert len(broad_points) == 6
    assert all(
        datetime.fromisoformat(point["timestamp"])
        >= _utcnow() - timedelta(days=30, seconds=2)
        for point in broad_points
    )
    assert [call.kwargs["days"] for call in mocked_chart.call_args_list] == [7, 30]


def test_watchlist_add_get_remove_flow(client, internal_api_headers):
    headers = _register_and_login(client)

    with patch(
        "app.api.routes.cryptocurrencies.coingecko_client.get_markets",
        return_value=MOCK_MARKETS,
    ):
        client.post("/api/cryptocurrencies/refresh", headers=internal_api_headers)
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


def test_watchlist_delete_only_queries_items_owned_by_current_user(
    client, internal_api_headers
):
    owner_headers = _register_and_login(client, email="watchlist_owner@example.com")
    other_user_headers = _register_and_login(
        client, email="watchlist_other@example.com"
    )
    with patch(
        "app.api.routes.cryptocurrencies.coingecko_client.get_markets",
        return_value=MOCK_MARKETS,
    ):
        client.post("/api/cryptocurrencies/refresh", headers=internal_api_headers)
    coin_id = client.get("/api/cryptocurrencies").json()[0]["id"]
    item = client.post(
        "/api/watchlist",
        json={"cryptocurrency_id": coin_id},
        headers=owner_headers,
    ).json()

    response = client.delete(
        f"/api/watchlist/{item['id']}", headers=other_user_headers
    )

    assert response.status_code == 404
    assert len(client.get("/api/watchlist", headers=owner_headers).json()) == 1


def test_watchlist_add_unknown_coin_returns_404(client):
    headers = _register_and_login(client, email="unknown_coin_user@example.com")
    response = client.post(
        "/api/watchlist", json={"cryptocurrency_id": 999999}, headers=headers
    )
    assert response.status_code == 404


def test_refresh_requires_configured_internal_token(client, monkeypatch):
    monkeypatch.setattr("app.api.deps.settings.INTERNAL_API_TOKEN", None)
    with patch(
        "app.api.routes.cryptocurrencies.coingecko_client.get_markets"
    ) as mocked_markets:
        response = client.post("/api/cryptocurrencies/refresh")

    mocked_markets.assert_not_called()

    assert response.status_code == 503


def test_refresh_rejects_missing_or_invalid_internal_token(
    client, internal_api_headers
):
    with patch(
        "app.api.routes.cryptocurrencies.coingecko_client.get_markets"
    ) as mocked_markets:
        missing_token_response = client.post("/api/cryptocurrencies/refresh")
        invalid_token_response = client.post(
            "/api/cryptocurrencies/refresh",
            headers={"X-Internal-Token": "wrong-internal-token"},
        )

    mocked_markets.assert_not_called()
    assert missing_token_response.status_code == 401
    assert invalid_token_response.status_code == 401


def test_price_history_requires_authentication(client):
    with patch(
        "app.api.routes.cryptocurrencies.coingecko_client.get_market_chart"
    ) as mocked_chart:
        response = client.get("/api/cryptocurrencies/1/history")

    mocked_chart.assert_not_called()
    assert response.status_code == 401


def test_history_provider_error_is_safe_and_logged_with_request_context(
    client, internal_api_headers
):
    auth_headers = _register_and_login(client, email="history_error_user@example.com")
    with patch(
        "app.api.routes.cryptocurrencies.coingecko_client.get_markets",
        return_value=MOCK_MARKETS,
    ):
        client.post("/api/cryptocurrencies/refresh", headers=internal_api_headers)
    coin_id = client.get("/api/cryptocurrencies").json()[0]["id"]
    provider_error = CoinGeckoError(
        "request failed at https://private-provider.example/path?token=secret"
    )

    with (
        patch(
            "app.api.routes.cryptocurrencies.coingecko_client.get_market_chart",
            side_effect=provider_error,
        ),
        patch("app.api.routes.cryptocurrencies.logger.exception") as log_exception,
    ):
        response = client.get(
            f"/api/cryptocurrencies/{coin_id}/history",
            headers={**auth_headers, "X-Request-ID": "history-error-request"},
        )

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "External provider is temporarily unavailable. Please try again later."
    )
    assert "private-provider.example" not in response.text
    assert "token=secret" not in response.text
    assert response.json()["request_id"] == "history-error-request"
    log_exception.assert_called_once()
    assert log_exception.call_args.args == (
        "failed to fetch price history from coingecko",
    )
    assert log_exception.call_args.kwargs["extra"] == {
        "request_id": "history-error-request",
        "crypto_id": coin_id,
        "external_provider_id": "bitcoin",
        "days": 7,
    }


def test_refresh_provider_error_is_safe_and_logged_with_request_context(
    client, internal_api_headers
):
    provider_error = CoinGeckoError(
        "request failed at https://private-provider.example/markets"
    )
    with (
        patch(
            "app.api.routes.cryptocurrencies.coingecko_client.get_markets",
            side_effect=provider_error,
        ),
        patch("app.api.routes.cryptocurrencies.logger.exception") as log_exception,
    ):
        response = client.post(
            "/api/cryptocurrencies/refresh",
            headers={
                **internal_api_headers,
                "X-Request-ID": "refresh-error-request",
            },
        )

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "External provider is temporarily unavailable. Please try again later."
    )
    assert "private-provider.example" not in response.text
    assert response.json()["request_id"] == "refresh-error-request"
    log_exception.assert_called_once()
    assert log_exception.call_args.args == (
        "crypto refresh failed to fetch from coingecko",
    )
    assert log_exception.call_args.kwargs["extra"] == {
        "request_id": "refresh-error-request",
        "limit": 50,
    }
