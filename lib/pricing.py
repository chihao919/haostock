"""Real-time pricing via yfinance."""

import yfinance as yf
from datetime import datetime


class PriceCache:
    """Per-request price cache to avoid duplicate yfinance calls."""

    def __init__(self):
        self._cache: dict[str, float | None] = {}

    def get_price(self, ticker: str) -> float | None:
        if ticker not in self._cache:
            self._cache[ticker] = _fetch_price(ticker)
        return self._cache[ticker]

    def get_fx(self) -> float:
        price = self.get_price("USDTWD=X")
        return price if price else 32.0

    def get_option_value(
        self, ticker: str, expiry: str, strike: float, opt_type: str, qty: int
    ) -> float | None:
        """Get current option mid price * 100 * abs(qty)."""
        try:
            t = yf.Ticker(ticker)
            exp_dates = t.options
            if not exp_dates:
                return None
            closest = min(
                exp_dates,
                key=lambda d: abs(
                    (datetime.strptime(d, "%Y-%m-%d").date()
                     - datetime.strptime(expiry, "%Y-%m-%d").date()).days
                ),
            )
            chain = t.option_chain(closest)
            df = chain.puts if opt_type == "put" else chain.calls
            row = df[df["strike"] == strike]
            if row.empty:
                return None
            mid = (row["bid"].values[0] + row["ask"].values[0]) / 2
            return round(mid * 100 * abs(qty), 2)
        except Exception:
            return None


def _fetch_price(ticker: str) -> float | None:
    try:
        t = yf.Ticker(ticker)
        return round(t.fast_info.last_price, 4)
    except Exception:
        return None
