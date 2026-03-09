"""BDD tests for Happy Five Lines (樂活五線譜) feature."""

import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from api.index import app


def _make_mock_prices(n=900, start_price=100.0, slope=0.05, noise=10.0):
    """Create mock historical prices with linear trend + noise.

    Args:
        n: number of data points
        start_price: starting price
        slope: daily price increase
        noise: standard deviation of random noise
    """
    import numpy as np
    np.random.seed(42)
    prices = []
    for i in range(n):
        day_offset = i
        date_str = f"2022-{(i // 30 % 12) + 1:02d}-{(i % 28) + 1:02d}"
        close = start_price + slope * i + np.random.normal(0, noise)
        prices.append({"date": date_str, "close": round(max(close, 1.0), 2)})
    return prices


def _make_mock_analysis(current_price, signal="中性"):
    """Create a mock five lines analysis result."""
    return {
        "ticker": "VOO",
        "current_price": current_price,
        "lines": {
            "plus_2sigma": 200.0,
            "plus_1sigma": 175.0,
            "mean": 150.0,
            "minus_1sigma": 125.0,
            "minus_2sigma": 100.0,
        },
        "position": "mean_to_plus_1sigma",
        "signal": signal,
        "sigma": 25.0,
        "slope_daily": 0.05,
        "data_period": "2022-09-01 ~ 2026-03-01",
        "data_points": 900,
    }


def _make_mock_analysis_with_history(current_price, signal="中性"):
    """Create a mock five lines analysis result with history."""
    result = _make_mock_analysis(current_price, signal)
    result["history"] = [
        {
            "date": "2022-09-01",
            "close": 100.0,
            "plus_2sigma": 150.0,
            "plus_1sigma": 137.5,
            "mean": 125.0,
            "minus_1sigma": 112.5,
            "minus_2sigma": 100.0,
        },
        {
            "date": "2026-03-01",
            "close": current_price,
            "plus_2sigma": 200.0,
            "plus_1sigma": 175.0,
            "mean": 150.0,
            "minus_1sigma": 125.0,
            "minus_2sigma": 100.0,
        },
    ]
    return result


# --- Core Calculation BDD Tests ---


class TestFiveLinesCalculation:
    """Scenario: Calculate five lines for a valid ticker"""

    def test_five_lines_values_order(self):
        from lib.five_lines import calculate_five_lines
        prices = _make_mock_prices(900)
        result = calculate_five_lines(prices)

        lines = result["lines"]
        assert "plus_2sigma" in lines
        assert "plus_1sigma" in lines
        assert "mean" in lines
        assert "minus_1sigma" in lines
        assert "minus_2sigma" in lines
        assert lines["plus_2sigma"] > lines["plus_1sigma"] > lines["mean"] > lines["minus_1sigma"] > lines["minus_2sigma"]

    def test_has_current_price(self):
        from lib.five_lines import calculate_five_lines
        prices = _make_mock_prices(900)
        result = calculate_five_lines(prices)
        assert "current_price" in result
        assert isinstance(result["current_price"], float)

    def test_has_signal(self):
        from lib.five_lines import calculate_five_lines
        prices = _make_mock_prices(900)
        result = calculate_five_lines(prices)
        assert "signal" in result
        assert result["signal"] in ["強烈買入", "加碼買入", "中性", "賣出", "強烈賣出"]

    def test_insufficient_data_raises_error(self):
        """Scenario: Insufficient data raises error"""
        from lib.five_lines import calculate_five_lines
        prices = _make_mock_prices(10)
        with pytest.raises(ValueError, match="Not enough data points"):
            calculate_five_lines(prices)


class TestFiveLinesSignal:
    """Scenarios: Signal determination based on price position."""

    def test_signal_below_minus_2sigma(self):
        """Scenario: Signal is '強烈買入' when price is below minus_2sigma"""
        from lib.five_lines import _get_signal
        lines = {"plus_2sigma": 200, "plus_1sigma": 175, "mean": 150, "minus_1sigma": 125, "minus_2sigma": 100}
        _, signal = _get_signal(90.0, lines)
        assert signal == "強烈買入"

    def test_signal_between_minus_2sigma_and_minus_1sigma(self):
        """Scenario: Signal is '加碼買入' when price is between minus_2sigma and minus_1sigma"""
        from lib.five_lines import _get_signal
        lines = {"plus_2sigma": 200, "plus_1sigma": 175, "mean": 150, "minus_1sigma": 125, "minus_2sigma": 100}
        _, signal = _get_signal(110.0, lines)
        assert signal == "加碼買入"

    def test_signal_between_minus_1sigma_and_mean(self):
        """Scenario: Signal is '中性' (lower half)"""
        from lib.five_lines import _get_signal
        lines = {"plus_2sigma": 200, "plus_1sigma": 175, "mean": 150, "minus_1sigma": 125, "minus_2sigma": 100}
        _, signal = _get_signal(135.0, lines)
        assert signal == "中性"

    def test_signal_between_mean_and_plus_1sigma(self):
        """Scenario: Signal is '中性' (upper half)"""
        from lib.five_lines import _get_signal
        lines = {"plus_2sigma": 200, "plus_1sigma": 175, "mean": 150, "minus_1sigma": 125, "minus_2sigma": 100}
        _, signal = _get_signal(160.0, lines)
        assert signal == "中性"

    def test_signal_between_plus_1sigma_and_plus_2sigma(self):
        """Scenario: Signal is '賣出' when price is between plus_1sigma and plus_2sigma"""
        from lib.five_lines import _get_signal
        lines = {"plus_2sigma": 200, "plus_1sigma": 175, "mean": 150, "minus_1sigma": 125, "minus_2sigma": 100}
        _, signal = _get_signal(185.0, lines)
        assert signal == "賣出"

    def test_signal_above_plus_2sigma(self):
        """Scenario: Signal is '強烈賣出' when price is above plus_2sigma"""
        from lib.five_lines import _get_signal
        lines = {"plus_2sigma": 200, "plus_1sigma": 175, "mean": 150, "minus_1sigma": 125, "minus_2sigma": 100}
        _, signal = _get_signal(210.0, lines)
        assert signal == "強烈賣出"

    def test_signal_at_exact_boundary_minus_2sigma(self):
        """Edge case: price exactly at minus_2sigma"""
        from lib.five_lines import _get_signal
        lines = {"plus_2sigma": 200, "plus_1sigma": 175, "mean": 150, "minus_1sigma": 125, "minus_2sigma": 100}
        _, signal = _get_signal(100.0, lines)
        assert signal == "加碼買入"

    def test_signal_at_exact_boundary_mean(self):
        """Edge case: price exactly at mean"""
        from lib.five_lines import _get_signal
        lines = {"plus_2sigma": 200, "plus_1sigma": 175, "mean": 150, "minus_1sigma": 125, "minus_2sigma": 100}
        _, signal = _get_signal(150.0, lines)
        assert signal == "中性"


# --- API Endpoint BDD Tests ---


@pytest.mark.asyncio
async def test_api_returns_five_lines_analysis():
    """Scenario: API returns five lines analysis"""
    mock_result = _make_mock_analysis(160.0, "中性")
    with patch("lib.five_lines.analyze", return_value=mock_result):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/fivelines/VOO")

    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "VOO"
    assert "current_price" in data
    assert "lines" in data
    assert "signal" in data
    lines = data["lines"]
    for key in ["plus_2sigma", "plus_1sigma", "mean", "minus_1sigma", "minus_2sigma"]:
        assert key in lines


@pytest.mark.asyncio
async def test_api_supports_custom_period():
    """Scenario: API supports custom period"""
    mock_result = _make_mock_analysis(160.0)
    mock_result["data_period"] = "2025-03-01 ~ 2026-03-01"
    with patch("lib.five_lines.analyze", return_value=mock_result):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/fivelines/0050.TW", params={"years": 1})

    assert resp.status_code == 200
    data = resp.json()
    assert "data_period" in data


@pytest.mark.asyncio
async def test_api_returns_history_for_charting():
    """Scenario: API returns history for charting"""
    mock_result = _make_mock_analysis_with_history(160.0)
    with patch("lib.five_lines.analyze", return_value=mock_result):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/fivelines/VOO", params={"include_history": "true"})

    assert resp.status_code == 200
    data = resp.json()
    assert "history" in data
    assert len(data["history"]) > 0
    entry = data["history"][0]
    for key in ["date", "close", "plus_2sigma", "plus_1sigma", "mean", "minus_1sigma", "minus_2sigma"]:
        assert key in entry


@pytest.mark.asyncio
async def test_api_returns_404_for_invalid_ticker():
    """Scenario: API returns 404 for invalid ticker"""
    with patch("lib.five_lines.analyze", side_effect=Exception("No data found")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/fivelines/INVALIDXYZ")

    assert resp.status_code == 404


# --- Web Page BDD Tests ---


@pytest.mark.asyncio
async def test_five_lines_page_loads():
    """Scenario: Five lines page loads"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/fivelines")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    html = resp.text
    assert "input" in html.lower()
    assert "chart" in html.lower()


# --- Batch Scanning BDD Tests ---


def test_batch_scan_returns_signals():
    """Scenario: Scan multiple tickers for buy signals"""
    from lib.five_lines import _get_signal

    tickers_and_prices = [
        ("0050.TW", 90.0),   # below -2σ → 強烈買入
        ("VOO", 160.0),      # between mean and +1σ → 中性
        ("2330.TW", 110.0),  # between -2σ and -1σ → 加碼買入
    ]
    lines = {"plus_2sigma": 200, "plus_1sigma": 175, "mean": 150, "minus_1sigma": 125, "minus_2sigma": 100}

    results = []
    for ticker, price in tickers_and_prices:
        _, signal = _get_signal(price, lines)
        results.append({"ticker": ticker, "current_price": price, "signal": signal})

    assert len(results) == 3
    for r in results:
        assert "ticker" in r
        assert "current_price" in r
        assert "signal" in r

    buy_signals = [r for r in results if r["signal"] in ["強烈買入", "加碼買入"]]
    assert len(buy_signals) == 2
