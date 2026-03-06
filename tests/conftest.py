"""Shared fixtures for BDD and unit tests."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture
def mock_notion_us_stocks():
    """Mock Notion US stocks data."""
    return {
        "Firstrade": [
            {"ticker": "NVDA", "shares": 100, "avg_cost": 185.26},
            {"ticker": "GOOG", "shares": 200, "avg_cost": 307.61},
        ],
        "IBKR": [
            {"ticker": "VOO", "shares": 3.19, "avg_cost": 627.38},
            {"ticker": "NVDA", "shares": 27, "avg_cost": 185.26},
        ],
    }


@pytest.fixture
def mock_notion_tw_stocks():
    """Mock Notion TW stocks data."""
    return {
        "Yongfeng_B": [
            {"ticker": "2330.TW", "name": "台積電", "shares": 5000, "avg_cost": 854.56},
        ],
        "Cathay_TW": [
            {"ticker": "0050.TW", "name": "元大台灣50", "shares": 4075, "avg_cost": 61.26},
        ],
    }


@pytest.fixture
def mock_notion_options():
    """Mock Notion options data."""
    return [
        {"account": "Firstrade", "ticker": "CCJ", "expiry": "2026-03-13", "strike": 110, "type": "put", "qty": -1, "cost": 479.98},
        {"account": "Firstrade", "ticker": "GOOG", "expiry": "2026-03-21", "strike": 330, "type": "call", "qty": -1, "cost": 244.98},
    ]


@pytest.fixture
def mock_notion_bonds():
    return [
        {"name": "UBS 5.699%", "face": 280000, "coupon": 0.05699, "maturity": "2035-02-08", "cost": 299040},
        {"name": "BAC 5.468%", "face": 480000, "coupon": 0.05468, "maturity": "2035-01-23", "cost": 503400},
    ]


@pytest.fixture
def mock_notion_loans():
    return [
        {"name": "房屋貸款", "rate": 0.022, "balance": 19600000, "monthly": 33078, "periods_done": 37, "total_periods": 360},
        {"name": "其他貸款", "rate": 0.022, "balance": 39450000, "monthly": 66579, "periods_done": 22, "total_periods": 84},
    ]


@pytest.fixture
def mock_trades():
    return [
        {"id": "1", "date": "2026-03-05", "ticker": "CCJ", "action": "Sell", "asset_type": "Option", "qty": 1, "price": 4.80, "total_amount": 480.00, "pl": 350.00, "result": "Win", "reason": "收取權利金", "lesson": "提前平倉鎖利", "tags": ["Covered Put"], "account": "Firstrade"},
        {"id": "2", "date": "2026-03-01", "ticker": "MU", "action": "Close", "asset_type": "Option", "qty": 1, "price": 22.00, "total_amount": 2200.00, "pl": -400.00, "result": "Loss", "reason": "財報超預期", "lesson": "財報前不賣裸 call", "tags": ["Earnings Play"], "account": "Firstrade"},
        {"id": "3", "date": "2026-02-20", "ticker": "NVDA", "action": "Buy", "asset_type": "Stock", "qty": 50, "price": 185.00, "total_amount": 9250.00, "pl": None, "result": None, "reason": "長期看多", "lesson": None, "tags": ["Momentum"], "account": "IBKR"},
    ]


@pytest.fixture
def price_map():
    """Default price map for mocking."""
    return {
        "NVDA": 250.00,
        "GOOG": 280.00,
        "VOO": 550.00,
        "CCJ": 120.00,
        "2330.TW": 900.00,
        "0050.TW": 180.00,
        "USDTWD=X": 32.15,
    }


@pytest.fixture
def mock_price_cache(price_map):
    """Create a PriceCache that returns prices from price_map."""
    with patch("lib.pricing._fetch_price", side_effect=lambda t: price_map.get(t)):
        yield
