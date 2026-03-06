"""BDD tests for Taiwan Stock Portfolio feature."""

import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from api.stocks.tw import app


@pytest.fixture
def notion_tw_data():
    return {
        "Yongfeng_B": [
            {"ticker": "2330.TW", "name": "台積電", "shares": 5000, "avg_cost": 854.56},
        ],
        "Cathay_TW": [
            {"ticker": "0050.TW", "name": "元大台灣50", "shares": 4075, "avg_cost": 61.26},
        ],
    }


@pytest.fixture
def tw_prices():
    prices = {"2330.TW": 900.00, "0050.TW": 180.00, "USDTWD=X": 32.15}
    return lambda t: prices.get(t)


@pytest.mark.asyncio
async def test_pl_in_twd(notion_tw_data, tw_prices):
    """Scenario: Calculate P&L in TWD for Taiwan stocks"""
    with patch("api.stocks.tw.get_tw_stocks", new_callable=AsyncMock, return_value=notion_tw_data), \
         patch("lib.pricing._fetch_price", side_effect=tw_prices):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/stocks/tw")

    data = resp.json()
    tsmc = next(p for p in data["accounts"]["Yongfeng_B"]["positions"] if p["ticker"] == "2330.TW")
    assert tsmc["market_value_twd"] == 4500000
    assert tsmc["cost_basis_twd"] == 4272800
    assert tsmc["unrealized_pl_twd"] == 227200


@pytest.mark.asyncio
async def test_usd_conversion(notion_tw_data, tw_prices):
    """Scenario: Convert TWD values to USD"""
    with patch("api.stocks.tw.get_tw_stocks", new_callable=AsyncMock, return_value=notion_tw_data), \
         patch("lib.pricing._fetch_price", side_effect=tw_prices):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/stocks/tw")

    data = resp.json()
    tsmc = next(p for p in data["accounts"]["Yongfeng_B"]["positions"] if p["ticker"] == "2330.TW")
    assert tsmc["market_value_usd"] == round(4500000 / 32.15, 2)


@pytest.mark.asyncio
async def test_response_includes_fx_rate(notion_tw_data, tw_prices):
    """Scenario: Response includes exchange rate"""
    with patch("api.stocks.tw.get_tw_stocks", new_callable=AsyncMock, return_value=notion_tw_data), \
         patch("lib.pricing._fetch_price", side_effect=tw_prices):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/stocks/tw")

    assert resp.json()["usdtwd_rate"] == 32.15


@pytest.mark.asyncio
async def test_summary_has_both_currencies(notion_tw_data, tw_prices):
    """Scenario: Summary totals in both currencies"""
    with patch("api.stocks.tw.get_tw_stocks", new_callable=AsyncMock, return_value=notion_tw_data), \
         patch("lib.pricing._fetch_price", side_effect=tw_prices):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/stocks/tw")

    summary = resp.json()["summary"]
    assert "total_market_value_twd" in summary
    assert "total_market_value_usd" in summary
    assert "total_pl_twd" in summary
    assert "total_pl_pct" in summary


@pytest.mark.asyncio
async def test_fx_fallback():
    """Scenario: Fallback exchange rate when unavailable"""
    notion_data = {"Test": [{"ticker": "2330.TW", "name": "台積電", "shares": 1000, "avg_cost": 800}]}
    prices = {"2330.TW": 900.00, "USDTWD=X": None}
    with patch("api.stocks.tw.get_tw_stocks", new_callable=AsyncMock, return_value=notion_data), \
         patch("lib.pricing._fetch_price", side_effect=lambda t: prices.get(t)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/stocks/tw")

    assert resp.json()["usdtwd_rate"] == 32.0
