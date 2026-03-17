"""Tests for lib/sbl_analyzer.py"""

import pytest
from lib.sbl_analyzer import (
    _roc_to_ad,
    _suggest_rate,
    analyze_lending_opportunities,
    format_sbl_notification,
    fetch_bid_borrowing,
)


class TestRocToAd:
    def test_standard_date(self):
        assert _roc_to_ad("115年03月12日") == "2026-03-12"

    def test_invalid_returns_original(self):
        assert _roc_to_ad("bad") == "bad"


class TestSuggestRate:
    def test_zero_avg_returns_zero(self):
        assert _suggest_rate(0, 0, 0) == 0

    def test_basic_premium(self):
        # 1.0 avg * 1.1 = 1.1, max*0.8 = 4.0, so base = 1.1
        rate = _suggest_rate(1.0, 0.8, 5.0)
        assert rate >= 1.0

    def test_recent_higher_trend(self):
        # recent > avg → blended higher
        rate = _suggest_rate(1.0, 2.0, 5.0)
        assert rate > 1.0

    def test_capped_by_max(self):
        # max=2.0, cap=1.6, avg=1.5 → should be capped
        rate = _suggest_rate(1.5, 2.0, 2.0)
        assert rate <= 2.0


class TestAnalyzeLendingOpportunities:
    def test_empty_holdings(self):
        result = analyze_lending_opportunities([], [], {})
        assert result == []

    def test_with_matching_transactions(self):
        holdings = [{"ticker": "2330", "name": "台積電"}]
        transactions = [
            {"ticker": "2330", "name": "台積電", "date": "2026-03-12",
             "method": "議借", "qty": 100, "rate": 0.5, "close_price": "900",
             "return_date": "2026-09-12", "days": 184},
            {"ticker": "2330", "name": "台積電", "date": "2026-03-11",
             "method": "議借", "qty": 200, "rate": 0.4, "close_price": "895",
             "return_date": "2026-09-11", "days": 184},
        ]
        borrowable = {"2330": 13640441}
        result = analyze_lending_opportunities(holdings, transactions, borrowable)
        assert len(result) == 1
        opp = result[0]
        assert opp["ticker"] == "2330"
        assert opp["tx_count"] == 2
        assert opp["total_qty"] == 300
        assert opp["suggested_rate"] > 0
        assert opp["demand"] == "低"  # 300 < 5000

    def test_strips_tw_suffix(self):
        holdings = [{"ticker": "2330.TW", "name": "台積電"}]
        transactions = [
            {"ticker": "2330", "name": "台積電", "date": "2026-03-12",
             "method": "議借", "qty": 100, "rate": 1.0, "close_price": "900",
             "return_date": "2026-09-12", "days": 184},
        ]
        result = analyze_lending_opportunities(holdings, transactions, {"2330": 100})
        assert len(result) == 1
        assert result[0]["ticker"] == "2330"

    def test_no_transactions_no_borrowable(self):
        holdings = [{"ticker": "9999", "name": "不存在"}]
        result = analyze_lending_opportunities(holdings, [], {})
        assert len(result) == 0

    def test_demand_levels(self):
        holdings = [{"ticker": "A", "name": "A"}, {"ticker": "B", "name": "B"}, {"ticker": "C", "name": "C"}]
        transactions = [
            {"ticker": "A", "name": "A", "date": "2026-03-12", "method": "議借",
             "qty": 60000, "rate": 2.0, "close_price": "100", "return_date": "2026-09-12", "days": 184},
            {"ticker": "B", "name": "B", "date": "2026-03-12", "method": "議借",
             "qty": 10000, "rate": 1.0, "close_price": "50", "return_date": "2026-09-12", "days": 184},
            {"ticker": "C", "name": "C", "date": "2026-03-12", "method": "議借",
             "qty": 500, "rate": 0.5, "close_price": "30", "return_date": "2026-09-12", "days": 184},
        ]
        result = analyze_lending_opportunities(holdings, transactions, {"A": 1, "B": 1, "C": 1})
        by_ticker = {o["ticker"]: o for o in result}
        assert by_ticker["A"]["demand"] == "高"
        assert by_ticker["B"]["demand"] == "中"
        assert by_ticker["C"]["demand"] == "低"

    def test_sorted_by_rate_desc(self):
        holdings = [{"ticker": "X", "name": "X"}, {"ticker": "Y", "name": "Y"}]
        transactions = [
            {"ticker": "X", "name": "X", "date": "2026-03-12", "method": "議借",
             "qty": 100, "rate": 1.0, "close_price": "100", "return_date": "2026-09-12", "days": 184},
            {"ticker": "Y", "name": "Y", "date": "2026-03-12", "method": "議借",
             "qty": 100, "rate": 5.0, "close_price": "50", "return_date": "2026-09-12", "days": 184},
        ]
        result = analyze_lending_opportunities(holdings, transactions, {"X": 1, "Y": 1})
        assert result[0]["ticker"] == "Y"  # higher rate first


class TestFormatSblNotification:
    def test_no_opportunities_skips(self):
        msg = format_sbl_notification([], reminder_num=1)
        assert msg is None

    def test_no_opportunities_end_of_day(self):
        msg = format_sbl_notification([], reminder_num=4)
        assert msg is not None
        assert "無借券機會" in msg

    def test_first_reminder(self):
        opps = [
            {"ticker": "5009", "name": "榮剛", "borrowable_shares": 1000,
             "tx_count": 10, "total_qty": 1000, "weighted_avg_rate": 5.0,
             "min_rate": 4.0, "max_rate": 6.0, "recent_avg_rate": 5.0,
             "suggested_rate": 5.25, "demand": "低"},
        ]
        msg = format_sbl_notification(opps, reminder_num=1)
        assert "第1次" in msg
        assert "5009" in msg
        assert "營業員" in msg

    def test_last_reminder(self):
        opps = [
            {"ticker": "2330", "name": "台積電", "borrowable_shares": 1000,
             "tx_count": 5, "total_qty": 100, "weighted_avg_rate": 0.3,
             "min_rate": 0.1, "max_rate": 0.5, "recent_avg_rate": 0.3,
             "suggested_rate": 0.33, "demand": "低"},
        ]
        msg = format_sbl_notification(opps, reminder_num=3)
        assert "最後" in msg

    def test_mixed_rates(self):
        opps = [
            {"ticker": "5009", "name": "榮剛", "borrowable_shares": 1000,
             "tx_count": 10, "total_qty": 1000, "weighted_avg_rate": 5.0,
             "min_rate": 4.0, "max_rate": 6.0, "recent_avg_rate": 5.0,
             "suggested_rate": 5.25, "demand": "低"},
            {"ticker": "1301", "name": "台塑", "borrowable_shares": 5000,
             "tx_count": 20, "total_qty": 10000, "weighted_avg_rate": 1.5,
             "min_rate": 1.0, "max_rate": 3.0, "recent_avg_rate": 1.5,
             "suggested_rate": 1.65, "demand": "中"},
            {"ticker": "2317", "name": "鴻海", "borrowable_shares": 10000,
             "tx_count": 30, "total_qty": 50000, "weighted_avg_rate": 0.3,
             "min_rate": 0.1, "max_rate": 0.5, "recent_avg_rate": 0.3,
             "suggested_rate": 0.33, "demand": "高"},
        ]
        msg = format_sbl_notification(opps, reminder_num=2)
        assert "高費率" in msg
        assert "中等費率" in msg
        assert "低費率" in msg

    def test_bid_borrowing_alert(self):
        opps = []
        bids = [
            {"ticker": "2330", "name": "台積電", "company": "元大金融",
             "bid_qty": 10, "max_bid_price": 9.5, "won_qty": 10,
             "min_won_price": 0.05, "max_won_price": 0.10, "short_qty": 0},
        ]
        msg = format_sbl_notification(
            opps, reminder_num=0,
            bid_borrowing=bids, holding_tickers={"2330"},
        )
        assert "標借" in msg
        assert "2330" in msg
        assert "12:00" in msg

    def test_bid_borrowing_with_shortage(self):
        bids = [
            {"ticker": "5009", "name": "榮剛", "company": "元大金融",
             "bid_qty": 100, "max_bid_price": 5.0, "won_qty": 80,
             "min_won_price": 0.5, "max_won_price": 1.0, "short_qty": 20},
        ]
        msg = format_sbl_notification(
            [], reminder_num=0,
            bid_borrowing=bids, holding_tickers={"5009"},
        )
        assert "不足" in msg
        assert "得標機率高" in msg

    def test_bid_no_match_skips(self):
        bids = [
            {"ticker": "9999", "name": "不存在", "company": "元大",
             "bid_qty": 10, "max_bid_price": 1.0, "won_qty": 10,
             "min_won_price": 0.01, "max_won_price": 0.01, "short_qty": 0},
        ]
        msg = format_sbl_notification(
            [], reminder_num=0,
            bid_borrowing=bids, holding_tickers={"2330"},
        )
        assert msg is None

    def test_reminder_0_no_bid_skips(self):
        msg = format_sbl_notification([], reminder_num=0)
        assert msg is None

    def test_end_of_day_no_opportunity(self):
        msg = format_sbl_notification(
            [], reminder_num=4,
            bid_borrowing=[], holding_tickers={"2330"},
        )
        assert msg is not None
        assert "明天" in msg
