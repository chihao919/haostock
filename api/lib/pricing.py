"""Real-time pricing via Yahoo Finance HTTP API (serverless-friendly)."""

import httpx
from datetime import datetime


class PriceCache:
    """Per-request price cache to avoid duplicate API calls."""

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
        """Get current option mid price * 100 * abs(qty) via Yahoo Finance API."""
        try:
            exp_ts = int(datetime.strptime(expiry, "%Y-%m-%d").timestamp())
            url = f"https://query2.finance.yahoo.com/v7/finance/options/{ticker}"
            resp = httpx.get(url, params={"date": exp_ts}, headers=_headers(), timeout=10)
            data = resp.json()

            chain = data["optionChain"]["result"][0]
            if not chain.get("options"):
                return None

            options = chain["options"][0]
            contracts = options.get("puts" if opt_type == "put" else "calls", [])

            for c in contracts:
                if c["strike"] == strike:
                    bid = c.get("bid", 0)
                    ask = c.get("ask", 0)
                    mid = (bid + ask) / 2
                    return round(mid * 100 * abs(qty), 2)
            return None
        except Exception:
            return None


def _headers():
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }


def _fetch_price(ticker: str) -> float | None:
    try:
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
        resp = httpx.get(
            url,
            params={"interval": "1d", "range": "1d"},
            headers=_headers(),
            timeout=10,
        )
        data = resp.json()
        result = data["chart"]["result"][0]
        price = result["meta"]["regularMarketPrice"]
        return round(price, 4)
    except Exception:
        return None
