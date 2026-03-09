"""Unit tests for calculator module."""

import pytest
from datetime import date
from lib.calculator import (
    calc_stock_pl,
    calc_account_totals,
    dte,
    urgency,
    itm_otm,
    suggest_action,
    calc_option_pl,
    calc_bond_income,
    calc_net_worth,
    calc_trade_summary,
)


# --- Stock P&L ---

class TestCalcStockPL:
    def test_profitable_position(self):
        result = calc_stock_pl(shares=100, avg_cost=185.26, current_price=250.00)
        assert result["market_value"] == 25000.00
        assert result["cost_basis"] == 18526.00
        assert result["unrealized_pl"] == 6474.00
        assert result["pl_pct"] == 34.95

    def test_losing_position(self):
        result = calc_stock_pl(shares=200, avg_cost=307.61, current_price=280.00)
        assert result["market_value"] == 56000.00
        assert result["cost_basis"] == 61522.00
        assert result["unrealized_pl"] == -5522.00
        assert result["pl_pct"] == -8.98

    def test_breakeven(self):
        result = calc_stock_pl(shares=100, avg_cost=100.00, current_price=100.00)
        assert result["unrealized_pl"] == 0
        assert result["pl_pct"] == 0

    def test_fractional_shares(self):
        result = calc_stock_pl(shares=100.15563, avg_cost=92.34, current_price=95.00)
        assert result["market_value"] == 9514.78
        assert result["cost_basis"] == 9248.37

    def test_zero_cost_basis(self):
        result = calc_stock_pl(shares=100, avg_cost=0, current_price=10.00)
        assert result["pl_pct"] == 0


# --- Account Totals ---

class TestCalcAccountTotals:
    def test_sum_positions_with_prices(self):
        positions = [
            {"current_price": 250.00, "market_value": 25000.00, "cost_basis": 18526.00},
            {"current_price": 280.00, "market_value": 56000.00, "cost_basis": 61522.00},
        ]
        result = calc_account_totals(positions)
        assert result["total_market_value"] == 81000.00
        assert result["total_cost_basis"] == 80048.00
        assert result["total_pl"] == 952.00

    def test_exclude_positions_without_price(self):
        positions = [
            {"current_price": 250.00, "market_value": 25000.00, "cost_basis": 18526.00},
            {"current_price": None},
        ]
        result = calc_account_totals(positions)
        assert result["total_market_value"] == 25000.00

    def test_empty_positions(self):
        result = calc_account_totals([])
        assert result["total_market_value"] == 0
        assert result["total_pl_pct"] == 0


# --- DTE ---

class TestDTE:
    def test_future_expiry(self):
        assert dte("2026-03-13", today=date(2026, 3, 6)) == 7

    def test_same_day(self):
        assert dte("2026-03-06", today=date(2026, 3, 6)) == 0

    def test_past_expiry(self):
        assert dte("2026-03-01", today=date(2026, 3, 6)) == -5


# --- Urgency ---

class TestUrgency:
    def test_red(self):
        assert urgency(7) == "red"
        assert urgency(0) == "red"
        assert urgency(3) == "red"

    def test_yellow(self):
        assert urgency(8) == "yellow"
        assert urgency(21) == "yellow"
        assert urgency(14) == "yellow"

    def test_green(self):
        assert urgency(22) == "green"
        assert urgency(45) == "green"


# --- ITM/OTM ---

class TestITMOTM:
    def test_otm_put(self):
        assert itm_otm(120.0, 110.0, "put") == "OTM $10.0"

    def test_itm_put(self):
        assert itm_otm(105.0, 110.0, "put") == "ITM $5.0"

    def test_otm_call(self):
        assert itm_otm(320.0, 330.0, "call") == "OTM $10.0"

    def test_itm_call(self):
        assert itm_otm(340.0, 330.0, "call") == "ITM $10.0"

    def test_at_the_money_put(self):
        assert itm_otm(110.0, 110.0, "put") == "ITM $0.0"

    def test_at_the_money_call(self):
        assert itm_otm(330.0, 330.0, "call") == "ITM $0.0"


# --- Suggest Action ---

class TestSuggestAction:
    def test_expired(self):
        assert suggest_action(0, 50, "OTM $10.0") == "EXPIRED"
        assert suggest_action(-1, 50, "OTM $10.0") == "EXPIRED"

    def test_let_expire_otm_near_expiry(self):
        assert suggest_action(3, 90, "OTM $15.0") == "Let expire"
        assert suggest_action(7, 90, "OTM $15.0") == "Let expire"

    def test_close_roll_itm_near_expiry(self):
        assert suggest_action(3, 20, "ITM $5.0") == "Close/Roll URGENT"
        assert suggest_action(7, 20, "ITM $5.0") == "Close/Roll URGENT"

    def test_close_high_profit(self):
        assert suggest_action(30, 80, "OTM $20.0") == "Close (75%+ profit)"
        assert suggest_action(30, 75, "OTM $20.0") == "Close (75%+ profit)"

    def test_monitor_within_21dte(self):
        assert suggest_action(15, 40, "OTM $10.0") == "Monitor"
        assert suggest_action(21, 40, "OTM $10.0") == "Monitor"

    def test_hold_far_dated(self):
        assert suggest_action(45, 30, "OTM $20.0") == "Hold"

    def test_priority_expired_over_profit(self):
        assert suggest_action(0, 90, "OTM $20.0") == "EXPIRED"

    def test_priority_near_expiry_over_profit(self):
        # DTE <= 7, OTM -> "Let expire" takes priority even if profit > 75%
        assert suggest_action(5, 80, "OTM $10.0") == "Let expire"


# --- Option P&L ---

class TestCalcOptionPL:
    def test_profitable_short(self):
        result = calc_option_pl(cost=479.98, current_value=120.00)
        assert result["unrealized_pl"] == 359.98
        assert result["pl_pct"] == 75.0

    def test_losing_short(self):
        result = calc_option_pl(cost=479.98, current_value=600.00)
        assert result["unrealized_pl"] == -120.02
        assert result["pl_pct"] == -25.0

    def test_no_current_value(self):
        result = calc_option_pl(cost=479.98, current_value=None)
        assert result["unrealized_pl"] is None
        assert result["pl_pct"] is None


# --- Bond Income ---

class TestCalcBondIncome:
    def test_single_bond(self):
        bonds = [{"face": 280000, "coupon": 0.05699}]
        result = calc_bond_income(bonds)
        assert result["annual_gross"] == 15957.20
        assert result["annual_net"] == round(15957.20 * 0.76, 2)
        assert result["withholding_tax_rate"] == "24%"

    def test_multiple_bonds(self):
        bonds = [
            {"face": 280000, "coupon": 0.05699},
            {"face": 480000, "coupon": 0.05468},
        ]
        result = calc_bond_income(bonds)
        expected_gross = round(280000 * 0.05699 + 480000 * 0.05468, 2)
        assert result["annual_gross"] == expected_gross

    def test_monthly_is_annual_divided_by_12(self):
        bonds = [{"face": 120000, "coupon": 0.06}]
        result = calc_bond_income(bonds)
        assert result["monthly_net"] == round(result["annual_net"] / 12, 2)

    def test_empty_bonds(self):
        result = calc_bond_income([])
        assert result["annual_gross"] == 0


# --- Net Worth ---

class TestCalcNetWorth:
    def test_basic_calculation(self):
        result = calc_net_worth(
            us_value=200000,
            tw_value_twd=20000000,
            bonds_cost=800000,
            loans_twd=59050000,
            fx=32.15,
        )
        assert result["us_stocks_usd"] == 200000
        assert result["tw_stocks_usd"] == round(20000000 / 32.15, 2)
        assert result["total_loans_usd"] == round(59050000 / 32.15, 2)
        expected_assets = 200000 + 20000000 / 32.15 + 800000
        expected_net = expected_assets - 59050000 / 32.15
        assert result["net_worth_usd"] == round(expected_net, 2)

    def test_net_worth_twd_conversion(self):
        result = calc_net_worth(
            us_value=100000,
            tw_value_twd=0,
            bonds_cost=0,
            loans_twd=0,
            fx=32.0,
        )
        assert result["net_worth_twd"] == round(100000 * 32.0, 0)


# --- Trade Summary ---

class TestCalcTradeSummary:
    def test_win_rate(self):
        trades = [
            {"result": "Win", "pl": 500},
            {"result": "Win", "pl": 800},
            {"result": "Loss", "pl": -200},
            {"result": "Breakeven", "pl": 0},
        ]
        result = calc_trade_summary(trades)
        assert result["total_trades"] == 4
        assert result["wins"] == 2
        assert result["losses"] == 1
        assert result["breakeven"] == 1
        assert result["win_rate"] == 50.0

    def test_average_win_loss(self):
        trades = [
            {"result": "Win", "pl": 500},
            {"result": "Win", "pl": 800},
            {"result": "Win", "pl": 1200},
            {"result": "Loss", "pl": -200},
            {"result": "Loss", "pl": -400},
        ]
        result = calc_trade_summary(trades)
        assert result["avg_win"] == 833.33
        assert result["avg_loss"] == -300.00
        assert result["total_realized_pl"] == 1900.00

    def test_empty_trades(self):
        result = calc_trade_summary([])
        assert result["total_trades"] == 0
        assert result["win_rate"] == 0

    def test_trades_without_pl(self):
        trades = [
            {"result": "Win", "pl": None},
        ]
        result = calc_trade_summary(trades)
        assert result["wins"] == 1
        assert result["avg_win"] == 0
