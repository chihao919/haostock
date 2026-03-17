"""Happy Five Lines (樂活五線譜) analysis using linear regression ± standard deviation."""

import httpx
import math
from datetime import datetime, timedelta


def _headers():
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }


def fetch_historical_prices(ticker: str, years: float = 3.5) -> list[dict]:
    """Fetch historical daily prices from Yahoo Finance.

    Returns list of {"date": "YYYY-MM-DD", "close": float, "high": float, "low": float}
    sorted by date ascending.
    """
    end = datetime.now()
    start = end - timedelta(days=int(years * 365))
    period1 = int(start.timestamp())
    period2 = int(end.timestamp())

    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
    resp = httpx.get(
        url,
        params={"period1": period1, "period2": period2, "interval": "1d"},
        headers=_headers(),
        timeout=15,
    )
    data = resp.json()
    result = data["chart"]["result"][0]

    timestamps = result["timestamp"]
    quote = result["indicators"]["quote"][0]
    closes = quote["close"]
    highs = quote.get("high", closes)
    lows = quote.get("low", closes)

    prices = []
    for ts, close, high, low in zip(timestamps, closes, highs, lows):
        if close is not None:
            prices.append({
                "date": datetime.fromtimestamp(ts).strftime("%Y-%m-%d"),
                "close": round(close, 2),
                "high": round(high, 2) if high is not None else round(close, 2),
                "low": round(low, 2) if low is not None else round(close, 2),
            })
    return prices


def calculate_five_lines(prices: list[dict]) -> dict:
    """Calculate five lines from historical prices.

    Args:
        prices: list of {"date": str, "close": float} sorted by date ascending.

    Returns dict with line values, current position, and signal.
    """
    if len(prices) < 30:
        raise ValueError("Not enough data points (need at least 30)")

    closes = [p["close"] for p in prices]
    n = len(closes)
    x = list(range(n))

    # Linear regression (least squares y = a*x + b)
    sum_x = sum(x)
    sum_y = sum(closes)
    sum_xy = sum(xi * yi for xi, yi in zip(x, closes))
    sum_x2 = sum(xi * xi for xi in x)
    a = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
    b = (sum_y - a * sum_x) / n
    regression = [a * xi + b for xi in x]

    # Standard deviation of residuals
    residuals = [c - r for c, r in zip(closes, regression)]
    mean_res = sum(residuals) / n
    sigma = math.sqrt(sum((r - mean_res) ** 2 for r in residuals) / n)

    # Current regression value (last point)
    reg_now = regression[-1]
    current_price = closes[-1]

    lines = {
        "plus_2sigma": round(reg_now + 2 * sigma, 2),
        "plus_1sigma": round(reg_now + 1 * sigma, 2),
        "mean": round(reg_now, 2),
        "minus_1sigma": round(reg_now - 1 * sigma, 2),
        "minus_2sigma": round(reg_now - 2 * sigma, 2),
    }

    # Determine position and signal
    position, signal = _get_signal(current_price, lines)

    # Historical lines for charting (optional)
    history = []
    for i, p in enumerate(prices):
        r = regression[i]
        history.append({
            "date": p["date"],
            "close": p["close"],
            "plus_2sigma": round(r + 2 * sigma, 2),
            "plus_1sigma": round(r + 1 * sigma, 2),
            "mean": round(r, 2),
            "minus_1sigma": round(r - 1 * sigma, 2),
            "minus_2sigma": round(r - 2 * sigma, 2),
        })

    return {
        "current_price": round(current_price, 2),
        "lines": lines,
        "position": position,
        "signal": signal,
        "sigma": round(sigma, 2),
        "slope_daily": round(a, 4),
        "data_period": f"{prices[0]['date']} ~ {prices[-1]['date']}",
        "data_points": len(prices),
        "history": history,
    }


def _get_signal(price: float, lines: dict) -> tuple[str, str]:
    """Determine position and trading signal based on current price vs five lines."""
    if price >= lines["plus_2sigma"]:
        return "above_plus_2sigma", "強烈賣出"
    elif price >= lines["plus_1sigma"]:
        return "plus_1sigma_to_2sigma", "賣出"
    elif price >= lines["minus_1sigma"]:
        return "neutral", "中性"
    elif price >= lines["minus_2sigma"]:
        return "minus_2sigma_to_minus_1sigma", "加碼買入"
    else:
        return "below_minus_2sigma", "強烈買入"


def calculate_channel(prices: list[dict], window_weeks: int = 20) -> dict:
    """Calculate Happy Channel (樂活通道) from daily prices.

    Converts daily data to weekly, computes 20-week rolling averages,
    then linearly interpolates back to daily for smooth chart lines:
    - Upper band: rolling mean of weekly highs
    - Middle line: rolling mean of weekly closes (SMA)
    - Lower band: rolling mean of weekly lows

    Returns dict with channel values and daily history for charting.
    """
    if len(prices) < window_weeks * 5:
        raise ValueError(f"Not enough data for {window_weeks}-week channel")

    # Group daily data into ISO weeks
    from collections import OrderedDict
    weeks = OrderedDict()
    for i, p in enumerate(prices):
        dt = datetime.strptime(p["date"], "%Y-%m-%d")
        week_key = dt.strftime("%G-W%V")
        if week_key not in weeks:
            weeks[week_key] = {"high": [], "low": [], "close": [], "last_idx": i}
        weeks[week_key]["high"].append(p["high"])
        weeks[week_key]["low"].append(p["low"])
        weeks[week_key]["close"].append(p["close"])
        weeks[week_key]["last_idx"] = i

    # Weekly aggregates with day index for interpolation
    weekly = []
    for vals in weeks.values():
        weekly.append({
            "idx": vals["last_idx"],
            "high": max(vals["high"]),
            "low": min(vals["low"]),
            "close": vals["close"][-1],
        })

    # Rolling Bollinger-style channel on weekly closes
    w_closes = [w["close"] for w in weekly]

    # Weekly channel points (idx, upper, middle, lower)
    # Middle = 20-week SMA of weekly closes
    # Upper = Middle + 1σ of weekly closes
    # Lower = Middle - 1σ of weekly closes
    weekly_points = []
    for i in range(len(weekly)):
        if i < window_weeks - 1:
            continue
        sl = slice(i - window_weeks + 1, i + 1)
        window_data = w_closes[sl]
        sma = sum(window_data) / window_weeks
        std = (sum((x - sma) ** 2 for x in window_data) / window_weeks) ** 0.5
        weekly_points.append({
            "idx": weekly[i]["idx"],
            "upper": sma + std,
            "middle": sma,
            "lower": sma - std,
        })

    # Linear interpolation to daily
    n = len(prices)
    daily_channel = [{"date": prices[i]["date"], "upper": None, "middle": None, "lower": None} for i in range(n)]

    for j in range(len(weekly_points)):
        wp = weekly_points[j]
        idx = wp["idx"]
        daily_channel[idx] = {
            "date": prices[idx]["date"],
            "upper": round(wp["upper"], 2),
            "middle": round(wp["middle"], 2),
            "lower": round(wp["lower"], 2),
        }

    # Interpolate between weekly anchor points
    for key in ("upper", "middle", "lower"):
        anchors = [(wp["idx"], wp[key]) for wp in weekly_points]
        for k in range(len(anchors) - 1):
            i0, v0 = anchors[k]
            i1, v1 = anchors[k + 1]
            for d in range(i0 + 1, i1):
                t = (d - i0) / (i1 - i0)
                daily_channel[d][key] = round(v0 + t * (v1 - v0), 2)
                daily_channel[d]["date"] = prices[d]["date"]

    # Current channel values
    last_valid = None
    for wp in reversed(weekly_points):
        last_valid = wp
        break

    current_price = prices[-1]["close"]
    channel_signal = "通道內"
    if last_valid:
        if current_price > last_valid["upper"]:
            channel_signal = "突破上緣"
        elif current_price < last_valid["lower"]:
            channel_signal = "跌破下緣"

    return {
        "upper": round(last_valid["upper"], 2) if last_valid else None,
        "middle": round(last_valid["middle"], 2) if last_valid else None,
        "lower": round(last_valid["lower"], 2) if last_valid else None,
        "channel_signal": channel_signal,
        "history": daily_channel,
    }


def analyze(ticker: str, years: float = 3.5, include_history: bool = False) -> dict:
    """Full five lines analysis for a ticker.

    Args:
        ticker: Stock ticker (e.g. "0050.TW", "VOO", "2330.TW")
        years: Historical data period (default 3.5 years)
        include_history: Whether to include full historical line data

    Returns analysis result dict.
    """
    prices = fetch_historical_prices(ticker, years)
    result = calculate_five_lines(prices)
    result["ticker"] = ticker

    # Calculate Happy Channel (樂活通道)
    try:
        channel = calculate_channel(prices)
        result["channel"] = {
            "upper": channel["upper"],
            "middle": channel["middle"],
            "lower": channel["lower"],
            "signal": channel["channel_signal"],
        }
        if include_history:
            # Merge channel history into five lines history
            ch_map = {ch["date"]: ch for ch in channel["history"]}
            for h in result["history"]:
                ch = ch_map.get(h["date"], {})
                h["channel_upper"] = ch.get("upper")
                h["channel_middle"] = ch.get("middle")
                h["channel_lower"] = ch.get("lower")
    except (ValueError, KeyError):
        result["channel"] = None

    if not include_history:
        del result["history"]

    return result
