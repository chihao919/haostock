"""Unit tests for pricing module."""

import pytest
from unittest.mock import patch, MagicMock
from lib.pricing import PriceCache, _fetch_price


class TestPriceCache:
    def test_caches_price_on_second_call(self):
        cache = PriceCache()
        with patch("lib.pricing._fetch_price", return_value=250.00) as mock:
            price1 = cache.get_price("NVDA")
            price2 = cache.get_price("NVDA")
            assert price1 == 250.00
            assert price2 == 250.00
            mock.assert_called_once_with("NVDA")

    def test_different_tickers_cached_separately(self):
        cache = PriceCache()
        with patch("lib.pricing._fetch_price", side_effect=[250.00, 320.00]) as mock:
            assert cache.get_price("NVDA") == 250.00
            assert cache.get_price("GOOG") == 320.00
            assert mock.call_count == 2

    def test_get_fx_returns_rate(self):
        cache = PriceCache()
        with patch("lib.pricing._fetch_price", return_value=32.15):
            assert cache.get_fx() == 32.15

    def test_get_fx_fallback(self):
        cache = PriceCache()
        with patch("lib.pricing._fetch_price", return_value=None):
            assert cache.get_fx() == 32.0

    def test_caches_none_for_unavailable(self):
        cache = PriceCache()
        with patch("lib.pricing._fetch_price", return_value=None) as mock:
            assert cache.get_price("INVALID") is None
            assert cache.get_price("INVALID") is None
            mock.assert_called_once_with("INVALID")


class TestFetchPrice:
    def test_returns_none_on_exception(self):
        with patch("lib.pricing.yf.Ticker") as mock_ticker:
            mock_ticker.side_effect = Exception("API Error")
            assert _fetch_price("BAD") is None

    def test_returns_rounded_price(self):
        mock_info = MagicMock()
        mock_info.last_price = 185.26789
        with patch("lib.pricing.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.fast_info = mock_info
            result = _fetch_price("NVDA")
            assert result == 185.2679
