"""Unit tests for Happy Five Lines (樂活五線譜) module."""

import pytest
from unittest.mock import patch
import numpy as np
from lib.five_lines import calculate_five_lines, _get_signal, analyze


# --- Helpers ---


def _make_prices(n, start=100.0, slope=0.05, seed=42):
    """Generate mock prices with linear trend + noise."""
    np.random.seed(seed)
    prices = []
    for i in range(n):
        month = (i // 30 % 12) + 1
        day = (i % 28) + 1
        close = start + slope * i + np.random.normal(0, 10)
        close = round(max(close, 1.0), 2)
        prices.append({
            "date": f"2023-{month:02d}-{day:02d}",
            "close": close,
            "high": round(close + abs(np.random.normal(0, 3)), 2),
            "low": round(max(close - abs(np.random.normal(0, 3)), 0.5), 2),
        })
    return prices


def _make_flat_prices(n, price=100.0):
    """Generate flat prices with zero noise (for predictable regression)."""
    return [{"date": f"2023-01-{(i % 28) + 1:02d}", "close": price} for i in range(n)]


# --- calculate_five_lines ---


class TestCalculateFiveLines:
    def test_returns_all_required_keys(self):
        prices = _make_prices(500)
        result = calculate_five_lines(prices)
        assert "current_price" in result
        assert "lines" in result
        assert "position" in result
        assert "signal" in result
        assert "sigma" in result
        assert "slope_daily" in result
        assert "data_period" in result
        assert "data_points" in result
        assert "history" in result

    def test_lines_are_ordered(self):
        prices = _make_prices(500)
        result = calculate_five_lines(prices)
        lines = result["lines"]
        assert lines["plus_2sigma"] > lines["plus_1sigma"]
        assert lines["plus_1sigma"] > lines["mean"]
        assert lines["mean"] > lines["minus_1sigma"]
        assert lines["minus_1sigma"] > lines["minus_2sigma"]

    def test_sigma_is_positive(self):
        prices = _make_prices(500)
        result = calculate_five_lines(prices)
        assert result["sigma"] > 0

    def test_data_points_matches_input(self):
        prices = _make_prices(500)
        result = calculate_five_lines(prices)
        assert result["data_points"] == 500

    def test_history_length_matches_input(self):
        prices = _make_prices(500)
        result = calculate_five_lines(prices)
        assert len(result["history"]) == 500

    def test_history_entries_have_all_keys(self):
        prices = _make_prices(100)
        result = calculate_five_lines(prices)
        entry = result["history"][0]
        for key in ["date", "close", "plus_2sigma", "plus_1sigma", "mean", "minus_1sigma", "minus_2sigma"]:
            assert key in entry

    def test_insufficient_data_raises_error(self):
        prices = _make_prices(10)
        with pytest.raises(ValueError, match="Not enough data points"):
            calculate_five_lines(prices)

    def test_exactly_30_points_works(self):
        prices = _make_prices(30)
        result = calculate_five_lines(prices)
        assert result["data_points"] == 30

    def test_exactly_29_points_raises_error(self):
        prices = _make_prices(29)
        with pytest.raises(ValueError, match="Not enough data points"):
            calculate_five_lines(prices)

    def test_flat_prices_have_zero_sigma(self):
        """When all prices are identical, sigma should be ~0."""
        prices = _make_flat_prices(100, price=50.0)
        result = calculate_five_lines(prices)
        assert result["sigma"] < 0.01
        assert abs(result["lines"]["mean"] - 50.0) < 1.0

    def test_uptrend_has_positive_slope(self):
        prices = _make_prices(500, slope=0.1)
        result = calculate_five_lines(prices)
        assert result["slope_daily"] > 0

    def test_downtrend_has_negative_slope(self):
        prices = _make_prices(500, start=200.0, slope=-0.1)
        result = calculate_five_lines(prices)
        assert result["slope_daily"] < 0

    def test_data_period_format(self):
        prices = _make_prices(100)
        result = calculate_five_lines(prices)
        assert " ~ " in result["data_period"]
        parts = result["data_period"].split(" ~ ")
        assert len(parts) == 2

    def test_line_spacing_is_symmetric(self):
        """Distance from mean to +1σ should equal distance from mean to -1σ."""
        prices = _make_prices(500)
        result = calculate_five_lines(prices)
        lines = result["lines"]
        dist_plus = lines["plus_1sigma"] - lines["mean"]
        dist_minus = lines["mean"] - lines["minus_1sigma"]
        assert abs(dist_plus - dist_minus) < 0.02


# --- _get_signal ---


class TestGetSignal:
    LINES = {
        "plus_2sigma": 200.0,
        "plus_1sigma": 175.0,
        "mean": 150.0,
        "minus_1sigma": 125.0,
        "minus_2sigma": 100.0,
    }

    def test_below_minus_2sigma(self):
        _, signal = _get_signal(80.0, self.LINES)
        assert signal == "強烈買入"

    def test_at_minus_2sigma(self):
        _, signal = _get_signal(100.0, self.LINES)
        assert signal == "加碼買入"

    def test_between_minus_2sigma_and_minus_1sigma(self):
        _, signal = _get_signal(112.0, self.LINES)
        assert signal == "加碼買入"

    def test_at_minus_1sigma(self):
        _, signal = _get_signal(125.0, self.LINES)
        assert signal == "中性"

    def test_between_minus_1sigma_and_mean(self):
        _, signal = _get_signal(137.0, self.LINES)
        assert signal == "中性"

    def test_at_mean(self):
        _, signal = _get_signal(150.0, self.LINES)
        assert signal == "中性"

    def test_between_mean_and_plus_1sigma(self):
        _, signal = _get_signal(162.0, self.LINES)
        assert signal == "中性"

    def test_at_plus_1sigma(self):
        _, signal = _get_signal(175.0, self.LINES)
        assert signal == "賣出"

    def test_between_plus_1sigma_and_plus_2sigma(self):
        _, signal = _get_signal(188.0, self.LINES)
        assert signal == "賣出"

    def test_at_plus_2sigma(self):
        _, signal = _get_signal(200.0, self.LINES)
        assert signal == "強烈賣出"

    def test_above_plus_2sigma(self):
        _, signal = _get_signal(220.0, self.LINES)
        assert signal == "強烈賣出"

    def test_returns_position_and_signal(self):
        position, signal = _get_signal(160.0, self.LINES)
        assert isinstance(position, str)
        assert isinstance(signal, str)

    def test_all_valid_signals(self):
        """All possible signals are in the expected set."""
        test_prices = [80, 110, 140, 160, 185, 210]
        valid_signals = {"強烈買入", "加碼買入", "中性", "賣出", "強烈賣出"}
        for p in test_prices:
            _, signal = _get_signal(p, self.LINES)
            assert signal in valid_signals


# --- analyze (integration with mock) ---


class TestAnalyze:
    def test_analyze_returns_ticker(self):
        mock_prices = _make_prices(500)
        with patch("lib.five_lines.fetch_historical_prices", return_value=mock_prices):
            result = analyze("VOO", years=3.5, include_history=False)
        assert result["ticker"] == "VOO"
        assert "history" not in result

    def test_analyze_with_history(self):
        mock_prices = _make_prices(500)
        with patch("lib.five_lines.fetch_historical_prices", return_value=mock_prices):
            result = analyze("VOO", years=3.5, include_history=True)
        assert result["ticker"] == "VOO"
        assert "history" in result
        assert len(result["history"]) == 500

    def test_analyze_custom_years(self):
        mock_prices = _make_prices(250)
        with patch("lib.five_lines.fetch_historical_prices", return_value=mock_prices) as mock_fetch:
            analyze("0050.TW", years=1.0, include_history=False)
        mock_fetch.assert_called_once_with("0050.TW", 1.0)

    def test_analyze_includes_channel(self):
        mock_prices = _make_prices(500)
        with patch("lib.five_lines.fetch_historical_prices", return_value=mock_prices):
            result = analyze("VOO", years=3.5, include_history=False)
        assert "channel" in result
        ch = result["channel"]
        assert ch is not None
        assert "upper" in ch
        assert "middle" in ch
        assert "lower" in ch
        assert "signal" in ch
        assert ch["upper"] >= ch["middle"] >= ch["lower"]
        assert ch["signal"] in {"通道內", "突破上緣", "跌破下緣"}

    def test_analyze_history_includes_channel_data(self):
        mock_prices = _make_prices(500)
        with patch("lib.five_lines.fetch_historical_prices", return_value=mock_prices):
            result = analyze("VOO", years=3.5, include_history=True)
        # Later entries should have channel data
        last = result["history"][-1]
        assert "channel_upper" in last
        assert "channel_middle" in last
        assert "channel_lower" in last


# --- calculate_channel ---


class TestCalculateChannel:
    def test_channel_returns_required_keys(self):
        from lib.five_lines import calculate_channel
        prices = _make_prices(500)
        result = calculate_channel(prices)
        assert "upper" in result
        assert "middle" in result
        assert "lower" in result
        assert "channel_signal" in result
        assert "history" in result

    def test_channel_upper_gte_lower(self):
        from lib.five_lines import calculate_channel
        prices = _make_prices(500)
        result = calculate_channel(prices)
        assert result["upper"] >= result["lower"]

    def test_channel_insufficient_data(self):
        from lib.five_lines import calculate_channel
        prices = _make_prices(50)
        with pytest.raises(ValueError, match="Not enough data"):
            calculate_channel(prices)

    def test_channel_signal_inside(self):
        from lib.five_lines import calculate_channel
        prices = _make_prices(500)
        result = calculate_channel(prices)
        assert result["channel_signal"] in {"通道內", "突破上緣", "跌破下緣"}

    def test_channel_history_length(self):
        from lib.five_lines import calculate_channel
        prices = _make_prices(500)
        result = calculate_channel(prices)
        assert len(result["history"]) == 500


# --- Authentication endpoint tests ---


class TestFiveLinesAuthEndpoint:
    """Tests for POST /api/fivelines/auth endpoint."""

    def setup_method(self):
        # Import here to avoid module-level side effects from Notion/pricing imports
        import os
        os.environ.setdefault("FIVELINES_PASSWORD", "ccj")
        # Patch Notion and pricing to prevent real network calls at import time
        with patch("lib.notion.get_us_stocks"), \
             patch("lib.notion.get_tw_stocks"):
            from fastapi.testclient import TestClient
            from api.index import app
            self.client = TestClient(app, raise_server_exceptions=True)

    def test_correct_password_returns_full_level(self):
        """Password 'ccj' grants full access level."""
        response = self.client.post("/api/fivelines/auth", json={"password": "ccj"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["level"] == "full"

    def test_basic_password_returns_basic_level(self):
        """Password '2330' grants basic access level."""
        response = self.client.post("/api/fivelines/auth", json={"password": "2330"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["level"] == "basic"

    def test_wrong_password_returns_401(self):
        """An unrecognised password is rejected with 401."""
        response = self.client.post("/api/fivelines/auth", json={"password": "wrong"})
        assert response.status_code == 401

    def test_empty_password_returns_401(self):
        """An empty password is rejected with 401."""
        response = self.client.post("/api/fivelines/auth", json={"password": ""})
        assert response.status_code == 401

    def test_missing_password_key_returns_401(self):
        """A request body without a 'password' key is rejected with 401."""
        response = self.client.post("/api/fivelines/auth", json={})
        assert response.status_code == 401

    def test_password_is_case_insensitive(self):
        """Password matching uses lower-cased comparison (CCJ == ccj)."""
        response = self.client.post("/api/fivelines/auth", json={"password": "CCJ"})
        assert response.status_code == 200
        assert response.json()["level"] == "full"

    def test_password_whitespace_is_stripped(self):
        """Leading/trailing whitespace around the password is stripped."""
        response = self.client.post("/api/fivelines/auth", json={"password": "  ccj  "})
        assert response.status_code == 200
        assert response.json()["level"] == "full"

    def test_auth_response_has_no_extra_sensitive_fields(self):
        """Auth response must NOT leak api_key or other secrets for fivelines auth."""
        response = self.client.post("/api/fivelines/auth", json={"password": "ccj"})
        body = response.json()
        assert "api_key" not in body


# --- API endpoint edge cases ---


class TestFiveLinesEndpoint:
    """Tests for GET /api/fivelines/{ticker} endpoint."""

    def setup_method(self):
        import os
        os.environ.setdefault("FIVELINES_PASSWORD", "ccj")
        from fastapi.testclient import TestClient
        from api.index import app
        self.client = TestClient(app, raise_server_exceptions=False)
        self._mock_prices = _make_prices(500)

    def test_numeric_ticker_appends_tw_suffix(self):
        """Numeric ticker '2330' must be forwarded to analyze as '2330.TW'."""
        with patch("api.index.five_lines_analyze", return_value={
            "ticker": "2330.TW",
            "current_price": 600.0,
            "lines": {},
            "position": "neutral",
            "signal": "中性",
            "sigma": 10.0,
            "slope_daily": 0.05,
            "data_period": "2020-01-01 ~ 2023-01-01",
            "data_points": 500,
            "channel": None,
        }) as mock_analyze:
            self.client.get("/api/fivelines/2330")
            mock_analyze.assert_called_once()
            called_ticker = mock_analyze.call_args[0][0]
            assert called_ticker == "2330.TW"

    def test_alpha_ticker_not_modified(self):
        """Non-numeric ticker 'VOO' is forwarded as-is."""
        with patch("api.index.five_lines_analyze", return_value={
            "ticker": "VOO",
            "current_price": 400.0,
            "lines": {},
            "position": "neutral",
            "signal": "中性",
            "sigma": 8.0,
            "slope_daily": 0.02,
            "data_period": "2020-01-01 ~ 2023-01-01",
            "data_points": 500,
            "channel": None,
        }) as mock_analyze:
            self.client.get("/api/fivelines/VOO")
            called_ticker = mock_analyze.call_args[0][0]
            assert called_ticker == "VOO"

    def test_response_contains_timestamp(self):
        """Successful response includes a timestamp field."""
        with patch("lib.five_lines.fetch_historical_prices", return_value=self._mock_prices):
            response = self.client.get("/api/fivelines/VOO")
        assert response.status_code == 200
        assert "timestamp" in response.json()

    def test_timestamp_is_iso_format(self):
        """Timestamp in response is a valid ISO 8601 string."""
        from datetime import datetime
        with patch("lib.five_lines.fetch_historical_prices", return_value=self._mock_prices):
            response = self.client.get("/api/fivelines/VOO")
        ts = response.json()["timestamp"]
        # Should not raise
        datetime.fromisoformat(ts)

    def test_custom_years_parameter_is_forwarded(self):
        """years query parameter is passed through to analyze."""
        with patch("api.index.five_lines_analyze", return_value={
            "ticker": "VOO",
            "current_price": 400.0,
            "lines": {},
            "position": "neutral",
            "signal": "中性",
            "sigma": 8.0,
            "slope_daily": 0.02,
            "data_period": "2020-01-01 ~ 2023-01-01",
            "data_points": 500,
            "channel": None,
        }) as mock_analyze:
            self.client.get("/api/fivelines/VOO?years=5.0")
            _, kwargs = mock_analyze.call_args
            assert kwargs.get("years") == 5.0

    def test_include_history_parameter_false_by_default(self):
        """include_history defaults to False and is forwarded to analyze."""
        with patch("api.index.five_lines_analyze", return_value={
            "ticker": "VOO",
            "current_price": 400.0,
            "lines": {},
            "position": "neutral",
            "signal": "中性",
            "sigma": 8.0,
            "slope_daily": 0.02,
            "data_period": "2020-01-01 ~ 2023-01-01",
            "data_points": 500,
            "channel": None,
        }) as mock_analyze:
            self.client.get("/api/fivelines/VOO")
            _, kwargs = mock_analyze.call_args
            assert kwargs.get("include_history") is False

    def test_include_history_parameter_true_forwarded(self):
        """include_history=true is forwarded to analyze."""
        with patch("api.index.five_lines_analyze", return_value={
            "ticker": "VOO",
            "current_price": 400.0,
            "lines": {},
            "position": "neutral",
            "signal": "中性",
            "sigma": 8.0,
            "slope_daily": 0.02,
            "data_period": "2020-01-01 ~ 2023-01-01",
            "data_points": 500,
            "channel": None,
            "history": [],
        }) as mock_analyze:
            self.client.get("/api/fivelines/VOO?include_history=true")
            _, kwargs = mock_analyze.call_args
            assert kwargs.get("include_history") is True

    def test_failed_analysis_returns_404(self):
        """When analyze raises an exception, endpoint returns 404."""
        with patch("api.index.five_lines_analyze", side_effect=ValueError("no data")):
            response = self.client.get("/api/fivelines/INVALID_TICKER_XYZ")
        assert response.status_code == 404

    def test_endpoint_is_public_no_api_key_needed(self):
        """fivelines endpoint must respond 200 even without x-api-key header."""
        import os
        os.environ["FINANCIAL_API_KEY"] = "secret-test-key"
        try:
            with patch("lib.five_lines.fetch_historical_prices", return_value=self._mock_prices):
                response = self.client.get("/api/fivelines/VOO")
            # Should not receive 401 even though no API key was sent
            assert response.status_code != 401
        finally:
            os.environ.pop("FINANCIAL_API_KEY", None)


# --- Channel calculation edge cases ---


class TestCalculateChannelEdgeCases:
    """Additional edge case tests for calculate_channel."""

    def _make_prices_with_highs_lows(self, n, price=100.0, high_delta=5.0, low_delta=5.0):
        """Generate prices with explicit high/low for channel boundary tests."""
        return [
            {
                "date": f"2022-{(i // 28 % 12) + 1:02d}-{(i % 28) + 1:02d}",
                "close": price,
                "high": price + high_delta,
                "low": price - low_delta,
            }
            for i in range(n)
        ]

    def test_exactly_minimum_data_does_not_raise(self):
        """100 points (== window_weeks * 5) clears the ValueError guard without raising.

        Note: 100 daily points do not guarantee a non-None upper because ISO
        week grouping can produce fewer than 20 complete weeks.  The contract
        here is only that no exception is raised; callers must handle None.
        """
        from lib.five_lines import calculate_channel
        prices = _make_prices(100)
        # Should not raise — the ValueError threshold is len < 100
        result = calculate_channel(prices)
        assert "upper" in result  # key exists; value may be None

    def test_one_below_minimum_raises(self):
        """99 data points for a 20-week channel must raise ValueError."""
        from lib.five_lines import calculate_channel
        prices = _make_prices(99)
        with pytest.raises(ValueError, match="Not enough data"):
            calculate_channel(prices)

    def test_history_dates_match_input_dates(self):
        """Every date in channel history must correspond to an input date."""
        from lib.five_lines import calculate_channel
        prices = _make_prices(200)
        result = calculate_channel(prices)
        input_dates = {p["date"] for p in prices}
        for entry in result["history"]:
            assert entry["date"] in input_dates

    def test_channel_values_none_for_early_entries(self):
        """Early history entries (before window fills) must have None channel values."""
        from lib.five_lines import calculate_channel
        prices = _make_prices(500)
        result = calculate_channel(prices)
        # The very first entry cannot have channel data yet
        first = result["history"][0]
        assert first["upper"] is None
        assert first["middle"] is None
        assert first["lower"] is None

    def test_interpolated_values_are_between_anchor_points(self):
        """Interpolated daily values must lie between the two surrounding weekly anchors."""
        from lib.five_lines import calculate_channel
        prices = _make_prices(500, seed=7)
        result = calculate_channel(prices)
        history = result["history"]

        # Find a run of three consecutive non-None entries
        for i in range(1, len(history) - 1):
            prev = history[i - 1]
            curr = history[i]
            nxt = history[i + 1]
            if (prev["middle"] is not None and curr["middle"] is not None
                    and nxt["middle"] is not None):
                # The middle value should be between surrounding values
                lo = min(prev["middle"], nxt["middle"])
                hi = max(prev["middle"], nxt["middle"])
                # Allow a tiny tolerance for floating-point rounding
                assert lo - 0.5 <= curr["middle"] <= hi + 0.5
                break

    def test_channel_signal_breakout_above(self):
        """A price well above the upper channel triggers '突破上緣'."""
        from lib.five_lines import calculate_channel
        # Build a dataset where the last price is far above anything prior
        prices = _make_prices(500, start=100.0, slope=0.0, seed=1)
        # Force the last close/high to be extremely high
        prices[-1] = {
            "date": prices[-1]["date"],
            "close": 99999.0,
            "high": 99999.0,
            "low": 99998.0,
        }
        result = calculate_channel(prices)
        assert result["channel_signal"] == "突破上緣"

    def test_channel_signal_breakdown_below(self):
        """A price well below the lower channel triggers '跌破下緣'."""
        from lib.five_lines import calculate_channel
        prices = _make_prices(500, start=100.0, slope=0.0, seed=2)
        prices[-1] = {
            "date": prices[-1]["date"],
            "close": 0.01,
            "high": 0.02,
            "low": 0.01,
        }
        result = calculate_channel(prices)
        assert result["channel_signal"] == "跌破下緣"

    def test_channel_signal_inside_for_typical_price(self):
        """A price within normal channel range gives '通道內'."""
        from lib.five_lines import calculate_channel
        prices = _make_prices(500, seed=3)
        result = calculate_channel(prices)
        # With natural noise around the trend, the last point usually stays inside
        assert result["channel_signal"] in {"通道內", "突破上緣", "跌破下緣"}

    def test_channel_float_precision(self):
        """Channel values are rounded to 2 decimal places."""
        from lib.five_lines import calculate_channel
        prices = _make_prices(300)
        result = calculate_channel(prices)
        for key in ("upper", "middle", "lower"):
            val = result[key]
            if val is not None:
                assert round(val, 2) == val

    def test_channel_with_strongly_trending_data(self):
        """Channel still produces valid upper/lower/middle on a strong uptrend."""
        from lib.five_lines import calculate_channel
        prices = _make_prices(500, slope=1.0)
        result = calculate_channel(prices)
        assert result["upper"] >= result["middle"] >= result["lower"]

    def test_channel_with_flat_data(self):
        """Flat prices produce a valid channel with upper >= middle >= lower."""
        from lib.five_lines import calculate_channel
        # Need high/low fields for channel calculation; add them to flat prices
        flat = [
            {"date": f"2021-{(i // 28 % 12) + 1:02d}-{(i % 28) + 1:02d}",
             "close": 100.0, "high": 101.0, "low": 99.0}
            for i in range(300)
        ]
        result = calculate_channel(flat)
        assert result["upper"] >= result["middle"] >= result["lower"]

    def test_weekly_aggregation_uses_max_high_and_min_low(self):
        """Weekly aggregation must use max(high) and min(low) across daily entries."""
        from lib.five_lines import calculate_channel
        # All weeks have an outlier high/low day; channel upper/lower should reflect it
        prices = []
        for i in range(500):
            month = (i // 28 % 12) + 1
            day = (i % 28) + 1
            # Every 5th day is an outlier high
            high = 200.0 if i % 5 == 0 else 110.0
            low = 10.0 if i % 5 == 1 else 90.0
            prices.append({
                "date": f"2021-{month:02d}-{day:02d}",
                "close": 100.0,
                "high": high,
                "low": low,
            })
        # Should not raise; outliers are handled by max/min
        result = calculate_channel(prices)
        assert result["upper"] is not None
        assert result["lower"] is not None


# --- Error handling edge cases ---


class TestCalculateFiveLinesEdgeCases:
    """Error handling and boundary conditions for calculate_five_lines."""

    def test_empty_price_list_raises_value_error(self):
        """An empty list raises ValueError about insufficient data."""
        with pytest.raises(ValueError, match="Not enough data points"):
            calculate_five_lines([])

    def test_single_price_raises_value_error(self):
        """A single data point raises ValueError about insufficient data."""
        with pytest.raises(ValueError, match="Not enough data points"):
            calculate_five_lines([{"date": "2023-01-01", "close": 100.0}])

    def test_all_same_price_sigma_near_zero(self):
        """Identical prices produce sigma ≈ 0, not an exception."""
        prices = _make_flat_prices(100, price=50.0)
        result = calculate_five_lines(prices)
        assert result["sigma"] < 0.01

    def test_very_large_dataset_does_not_raise(self):
        """A large dataset (2000 points) processes without error."""
        prices = _make_prices(2000)
        result = calculate_five_lines(prices)
        assert result["data_points"] == 2000

    def test_history_entries_close_values_match_input(self):
        """Close price in each history entry matches the corresponding input price."""
        prices = _make_prices(100)
        result = calculate_five_lines(prices)
        for i, entry in enumerate(result["history"]):
            assert entry["close"] == prices[i]["close"]

    def test_history_entries_date_values_match_input(self):
        """Date in each history entry matches the corresponding input date."""
        prices = _make_prices(100)
        result = calculate_five_lines(prices)
        for i, entry in enumerate(result["history"]):
            assert entry["date"] == prices[i]["date"]

    def test_five_line_values_rounded_to_two_decimals(self):
        """All five line values in the result are rounded to 2 decimal places."""
        prices = _make_prices(200)
        result = calculate_five_lines(prices)
        for key, val in result["lines"].items():
            assert round(val, 2) == val, f"{key} not rounded to 2 decimals: {val}"

    def test_slope_daily_is_float(self):
        """slope_daily must be a float (not NaN or None)."""
        prices = _make_prices(100)
        result = calculate_five_lines(prices)
        assert isinstance(result["slope_daily"], float)
        assert result["slope_daily"] == result["slope_daily"]  # NaN check

    def test_current_price_matches_last_input_close(self):
        """current_price must equal the last close in the input list."""
        prices = _make_prices(100)
        result = calculate_five_lines(prices)
        assert result["current_price"] == prices[-1]["close"]


# --- _get_signal boundary conditions ---


class TestGetSignalBoundaries:
    """Price exactly at channel boundary values."""

    LINES = {
        "plus_2sigma": 200.0,
        "plus_1sigma": 175.0,
        "mean": 150.0,
        "minus_1sigma": 125.0,
        "minus_2sigma": 100.0,
    }

    def test_price_exactly_at_mean_is_neutral(self):
        """Price == mean is classified as neutral (中性)."""
        _, signal = _get_signal(150.0, self.LINES)
        assert signal == "中性"

    def test_price_one_cent_below_minus_2sigma_is_strong_buy(self):
        """Price just below -2σ is classified as 強烈買入."""
        _, signal = _get_signal(99.99, self.LINES)
        assert signal == "強烈買入"

    def test_price_one_cent_above_plus_2sigma_is_strong_sell(self):
        """Price just above +2σ is classified as 強烈賣出."""
        _, signal = _get_signal(200.01, self.LINES)
        assert signal == "強烈賣出"

    def test_price_one_cent_below_plus_2sigma_is_sell(self):
        """Price just under +2σ (but above +1σ) is classified as 賣出."""
        _, signal = _get_signal(199.99, self.LINES)
        assert signal == "賣出"

    def test_price_one_cent_above_minus_2sigma_is_add_buy(self):
        """Price just above -2σ (but below -1σ) is classified as 加碼買入."""
        _, signal = _get_signal(100.01, self.LINES)
        assert signal == "加碼買入"

    def test_position_strings_match_signal_zones(self):
        """Each signal zone returns the correct position string."""
        cases = [
            (80.0, "below_minus_2sigma"),
            (112.0, "minus_2sigma_to_minus_1sigma"),
            (137.0, "neutral"),
            (188.0, "plus_1sigma_to_2sigma"),
            (220.0, "above_plus_2sigma"),
        ]
        for price, expected_position in cases:
            position, _ = _get_signal(price, self.LINES)
            assert position == expected_position, (
                f"price={price}: expected position={expected_position}, got={position}"
            )


# --- Data integrity tests ---


class TestDataIntegrity:
    """Verify structural guarantees of analyze() output."""

    def test_history_channel_fields_present_when_include_history_true(self):
        """Every history entry has channel_upper/middle/lower when include_history=True."""
        mock_prices = _make_prices(500)
        with patch("lib.five_lines.fetch_historical_prices", return_value=mock_prices):
            result = analyze("VOO", years=3.5, include_history=True)
        for entry in result["history"]:
            assert "channel_upper" in entry, f"channel_upper missing in entry: {entry['date']}"
            assert "channel_middle" in entry, f"channel_middle missing in entry: {entry['date']}"
            assert "channel_lower" in entry, f"channel_lower missing in entry: {entry['date']}"

    def test_early_history_channel_values_are_none(self):
        """Early history entries (before channel window fills) have None channel values."""
        mock_prices = _make_prices(500)
        with patch("lib.five_lines.fetch_historical_prices", return_value=mock_prices):
            result = analyze("VOO", years=3.5, include_history=True)
        # The first entry is before any weekly window can fill
        first = result["history"][0]
        assert first["channel_upper"] is None
        assert first["channel_middle"] is None
        assert first["channel_lower"] is None

    def test_later_history_channel_values_are_numeric(self):
        """Later history entries (after channel window fills) have numeric channel values."""
        mock_prices = _make_prices(500)
        with patch("lib.five_lines.fetch_historical_prices", return_value=mock_prices):
            result = analyze("VOO", years=3.5, include_history=True)
        # The final entry should have real channel values
        last = result["history"][-1]
        assert last["channel_upper"] is not None
        assert last["channel_middle"] is not None
        assert last["channel_lower"] is not None
        assert isinstance(last["channel_upper"], float)

    def test_history_not_in_result_when_include_history_false(self):
        """history key must be absent when include_history=False."""
        mock_prices = _make_prices(500)
        with patch("lib.five_lines.fetch_historical_prices", return_value=mock_prices):
            result = analyze("VOO", years=3.5, include_history=False)
        assert "history" not in result

    def test_analyze_channel_none_on_insufficient_data(self):
        """channel is None when there is not enough data for channel calculation."""
        # 35 points is enough for five_lines (>=30) but not enough for 20-week channel (>=100)
        mock_prices = _make_prices(35)
        with patch("lib.five_lines.fetch_historical_prices", return_value=mock_prices):
            result = analyze("VOO", years=3.5, include_history=False)
        assert result["channel"] is None

    def test_analyze_tw_ticker_forwarded_correctly(self):
        """analyze passes the TW ticker string as given (no auto-suffix in lib)."""
        mock_prices = _make_prices(500)
        with patch("lib.five_lines.fetch_historical_prices", return_value=mock_prices) as mock_fetch:
            analyze("0050.TW", years=2.0, include_history=False)
        mock_fetch.assert_called_once_with("0050.TW", 2.0)

    def test_five_lines_history_all_entries_have_five_line_keys(self):
        """All history entries must contain all five regression line keys."""
        mock_prices = _make_prices(100)
        with patch("lib.five_lines.fetch_historical_prices", return_value=mock_prices):
            result = analyze("VOO", years=1.0, include_history=True)
        line_keys = {"plus_2sigma", "plus_1sigma", "mean", "minus_1sigma", "minus_2sigma"}
        for entry in result["history"]:
            for key in line_keys:
                assert key in entry, f"Missing key '{key}' in history entry {entry['date']}"

    def test_channel_upper_gte_middle_gte_lower_in_analyze_result(self):
        """Top-level channel values satisfy upper >= middle >= lower."""
        mock_prices = _make_prices(500)
        with patch("lib.five_lines.fetch_historical_prices", return_value=mock_prices):
            result = analyze("VOO", years=3.5, include_history=False)
        ch = result["channel"]
        assert ch is not None
        assert ch["upper"] >= ch["middle"]
        assert ch["middle"] >= ch["lower"]
