"""BDD tests for Net Worth Summary feature."""

import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from api.networth import app


@pytest.fixture
def notion_mocks():
    us = {"Firstrade": [{"ticker": "NVDA", "shares": 100, "avg_cost": 185.26}]}
    tw = {"Yongfeng_B": [{"ticker": "2330.TW", "name": "台積電", "shares": 5000, "avg_cost": 854.56}]}
    bonds = [
        {"name": "UBS 5.699%", "face": 280000, "coupon": 0.05699, "maturity": "2035-02-08", "cost": 299040},
        {"name": "BAC 5.468%", "face": 480000, "coupon": 0.05468, "maturity": "2035-01-23", "cost": 503400},
    ]
    loans = [
        {"name": "房屋貸款", "rate": 0.022, "balance": 19600000, "monthly": 33078, "periods_done": 37, "total_periods": 360},
        {"name": "其他貸款", "rate": 0.022, "balance": 39450000, "monthly": 66579, "periods_done": 22, "total_periods": 84},
    ]
    return us, tw, bonds, loans


@pytest.fixture
def prices():
    return {"NVDA": 250.00, "2330.TW": 900.00, "USDTWD=X": 32.15}


async def _call_networth(notion_mocks, prices):
    us, tw, bonds, loans = notion_mocks
    with patch("api.networth.get_us_stocks", new_callable=AsyncMock, return_value=us), \
         patch("api.networth.get_tw_stocks", new_callable=AsyncMock, return_value=tw), \
         patch("api.networth.get_bonds", new_callable=AsyncMock, return_value=bonds), \
         patch("api.networth.get_loans", new_callable=AsyncMock, return_value=loans), \
         patch("lib.pricing._fetch_price", side_effect=lambda t: prices.get(t)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.get("/api/networth")


@pytest.mark.asyncio
async def test_total_assets(notion_mocks, prices):
    """Scenario: Calculate total assets in USD"""
    resp = await _call_networth(notion_mocks, prices)
    data = resp.json()
    assert data["assets"]["us_stocks_usd"] == 25000.00
    assert data["assets"]["tw_stocks_usd"] == round(4500000 / 32.15, 2)
    assert data["assets"]["bonds_cost_usd"] == 802440


@pytest.mark.asyncio
async def test_liabilities(notion_mocks, prices):
    """Scenario: Calculate total liabilities"""
    resp = await _call_networth(notion_mocks, prices)
    data = resp.json()
    assert data["liabilities"]["total_loans_twd"] == 59050000
    assert data["liabilities"]["monthly_payments_twd"] == 99657


@pytest.mark.asyncio
async def test_loans_usd_conversion(notion_mocks, prices):
    """Scenario: Convert loans TWD to USD"""
    resp = await _call_networth(notion_mocks, prices)
    data = resp.json()
    assert data["liabilities"]["total_loans_usd"] == round(59050000 / 32.15, 2)


@pytest.mark.asyncio
async def test_bond_income_withholding(notion_mocks, prices):
    """Scenario: Calculate bond income with 30% withholding tax"""
    resp = await _call_networth(notion_mocks, prices)
    data = resp.json()
    gross = data["income"]["bonds_annual_gross_usd"]
    net = data["income"]["bonds_annual_net_usd"]
    assert net == round(gross * 0.70, 2)
    assert data["income"]["bonds_monthly_net_usd"] == round(net / 12, 2)
    assert data["income"]["withholding_tax_rate"] == "30%"


@pytest.mark.asyncio
async def test_net_worth_formula(notion_mocks, prices):
    """Scenario: Net worth = assets - liabilities"""
    resp = await _call_networth(notion_mocks, prices)
    data = resp.json()
    expected = round(data["assets"]["total_assets_usd"] - data["liabilities"]["total_loans_usd"], 2)
    assert abs(data["net_worth_usd"] - expected) < 0.02


@pytest.mark.asyncio
async def test_includes_fx_rate(notion_mocks, prices):
    """Scenario: Response includes exchange rate"""
    resp = await _call_networth(notion_mocks, prices)
    assert resp.json()["usdtwd_rate"] == 32.15
