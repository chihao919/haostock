"""BDD tests for Single Stock Quote & FX Rate feature."""

import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from api.health import app as health_app
from api.fx import app as fx_app
from api.quote import app as quote_app


# Note: Vercel uses [ticker].py but for testing we import the app directly


@pytest.mark.asyncio
async def test_valid_us_stock_quote():
    """Scenario: Get a valid US stock quote"""
    with patch("lib.pricing._fetch_price", return_value=250.00):
        async with AsyncClient(transport=ASGITransport(app=quote_app), base_url="http://test") as client:
            resp = await client.get("/api/quote/NVDA")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "NVDA"
    assert data["price"] == 250.00


@pytest.mark.asyncio
async def test_ticker_case_insensitive():
    """Scenario: Ticker is case-insensitive"""
    with patch("lib.pricing._fetch_price", return_value=250.00):
        async with AsyncClient(transport=ASGITransport(app=quote_app), base_url="http://test") as client:
            resp = await client.get("/api/quote/nvda")
    assert resp.json()["ticker"] == "NVDA"


@pytest.mark.asyncio
async def test_tw_stock_quote():
    """Scenario: Get a Taiwan stock quote"""
    with patch("lib.pricing._fetch_price", return_value=900.00):
        async with AsyncClient(transport=ASGITransport(app=quote_app), base_url="http://test") as client:
            resp = await client.get("/api/quote/2330.TW")
    data = resp.json()
    assert data["ticker"] == "2330.TW"
    assert data["price"] == 900.00


@pytest.mark.asyncio
async def test_invalid_ticker_404():
    """Scenario: Return 404 for invalid ticker"""
    with patch("lib.pricing._fetch_price", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=quote_app), base_url="http://test") as client:
            resp = await client.get("/api/quote/INVALIDTICKER")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_fx_rate():
    """Scenario: Get USD/TWD exchange rate"""
    with patch("lib.pricing._fetch_price", return_value=32.15):
        async with AsyncClient(transport=ASGITransport(app=fx_app), base_url="http://test") as client:
            resp = await client.get("/api/fx")
    assert resp.status_code == 200
    assert resp.json()["USDTWD"] == 32.15


@pytest.mark.asyncio
async def test_fx_fallback():
    """Scenario: FX fallback when unavailable"""
    with patch("lib.pricing._fetch_price", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=fx_app), base_url="http://test") as client:
            resp = await client.get("/api/fx")
    assert resp.json()["USDTWD"] == 32.0


@pytest.mark.asyncio
async def test_health_check():
    """Scenario: Health check returns ok"""
    async with AsyncClient(transport=ASGITransport(app=health_app), base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "timestamp" in data
