"""BDD tests for Trade Journal feature."""

import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from api.trades import app


@pytest.fixture
def mock_trades_data():
    return [
        {"id": "1", "date": "2026-03-05", "ticker": "CCJ", "action": "Sell", "asset_type": "Option",
         "qty": 1, "price": 4.80, "total_amount": 480.00, "pl": 350.00, "result": "Win",
         "reason": "收取權利金", "lesson": "提前平倉鎖利", "tags": ["Covered Put"], "account": "Firstrade"},
        {"id": "2", "date": "2026-03-01", "ticker": "MU", "action": "Close", "asset_type": "Option",
         "qty": 1, "price": 22.00, "total_amount": 2200.00, "pl": -400.00, "result": "Loss",
         "reason": "財報超預期", "lesson": "財報前不賣裸 call", "tags": ["Earnings Play"], "account": "Firstrade"},
        {"id": "3", "date": "2026-02-20", "ticker": "NVDA", "action": "Buy", "asset_type": "Stock",
         "qty": 50, "price": 185.00, "total_amount": 9250.00, "pl": None, "result": None,
         "reason": "長期看多", "lesson": None, "tags": ["Momentum"], "account": "IBKR"},
    ]


# --- Recording Trades ---

@pytest.mark.asyncio
async def test_record_winning_trade():
    """Scenario: Record a winning stock trade"""
    with patch("api.trades.create_trade", new_callable=AsyncMock, return_value="page-id-123"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/trades", json={
                "date": "2026-03-06",
                "ticker": "NVDA",
                "action": "Sell",
                "asset_type": "Stock",
                "qty": 50,
                "price": 250.00,
                "total_amount": 12500.00,
                "pl": 3287.00,
                "result": "Win",
                "reason": "目標價到達",
                "lesson": "分批出場更好",
                "tags": ["Momentum", "Technical"],
                "account": "IBKR",
            })
    assert resp.status_code == 201
    assert resp.json()["status"] == "created"


@pytest.mark.asyncio
async def test_record_losing_trade():
    """Scenario: Record a losing option trade"""
    with patch("api.trades.create_trade", new_callable=AsyncMock, return_value="page-id-456"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/trades", json={
                "date": "2026-03-06",
                "ticker": "MU",
                "action": "Close",
                "asset_type": "Option",
                "qty": 1,
                "price": 22.00,
                "total_amount": 2200.00,
                "pl": -400.00,
                "result": "Loss",
                "reason": "賣 call 被穿",
                "lesson": "財報前不要賣裸 call",
                "tags": ["Earnings Play"],
                "account": "Firstrade",
            })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_record_minimal_trade():
    """Scenario: Record a trade with minimal fields"""
    with patch("api.trades.create_trade", new_callable=AsyncMock, return_value="page-id-789"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/trades", json={
                "date": "2026-03-06",
                "ticker": "CCJ",
                "action": "Buy",
                "asset_type": "Stock",
                "qty": 100,
                "price": 95.00,
                "total_amount": 9500.00,
                "reason": "鈾礦長期看多",
                "account": "Firstrade",
            })
    assert resp.status_code == 201


# --- Validation ---

@pytest.mark.asyncio
async def test_reject_missing_ticker():
    """Scenario: Reject trade without required fields"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/trades", json={
            "date": "2026-03-06",
            "action": "Buy",
            "asset_type": "Stock",
            "qty": 100,
            "price": 95.00,
            "total_amount": 9500.00,
            "reason": "test",
            "account": "Firstrade",
        })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_reject_invalid_action():
    """Scenario: Reject invalid action type"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/trades", json={
            "date": "2026-03-06",
            "ticker": "CCJ",
            "action": "InvalidAction",
            "asset_type": "Stock",
            "qty": 100,
            "price": 95.00,
            "total_amount": 9500.00,
            "reason": "test",
            "account": "Firstrade",
        })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_reject_invalid_result():
    """Scenario: Reject invalid result type"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/trades", json={
            "date": "2026-03-06",
            "ticker": "CCJ",
            "action": "Buy",
            "asset_type": "Stock",
            "qty": 100,
            "price": 95.00,
            "total_amount": 9500.00,
            "result": "Maybe",
            "reason": "test",
            "account": "Firstrade",
        })
    assert resp.status_code == 422


# --- Querying Trades ---

@pytest.mark.asyncio
async def test_query_all_trades(mock_trades_data):
    """Scenario: Query all trades"""
    with patch("api.trades.get_trades", new_callable=AsyncMock, return_value=mock_trades_data):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/trades")

    data = resp.json()
    assert len(data["trades"]) == 3
    assert "summary" in data


@pytest.mark.asyncio
async def test_filter_by_ticker(mock_trades_data):
    """Scenario: Filter trades by ticker"""
    filtered = [t for t in mock_trades_data if t["ticker"] == "CCJ"]
    with patch("api.trades.get_trades", new_callable=AsyncMock, return_value=filtered):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/trades?ticker=CCJ")

    trades = resp.json()["trades"]
    assert all(t["ticker"] == "CCJ" for t in trades)


@pytest.mark.asyncio
async def test_filter_by_result(mock_trades_data):
    """Scenario: Filter trades by result"""
    wins = [t for t in mock_trades_data if t["result"] == "Win"]
    with patch("api.trades.get_trades", new_callable=AsyncMock, return_value=wins):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/trades?result=Win")

    trades = resp.json()["trades"]
    assert all(t["result"] == "Win" for t in trades)


# --- Trade Summary ---

@pytest.mark.asyncio
async def test_trade_summary_statistics(mock_trades_data):
    """Scenario: Calculate win rate and averages"""
    with patch("api.trades.get_trades", new_callable=AsyncMock, return_value=mock_trades_data):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/trades")

    summary = resp.json()["summary"]
    assert summary["wins"] == 1
    assert summary["losses"] == 1
    assert summary["total_realized_pl"] == -50.00
