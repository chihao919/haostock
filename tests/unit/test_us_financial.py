"""Unit tests for US stock financial analysis module."""

import pytest
import pandas as pd
from lib.us_financial import (
    analyze_us_revenue_growth,
    analyze_us_cash_flow_health,
    analyze_us_financial_strength,
    analyze_us_profitability,
    estimate_us_valuation,
)


# --- Revenue Growth ---

class TestAnalyzeUSRevenueGrowth:
    def test_high_growth_pass(self):
        info = {"revenueGrowth": 0.35, "earningsGrowth": 0.50}
        result = analyze_us_revenue_growth(info)
        assert result["pass"] is True
        assert result["revenue_growth_pct"] == 35.0
        assert result["earnings_growth_pct"] == 50.0

    def test_low_growth_fail(self):
        info = {"revenueGrowth": 0.05, "earningsGrowth": 0.03}
        result = analyze_us_revenue_growth(info)
        assert result["pass"] is False
        assert result["revenue_growth_pct"] == 5.0

    def test_negative_growth_fail(self):
        info = {"revenueGrowth": -0.10, "earningsGrowth": -0.20}
        result = analyze_us_revenue_growth(info)
        assert result["pass"] is False
        assert result["revenue_growth_pct"] == -10.0

    def test_missing_data(self):
        result = analyze_us_revenue_growth({})
        assert result["pass"] is False
        assert result["revenue_growth_pct"] is None


# --- Cash Flow Health (with FCF Conversion) ---

class TestAnalyzeUSCashFlowHealth:
    def _make_cashflow(self, ocf, capex=None, prev_ocf=None):
        data = {}
        cols = ["2025-12-31"]
        if prev_ocf is not None:
            cols.append("2024-12-31")
        data["Operating Cash Flow"] = [ocf] + ([prev_ocf] if prev_ocf is not None else [])
        if capex is not None:
            data["Capital Expenditure"] = [capex] + ([capex] if prev_ocf is not None else [])
        return pd.DataFrame(data, index=cols).T

    def _make_income(self, net_income):
        return pd.DataFrame({"2025-12-31": [net_income]}, index=["Net Income"])

    def test_positive_ocf_and_high_fcf_conversion_pass(self):
        cf = self._make_cashflow(ocf=5_000_000_000, capex=-1_000_000_000)
        inc = self._make_income(4_000_000_000)
        result = analyze_us_cash_flow_health(cf, inc)
        assert result["pass"] is True
        assert result["ocf"] == 5000.0
        assert result["fcf"] == 4000.0
        assert result["fcf_conversion"] == 100.0  # 4B FCF / 4B NI

    def test_low_fcf_conversion_fail(self):
        cf = self._make_cashflow(ocf=5_000_000_000, capex=-4_500_000_000)
        inc = self._make_income(3_000_000_000)
        result = analyze_us_cash_flow_health(cf, inc)
        # FCF = 500M, NI = 3B, conversion = 16.7%
        assert result["pass"] is False
        assert result["fcf_conversion"] < 80

    def test_negative_ocf_fail(self):
        cf = self._make_cashflow(ocf=-500_000_000)
        result = analyze_us_cash_flow_health(cf, None)
        assert result["pass"] is False
        assert result["ocf_positive"] is False

    def test_trending_up(self):
        cf = self._make_cashflow(ocf=6_000_000_000, prev_ocf=4_000_000_000)
        result = analyze_us_cash_flow_health(cf, None)
        assert result["ocf_trending_up"] is True

    def test_empty_dataframe(self):
        result = analyze_us_cash_flow_health(pd.DataFrame(), None)
        assert result["pass"] is False

    def test_none_cashflow(self):
        result = analyze_us_cash_flow_health(None, None)
        assert result["pass"] is False


# --- Financial Strength (Interest Coverage, CCC, ROIC) ---

class TestAnalyzeUSFinancialStrength:
    def _make_income_stmt(self, ebit, interest_exp=None, revenue=None, cogs=None, tax=None, pretax=None):
        data = {"EBIT": [ebit]}
        if interest_exp is not None:
            data["Interest Expense"] = [interest_exp]
        if revenue is not None:
            data["Total Revenue"] = [revenue]
        if cogs is not None:
            data["Cost Of Revenue"] = [cogs]
        if tax is not None:
            data["Tax Provision"] = [tax]
        if pretax is not None:
            data["Pretax Income"] = [pretax]
        return pd.DataFrame(data, index=["2025-12-31"]).T

    def _make_balance_sheet(self, equity=1000, debt=200, cash=100, receivables=None, inventory=None, payables=None, ca=None, cl=None):
        data = {
            "Stockholders Equity": [equity],
            "Total Debt": [debt],
            "Cash And Cash Equivalents": [cash],
        }
        if receivables is not None:
            data["Accounts Receivable"] = [receivables]
        if inventory is not None:
            data["Inventory"] = [inventory]
        if payables is not None:
            data["Accounts Payable"] = [payables]
        if ca is not None:
            data["Current Assets"] = [ca]
        if cl is not None:
            data["Current Liabilities"] = [cl]
        return pd.DataFrame(data, index=["2025-12-31"]).T

    def test_strong_company_pass(self):
        inc = self._make_income_stmt(
            ebit=1000, interest_exp=-50, revenue=5000, cogs=2000,
            tax=200, pretax=950,
        )
        bs = self._make_balance_sheet(equity=2000, debt=500, cash=300,
                                      receivables=500, inventory=300, payables=400)
        result = analyze_us_financial_strength(inc, bs)
        assert result["pass"] is True
        assert result["interest_coverage"] == 20.0  # 1000/50
        assert result["roic"] is not None and result["roic"] > 15

    def test_low_interest_coverage_fail(self):
        inc = self._make_income_stmt(ebit=100, interest_exp=-50,
                                     tax=20, pretax=50)
        bs = self._make_balance_sheet(equity=2000, debt=500, cash=300)
        result = analyze_us_financial_strength(inc, bs)
        assert result["interest_coverage"] == 2.0
        assert result["criteria"]["interest_coverage_ok"] is False

    def test_no_interest_expense_passes(self):
        """Companies with no debt should pass interest coverage."""
        inc = self._make_income_stmt(ebit=1000, tax=200, pretax=1000)
        bs = self._make_balance_sheet(equity=2000, debt=0, cash=500)
        result = analyze_us_financial_strength(inc, bs)
        assert result["criteria"]["interest_coverage_ok"] is True

    def test_low_roic_fail(self):
        inc = self._make_income_stmt(ebit=50, interest_exp=-10,
                                     tax=10, pretax=40)
        bs = self._make_balance_sheet(equity=5000, debt=2000, cash=100)
        result = analyze_us_financial_strength(inc, bs)
        assert result["roic"] is not None and result["roic"] < 15
        assert result["criteria"]["roic_ok"] is False

    def test_negative_ccc_is_excellent(self):
        """Negative CCC means company uses suppliers' money (like AAPL)."""
        inc = self._make_income_stmt(ebit=1000, revenue=10000, cogs=6000,
                                     tax=200, pretax=950)
        bs = self._make_balance_sheet(equity=2000, debt=500, cash=300,
                                      receivables=200, inventory=100, payables=2000)
        result = analyze_us_financial_strength(inc, bs)
        assert result["cash_conversion_cycle"] < 0
        assert result["criteria"]["ccc_ok"] is True

    def test_high_ccc_flagged(self):
        inc = self._make_income_stmt(ebit=1000, revenue=5000, cogs=3000,
                                     tax=200, pretax=950)
        bs = self._make_balance_sheet(equity=2000, debt=500, cash=300,
                                      receivables=2000, inventory=1500, payables=200)
        result = analyze_us_financial_strength(inc, bs)
        assert result["cash_conversion_cycle"] > 60
        assert result["criteria"]["ccc_ok"] is False

    def test_current_ratio_still_reported(self):
        inc = self._make_income_stmt(ebit=1000, tax=200, pretax=1000)
        bs = self._make_balance_sheet(equity=2000, debt=0, cash=500, ca=3000, cl=1000)
        result = analyze_us_financial_strength(inc, bs)
        assert result["current_ratio"] == 300.0

    def test_empty_income_stmt(self):
        result = analyze_us_financial_strength(pd.DataFrame(), None)
        assert result["pass"] is False

    def test_none_income_stmt(self):
        result = analyze_us_financial_strength(None, None)
        assert result["pass"] is False


# --- Profitability ---

class TestAnalyzeUSProfitability:
    def test_high_margin_and_roe_pass(self):
        info = {"profitMargins": 0.25, "returnOnEquity": 0.35, "grossMargins": 0.60}
        result = analyze_us_profitability(None, info)
        assert result["pass"] is True
        assert result["net_profit_margin"] == 25.0
        assert result["roe"] == 35.0
        assert result["gross_margin"] == 60.0

    def test_low_margin_fail(self):
        info = {"profitMargins": 0.01, "returnOnEquity": 0.30}
        result = analyze_us_profitability(None, info)
        assert result["pass"] is False
        assert result["criteria"]["net_profit_margin_ok"] is False

    def test_low_roe_fail(self):
        info = {"profitMargins": 0.10, "returnOnEquity": 0.10}
        result = analyze_us_profitability(None, info)
        assert result["pass"] is False
        assert result["criteria"]["roe_ok"] is False

    def test_missing_data(self):
        result = analyze_us_profitability(None, {})
        assert result["pass"] is False


# --- Valuation ---

class TestEstimateUSValuation:
    def test_all_metrics(self):
        info = {
            "trailingPE": 30.0,
            "forwardPE": 25.0,
            "priceToBook": 8.0,
            "pegRatio": 1.5,
            "marketCap": 1_000_000_000_000,
            "targetMeanPrice": 200.0,
            "currentPrice": 180.0,
        }
        result = estimate_us_valuation(info)
        assert result["pe_ratio"] == 30.0
        assert result["forward_pe"] == 25.0
        assert result["pb_ratio"] == 8.0
        assert result["market_cap"] == 1_000_000_000_000
        assert result["current_price"] == 180.0

    def test_missing_metrics(self):
        result = estimate_us_valuation({})
        assert result["pe_ratio"] is None
        assert result["forward_pe"] is None
        assert result["current_price"] is None
