"""Unit tests for lib/invest_scanner.py"""

import pytest
from lib.invest_scanner import (
    Action, scan_stop_losses, scan_option_expiry, generate_cc_tasks, find_completed,
    _parse_float, _dte,
)
from datetime import date, timedelta


class TestParseFloat:
    def test_valid(self):
        assert _parse_float("12.5") == 12.5

    def test_none(self):
        assert _parse_float(None) == 0.0

    def test_empty(self):
        assert _parse_float("") == 0.0

    def test_custom_default(self):
        assert _parse_float("bad", -10) == -10


class TestDTE:
    def test_future_date(self):
        future = (date.today() + timedelta(days=10)).strftime("%Y-%m-%d")
        assert _dte(future) == 10

    def test_past_date(self):
        past = (date.today() - timedelta(days=3)).strftime("%Y-%m-%d")
        assert _dte(past) == -3

    def test_invalid_date(self):
        assert _dte("bad-date") == 999

    def test_today(self):
        assert _dte(date.today().strftime("%Y-%m-%d")) == 0


class TestScanStopLosses:
    def _user(self, spec_tickers="", stop_spec=-10, stop_invest=-20):
        return {
            "spec_tickers": spec_tickers,
            "stop_loss_spec": str(stop_spec),
            "stop_loss_invest": str(stop_invest),
        }

    def test_no_stocks(self):
        assert scan_stop_losses([], [], self._user()) == []

    def test_positive_pl_ignored(self):
        stocks = [{"ticker": "AAPL", "pl_pct": "15", "account": "IB"}]
        assert scan_stop_losses(stocks, [], self._user()) == []

    def test_invest_stop_loss_triggered(self):
        stocks = [{"ticker": "AAPL", "pl_pct": "-25", "account": "IB"}]
        actions = scan_stop_losses(stocks, [], self._user())
        assert len(actions) == 1
        assert actions[0].urgency == "red"
        assert actions[0].type == "stop_loss"
        assert "停損觸發" in actions[0].detail

    def test_spec_stop_loss_triggered(self):
        stocks = [{"ticker": "HIMS", "pl_pct": "-12", "account": "IB"}]
        actions = scan_stop_losses(stocks, [], self._user(spec_tickers="HIMS,GRAB"))
        assert len(actions) == 1
        assert actions[0].urgency == "red"
        assert "投機" in actions[0].detail

    def test_invest_warning(self):
        # -16% is within 80% of -20% threshold (-16 <= -16)
        stocks = [{"ticker": "AAPL", "pl_pct": "-17", "account": "IB"}]
        actions = scan_stop_losses(stocks, [], self._user())
        assert len(actions) == 1
        assert actions[0].urgency == "yellow"

    def test_tw_stocks_included(self):
        tw = [{"ticker": "2330.TW", "pl_pct": "-25", "account": "Fubon"}]
        actions = scan_stop_losses([], tw, self._user())
        assert len(actions) == 1
        assert "2330.TW" in actions[0].ticker


class TestScanOptionExpiry:
    def _opt(self, days_from_now=30, itm_otm="OTM $5.0", pl_pct=0, opt_type="put"):
        expiry = (date.today() + timedelta(days=days_from_now)).strftime("%Y-%m-%d")
        return {
            "ticker": "AAPL", "expiry": expiry, "strike": "150",
            "type": opt_type, "pl_pct": str(pl_pct), "itm_otm": itm_otm,
            "account": "IB",
        }

    def test_expired(self):
        actions = scan_option_expiry([self._opt(days_from_now=-1)])
        assert len(actions) == 1
        assert actions[0].urgency == "red"
        assert "EXPIRED" in actions[0].detail

    def test_itm_urgent(self):
        actions = scan_option_expiry([self._opt(days_from_now=3, itm_otm="ITM $2.0")])
        assert len(actions) == 1
        assert actions[0].urgency == "red"
        assert "URGENT" in actions[0].detail

    def test_otm_let_expire(self):
        actions = scan_option_expiry([self._opt(days_from_now=3, itm_otm="OTM $5.0")])
        assert len(actions) == 1
        assert actions[0].urgency == "green"
        assert "Let expire" in actions[0].detail

    def test_profit_take_75(self):
        actions = scan_option_expiry([self._opt(days_from_now=30, pl_pct=80)])
        assert len(actions) == 1
        assert actions[0].urgency == "green"
        assert "75%+ profit" in actions[0].detail

    def test_monitor_21d(self):
        actions = scan_option_expiry([self._opt(days_from_now=15)])
        assert len(actions) == 1
        assert actions[0].urgency == "yellow"
        assert "Monitor" in actions[0].detail

    def test_hold_beyond_21d(self):
        actions = scan_option_expiry([self._opt(days_from_now=30)])
        assert len(actions) == 0


class TestGenerateCCTasks:
    def test_no_pipeline(self):
        assert generate_cc_tasks([], {"cc_pipeline": ""}) == []

    def test_all_have_open_calls(self):
        options = [{"ticker": "CCJ", "type": "call", "expiry": (date.today() + timedelta(30)).strftime("%Y-%m-%d")}]
        tasks = generate_cc_tasks(options, {"cc_pipeline": "CCJ"})
        assert len(tasks) == 0

    def test_missing_call(self):
        options = []
        tasks = generate_cc_tasks(options, {"cc_pipeline": "CCJ,GOOG"})
        assert len(tasks) == 2
        tickers = [t.ticker for t in tasks]
        assert "CCJ" in tickers
        assert "GOOG" in tickers
        assert all(t.type == "covered_call" for t in tasks)

    def test_expired_call_not_counted(self):
        options = [{"ticker": "CCJ", "type": "call", "expiry": (date.today() - timedelta(1)).strftime("%Y-%m-%d")}]
        tasks = generate_cc_tasks(options, {"cc_pipeline": "CCJ"})
        assert len(tasks) == 1  # expired call doesn't count


class TestFindCompleted:
    def test_no_match(self):
        trades = [{"ticker": "AAPL", "action": "Close"}]
        cards = [{"id": "c1", "name": "Monitor GOOG 150P DTE=15"}]
        assert find_completed(trades, cards) == []

    def test_match_close(self):
        trades = [{"ticker": "AAPL", "action": "Close"}]
        cards = [{"id": "c1", "name": "URGENT Close/Roll AAPL 150P"}]
        assert find_completed(trades, cards) == ["c1"]

    def test_buy_not_matched(self):
        trades = [{"ticker": "AAPL", "action": "Buy"}]
        cards = [{"id": "c1", "name": "AAPL something"}]
        assert find_completed(trades, cards) == []

    def test_multiple_matches(self):
        trades = [
            {"ticker": "AAPL", "action": "Sell"},
            {"ticker": "GOOG", "action": "Close"},
        ]
        cards = [
            {"id": "c1", "name": "Stop loss AAPL -15%"},
            {"id": "c2", "name": "Monitor GOOG 150P"},
            {"id": "c3", "name": "Write CC: NVDA"},
        ]
        result = find_completed(trades, cards)
        assert "c1" in result
        assert "c2" in result
        assert "c3" not in result
