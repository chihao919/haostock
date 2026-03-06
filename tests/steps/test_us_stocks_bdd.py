"""BDD tests for US Stock Portfolio feature."""

import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from api.stocks.us import app


@pytest.fixture
def notion_us_data():
    return {
        "Firstrade": [
            {"ticker": "NVDA", "shares": 100, "avg_cost": 185.26},
            {"ticker": "GOOG", "shares": 200, "avg_cost": 307.61},
        ],
        "IBKR": [
            {"ticker": "VOO", "shares": 3.19, "avg_cost": 627.38},
        ],
    }


@pytest.fixture
def price_side_effect():
    prices = {"NVDA": 250.00, "GOOG": 280.00, "VOO": 550.00}
    return lambda t: prices.get(t)


@pytest.mark.asyncio
async def test_profitable_position_pl(notion_us_data, price_side_effect):
    """Scenario: Calculate P&L for a profitable position"""
    with patch("api.stocks.us.get_us_stocks", new_callable=AsyncMock, return_value=notion_us_data), \
         patch("lib.pricing._fetch_price", side_effect=price_side_effect):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/stocks/us")

    assert resp.status_code == 200
    data = resp.json()
    nvda = next(p for p in data["accounts"]["Firstrade"]["positions"] if p["ticker"] == "NVDA")
    assert nvda["market_value"] == 25000.00
    assert nvda["cost_basis"] == 18526.00
    assert nvda["unrealized_pl"] == 6474.00
    assert nvda["pl_pct"] == 34.95


@pytest.mark.asyncio
async def test_losing_position_pl(notion_us_data, price_side_effect):
    """Scenario: Calculate P&L for a losing position"""
    with patch("api.stocks.us.get_us_stocks", new_callable=AsyncMock, return_value=notion_us_data), \
         patch("lib.pricing._fetch_price", side_effect=price_side_effect):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/stocks/us")

    data = resp.json()
    goog = next(p for p in data["accounts"]["Firstrade"]["positions"] if p["ticker"] == "GOOG")
    assert goog["market_value"] == 56000.00
    assert goog["cost_basis"] == 61522.00
    assert goog["unrealized_pl"] == -5522.00
    assert goog["pl_pct"] == -8.98


@pytest.mark.asyncio
async def test_account_totals(notion_us_data, price_side_effect):
    """Scenario: Aggregate totals per account"""
    with patch("api.stocks.us.get_us_stocks", new_callable=AsyncMock, return_value=notion_us_data), \
         patch("lib.pricing._fetch_price", side_effect=price_side_effect):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/stocks/us")

    data = resp.json()
    ft = data["accounts"]["Firstrade"]
    assert ft["total_market_value"] == 81000.00
    assert ft["total_cost_basis"] == 80048.00


@pytest.mark.asyncio
async def test_grand_summary(notion_us_data, price_side_effect):
    """Scenario: Grand summary across all accounts"""
    with patch("api.stocks.us.get_us_stocks", new_callable=AsyncMock, return_value=notion_us_data), \
         patch("lib.pricing._fetch_price", side_effect=price_side_effect):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/stocks/us")

    data = resp.json()
    summary = data["summary"]
    assert "total_market_value" in summary
    assert "total_cost_basis" in summary
    assert "total_pl" in summary
    assert "total_pl_pct" in summary


@pytest.mark.asyncio
async def test_unavailable_price():
    """Scenario: Handle unavailable price gracefully"""
    notion_data = {"Firstrade": [{"ticker": "NVDA", "shares": 100, "avg_cost": 185.26}]}
    with patch("api.stocks.us.get_us_stocks", new_callable=AsyncMock, return_value=notion_data), \
         patch("lib.pricing._fetch_price", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/stocks/us")

    data = resp.json()
    nvda = data["accounts"]["Firstrade"]["positions"][0]
    assert nvda["current_price"] is None
    assert "market_value" not in nvda


@pytest.mark.asyncio
async def test_price_caching():
    """Scenario: Price caching within a single request"""
    notion_data = {
        "Firstrade": [{"ticker": "NVDA", "shares": 100, "avg_cost": 185.26}],
        "IBKR": [{"ticker": "NVDA", "shares": 27, "avg_cost": 185.26}],
    }
    with patch("api.stocks.us.get_us_stocks", new_callable=AsyncMock, return_value=notion_data), \
         patch("lib.pricing._fetch_price", return_value=250.00) as mock_fetch:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/stocks/us")

    assert resp.status_code == 200
    mock_fetch.assert_called_once_with("NVDA")


@pytest.mark.asyncio
async def test_notion_api_error():
    """Scenario: Handle Notion API errors gracefully"""
    from lib.notion import NotionAPIError
    with patch("api.stocks.us.get_us_stocks", new_callable=AsyncMock, side_effect=NotionAPIError(500, "error")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/stocks/us")

    assert resp.status_code == 502
