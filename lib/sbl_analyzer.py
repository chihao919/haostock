"""Securities Borrowing & Lending (SBL) analyzer.

Fetches TWSE SBL data and generates lending recommendations
for user's TW stock holdings.
"""

import httpx
import re
from datetime import datetime, timedelta


_TWSE_SBL = "https://www.twse.com.tw/SBL"
_TWSE_EXCHANGE = "https://www.twse.com.tw/exchangeReport"
_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _twse_date(dt: datetime) -> str:
    """Format date as TWSE expects: YYYYMMDD."""
    return dt.strftime("%Y%m%d")


def _roc_to_ad(roc_str: str) -> str:
    """Convert ROC date like '115年03月12日' to '2026-03-12'."""
    m = re.match(r"(\d+)年(\d+)月(\d+)日", roc_str.strip())
    if not m:
        return roc_str
    year = int(m.group(1)) + 1911
    return f"{year}-{m.group(2)}-{m.group(3)}"


def fetch_borrowable_shares() -> dict[str, int]:
    """Fetch today's borrowable share counts from TWSE TWT96U.

    Returns dict of {ticker: share_count}.
    """
    today = _twse_date(datetime.now())
    url = f"{_TWSE_SBL}/TWT96U"
    resp = httpx.get(
        url,
        params={"response": "json", "date": today},
        headers={"User-Agent": _USER_AGENT},
        timeout=15,
    )
    data = resp.json()
    if data.get("stat") != "OK":
        return {}

    result = {}
    for row in data.get("data", []):
        for i in range(0, len(row), 2):
            m = re.search(r"stock=(\w+)", row[i])
            if m:
                ticker = m.group(1)
                shares = int(row[i + 1].replace(",", ""))
                result[ticker] = shares
    return result


def fetch_recent_sbl_transactions(days: int = 14) -> list[dict]:
    """Fetch recent SBL transaction history from TWSE t13sa710.

    Returns list of transaction dicts with ticker, rate, qty, method, date.
    """
    end = datetime.now()
    start = end - timedelta(days=days)
    url = f"{_TWSE_SBL}/t13sa710"
    resp = httpx.get(
        url,
        params={
            "response": "json",
            "startDate": _twse_date(start),
            "endDate": _twse_date(end),
            "selectType": "ALL",
        },
        headers={"User-Agent": _USER_AGENT},
        timeout=30,
    )
    data = resp.json()
    if data.get("stat") != "OK":
        return []

    transactions = []
    for row in data.get("data", []):
        parts = row[1].strip().split()
        ticker = parts[0] if parts else ""
        name = " ".join(parts[1:]) if len(parts) > 1 else ""
        transactions.append({
            "date": _roc_to_ad(row[0]),
            "ticker": ticker,
            "name": name,
            "method": row[2].strip(),
            "qty": int(row[3].replace(",", "")),
            "rate": float(row[4]),
            "close_price": row[5],
            "return_date": _roc_to_ad(row[6]),
            "days": row[7],
        })
    return transactions


def fetch_bid_borrowing() -> list[dict]:
    """Fetch today's 標借 (bid borrowing) demand from TWSE BFIB8U.

    Returns list of dicts with ticker, name, bid_qty, max_bid_price,
    won_qty, min_won_price, max_won_price, short_qty.
    The bid price is per-share-per-day in TWD (not annualized %).
    """
    today = _twse_date(datetime.now())
    url = f"{_TWSE_EXCHANGE}/BFIB8U"
    resp = httpx.get(
        url,
        params={"response": "json", "date": today},
        headers={"User-Agent": _USER_AGENT},
        timeout=15,
    )
    data = resp.json()
    if data.get("stat") != "OK":
        return []

    results = []
    for table in data.get("tables", []):
        if "標借證券明細" not in table.get("title", ""):
            continue
        for row in table.get("data", []):
            if len(row) < 10:
                continue
            results.append({
                "ticker": row[1].strip(),
                "name": row[2].strip(),
                "company": row[3].strip(),
                "bid_qty": int(row[4].replace(",", "")),
                "max_bid_price": float(row[5]),
                "won_qty": int(row[6].replace(",", "")),
                "min_won_price": float(row[7]),
                "max_won_price": float(row[8]),
                "short_qty": int(row[9].replace(",", "")),
            })
    return results


def analyze_lending_opportunities(
    tw_holdings: list[dict],
    transactions: list[dict] | None = None,
    borrowable: dict[str, int] | None = None,
) -> list[dict]:
    """Analyze lending opportunities for user's TW holdings.

    Args:
        tw_holdings: list of dicts with at least 'ticker' and 'name' fields.
                     ticker should be raw number like '2330', not '2330.TW'.
        transactions: recent SBL transactions (or None to fetch).
        borrowable: today's borrowable shares (or None to fetch).

    Returns list of lending opportunity dicts sorted by suggested rate desc.
    """
    if transactions is None:
        transactions = fetch_recent_sbl_transactions()
    if borrowable is None:
        borrowable = fetch_borrowable_shares()

    # Build holding ticker set (strip .TW suffix if present)
    holding_tickers = {}
    for h in tw_holdings:
        raw = h.get("ticker", "").replace(".TW", "").replace(".tw", "")
        if raw:
            holding_tickers[raw] = h.get("name", raw)

    # Group transactions by ticker
    tx_by_ticker = {}
    for tx in transactions:
        t = tx["ticker"]
        if t in holding_tickers:
            if t not in tx_by_ticker:
                tx_by_ticker[t] = []
            tx_by_ticker[t].append(tx)

    opportunities = []
    for ticker, name in holding_tickers.items():
        txs = tx_by_ticker.get(ticker, [])
        borrow_shares = borrowable.get(ticker, 0)

        if not txs and borrow_shares == 0:
            continue  # no demand at all

        # Calculate fee rate stats
        if txs:
            rates = [tx["rate"] for tx in txs]
            qtys = [tx["qty"] for tx in txs]
            total_qty = sum(qtys)
            weighted_avg = sum(r * q for r, q in zip(rates, qtys)) / total_qty if total_qty else 0
            min_rate = min(rates)
            max_rate = max(rates)
            # Recent trend: last 5 transactions
            recent_rates = [tx["rate"] for tx in txs[-5:]]
            recent_avg = sum(recent_rates) / len(recent_rates)
            tx_count = len(txs)
        else:
            weighted_avg = 0
            min_rate = 0
            max_rate = 0
            recent_avg = 0
            total_qty = 0
            tx_count = 0

        # Suggest fee rate
        suggested_rate = _suggest_rate(weighted_avg, recent_avg, max_rate)

        # Demand level
        if total_qty > 50000:
            demand = "高"
        elif total_qty > 5000:
            demand = "中"
        elif total_qty > 0:
            demand = "低"
        else:
            demand = "無近期成交"

        opportunities.append({
            "ticker": ticker,
            "name": name,
            "borrowable_shares": borrow_shares,
            "tx_count": tx_count,
            "total_qty": total_qty,
            "weighted_avg_rate": round(weighted_avg, 2),
            "min_rate": round(min_rate, 2),
            "max_rate": round(max_rate, 2),
            "recent_avg_rate": round(recent_avg, 2),
            "suggested_rate": round(suggested_rate, 2),
            "demand": demand,
        })

    # Sort by suggested rate descending (best opportunities first)
    opportunities.sort(key=lambda x: -x["suggested_rate"])
    return opportunities


def _suggest_rate(weighted_avg: float, recent_avg: float, max_rate: float) -> float:
    """Suggest a lending fee rate based on market data.

    Strategy: slightly above weighted average, capped by recent trend.
    """
    if weighted_avg == 0:
        return 0

    # Base: weighted average + 10% premium
    base = weighted_avg * 1.1

    # If recent trend is higher, lean toward recent
    if recent_avg > weighted_avg:
        base = (base + recent_avg) / 2

    # Don't exceed 80% of max (leave room for negotiation)
    cap = max_rate * 0.8
    if cap > 0 and base > cap:
        base = cap

    # Floor at weighted average
    if base < weighted_avg:
        base = weighted_avg

    return round(base, 2)


def format_sbl_notification(
    opportunities: list[dict],
    reminder_num: int = 1,
    bid_borrowing: list[dict] | None = None,
    holding_tickers: set[str] | None = None,
) -> str | None:
    """Format SBL lending opportunities as LINE message.

    Args:
        opportunities: list from analyze_lending_opportunities()
        reminder_num: 0=bid-only(9:30), 1=first(10:30), 2=second(11:00),
                      3=last(11:30), 4=end-of-day(12:00)
        bid_borrowing: today's 標借 demand list (from fetch_bid_borrowing)
        holding_tickers: set of user's TW tickers (raw, no .TW suffix)

    Returns formatted message string, or None if no notification needed.
    """
    now = datetime.now()
    time_str = now.strftime("%H:%M")

    # Match 標借 demand with user's holdings
    bid_matches = []
    if bid_borrowing and holding_tickers:
        for bid in bid_borrowing:
            if bid["ticker"] in holding_tickers:
                bid_matches.append(bid)

    # Filter to actionable opportunities (has recent transactions)
    actionable = [o for o in opportunities if o["tx_count"] > 0]

    has_opportunity = bool(actionable or bid_matches)

    # No opportunity: only notify at end-of-day (reminder_num=4)
    if not has_opportunity:
        if reminder_num == 4:
            return f"📋 借券日報 ({time_str})\n\n今日你的持股無借券機會。明天再看！"
        return None  # skip notification

    # Urgency prefix based on reminder number
    if reminder_num == 0:
        prefix = "🚨 標借速報"
        suffix = "⏰ 12:00 前打電話給營業員掛標借！"
    elif reminder_num == 1:
        prefix = "📋 借券提醒 第1次"
        suffix = "👉 請打電話給營業員出借"
    elif reminder_num == 2:
        prefix = "⏰ 借券提醒 第2次"
        suffix = "⚠️ 請儘快聯繫營業員"
    elif reminder_num == 3:
        prefix = "🔔 借券提醒 最後一次"
        suffix = "❗ 最後機會，請立即聯繫營業員"
    else:
        prefix = "📋 借券日報"
        suffix = ""

    lines = [f"{prefix} ({time_str})", ""]

    # 標借 matches — highest priority, always show first
    if bid_matches:
        lines.append("🚨 今日標借需求（12:00前掛單）：")
        for b in bid_matches:
            price_info = ""
            if b["won_qty"] > 0:
                price_info = f" 得標價 {b['min_won_price']:.4f}~{b['max_won_price']:.4f}元/股/天"
            else:
                price_info = f" 最高標借 {b['max_bid_price']:.4f}元/股/天"
            lines.append(
                f"  {b['ticker']} {b['name']} "
                f"需求{b['bid_qty']}張{price_info}"
            )
            if b["short_qty"] > 0:
                lines.append(f"    ⚠️ 不足{b['short_qty']}張，得標機率高！")
        lines.append("")

    # Skip detailed 議借 info for bid-only notification (9:30)
    if reminder_num == 0 and not actionable:
        lines.append(suffix)
        return "\n".join(lines)

    # High-value opportunities first (rate > 2%)
    high = [o for o in actionable if o["suggested_rate"] >= 2.0]
    medium = [o for o in actionable if 0.5 <= o["suggested_rate"] < 2.0]
    low = [o for o in actionable if 0 < o["suggested_rate"] < 0.5]

    if high:
        lines.append("🔥 高費率議借標的：")
        for o in high:
            lines.append(
                f"  {o['ticker']} {o['name']} "
                f"建議 {o['suggested_rate']:.1f}% "
                f"(市場 {o['min_rate']:.1f}~{o['max_rate']:.1f}%)"
            )
        lines.append("")

    if medium:
        lines.append("💰 中等費率：")
        for o in medium:
            lines.append(
                f"  {o['ticker']} {o['name']} "
                f"建議 {o['suggested_rate']:.1f}% "
                f"(均 {o['weighted_avg_rate']:.1f}%)"
            )
        lines.append("")

    if low:
        lines.append(f"📉 低費率 ({len(low)} 檔)：")
        tickers = ", ".join(f"{o['ticker']}" for o in low)
        lines.append(f"  {tickers} (費率 <0.5%，量大才值得)")
        lines.append("")

    lines.append(suffix)
    return "\n".join(lines)
