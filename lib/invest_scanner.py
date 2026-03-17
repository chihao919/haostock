"""Investment action scanner — generates actions from portfolio data."""

from dataclasses import dataclass, field
from datetime import datetime, date


@dataclass
class Action:
    type: str        # stop_loss, option_expiry, covered_call, profit_take
    ticker: str
    account: str
    urgency: str     # red, yellow, green
    detail: str
    metadata: dict = field(default_factory=dict)


def _parse_float(val, default=0.0) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _dte(expiry_str: str) -> int:
    """Days to expiration from YYYY-MM-DD string."""
    try:
        exp = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        return (exp - date.today()).days
    except (ValueError, TypeError):
        return 999


def scan_stop_losses(
    us_stocks: list[dict],
    tw_stocks: list[dict],
    user_config: dict,
) -> list[Action]:
    """Scan US + TW stocks for stop-loss triggers."""
    actions = []
    spec_tickers = set(
        t.strip().upper()
        for t in user_config.get("spec_tickers", "").split(",")
        if t.strip()
    )
    stop_spec = _parse_float(user_config.get("stop_loss_spec"), -10)
    stop_invest = _parse_float(user_config.get("stop_loss_invest"), -20)

    for stock in us_stocks + tw_stocks:
        pl_pct = _parse_float(stock.get("pl_pct"))
        if pl_pct >= 0:
            continue
        ticker = stock.get("ticker", "")
        is_spec = ticker.upper() in spec_tickers
        threshold = stop_spec if is_spec else stop_invest
        tag = "投機" if is_spec else "投資"

        if pl_pct <= threshold:
            actions.append(Action(
                type="stop_loss",
                ticker=ticker,
                account=stock.get("account", ""),
                urgency="red",
                detail=f"🔴 {tag}停損觸發 {ticker}: {pl_pct:+.1f}% (門檻 {threshold}%)",
                metadata={"pl_pct": pl_pct, "threshold": threshold, "tag": tag},
            ))
        elif pl_pct <= threshold * 0.8:  # within 80% of threshold = warning
            actions.append(Action(
                type="stop_loss",
                ticker=ticker,
                account=stock.get("account", ""),
                urgency="yellow",
                detail=f"⚠️ {tag}接近停損 {ticker}: {pl_pct:+.1f}% (門檻 {threshold}%)",
                metadata={"pl_pct": pl_pct, "threshold": threshold, "tag": tag},
            ))

    return actions


def scan_option_expiry(options: list[dict]) -> list[Action]:
    """Scan options for expiry/action alerts."""
    actions = []
    for opt in options:
        expiry = opt.get("expiry", "")
        days = _dte(expiry)
        ticker = opt.get("ticker", "")
        strike = _parse_float(opt.get("strike"))
        opt_type = opt.get("type", "")
        pl_pct = _parse_float(opt.get("pl_pct"))
        itm_otm = opt.get("itm_otm", "")

        if days <= 0:
            actions.append(Action(
                type="option_expiry",
                ticker=ticker,
                account=opt.get("account", ""),
                urgency="red",
                detail=f"🔴 EXPIRED {ticker} {strike}{opt_type[0].upper() if opt_type else ''} {expiry}",
                metadata={"dte": days, "strike": strike, "type": opt_type},
            ))
        elif days <= 7 and "ITM" in itm_otm:
            actions.append(Action(
                type="option_expiry",
                ticker=ticker,
                account=opt.get("account", ""),
                urgency="red",
                detail=f"🔴 URGENT Close/Roll {ticker} {strike}{opt_type[0].upper() if opt_type else ''} DTE={days} {itm_otm}",
                metadata={"dte": days, "strike": strike, "type": opt_type, "itm_otm": itm_otm},
            ))
        elif days <= 7 and "OTM" in itm_otm:
            actions.append(Action(
                type="option_expiry",
                ticker=ticker,
                account=opt.get("account", ""),
                urgency="green",
                detail=f"✅ Let expire {ticker} {strike}{opt_type[0].upper() if opt_type else ''} DTE={days} {itm_otm}",
                metadata={"dte": days},
            ))
        elif pl_pct >= 75:
            actions.append(Action(
                type="profit_take",
                ticker=ticker,
                account=opt.get("account", ""),
                urgency="green",
                detail=f"✅ Close (75%+ profit) {ticker} {strike}{opt_type[0].upper() if opt_type else ''} P&L={pl_pct:+.0f}%",
                metadata={"dte": days, "pl_pct": pl_pct},
            ))
        elif days <= 21:
            actions.append(Action(
                type="option_expiry",
                ticker=ticker,
                account=opt.get("account", ""),
                urgency="yellow",
                detail=f"⚠️ Monitor {ticker} {strike}{opt_type[0].upper() if opt_type else ''} DTE={days} {itm_otm}",
                metadata={"dte": days},
            ))

    return actions


def generate_cc_tasks(options: list[dict], user_config: dict) -> list[Action]:
    """Generate covered call writing tasks for CC pipeline tickers."""
    cc_tickers = set(
        t.strip().upper()
        for t in user_config.get("cc_pipeline", "").split(",")
        if t.strip()
    )
    if not cc_tickers:
        return []

    # Find tickers that already have open calls
    has_open_call = set()
    for opt in options:
        if opt.get("type", "").lower() == "call" and _dte(opt.get("expiry", "")) > 0:
            has_open_call.add(opt.get("ticker", "").upper())

    actions = []
    for ticker in sorted(cc_tickers):
        if ticker not in has_open_call:
            actions.append(Action(
                type="covered_call",
                ticker=ticker,
                account="",
                urgency="green",
                detail=f"📋 Write CC: {ticker} (no open call)",
                metadata={"reason": "no_open_call"},
            ))

    return actions


def find_completed(recent_trades: list[dict], open_cards: list[dict]) -> list[str]:
    """Match recent trades against open Trello cards. Returns card IDs to delete."""
    # Build set of recently traded tickers (last 7 days)
    traded_tickers = set()
    for trade in recent_trades:
        action = trade.get("action", "")
        if action in ("Close", "Sell", "Roll"):
            traded_tickers.add(trade.get("ticker", "").upper())

    card_ids_to_delete = []
    for card in open_cards:
        # Card name format: "[URGENCY] TICKER ..." or "📋 Write CC: TICKER ..."
        name = card.get("name", "")
        for ticker in traded_tickers:
            if ticker in name.upper():
                card_ids_to_delete.append(card["id"])
                break

    return card_ids_to_delete
