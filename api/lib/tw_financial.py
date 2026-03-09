"""Taiwan stock financial analysis using FinMind API (Huang Kuo-Hua method)."""

import os
import httpx
from datetime import datetime, timedelta


FINMIND_API = "https://api.finmindtrade.com/api/v4/data"
FINMIND_TOKEN = os.environ.get("FINMIND_TOKEN", "")

# Huang Kuo-Hua criteria
CRITERIA = {
    "revenue_yoy_months": 2,        # consecutive months > 10%
    "revenue_yoy_min": 10,          # %
    "current_ratio_min": 300,       # %
    "quick_ratio_min": 150,         # %
    "cash_to_assets_min": 10,       # %
    "cash_to_assets_max": 25,       # %
    "net_profit_margin_min": 2,     # %
    "roe_min": 20,                  # %
    "ocf_positive": True,
    "asset_turnover_min": 1,
    "price_min": 50,                # TWD
    "capital_max": 10_000_000_000,  # 100 億
}


async def fetch_finmind(dataset: str, stock_id: str, start_date: str) -> list[dict]:
    """Generic FinMind data fetch."""
    params = {
        "dataset": dataset,
        "data_id": stock_id,
        "start_date": start_date,
        "token": FINMIND_TOKEN,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(FINMIND_API, params=params)
        r.raise_for_status()
        data = r.json()
        return data.get("data", [])


async def fetch_monthly_revenue(stock_id: str, months: int = 24) -> list[dict]:
    """Fetch monthly revenue data."""
    start = (datetime.now() - timedelta(days=months * 35)).strftime("%Y-%m-%d")
    return await fetch_finmind("TaiwanStockMonthRevenue", stock_id, start)


async def fetch_financial_statements(stock_id: str) -> list[dict]:
    """Fetch income statement (quarterly)."""
    start = (datetime.now() - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
    return await fetch_finmind("TaiwanStockFinancialStatements", stock_id, start)


async def fetch_balance_sheet(stock_id: str) -> list[dict]:
    """Fetch balance sheet data."""
    start = (datetime.now() - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
    return await fetch_finmind("TaiwanStockBalanceSheet", stock_id, start)


async def fetch_cash_flows(stock_id: str) -> list[dict]:
    """Fetch cash flow statement."""
    start = (datetime.now() - timedelta(days=365 * 3)).strftime("%Y-%m-%d")
    return await fetch_finmind("TaiwanStockCashFlowsStatement", stock_id, start)


async def fetch_per(stock_id: str) -> list[dict]:
    """Fetch PER (price-to-earnings ratio) data."""
    start = (datetime.now() - timedelta(days=365 * 2)).strftime("%Y-%m-%d")
    return await fetch_finmind("TaiwanStockPER", stock_id, start)


def _extract_metric(data: list[dict], metric_type: str) -> list[dict]:
    """Extract rows matching a specific type from FinMind financial data."""
    return [r for r in data if r.get("type") == metric_type]


def analyze_revenue_growth(revenues: list[dict]) -> dict:
    """Analyze monthly revenue YoY growth. Check consecutive months > 10%."""
    if not revenues:
        return {"pass": False, "detail": "No revenue data", "recent_yoy": []}

    # Sort by revenue_year and revenue_month
    revenues = sorted(revenues, key=lambda x: (x.get("revenue_year", 0), x.get("revenue_month", 0)))

    # Group by (year, month) for YoY calculation
    by_month: dict[int, dict[int, int]] = {}
    for rev in revenues:
        year = rev.get("revenue_year", 0)
        month = rev.get("revenue_month", 0)
        if year and month:
            by_month.setdefault(month, {})[year] = rev.get("revenue", 0)

    recent_yoy = []
    for rev in revenues:
        year = rev.get("revenue_year", 0)
        month = rev.get("revenue_month", 0)
        prev_rev = by_month.get(month, {}).get(year - 1)
        curr_rev = rev.get("revenue", 0)
        if prev_rev and prev_rev > 0:
            yoy = round((curr_rev - prev_rev) / prev_rev * 100, 2)
            recent_yoy.append({
                "date": f"{year}-{month:02d}",
                "revenue": curr_rev,
                "yoy_pct": yoy,
            })

    # Check last N months consecutive > threshold
    n = CRITERIA["revenue_yoy_months"]
    threshold = CRITERIA["revenue_yoy_min"]
    last_n = recent_yoy[-n:] if len(recent_yoy) >= n else recent_yoy
    consecutive = len(last_n) >= n and all(r["yoy_pct"] > threshold for r in last_n)

    return {
        "pass": consecutive,
        "consecutive_months_above_10pct": sum(1 for r in reversed(recent_yoy) if r["yoy_pct"] > threshold),
        "recent_yoy": recent_yoy[-6:],
    }


def analyze_balance_sheet_safety(balance: list[dict]) -> dict:
    """Analyze current ratio, quick ratio from balance sheet data."""
    if not balance:
        return {"pass": False, "detail": "No balance sheet data"}

    # FinMind uses English type names
    current_assets = _extract_metric(balance, "CurrentAssets")
    current_liabilities = _extract_metric(balance, "CurrentLiabilities")
    inventories = _extract_metric(balance, "Inventories")
    total_assets = _extract_metric(balance, "TotalAssets")
    cash = _extract_metric(balance, "CashAndCashEquivalents")

    def latest_val(items):
        if not items:
            return None
        sorted_items = sorted(items, key=lambda x: x.get("date", ""))
        return sorted_items[-1].get("value")

    ca = latest_val(current_assets)
    cl = latest_val(current_liabilities)
    inv = latest_val(inventories) or 0
    ta = latest_val(total_assets)
    cash_val = latest_val(cash)

    result = {"current_ratio": None, "quick_ratio": None, "cash_to_assets": None, "pass": False}

    if ca and cl and cl != 0:
        result["current_ratio"] = round(ca / cl * 100, 1)
        result["quick_ratio"] = round((ca - inv) / cl * 100, 1)

    if cash_val and ta and ta != 0:
        result["cash_to_assets"] = round(cash_val / ta * 100, 1)

    cr_ok = result["current_ratio"] and result["current_ratio"] >= CRITERIA["current_ratio_min"]
    qr_ok = result["quick_ratio"] and result["quick_ratio"] >= CRITERIA["quick_ratio_min"]
    cash_ok = (result["cash_to_assets"] is not None and
               CRITERIA["cash_to_assets_min"] <= result["cash_to_assets"] <= CRITERIA["cash_to_assets_max"])

    result["pass"] = bool(cr_ok and qr_ok and cash_ok)
    result["criteria"] = {
        "current_ratio_ok": bool(cr_ok),
        "quick_ratio_ok": bool(qr_ok),
        "cash_to_assets_ok": bool(cash_ok),
    }
    return result


def analyze_profitability(statements: list[dict], balance: list[dict]) -> dict:
    """Analyze net profit margin and ROE."""
    if not statements:
        return {"pass": False, "detail": "No financial statement data"}

    # FinMind income statement types
    net_income = _extract_metric(statements, "IncomeAfterTaxes")
    revenue = _extract_metric(statements, "Revenue")
    # Equity is in balance sheet
    equity_list = _extract_metric(balance, "Equity") if balance else []

    result = {"net_profit_margin": None, "roe": None, "pass": False}

    if net_income and revenue:
        ni_sorted = sorted(net_income, key=lambda x: x.get("date", ""))
        rev_sorted = sorted(revenue, key=lambda x: x.get("date", ""))
        # Use latest 4 quarters (TTM)
        recent_ni = sum(r.get("value", 0) for r in ni_sorted[-4:])
        recent_rev = sum(r.get("value", 0) for r in rev_sorted[-4:])
        if recent_rev != 0:
            result["net_profit_margin"] = round(recent_ni / recent_rev * 100, 2)

    if net_income and equity_list:
        ni_sorted = sorted(net_income, key=lambda x: x.get("date", ""))
        eq_sorted = sorted(equity_list, key=lambda x: x.get("date", ""))
        recent_ni = sum(r.get("value", 0) for r in ni_sorted[-4:])
        latest_eq = eq_sorted[-1].get("value", 0)
        if latest_eq != 0:
            result["roe"] = round(recent_ni / latest_eq * 100, 2)

    npm_ok = result["net_profit_margin"] is not None and result["net_profit_margin"] >= CRITERIA["net_profit_margin_min"]
    roe_ok = result["roe"] is not None and result["roe"] >= CRITERIA["roe_min"]
    result["pass"] = bool(npm_ok and roe_ok)
    result["criteria"] = {"net_profit_margin_ok": bool(npm_ok), "roe_ok": bool(roe_ok)}
    return result


def analyze_cash_flow_health(cash_flows: list[dict]) -> dict:
    """Analyze OCF positivity and trend."""
    if not cash_flows:
        return {"pass": False, "detail": "No cash flow data"}

    # FinMind cash flow types
    ocf_items = _extract_metric(cash_flows, "CashFlowsFromOperatingActivities")
    if not ocf_items:
        ocf_items = _extract_metric(cash_flows, "NetCashInflowFromOperatingActivities")

    if not ocf_items:
        return {"pass": False, "detail": "No OCF data found"}

    ocf_sorted = sorted(ocf_items, key=lambda x: x.get("date", ""))
    ocf_values = [{"date": r.get("date"), "value": r.get("value", 0)} for r in ocf_sorted]

    latest_ocf = ocf_values[-1]["value"] if ocf_values else 0
    ocf_positive = latest_ocf > 0

    trending_up = False
    if len(ocf_values) >= 2:
        trending_up = ocf_values[-1]["value"] > ocf_values[-2]["value"]

    # FCF (OCF - investing)
    invest_items = _extract_metric(cash_flows, "CashProvidedByInvestingActivities")
    fcf = None
    if invest_items:
        inv_sorted = sorted(invest_items, key=lambda x: x.get("date", ""))
        latest_invest = inv_sorted[-1].get("value", 0)
        fcf = latest_ocf + latest_invest

    return {
        "ocf_positive": ocf_positive,
        "ocf_trending_up": trending_up,
        "latest_ocf": latest_ocf,
        "fcf": fcf,
        "ocf_history": ocf_values[-4:],
        "pass": ocf_positive,
    }


def analyze_asset_turnover(statements: list[dict], balance: list[dict]) -> dict:
    """Analyze total asset turnover ratio."""
    revenue = _extract_metric(statements, "Revenue")
    total_assets = _extract_metric(balance, "TotalAssets")

    if not revenue or not total_assets:
        return {"pass": False, "detail": "Missing data", "asset_turnover": None}

    rev_sorted = sorted(revenue, key=lambda x: x.get("date", ""))
    ta_sorted = sorted(total_assets, key=lambda x: x.get("date", ""))

    ttm_rev = sum(r.get("value", 0) for r in rev_sorted[-4:])
    latest_ta = ta_sorted[-1].get("value", 0)

    turnover = round(ttm_rev / latest_ta, 2) if latest_ta else 0

    return {
        "asset_turnover": turnover,
        "pass": turnover >= CRITERIA["asset_turnover_min"],
    }


def estimate_eps_and_target(statements: list[dict], per_data: list[dict]) -> dict:
    """Estimate forward EPS and target price based on historical PE."""
    result = {"estimated_eps": None, "avg_pe": None, "target_price": None}

    eps_items = _extract_metric(statements, "EPS")
    if eps_items:
        eps_sorted = sorted(eps_items, key=lambda x: x.get("date", ""))
        ttm_eps = sum(r.get("value", 0) for r in eps_sorted[-4:])
        result["estimated_eps"] = round(ttm_eps, 2)

    if per_data:
        pe_values = [r.get("PER", 0) for r in per_data if r.get("PER") and r.get("PER") > 0]
        if pe_values:
            result["avg_pe"] = round(sum(pe_values) / len(pe_values), 1)

    if result["estimated_eps"] and result["avg_pe"]:
        result["target_price"] = round(result["estimated_eps"] * result["avg_pe"], 1)

    return result


async def analyze_stock(stock_id: str) -> dict:
    """Full financial analysis for a Taiwan stock using Huang Kuo-Hua method."""
    import asyncio
    revenues, statements, balance, cash_flows, per_data = await asyncio.gather(
        fetch_monthly_revenue(stock_id),
        fetch_financial_statements(stock_id),
        fetch_balance_sheet(stock_id),
        fetch_cash_flows(stock_id),
        fetch_per(stock_id),
    )

    revenue_analysis = analyze_revenue_growth(revenues)
    balance_analysis = analyze_balance_sheet_safety(balance)
    profit_analysis = analyze_profitability(statements, balance)
    cashflow_analysis = analyze_cash_flow_health(cash_flows)
    turnover_analysis = analyze_asset_turnover(statements, balance)
    valuation = estimate_eps_and_target(statements, per_data)

    checks = [
        revenue_analysis["pass"],
        balance_analysis["pass"],
        profit_analysis["pass"],
        cashflow_analysis["pass"],
        turnover_analysis["pass"],
    ]
    score = sum(1 for c in checks if c)

    return {
        "stock_id": stock_id,
        "market": "TW",
        "method": "Huang Kuo-Hua",
        "score": f"{score}/5",
        "overall_pass": score >= 4,
        "revenue_growth": revenue_analysis,
        "balance_sheet": balance_analysis,
        "profitability": profit_analysis,
        "cash_flow": cashflow_analysis,
        "asset_turnover": turnover_analysis,
        "valuation": valuation,
        "criteria_reference": CRITERIA,
    }
