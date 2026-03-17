"""Unit tests for lib/invest_notifier.py"""

import pytest
from lib.invest_scanner import Action
from lib.invest_notifier import (
    format_daily_report, format_weekly_cc, format_completion,
    _urgency_to_color,
)


class TestFormatDailyReport:
    def test_no_actions(self):
        msg = format_daily_report([])
        assert "無警報" in msg

    def test_red_actions(self):
        actions = [Action("stop_loss", "AAPL", "IB", "red", "🔴 停損觸發 AAPL: -25%")]
        msg = format_daily_report(actions)
        assert "緊急" in msg
        assert "AAPL" in msg

    def test_mixed_urgencies(self):
        actions = [
            Action("stop_loss", "AAPL", "IB", "red", "🔴 紅色"),
            Action("stop_loss", "GOOG", "IB", "yellow", "⚠️ 黃色"),
            Action("option_expiry", "NVDA", "IB", "green", "✅ 綠色"),
        ]
        msg = format_daily_report(actions)
        assert "緊急" in msg
        assert "注意" in msg
        assert "可執行" in msg


class TestFormatWeeklyCC:
    def test_no_tasks(self):
        msg = format_weekly_cc([])
        assert "無需操作" in msg

    def test_with_tasks(self):
        tasks = [
            Action("covered_call", "CCJ", "", "green", "📋 Write CC: CCJ"),
            Action("covered_call", "GOOG", "", "green", "📋 Write CC: GOOG"),
        ]
        msg = format_weekly_cc(tasks)
        assert "CCJ" in msg
        assert "GOOG" in msg
        assert "共 2 檔" in msg


class TestFormatCompletion:
    def test_format(self):
        msg = format_completion("AAPL")
        assert "AAPL" in msg
        assert "完成" in msg


class TestUrgencyToColor:
    def test_mapping(self):
        assert _urgency_to_color("red") == "red"
        assert _urgency_to_color("yellow") == "yellow"
        assert _urgency_to_color("green") == "blue"
        assert _urgency_to_color("unknown") == "blue"
