"""P&L calculation and options action logic."""

from datetime import date, datetime


def calc_stock_pl(shares: float, avg_cost: float, current_price: float) -> dict:
    """Calculate stock position P&L."""
    market_value = round(current_price * shares, 2)
    cost_basis = round(avg_cost * shares, 2)
    pl = round(market_value - cost_basis, 2)
    pl_pct = round((pl / cost_basis) * 100, 2) if cost_basis else 0
    return {
        "market_value": market_value,
        "cost_basis": cost_basis,
        "unrealized_pl": pl,
        "pl_pct": pl_pct,
    }


def calc_account_totals(positions: list[dict]) -> dict:
    """Sum up market_value, cost_basis, pl for positions that have prices."""
    total_value = sum(p.get("market_value", 0) for p in positions if p.get("current_price"))
    total_cost = sum(p.get("cost_basis", 0) for p in positions if p.get("current_price"))
    total_pl = round(total_value - total_cost, 2)
    total_pl_pct = round((total_pl / total_cost * 100) if total_cost else 0, 2)
    return {
        "total_market_value": round(total_value, 2),
        "total_cost_basis": round(total_cost, 2),
        "total_pl": total_pl,
        "total_pl_pct": total_pl_pct,
    }


def dte(expiry_str: str, today: date | None = None) -> int:
    """Calculate days to expiry."""
    if today is None:
        today = date.today()
    exp = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    return (exp - today).days


def urgency(days: int) -> str:
    """Determine urgency level based on DTE."""
    if days <= 7:
        return "red"
    if days <= 21:
        return "yellow"
    return "green"


def itm_otm(underlying_price: float, strike: float, opt_type: str) -> str:
    """Determine ITM/OTM status and distance."""
    if opt_type == "put":
        diff = underlying_price - strike
    else:
        diff = strike - underlying_price

    if diff > 0:
        return f"OTM ${diff:.1f}"
    return f"ITM ${abs(diff):.1f}"


def suggest_action(days: int, pl_pct: float, itm_otm_str: str) -> str:
    """Suggest action for an options position."""
    if days <= 0:
        return "EXPIRED"
    if days <= 7 and "OTM" in itm_otm_str:
        return "Let expire"
    if days <= 7 and "ITM" in itm_otm_str:
        return "Close/Roll URGENT"
    if pl_pct >= 75:
        return "Close (75%+ profit)"
    if days <= 21:
        return "Monitor"
    return "Hold"


def calc_option_pl(cost: float, current_value: float | None) -> dict:
    """Calculate P&L for a short option position.
    cost = premium received, current_value = cost to buy back.
    P&L = cost - current_value (positive = profit).
    """
    if current_value is None:
        return {"unrealized_pl": None, "pl_pct": None}
    pl = round(cost - current_value, 2)
    pl_pct = round((pl / cost) * 100, 1) if cost else None
    return {"unrealized_pl": pl, "pl_pct": pl_pct}


def calc_bond_income(bonds: list[dict], tax_rate: float = 0.30) -> dict:
    """Calculate annual bond income (gross and net after withholding)."""
    gross = sum(b["face"] * b["coupon"] for b in bonds)
    net = round(gross * (1 - tax_rate), 2)
    return {
        "annual_gross": round(gross, 2),
        "annual_net": net,
        "monthly_net": round(net / 12, 2),
        "withholding_tax_rate": f"{int(tax_rate * 100)}%",
    }


def calc_net_worth(
    us_value: float,
    tw_value_twd: float,
    bonds_cost: float,
    loans_twd: float,
    fx: float,
) -> dict:
    """Calculate total net worth."""
    tw_value_usd = tw_value_twd / fx
    loans_usd = loans_twd / fx
    total_assets = us_value + tw_value_usd + bonds_cost
    net_worth = total_assets - loans_usd
    return {
        "us_stocks_usd": round(us_value, 2),
        "tw_stocks_twd": round(tw_value_twd, 2),
        "tw_stocks_usd": round(tw_value_usd, 2),
        "bonds_cost_usd": bonds_cost,
        "total_assets_usd": round(total_assets, 2),
        "total_loans_twd": loans_twd,
        "total_loans_usd": round(loans_usd, 2),
        "net_worth_usd": round(net_worth, 2),
        "net_worth_twd": round(net_worth * fx, 0),
    }


def calc_trade_summary(trades: list[dict]) -> dict:
    """Calculate trade journal statistics."""
    wins = [t for t in trades if t.get("result") == "Win"]
    losses = [t for t in trades if t.get("result") == "Loss"]
    breakeven = [t for t in trades if t.get("result") == "Breakeven"]
    total = len(wins) + len(losses) + len(breakeven)

    win_pls = [t["pl"] for t in wins if t.get("pl") is not None]
    loss_pls = [t["pl"] for t in losses if t.get("pl") is not None]
    all_pls = [t["pl"] for t in trades if t.get("pl") is not None]

    return {
        "total_trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": len(breakeven),
        "win_rate": round((len(wins) / total * 100), 1) if total else 0,
        "total_realized_pl": round(sum(all_pls), 2) if all_pls else 0,
        "avg_win": round(sum(win_pls) / len(win_pls), 2) if win_pls else 0,
        "avg_loss": round(sum(loss_pls) / len(loss_pls), 2) if loss_pls else 0,
    }
