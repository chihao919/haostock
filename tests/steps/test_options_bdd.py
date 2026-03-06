"""BDD tests for Options Positions feature."""

import pytest
from datetime import date
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from api.options import app
from lib.calculator import dte, urgency, itm_otm, suggest_action


# --- Pure logic tests (no API call needed) ---

class TestITMOTMDetection:
    def test_otm_put(self):
        assert itm_otm(120.0, 110.0, "put") == "OTM $10.0"

    def test_itm_put(self):
        assert itm_otm(105.0, 110.0, "put") == "ITM $5.0"

    def test_otm_call(self):
        assert itm_otm(320.0, 330.0, "call") == "OTM $10.0"

    def test_itm_call(self):
        assert itm_otm(340.0, 330.0, "call") == "ITM $10.0"


class TestDTECalculation:
    def test_dte_7_days(self):
        assert dte("2026-03-13", today=date(2026, 3, 6)) == 7


class TestUrgencyLevels:
    @pytest.mark.parametrize("today_str,expected", [
        (date(2026, 3, 6), "red"),      # 7 days
        (date(2026, 3, 1), "yellow"),    # 12 days
        (date(2026, 2, 1), "green"),     # 40 days
    ])
    def test_urgency(self, today_str, expected):
        days = dte("2026-03-13", today=today_str)
        assert urgency(days) == expected


class TestActionSuggestions:
    def test_expired(self):
        assert suggest_action(0, 50, "OTM $10.0") == "EXPIRED"

    def test_let_expire_otm(self):
        assert suggest_action(3, 90, "OTM $15.0") == "Let expire"

    def test_close_roll_itm_urgent(self):
        assert suggest_action(3, 20, "ITM $5.0") == "Close/Roll URGENT"

    def test_close_high_profit(self):
        assert suggest_action(30, 80, "OTM $20.0") == "Close (75%+ profit)"

    def test_monitor(self):
        assert suggest_action(15, 40, "OTM $10.0") == "Monitor"

    def test_hold(self):
        assert suggest_action(45, 30, "OTM $20.0") == "Hold"


# --- API integration tests ---

@pytest.fixture
def notion_options():
    return [
        {"account": "Firstrade", "ticker": "CCJ", "expiry": "2026-03-13", "strike": 110, "type": "put", "qty": -1, "cost": 479.98},
        {"account": "Firstrade", "ticker": "GOOG", "expiry": "2026-04-21", "strike": 330, "type": "call", "qty": -1, "cost": 244.98},
    ]


@pytest.mark.asyncio
async def test_options_sorted_by_dte(notion_options):
    """Scenario: Options sorted by DTE ascending"""
    prices = {"CCJ": 120.00, "GOOG": 320.00}
    with patch("api.options.get_options", new_callable=AsyncMock, return_value=notion_options), \
         patch("lib.pricing._fetch_price", side_effect=lambda t: prices.get(t)), \
         patch("lib.pricing.PriceCache.get_option_value", return_value=100.00):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/options")

    data = resp.json()
    positions = data["positions"]
    assert positions[0]["dte"] <= positions[1]["dte"]


@pytest.mark.asyncio
async def test_options_summary(notion_options):
    """Scenario: Options summary totals"""
    prices = {"CCJ": 120.00, "GOOG": 320.00}
    with patch("api.options.get_options", new_callable=AsyncMock, return_value=notion_options), \
         patch("lib.pricing._fetch_price", side_effect=lambda t: prices.get(t)), \
         patch("lib.pricing.PriceCache.get_option_value", return_value=100.00):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/options")

    summary = resp.json()["summary"]
    assert "total_cost_basis" in summary
    assert "total_current_value" in summary
    assert "total_pl" in summary


@pytest.mark.asyncio
async def test_options_pl_calculation():
    """Scenario: Calculate options P&L for short position"""
    options = [{"account": "Firstrade", "ticker": "CCJ", "expiry": "2026-03-13", "strike": 110, "type": "put", "qty": -1, "cost": 479.98}]
    with patch("api.options.get_options", new_callable=AsyncMock, return_value=options), \
         patch("lib.pricing._fetch_price", side_effect=lambda t: {"CCJ": 120.00}.get(t)), \
         patch("lib.pricing.PriceCache.get_option_value", return_value=120.00):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/options")

    pos = resp.json()["positions"][0]
    assert pos["unrealized_pl"] == 359.98
    assert pos["pl_pct"] == 75.0
