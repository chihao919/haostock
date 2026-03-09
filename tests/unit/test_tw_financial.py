"""Unit tests for Taiwan stock financial analysis module."""

import pytest
from lib.tw_financial import (
    analyze_revenue_growth,
    analyze_balance_sheet_safety,
    analyze_profitability,
    analyze_cash_flow_health,
    analyze_asset_turnover,
    estimate_eps_and_target,
)


# --- Revenue Growth ---

class TestAnalyzeRevenueGrowth:
    def test_consecutive_yoy_above_10pct(self):
        revenues = [
            {"revenue_year": 2024, "revenue_month": 11, "revenue": 100, "date": "2025-01-01"},
            {"revenue_year": 2024, "revenue_month": 12, "revenue": 110, "date": "2025-02-01"},
            {"revenue_year": 2025, "revenue_month": 11, "revenue": 120, "date": "2026-01-01"},
            {"revenue_year": 2025, "revenue_month": 12, "revenue": 130, "date": "2026-02-01"},
        ]
        result = analyze_revenue_growth(revenues)
        assert result["pass"] is True
        assert len(result["recent_yoy"]) == 2

    def test_yoy_below_threshold_fails(self):
        revenues = [
            {"revenue_year": 2024, "revenue_month": 11, "revenue": 100, "date": "2025-01-01"},
            {"revenue_year": 2024, "revenue_month": 12, "revenue": 100, "date": "2025-02-01"},
            {"revenue_year": 2025, "revenue_month": 11, "revenue": 105, "date": "2026-01-01"},
            {"revenue_year": 2025, "revenue_month": 12, "revenue": 115, "date": "2026-02-01"},
        ]
        result = analyze_revenue_growth(revenues)
        # month 11: 5% (fail), month 12: 15% (pass) -> not consecutive
        assert result["pass"] is False

    def test_empty_revenues(self):
        result = analyze_revenue_growth([])
        assert result["pass"] is False

    def test_yoy_calculation_accuracy(self):
        revenues = [
            {"revenue_year": 2024, "revenue_month": 1, "revenue": 200, "date": "2024-02-01"},
            {"revenue_year": 2025, "revenue_month": 1, "revenue": 260, "date": "2025-02-01"},
        ]
        result = analyze_revenue_growth(revenues)
        assert result["recent_yoy"][0]["yoy_pct"] == 30.0

    def test_single_month_not_enough_for_consecutive(self):
        revenues = [
            {"revenue_year": 2024, "revenue_month": 1, "revenue": 100, "date": "2024-02-01"},
            {"revenue_year": 2025, "revenue_month": 1, "revenue": 150, "date": "2025-02-01"},
        ]
        result = analyze_revenue_growth(revenues)
        # Only 1 month of YoY data, need 2 consecutive
        assert result["pass"] is False


# --- Balance Sheet Safety ---

class TestAnalyzeBalanceSheetSafety:
    def _make_balance(self, ca, cl, inv, ta, cash):
        """Helper to create balance sheet data."""
        date = "2025-12-31"
        items = []
        if ca is not None:
            items.append({"type": "CurrentAssets", "value": ca, "date": date})
        if cl is not None:
            items.append({"type": "CurrentLiabilities", "value": cl, "date": date})
        if inv is not None:
            items.append({"type": "Inventories", "value": inv, "date": date})
        if ta is not None:
            items.append({"type": "TotalAssets", "value": ta, "date": date})
        if cash is not None:
            items.append({"type": "CashAndCashEquivalents", "value": cash, "date": date})
        return items

    def test_all_criteria_pass(self):
        # CR=400%, QR=300%, Cash/TA=15%
        balance = self._make_balance(ca=400, cl=100, inv=100, ta=1000, cash=150)
        result = analyze_balance_sheet_safety(balance)
        assert result["pass"] is True
        assert result["current_ratio"] == 400.0
        assert result["quick_ratio"] == 300.0
        assert result["cash_to_assets"] == 15.0

    def test_low_current_ratio_fails(self):
        # CR=200% (< 300%)
        balance = self._make_balance(ca=200, cl=100, inv=50, ta=1000, cash=150)
        result = analyze_balance_sheet_safety(balance)
        assert result["pass"] is False
        assert result["criteria"]["current_ratio_ok"] is False

    def test_low_quick_ratio_fails(self):
        # CR=350%, QR=100% (< 150%)
        balance = self._make_balance(ca=350, cl=100, inv=250, ta=1000, cash=150)
        result = analyze_balance_sheet_safety(balance)
        assert result["pass"] is False
        assert result["criteria"]["quick_ratio_ok"] is False

    def test_cash_too_high_fails(self):
        # Cash/TA=30% (> 25%)
        balance = self._make_balance(ca=400, cl=100, inv=50, ta=1000, cash=300)
        result = analyze_balance_sheet_safety(balance)
        assert result["pass"] is False
        assert result["criteria"]["cash_to_assets_ok"] is False

    def test_cash_too_low_fails(self):
        # Cash/TA=5% (< 10%)
        balance = self._make_balance(ca=400, cl=100, inv=50, ta=1000, cash=50)
        result = analyze_balance_sheet_safety(balance)
        assert result["pass"] is False
        assert result["criteria"]["cash_to_assets_ok"] is False

    def test_empty_balance_sheet(self):
        result = analyze_balance_sheet_safety([])
        assert result["pass"] is False


# --- Profitability ---

class TestAnalyzeProfitability:
    def _make_data(self, net_income_vals, revenue_vals, equity_vals):
        stmts = []
        balance = []
        for i, ni in enumerate(net_income_vals):
            stmts.append({"type": "IncomeAfterTaxes", "value": ni, "date": f"2025-{(i+1)*3:02d}-30"})
        for i, rev in enumerate(revenue_vals):
            stmts.append({"type": "Revenue", "value": rev, "date": f"2025-{(i+1)*3:02d}-30"})
        for i, eq in enumerate(equity_vals):
            balance.append({"type": "Equity", "value": eq, "date": f"2025-{(i+1)*3:02d}-30"})
        return stmts, balance

    def test_high_margin_and_roe_pass(self):
        # NPM = 200/1000 = 20%, ROE = 200/500 = 40%
        stmts, balance = self._make_data([50, 50, 50, 50], [250, 250, 250, 250], [500])
        result = analyze_profitability(stmts, balance)
        assert result["pass"] is True
        assert result["net_profit_margin"] == 20.0
        assert result["roe"] == 40.0

    def test_low_margin_fails(self):
        # NPM = 10/1000 = 1% (< 2%)
        stmts, balance = self._make_data([2.5, 2.5, 2.5, 2.5], [250, 250, 250, 250], [500])
        result = analyze_profitability(stmts, balance)
        assert result["pass"] is False
        assert result["criteria"]["net_profit_margin_ok"] is False

    def test_low_roe_fails(self):
        # NPM = 20%, ROE = 200/2000 = 10% (< 20%)
        stmts, balance = self._make_data([50, 50, 50, 50], [250, 250, 250, 250], [2000])
        result = analyze_profitability(stmts, balance)
        assert result["pass"] is False
        assert result["criteria"]["roe_ok"] is False

    def test_empty_statements(self):
        result = analyze_profitability([], [])
        assert result["pass"] is False


# --- Cash Flow Health ---

class TestAnalyzeCashFlowHealth:
    def test_positive_ocf_pass(self):
        data = [
            {"type": "CashFlowsFromOperatingActivities", "value": 100, "date": "2024-12-31"},
            {"type": "CashFlowsFromOperatingActivities", "value": 150, "date": "2025-12-31"},
            {"type": "CashProvidedByInvestingActivities", "value": -50, "date": "2025-12-31"},
        ]
        result = analyze_cash_flow_health(data)
        assert result["pass"] is True
        assert result["ocf_positive"] is True
        assert result["ocf_trending_up"] is True
        assert result["fcf"] == 100  # 150 + (-50)

    def test_negative_ocf_fail(self):
        data = [
            {"type": "CashFlowsFromOperatingActivities", "value": -50, "date": "2025-12-31"},
        ]
        result = analyze_cash_flow_health(data)
        assert result["pass"] is False
        assert result["ocf_positive"] is False

    def test_ocf_trending_down(self):
        data = [
            {"type": "CashFlowsFromOperatingActivities", "value": 200, "date": "2024-12-31"},
            {"type": "CashFlowsFromOperatingActivities", "value": 150, "date": "2025-12-31"},
        ]
        result = analyze_cash_flow_health(data)
        assert result["pass"] is True  # still positive
        assert result["ocf_trending_up"] is False

    def test_empty_cash_flows(self):
        result = analyze_cash_flow_health([])
        assert result["pass"] is False

    def test_no_ocf_type_found(self):
        data = [{"type": "SomeOtherType", "value": 100, "date": "2025-12-31"}]
        result = analyze_cash_flow_health(data)
        assert result["pass"] is False

    def test_fallback_to_net_cash_inflow(self):
        data = [
            {"type": "NetCashInflowFromOperatingActivities", "value": 200, "date": "2025-12-31"},
        ]
        result = analyze_cash_flow_health(data)
        assert result["pass"] is True
        assert result["latest_ocf"] == 200


# --- Asset Turnover ---

class TestAnalyzeAssetTurnover:
    def test_turnover_above_1_pass(self):
        stmts = [{"type": "Revenue", "value": 300, "date": f"2025-{m:02d}-30"} for m in [3, 6, 9, 12]]
        balance = [{"type": "TotalAssets", "value": 1000, "date": "2025-12-31"}]
        result = analyze_asset_turnover(stmts, balance)
        assert result["pass"] is True
        assert result["asset_turnover"] == 1.2

    def test_turnover_below_1_fail(self):
        stmts = [{"type": "Revenue", "value": 200, "date": f"2025-{m:02d}-30"} for m in [3, 6, 9, 12]]
        balance = [{"type": "TotalAssets", "value": 1000, "date": "2025-12-31"}]
        result = analyze_asset_turnover(stmts, balance)
        assert result["pass"] is False
        assert result["asset_turnover"] == 0.8

    def test_missing_data(self):
        result = analyze_asset_turnover([], [])
        assert result["pass"] is False


# --- EPS and Target Price ---

class TestEstimateEPSAndTarget:
    def test_eps_and_target_calculation(self):
        stmts = [{"type": "EPS", "value": 5.0, "date": f"2025-{m:02d}-30"} for m in [3, 6, 9, 12]]
        per_data = [
            {"PER": 20.0},
            {"PER": 25.0},
            {"PER": 30.0},
        ]
        result = estimate_eps_and_target(stmts, per_data)
        assert result["estimated_eps"] == 20.0
        assert result["avg_pe"] == 25.0
        assert result["target_price"] == 500.0

    def test_no_eps_data(self):
        result = estimate_eps_and_target([], [])
        assert result["estimated_eps"] is None
        assert result["target_price"] is None

    def test_no_per_data(self):
        stmts = [{"type": "EPS", "value": 5.0, "date": "2025-12-30"}]
        result = estimate_eps_and_target(stmts, [])
        assert result["estimated_eps"] == 5.0
        assert result["avg_pe"] is None
        assert result["target_price"] is None

    def test_negative_per_excluded(self):
        stmts = [{"type": "EPS", "value": 10.0, "date": "2025-12-30"}]
        per_data = [{"PER": -5.0}, {"PER": 0}, {"PER": 20.0}]
        result = estimate_eps_and_target(stmts, per_data)
        assert result["avg_pe"] == 20.0
