"""BDD tests for Financial Analysis feature."""

import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from api.index import app


def _make_tw_revenue(yoy_pct):
    """Create mock FinMind revenue data with given YoY%."""
    return [
        {"stock_id": "2330", "revenue_year": 2024, "revenue_month": 11, "revenue": 100_000, "date": "2025-01-01"},
        {"stock_id": "2330", "revenue_year": 2024, "revenue_month": 12, "revenue": 100_000, "date": "2025-02-01"},
        {"stock_id": "2330", "revenue_year": 2025, "revenue_month": 11, "revenue": int(100_000 * (1 + yoy_pct / 100)), "date": "2026-01-01"},
        {"stock_id": "2330", "revenue_year": 2025, "revenue_month": 12, "revenue": int(100_000 * (1 + yoy_pct / 100)), "date": "2026-02-01"},
    ]


def _make_tw_balance(cr_pct, cash_pct):
    """Create mock balance sheet for target CR and cash/TA ratio."""
    cl = 1000
    ca = cl * cr_pct / 100
    ta = 10000
    cash = ta * cash_pct / 100
    return [
        {"type": "CurrentAssets", "value": ca, "date": "2025-12-31"},
        {"type": "CurrentLiabilities", "value": cl, "date": "2025-12-31"},
        {"type": "Inventories", "value": ca * 0.1, "date": "2025-12-31"},
        {"type": "TotalAssets", "value": ta, "date": "2025-12-31"},
        {"type": "CashAndCashEquivalents", "value": cash, "date": "2025-12-31"},
        {"type": "Equity", "value": 5000, "date": "2025-12-31"},
    ]


def _make_tw_statements(npm_pct, roe_pct, equity=5000):
    """Create mock income statement data."""
    revenue_per_q = 2500
    ni_per_q = revenue_per_q * npm_pct / 100
    stmts = []
    for i, m in enumerate([3, 6, 9, 12]):
        stmts.append({"type": "Revenue", "value": revenue_per_q, "date": f"2025-{m:02d}-30"})
        stmts.append({"type": "IncomeAfterTaxes", "value": ni_per_q, "date": f"2025-{m:02d}-30"})
        stmts.append({"type": "EPS", "value": 5.0, "date": f"2025-{m:02d}-30"})
    return stmts


def _make_tw_cashflows(ocf_positive=True, trending_up=True):
    """Create mock cash flow data."""
    ocf1 = 500 if ocf_positive else -100
    ocf2 = 800 if trending_up else 300
    return [
        {"type": "CashFlowsFromOperatingActivities", "value": ocf1, "date": "2024-12-31"},
        {"type": "CashFlowsFromOperatingActivities", "value": ocf2, "date": "2025-12-31"},
        {"type": "CashProvidedByInvestingActivities", "value": -200, "date": "2025-12-31"},
    ]


def _make_tw_per():
    return [{"PER": 20.0}, {"PER": 25.0}, {"PER": 30.0}]


def _mock_finmind_strong():
    """Mock all FinMind calls for a strong TW stock."""
    revenues = _make_tw_revenue(20)
    balance = _make_tw_balance(400, 15)
    statements = _make_tw_statements(20, 40)
    cashflows = _make_tw_cashflows(True, True)
    # Asset turnover > 1: need revenue/TA > 1, so boost revenue
    for s in statements:
        if s["type"] == "Revenue":
            s["value"] = 3000  # 4 * 3000 / 10000 = 1.2
    per = _make_tw_per()

    async def mock_fetch(dataset, stock_id, start_date):
        mapping = {
            "TaiwanStockMonthRevenue": revenues,
            "TaiwanStockFinancialStatements": statements,
            "TaiwanStockBalanceSheet": balance,
            "TaiwanStockCashFlowsStatement": cashflows,
            "TaiwanStockPER": per,
        }
        return mapping.get(dataset, [])

    return mock_fetch


def _mock_finmind_weak():
    """Mock all FinMind calls for a weak TW stock."""
    revenues = _make_tw_revenue(5)
    balance = _make_tw_balance(150, 5)
    statements = _make_tw_statements(1, 5)
    cashflows = _make_tw_cashflows(False, False)
    per = []

    async def mock_fetch(dataset, stock_id, start_date):
        mapping = {
            "TaiwanStockMonthRevenue": revenues,
            "TaiwanStockFinancialStatements": statements,
            "TaiwanStockBalanceSheet": balance,
            "TaiwanStockCashFlowsStatement": cashflows,
            "TaiwanStockPER": per,
        }
        return mapping.get(dataset, [])

    return mock_fetch


# --- TW Stock BDD Tests ---

@pytest.mark.asyncio
async def test_tw_strong_fundamentals():
    """Scenario: Analyze a Taiwan stock with strong fundamentals"""
    with patch("lib.tw_financial.fetch_finmind", side_effect=_mock_finmind_strong()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/financial/analyze/2330")

    assert resp.status_code == 200
    data = resp.json()
    assert data["market"] == "TW"
    assert data["method"] == "Huang Kuo-Hua"
    assert data["score"] == "5/5"
    assert data["overall_pass"] is True


@pytest.mark.asyncio
async def test_tw_weak_fundamentals():
    """Scenario: Analyze a Taiwan stock with weak fundamentals"""
    with patch("lib.tw_financial.fetch_finmind", side_effect=_mock_finmind_weak()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/financial/analyze/9999")

    data = resp.json()
    assert data["overall_pass"] is False


@pytest.mark.asyncio
async def test_tw_valuation_contains_eps():
    """Scenario: TW stock returns EPS and target price"""
    with patch("lib.tw_financial.fetch_finmind", side_effect=_mock_finmind_strong()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/financial/analyze/2330")

    data = resp.json()
    assert data["valuation"]["estimated_eps"] is not None
    assert data["valuation"]["avg_pe"] is not None
    assert data["valuation"]["target_price"] is not None


@pytest.mark.asyncio
async def test_tw_revenue_analysis_detail():
    """Scenario: TW revenue analysis returns YoY data"""
    with patch("lib.tw_financial.fetch_finmind", side_effect=_mock_finmind_strong()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/financial/analyze/2330")

    data = resp.json()
    assert data["revenue_growth"]["pass"] is True
    assert len(data["revenue_growth"]["recent_yoy"]) > 0


@pytest.mark.asyncio
async def test_tw_balance_sheet_detail():
    """Scenario: TW balance sheet analysis returns ratios"""
    with patch("lib.tw_financial.fetch_finmind", side_effect=_mock_finmind_strong()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/financial/analyze/2330")

    data = resp.json()
    bs = data["balance_sheet"]
    assert bs["current_ratio"] is not None
    assert bs["quick_ratio"] is not None
    assert bs["cash_to_assets"] is not None


# --- US Stock BDD Tests ---

def _mock_yfinance_strong():
    """Return mock yfinance data for a strong US stock."""
    import pandas as pd
    info = {
        "shortName": "NVIDIA Corp",
        "revenueGrowth": 0.35,
        "earningsGrowth": 0.50,
        "profitMargins": 0.25,
        "returnOnEquity": 0.35,
        "grossMargins": 0.60,
        "trailingPE": 30.0,
        "forwardPE": 25.0,
        "priceToBook": 8.0,
        "pegRatio": 1.5,
        "marketCap": 1_000_000_000_000,
        "targetMeanPrice": 200.0,
        "currentPrice": 180.0,
    }
    income_stmt = pd.DataFrame({
        "2025-12-31": [10_000_000_000, 4_000_000_000, 3_000_000_000,
                       -100_000_000, 2_900_000_000, 600_000_000, 2_300_000_000],
    }, index=["Total Revenue", "Cost Of Revenue", "EBIT",
              "Interest Expense", "Pretax Income", "Tax Provision", "Net Income"]).T.T
    cashflow = pd.DataFrame({
        "2025-12-31": [5_000_000_000, -1_000_000_000],
    }, index=["Operating Cash Flow", "Capital Expenditure"]).T.T
    balance = pd.DataFrame({
        "2025-12-31": [3_000_000_000, 1_000_000_000, 200_000_000, 500_000_000,
                       2_000_000_000, 300_000_000, 400_000_000, 100_000_000, 800_000_000],
    }, index=["Current Assets", "Current Liabilities", "Inventory", "Total Debt",
              "Stockholders Equity", "Cash And Cash Equivalents",
              "Accounts Receivable", "Accounts Payable", "Accounts Receivable"]).T.T
    # Fix duplicate index - use unique names
    balance = pd.DataFrame({
        "2025-12-31": [3_000_000_000, 1_000_000_000, 200_000_000, 500_000_000,
                       2_000_000_000, 300_000_000, 400_000_000, 800_000_000],
    }, index=["Current Assets", "Current Liabilities", "Inventory", "Total Debt",
              "Stockholders Equity", "Cash And Cash Equivalents",
              "Accounts Receivable", "Accounts Payable"]).T.T
    return {
        "info": info,
        "income_stmt": income_stmt,
        "balance_sheet": balance,
        "cashflow": cashflow,
    }


def _mock_yfinance_weak():
    """Return mock yfinance data for a weak US stock."""
    import pandas as pd
    info = {
        "shortName": "Weak Corp",
        "revenueGrowth": 0.05,
        "earningsGrowth": 0.01,
        "profitMargins": 0.01,
        "returnOnEquity": 0.10,
        "grossMargins": 0.20,
    }
    return {
        "info": info,
        "income_stmt": pd.DataFrame(),
        "balance_sheet": pd.DataFrame(),
        "cashflow": pd.DataFrame(),
    }


@pytest.mark.asyncio
async def test_us_strong_fundamentals():
    """Scenario: Analyze a US stock with strong fundamentals"""
    with patch("lib.us_financial.fetch_us_financials", return_value=_mock_yfinance_strong()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/financial/analyze/NVDA")

    assert resp.status_code == 200
    data = resp.json()
    assert data["market"] == "US"
    assert data["overall_pass"] is True
    assert data["name"] == "NVIDIA Corp"
    assert "financial_strength" in data


@pytest.mark.asyncio
async def test_us_weak_fundamentals():
    """Scenario: Analyze a US stock with weak profitability"""
    with patch("lib.us_financial.fetch_us_financials", return_value=_mock_yfinance_weak()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/financial/analyze/WEAK")

    data = resp.json()
    assert data["overall_pass"] is False


@pytest.mark.asyncio
async def test_us_valuation_contains_pe():
    """Scenario: US stock returns PE and forward PE"""
    with patch("lib.us_financial.fetch_us_financials", return_value=_mock_yfinance_strong()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/financial/analyze/NVDA")

    data = resp.json()
    assert data["valuation"]["pe_ratio"] == 30.0
    assert data["valuation"]["forward_pe"] == 25.0


# --- Auto-detection ---

@pytest.mark.asyncio
async def test_numeric_ticker_routes_to_tw():
    """Scenario: Numeric ticker routes to TW analysis"""
    with patch("lib.tw_financial.fetch_finmind", side_effect=_mock_finmind_strong()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/financial/analyze/2330")

    assert resp.json()["market"] == "TW"


@pytest.mark.asyncio
async def test_alpha_ticker_routes_to_us():
    """Scenario: Alpha ticker routes to US analysis"""
    with patch("lib.us_financial.fetch_us_financials", return_value=_mock_yfinance_strong()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/financial/analyze/AAPL")

    assert resp.json()["market"] == "US"


@pytest.mark.asyncio
async def test_response_contains_timestamp():
    """Every response should include a timestamp."""
    with patch("lib.us_financial.fetch_us_financials", return_value=_mock_yfinance_strong()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/financial/analyze/NVDA")

    assert "timestamp" in resp.json()


@pytest.mark.asyncio
async def test_tw_criteria_reference_included():
    """TW analysis should include criteria reference for transparency."""
    with patch("lib.tw_financial.fetch_finmind", side_effect=_mock_finmind_strong()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/financial/analyze/2330")

    data = resp.json()
    assert "criteria_reference" in data
    assert data["criteria_reference"]["revenue_yoy_min"] == 10
    assert data["criteria_reference"]["roe_min"] == 20
