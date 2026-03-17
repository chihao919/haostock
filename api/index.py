"""Single FastAPI app for all Vercel serverless endpoints."""

import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, field_validator
from datetime import datetime

app = FastAPI(title="Portfolio Quotes API", version="2.0.0")

_API_KEY = os.environ.get("FINANCIAL_API_KEY", "")

# Paths that don't require API key
_PUBLIC_PATHS = {"/api/health", "/api/auth", "/api/fivelines/auth", "/api/config", "/", "/fivelines", "/portfolio", "/privacy", "/terms", "/setup.sh", "/settings", "/guide"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Skip auth for public paths, non-API paths, MCP endpoint, and OPTIONS
        if (not _API_KEY
                or request.method == "OPTIONS"
                or path in _PUBLIC_PATHS
                or path.startswith("/mcp")
                or path.startswith("/.well-known")
                or path.startswith("/authorize")
                or path.startswith("/token")
                or path.startswith("/api/fivelines/")
                or path.startswith("/api/ai/")
                or path.startswith("/api/cron/")
                or path.startswith("/api/invest/settings")
                or path.startswith("/api/quote/")
                or path == "/api/fx"
                or path == "/api/bonds"
                or path == "/api/loans"
                or path == "/api/stocks/us"
                or path == "/api/stocks/tw"
                or path == "/api/options"
                or path == "/api/networth"
                or path.startswith("/static/")
                or not path.startswith("/api")):
            return await call_next(request)
        # Check x-api-key header
        key = request.headers.get("x-api-key")
        if key != _API_KEY:
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
        return await call_next(request)


app.add_middleware(APIKeyMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Mount static files
_static_dir = Path(__file__).parent / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# Import lib modules
from lib.sheets_client import read_sheet, read_all_sheets, append_rows
from lib.pricing import PriceCache

_PORTFOLIO_SHEET_ID = os.environ.get("PORTFOLIO_SHEET_ID", "")


def _safe_float(val, default=0.0):
    """Convert string to float, return default if empty/invalid."""
    if not val:
        return default
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return default


def _safe_int(val, default=0):
    """Convert string to int, return default if empty/invalid."""
    return int(_safe_float(val, default))


def _sheet_us_stocks() -> dict[str, list[dict]]:
    """Read US stocks from Sheets, grouped by account."""
    rows = read_sheet("US_Stocks", _PORTFOLIO_SHEET_ID)
    grouped = {}
    for r in rows:
        acct = r.get("account", "Unknown")
        grouped.setdefault(acct, []).append({
            "ticker": r.get("ticker", ""),
            "shares": _safe_float(r.get("shares")),
            "avg_cost": _safe_float(r.get("avg_cost")),
        })
    return grouped


def _sheet_tw_stocks() -> dict[str, list[dict]]:
    """Read TW stocks from Sheets, grouped by account."""
    rows = read_sheet("TW_Stocks", _PORTFOLIO_SHEET_ID)
    grouped = {}
    for r in rows:
        acct = r.get("account", "Unknown")
        ticker = r.get("ticker", "")
        if not ticker.endswith(".TW") and not ticker.endswith(".tw") and ticker.isdigit():
            ticker = f"{ticker}.TW"
        grouped.setdefault(acct, []).append({
            "ticker": ticker,
            "name": r.get("name", ""),
            "shares": _safe_float(r.get("shares")),
            "avg_cost": _safe_float(r.get("avg_cost_twd")),
        })
    return grouped


def _sheet_options() -> list[dict]:
    """Read options from Sheets."""
    rows = read_sheet("Options", _PORTFOLIO_SHEET_ID)
    return [{
        "account": r.get("account", ""),
        "ticker": r.get("ticker", ""),
        "expiry": r.get("expiry", ""),
        "strike": _safe_float(r.get("strike")),
        "type": r.get("type", ""),
        "qty": _safe_int(r.get("qty")),
        "cost": _safe_float(r.get("cost")),
    } for r in rows]


def _sheet_bonds() -> list[dict]:
    """Read bonds from Sheets."""
    rows = read_sheet("Bonds", _PORTFOLIO_SHEET_ID)
    return [{
        "name": r.get("name", ""),
        "face": _safe_float(r.get("face")),
        "coupon": _safe_float(r.get("coupon")),
        "maturity": r.get("maturity", ""),
        "cost": _safe_float(r.get("cost")),
    } for r in rows]


def _sheet_loans() -> list[dict]:
    """Read loans from Sheets."""
    rows = read_sheet("Loans", _PORTFOLIO_SHEET_ID)
    return [{
        "name": r.get("name", ""),
        "rate": _safe_float(r.get("rate")),
        "balance": _safe_float(r.get("balance")),
        "monthly": _safe_float(r.get("monthly")),
        "periods_done": _safe_int(r.get("periods_done")),
        "total_periods": _safe_int(r.get("total_periods")),
    } for r in rows]


def _sheet_trades(ticker=None, result=None, asset_type=None, limit=50) -> list[dict]:
    """Read trades from Sheets with optional filters."""
    rows = read_sheet("Trades", _PORTFOLIO_SHEET_ID)
    trades = []
    for r in rows:
        trade = {
            "id": r.get("id", ""),
            "date": r.get("date", ""),
            "ticker": r.get("ticker", ""),
            "action": r.get("action", ""),
            "asset_type": r.get("asset_type", ""),
            "qty": _safe_float(r.get("qty")),
            "price": _safe_float(r.get("price")),
            "total_amount": _safe_float(r.get("total_amount")),
            "pl": _safe_float(r.get("pl")) if r.get("pl") else None,
            "result": r.get("result", "") or None,
            "reason": r.get("reason", ""),
            "lesson": r.get("lesson", ""),
            "tags": [t.strip() for t in r.get("tags", "").split(",") if t.strip()],
            "account": r.get("account", ""),
        }
        if ticker and trade["ticker"].upper() != ticker.upper():
            continue
        if result and trade["result"] != result:
            continue
        if asset_type and trade["asset_type"] != asset_type:
            continue
        trades.append(trade)
    # Sort by date descending
    trades.sort(key=lambda x: x.get("date", ""), reverse=True)
    return trades[:limit]
from lib.calculator import (
    calc_stock_pl, calc_account_totals, dte, urgency, itm_otm,
    suggest_action, calc_option_pl, calc_bond_income, calc_net_worth,
    calc_trade_summary,
)
from lib.tw_financial import analyze_stock as analyze_tw_stock
from lib.us_financial import analyze_stock as analyze_us_stock
from lib.five_lines import analyze as five_lines_analyze
# Lazy imports for invest agent (google-api-python-client may not be available at import time on Vercel)
def _import_invest():
    from lib.sheets_client import (
        read_sheet as sheets_read_sheet, read_all_sheets as sheets_read_all,
        get_active_users, find_user_by_email, upsert_user, mask_token,
    )
    from lib.invest_scanner import scan_stop_losses, scan_option_expiry, generate_cc_tasks, find_completed
    from lib.invest_notifier import (
        format_daily_report, format_weekly_cc, format_completion,
        send_line, sync_trello, cleanup_completed,
    )
    return {
        "sheets_read_sheet": sheets_read_sheet, "sheets_read_all": sheets_read_all,
        "get_active_users": get_active_users, "find_user_by_email": find_user_by_email,
        "upsert_user": upsert_user, "mask_token": mask_token,
        "scan_stop_losses": scan_stop_losses, "scan_option_expiry": scan_option_expiry,
        "generate_cc_tasks": generate_cc_tasks, "find_completed": find_completed,
        "format_daily_report": format_daily_report, "format_weekly_cc": format_weekly_cc,
        "format_completion": format_completion, "send_line": send_line,
        "sync_trello": sync_trello, "cleanup_completed": cleanup_completed,
    }


# --- Validation models ---

VALID_ACTIONS = {"Buy", "Sell", "Open", "Close", "Roll"}
VALID_RESULTS = {"Win", "Loss", "Breakeven"}
VALID_ASSET_TYPES = {"Stock", "Option"}


class TradeCreate(BaseModel):
    date: str
    ticker: str
    action: str
    asset_type: str
    qty: float
    price: float
    total_amount: float
    pl: float | None = None
    result: str | None = None
    reason: str
    lesson: str | None = None
    tags: list[str] | None = None
    account: str

    @field_validator("action")
    @classmethod
    def validate_action(cls, v):
        if v not in VALID_ACTIONS:
            raise ValueError(f"action must be one of {VALID_ACTIONS}")
        return v

    @field_validator("asset_type")
    @classmethod
    def validate_asset_type(cls, v):
        if v not in VALID_ASSET_TYPES:
            raise ValueError(f"asset_type must be one of {VALID_ASSET_TYPES}")
        return v

    @field_validator("result")
    @classmethod
    def validate_result(cls, v):
        if v is not None and v not in VALID_RESULTS:
            raise ValueError(f"result must be one of {VALID_RESULTS}")
        return v


# --- Dashboard ---

_DASHBOARD_PASSWORD = os.environ.get("FIVELINES_PASSWORD", "ccj")


@app.get("/", response_class=HTMLResponse)
def home():
    html_path = Path(__file__).parent / "templates" / "portfolio.html"
    return html_path.read_text(encoding="utf-8")


_GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")


@app.get("/portfolio")
def portfolio_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/", status_code=301)


@app.get("/privacy", response_class=HTMLResponse)
def privacy_page():
    html_path = Path(__file__).parent / "templates" / "privacy.html"
    return html_path.read_text(encoding="utf-8")


@app.get("/terms", response_class=HTMLResponse)
def terms_page():
    html_path = Path(__file__).parent / "templates" / "terms.html"
    return html_path.read_text(encoding="utf-8")


@app.get("/setup.sh", response_class=PlainTextResponse)
def setup_script():
    from fastapi.responses import PlainTextResponse as _PT
    script_path = Path(__file__).parent / "templates" / "setup.sh"
    return _PT(content=script_path.read_text(encoding="utf-8"), media_type="text/plain")


@app.get("/api/config")
def public_config():
    """Return public config (Google Client ID) — no auth required."""
    return {"google_client_id": _GOOGLE_CLIENT_ID}


@app.post("/api/auth")
async def dashboard_auth(request: Request):
    """Authenticate and return API key for dashboard."""
    body = await request.json()
    pw = body.get("password", "").strip().lower()
    if pw == _DASHBOARD_PASSWORD:
        return {"ok": True, "api_key": _API_KEY}
    raise HTTPException(status_code=401, detail="密碼錯誤")


# --- Endpoints ---

@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/fx")
def fx_rate():
    cache = PriceCache()
    rate = cache.get_fx()
    return {"USDTWD": rate, "timestamp": datetime.now().isoformat()}


@app.get("/api/quote/{ticker}")
def single_quote(ticker: str):
    cache = PriceCache()
    price = cache.get_price(ticker.upper())
    if not price:
        raise HTTPException(status_code=404, detail=f"Could not fetch price for {ticker}")
    return {"ticker": ticker.upper(), "price": price, "timestamp": datetime.now().isoformat()}


@app.get("/api/stocks/us")
def us_stocks():
    try:
        accounts_data = _sheet_us_stocks()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Sheets API error: {e}")

    cache = PriceCache()
    result = {}
    all_positions = []

    for account, positions in accounts_data.items():
        acct_positions = []
        for pos in positions:
            price = cache.get_price(pos["ticker"])
            row = {
                "ticker": pos["ticker"],
                "shares": pos["shares"],
                "avg_cost": pos["avg_cost"],
                "current_price": price,
            }
            if price:
                pl = calc_stock_pl(pos["shares"], pos["avg_cost"], price)
                row.update(pl)
            acct_positions.append(row)

        totals = calc_account_totals(acct_positions)
        result[account] = {"positions": acct_positions, **totals}
        all_positions.extend(acct_positions)

    summary = calc_account_totals(all_positions)
    return {"accounts": result, "summary": summary, "timestamp": datetime.now().isoformat()}


@app.get("/api/stocks/tw")
def tw_stocks():
    try:
        accounts_data = _sheet_tw_stocks()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Sheets API error: {e}")

    cache = PriceCache()
    fx = cache.get_fx()
    result = {}
    grand_twd = 0
    grand_cost_twd = 0

    for account, positions in accounts_data.items():
        acct_positions = []
        acct_value_twd = 0
        acct_cost_twd = 0

        for pos in positions:
            price = cache.get_price(pos["ticker"])
            row = {
                "ticker": pos["ticker"],
                "name": pos["name"],
                "shares": pos["shares"],
                "avg_cost_twd": pos["avg_cost"],
                "current_price_twd": price,
            }
            if price:
                mkt_val_twd = round(price * pos["shares"], 0)
                cost_twd = round(pos["avg_cost"] * pos["shares"], 0)
                pl_twd = round(mkt_val_twd - cost_twd, 0)
                pl_pct = round((pl_twd / cost_twd * 100) if cost_twd else 0, 2)
                row.update({
                    "market_value_twd": mkt_val_twd,
                    "market_value_usd": round(mkt_val_twd / fx, 2),
                    "cost_basis_twd": cost_twd,
                    "unrealized_pl_twd": pl_twd,
                    "pl_pct": pl_pct,
                })
                acct_value_twd += mkt_val_twd
                acct_cost_twd += cost_twd
            acct_positions.append(row)

        acct_pl_twd = round(acct_value_twd - acct_cost_twd, 0)
        grand_twd += acct_value_twd
        grand_cost_twd += acct_cost_twd
        result[account] = {
            "positions": acct_positions,
            "total_market_value_twd": acct_value_twd,
            "total_market_value_usd": round(acct_value_twd / fx, 2),
            "total_pl_twd": acct_pl_twd,
            "total_pl_pct": round((acct_pl_twd / acct_cost_twd * 100) if acct_cost_twd else 0, 2),
        }

    grand_pl_twd = round(grand_twd - grand_cost_twd, 0)
    return {
        "usdtwd_rate": fx,
        "accounts": result,
        "summary": {
            "total_market_value_twd": grand_twd,
            "total_market_value_usd": round(grand_twd / fx, 2),
            "total_pl_twd": grand_pl_twd,
            "total_pl_pct": round((grand_pl_twd / grand_cost_twd * 100) if grand_cost_twd else 0, 2),
        },
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/options")
def options_positions():
    try:
        options_data = _sheet_options()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Sheets API error: {e}")

    cache = PriceCache()
    result = []

    for opt in options_data:
        underlying = cache.get_price(opt["ticker"])
        days = dte(opt["expiry"])
        urg = urgency(days)

        itm_otm_str = "unknown"
        if underlying:
            itm_otm_str = itm_otm(underlying, opt["strike"], opt["type"])

        curr_val = cache.get_option_value(
            opt["ticker"], opt["expiry"], opt["strike"], opt["type"], opt["qty"]
        )
        pl_data = calc_option_pl(opt["cost"], curr_val)
        action = suggest_action(days, pl_data["pl_pct"] or 0, itm_otm_str) if pl_data["pl_pct"] is not None else "Check manually"

        result.append({
            "account": opt["account"],
            "ticker": opt["ticker"],
            "expiry": opt["expiry"],
            "strike": opt["strike"],
            "type": opt["type"],
            "qty": opt["qty"],
            "underlying_price": underlying,
            "itm_otm": itm_otm_str,
            "dte": days,
            "urgency": urg,
            "cost_basis": opt["cost"],
            "current_value": curr_val,
            "unrealized_pl": pl_data["unrealized_pl"],
            "pl_pct": pl_data["pl_pct"],
            "action": action,
        })

    result.sort(key=lambda x: x["dte"])
    total_cost = sum(o["cost_basis"] for o in result)
    total_curr = sum(o["current_value"] for o in result if o["current_value"])
    total_pl = round(total_cost - total_curr, 2) if total_curr else None

    return {
        "positions": result,
        "summary": {
            "total_cost_basis": round(total_cost, 2),
            "total_current_value": round(total_curr, 2) if total_curr else None,
            "total_pl": total_pl,
            "total_pl_pct": round((total_pl / total_cost * 100), 1) if total_pl else None,
        },
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/networth")
def net_worth():
    try:
        us_data = _sheet_us_stocks()
        tw_data = _sheet_tw_stocks()
        bonds = _sheet_bonds()
        loans = _sheet_loans()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Sheets API error: {e}")

    cache = PriceCache()
    fx = cache.get_fx()

    us_value = sum(
        (cache.get_price(p["ticker"]) or 0) * p["shares"]
        for positions in us_data.values() for p in positions
    )
    tw_value_twd = sum(
        (cache.get_price(p["ticker"]) or 0) * p["shares"]
        for positions in tw_data.values() for p in positions
    )

    bonds_cost = sum(b["cost"] for b in bonds)
    loans_twd = sum(l["balance"] for l in loans)
    monthly_payments_twd = sum(l["monthly"] for l in loans)

    income = calc_bond_income(bonds)
    nw = calc_net_worth(us_value, tw_value_twd, bonds_cost, loans_twd, fx)

    return {
        "usdtwd_rate": fx,
        "assets": {
            "us_stocks_usd": nw["us_stocks_usd"],
            "tw_stocks_twd": nw["tw_stocks_twd"],
            "tw_stocks_usd": nw["tw_stocks_usd"],
            "bonds_cost_usd": nw["bonds_cost_usd"],
            "total_assets_usd": nw["total_assets_usd"],
        },
        "liabilities": {
            "total_loans_twd": nw["total_loans_twd"],
            "total_loans_usd": nw["total_loans_usd"],
            "monthly_payments_twd": monthly_payments_twd,
        },
        "income": {
            "bonds_annual_gross_usd": income["annual_gross"],
            "bonds_annual_net_usd": income["annual_net"],
            "bonds_monthly_net_usd": income["monthly_net"],
            "withholding_tax_rate": income["withholding_tax_rate"],
        },
        "net_worth_usd": nw["net_worth_usd"],
        "net_worth_twd": nw["net_worth_twd"],
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/bonds")
def list_bonds():
    try:
        bonds = _sheet_bonds()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Sheets API error: {e}")
    return {"bonds": bonds, "timestamp": datetime.now().isoformat()}


@app.get("/api/loans")
def list_loans():
    try:
        loans = _sheet_loans()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Sheets API error: {e}")
    return {"loans": loans, "timestamp": datetime.now().isoformat()}


@app.get("/api/trades")
def list_trades(
    ticker: str | None = None,
    result: str | None = None,
    asset_type: str | None = None,
    limit: int = 50,
):
    try:
        trades = _sheet_trades(ticker=ticker, result=result, asset_type=asset_type, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Sheets API error: {e}")

    summary = calc_trade_summary(trades)
    return {"trades": trades, "summary": summary, "timestamp": datetime.now().isoformat()}


@app.post("/api/trades", status_code=201)
def add_trade(trade: TradeCreate):
    try:
        data = trade.model_dump()
        row = [
            data.get("date", ""),
            data.get("ticker", ""),
            data.get("action", ""),
            data.get("asset_type", ""),
            str(data.get("qty", "")),
            str(data.get("price", "")),
            str(data.get("total_amount", "")),
            str(data.get("pl", "")) if data.get("pl") is not None else "",
            data.get("result", "") or "",
            data.get("reason", ""),
            data.get("lesson", "") or "",
            ",".join(data.get("tags") or []),
            data.get("account", ""),
        ]
        append_rows("Trades", [row], _PORTFOLIO_SHEET_ID)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Sheets API error: {e}")
    return {"id": f"sheet-{datetime.now().strftime('%Y%m%d%H%M%S')}", "status": "created", "timestamp": datetime.now().isoformat()}


@app.get("/api/strategy")
async def get_strategy():
    """Return investment strategy markdown."""
    strategy_path = Path(__file__).parent / "docs" / "INVESTMENT_STRATEGY.md"
    if not strategy_path.exists():
        raise HTTPException(status_code=404, detail="Strategy file not found")
    return {"content": strategy_path.read_text(encoding="utf-8")}


@app.get("/api/financial/analyze/{ticker}")
async def financial_analyze(ticker: str):
    ticker = ticker.strip()
    try:
        if ticker.isdigit():
            result = await analyze_tw_stock(ticker)
        else:
            result = await analyze_us_stock(ticker.upper())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Analysis failed: {e}")
    result["timestamp"] = datetime.now().isoformat()
    return result


# --- Investment Action Agent ---

_CRON_SECRET = os.environ.get("CRON_SECRET", "")


def _verify_cron(authorization: str | None) -> None:
    """Verify CRON_SECRET from Authorization header."""
    if not _CRON_SECRET:
        return  # no secret configured, skip check
    if not authorization or authorization != f"Bearer {_CRON_SECRET}":
        raise HTTPException(status_code=401, detail="Invalid cron secret")


async def _verify_google_token(request: Request) -> str:
    """Verify Google ID token from Authorization header. Returns email."""
    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests as google_requests

    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Google ID token")
    token = auth[7:]
    try:
        idinfo = google_id_token.verify_oauth2_token(
            token, google_requests.Request(), _GOOGLE_CLIENT_ID
        )
        return idinfo["email"]
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {e}")


async def _run_daily_scan(user: dict, inv: dict) -> dict:
    """Run daily scan for a single user. Returns scan result."""
    sid = user.get("spreadsheet_id", "")
    if not sid:
        return {"user": user.get("email"), "error": "no_spreadsheet_id"}

    try:
        data = inv["sheets_read_all"](
            sheet_names=["US_Stocks", "TW_Stocks", "Options", "Trades"],
            spreadsheet_id=sid,
        )
    except Exception as e:
        return {"user": user.get("email"), "error": str(e)}

    # Scan for actions
    stop_actions = inv["scan_stop_losses"](
        data.get("US_Stocks", []), data.get("TW_Stocks", []), user
    )
    option_actions = inv["scan_option_expiry"](data.get("Options", []))
    all_actions = stop_actions + option_actions

    # Send LINE
    report = inv["format_daily_report"](all_actions)
    line_ok = await inv["send_line"](user, report)

    # Sync Trello
    trello_result = await inv["sync_trello"](user, [a for a in all_actions if a.urgency in ("red", "yellow")])

    # Cleanup completed cards
    list_id = user.get("trello_list_id", "") or trello_result.get("list_id", "")
    if list_id and user.get("trello_api_key") and user.get("trello_token"):
        from lib.trello import get_cards as trello_get_cards
        open_cards = await trello_get_cards(user["trello_api_key"], user["trello_token"], list_id)
        recent_trades = data.get("Trades", [])[:20]
        completed_ids = inv["find_completed"](recent_trades, open_cards)
        if completed_ids:
            await inv["cleanup_completed"](user, completed_ids)

    return {
        "user": user.get("email"),
        "actions": len(all_actions),
        "line_sent": line_ok,
        "trello": trello_result,
    }


@app.get("/api/cron/invest-daily")
async def cron_invest_daily(authorization: str | None = Header(None)):
    """Daily investment scan — stop losses + option expiry."""
    _verify_cron(authorization)
    inv = _import_invest()
    users = inv["get_active_users"]()
    results = []
    for user in users:
        result = await _run_daily_scan(user, inv)
        results.append(result)
    return {"status": "ok", "scanned": len(results), "results": results, "timestamp": datetime.now().isoformat()}


@app.get("/api/cron/invest-weekly")
async def cron_invest_weekly(authorization: str | None = Header(None)):
    """Weekly covered call task generation."""
    _verify_cron(authorization)
    inv = _import_invest()
    users = inv["get_active_users"]()
    results = []
    for user in users:
        sid = user.get("spreadsheet_id", "")
        if not sid:
            results.append({"user": user.get("email"), "error": "no_spreadsheet_id"})
            continue
        try:
            options = inv["sheets_read_sheet"]("Options", spreadsheet_id=sid)
        except Exception as e:
            results.append({"user": user.get("email"), "error": str(e)})
            continue

        cc_tasks = inv["generate_cc_tasks"](options, user)
        msg = inv["format_weekly_cc"](cc_tasks)
        line_ok = await inv["send_line"](user, msg)
        trello_result = await inv["sync_trello"](user, cc_tasks)

        results.append({
            "user": user.get("email"),
            "cc_tasks": len(cc_tasks),
            "line_sent": line_ok,
            "trello": trello_result,
        })

    return {"status": "ok", "scanned": len(results), "results": results, "timestamp": datetime.now().isoformat()}


@app.get("/api/cron/sbl-notify")
async def cron_sbl_notify(authorization: str | None = Header(None)):
    """SBL lending reminder — runs up to 4x daily on TW trading days."""
    _verify_cron(authorization)
    from lib.sbl_analyzer import (
        fetch_borrowable_shares, fetch_recent_sbl_transactions,
        fetch_bid_borrowing, analyze_lending_opportunities,
        format_sbl_notification,
    )
    inv = _import_invest()
    users = inv["get_active_users"]()

    # Determine reminder number based on current TW time (UTC+8)
    # 0=9:30 bid-only, 1=10:30, 2=11:00, 3=11:30, 4=12:00 end-of-day
    from datetime import timezone, timedelta as td
    tw_now = datetime.now(timezone(td(hours=8)))
    tw_time = tw_now.hour * 60 + tw_now.minute
    if tw_time < 630:  # before 10:30 → bid-only alert (9:30)
        reminder_num = 0
    elif tw_time < 660:  # before 11:00
        reminder_num = 1
    elif tw_time < 690:  # before 11:30
        reminder_num = 2
    elif tw_time < 730:  # before 12:10
        reminder_num = 3
    else:
        reminder_num = 4

    # Fetch TWSE data once for all users
    try:
        transactions = fetch_recent_sbl_transactions(days=14)
        borrowable = fetch_borrowable_shares()
        bid_borrowing = fetch_bid_borrowing()
    except Exception as e:
        return {"status": "error", "error": f"TWSE fetch failed: {e}"}

    results = []
    for user in users:
        sid = user.get("spreadsheet_id", "")
        if not sid:
            results.append({"user": user.get("email"), "error": "no_spreadsheet_id"})
            continue
        try:
            tw_stocks = inv["sheets_read_sheet"]("TW_Stocks", spreadsheet_id=sid)
            # Build holdings list with ticker and name
            holdings = []
            holding_ticker_set = set()
            for s in tw_stocks:
                ticker = s.get("ticker", "").replace(".TW", "").replace(".tw", "")
                name = s.get("name", ticker)
                if ticker:
                    holdings.append({"ticker": ticker, "name": name})
                    holding_ticker_set.add(ticker)

            opportunities = analyze_lending_opportunities(
                holdings, transactions=transactions, borrowable=borrowable,
            )
            msg = format_sbl_notification(
                opportunities, reminder_num=reminder_num,
                bid_borrowing=bid_borrowing, holding_tickers=holding_ticker_set,
            )
            bid_matches = [b for b in bid_borrowing if b["ticker"] in holding_ticker_set]
            if msg is not None:
                line_ok = await inv["send_line"](user, msg)
            else:
                line_ok = False
            results.append({
                "user": user.get("email"),
                "opportunities": len([o for o in opportunities if o["tx_count"] > 0]),
                "bid_matches": len(bid_matches),
                "reminder_num": reminder_num,
                "line_sent": line_ok,
                "skipped": msg is None,
            })
        except Exception as e:
            results.append({"user": user.get("email"), "error": str(e)})

    return {"status": "ok", "scanned": len(results), "results": results, "timestamp": datetime.now().isoformat()}


@app.post("/api/invest/complete")
async def invest_complete(request: Request):
    """Webhook: trade completed, cleanup Trello card + notify."""
    inv = _import_invest()
    body = await request.json()
    ticker = body.get("ticker", "").upper()
    email = body.get("email")

    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")

    users = inv["get_active_users"]()
    if email:
        users = [u for u in users if u.get("email", "").lower() == email.lower()]

    results = []
    for user in users:
        api_key = user.get("trello_api_key", "")
        token = user.get("trello_token", "")
        list_id = user.get("trello_list_id", "")
        if not api_key or not token or not list_id:
            continue

        from lib.trello import get_cards as trello_get_cards
        cards = await trello_get_cards(api_key, token, list_id)
        to_delete = [c["id"] for c in cards if ticker in c.get("name", "").upper()]
        deleted = await inv["cleanup_completed"](user, to_delete)

        if deleted > 0:
            msg = inv["format_completion"](ticker)
            await inv["send_line"](user, msg)

        results.append({"user": user.get("email"), "deleted": deleted})

    return {"status": "ok", "ticker": ticker, "results": results}


@app.get("/api/invest/settings")
async def get_invest_settings(request: Request):
    """Get user settings (requires Google ID token)."""
    inv = _import_invest()
    email = await _verify_google_token(request)
    user = inv["find_user_by_email"](email)

    if not user:
        return {"exists": False, "email": email, "defaults": {
            "stop_loss_spec": "-10",
            "stop_loss_invest": "-20",
            "cc_pipeline": "",
            "spec_tickers": "",
            "active": "false",
        }}

    # Mask sensitive tokens
    masked = dict(user)
    for key in ("line_channel_token", "trello_api_key", "trello_token"):
        if masked.get(key):
            masked[key] = inv["mask_token"](masked[key])
    return {"exists": True, "email": email, "settings": masked}


@app.post("/api/invest/settings")
async def save_invest_settings(request: Request):
    """Save user settings (requires Google ID token)."""
    inv = _import_invest()
    email = await _verify_google_token(request)
    body = await request.json()
    body["email"] = email

    # Preserve masked tokens — if value looks like a mask, keep the old one
    existing = inv["find_user_by_email"](email)
    if existing:
        for key in ("line_channel_token", "trello_api_key", "trello_token"):
            val = body.get(key, "")
            if val and val.startswith("*"):
                body[key] = existing.get(key, "")

    result = inv["upsert_user"](body)
    return {"status": result, "email": email}


@app.get("/settings", response_class=HTMLResponse)
def settings_page():
    html_path = Path(__file__).parent / "templates" / "settings.html"
    return html_path.read_text(encoding="utf-8")


@app.get("/guide", response_class=HTMLResponse)
def guide_page():
    html_path = Path(__file__).parent / "templates" / "guide.html"
    return html_path.read_text(encoding="utf-8")


# --- Five Lines (樂活五線譜) ---


_FIVELINES_PASSWORD = os.environ.get("FIVELINES_PASSWORD", "ccj")


@app.get("/fivelines", response_class=HTMLResponse)
def five_lines_page():
    html_path = Path(__file__).parent / "templates" / "fivelines.html"
    return html_path.read_text(encoding="utf-8")


@app.post("/api/fivelines/auth")
async def five_lines_auth(request: Request):
    body = await request.json()
    pw = body.get("password", "").strip().lower()
    if pw == _FIVELINES_PASSWORD:
        return {"ok": True, "level": "full"}
    if pw == "2330":
        return {"ok": True, "level": "basic"}
    raise HTTPException(status_code=401, detail="密碼錯誤")


@app.get("/api/fivelines/{ticker}")
def five_lines(ticker: str, years: float = 3.5, include_history: bool = False):
    # Auto-append .TW for numeric TW stock tickers
    ticker = ticker.strip()
    if ticker.isdigit():
        ticker = f"{ticker}.TW"
    try:
        result = five_lines_analyze(ticker, years=years, include_history=include_history)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Analysis failed for {ticker}: {e}")
    result["timestamp"] = datetime.now().isoformat()
    return result


# --- Remote MCP Endpoint (Streamable HTTP, spec 2025-03-26) ---

import json
import uuid
import secrets
import hashlib
import base64
import httpx as _httpx
from urllib.parse import urlencode, parse_qs, urlparse
from fastapi.responses import JSONResponse, Response, RedirectResponse

_MCP_API = "https://stock.cwithb.com"

# --- OAuth 2.1 for MCP (minimal implementation for personal use) ---
_OAUTH_CLIENT_ID = "portfolio-mcp-client"
_OAUTH_CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET", "")
_OAUTH_ISSUER = "https://stock.cwithb.com"

# In-memory stores (reset on cold start, fine for serverless personal use)
_auth_codes: dict[str, dict] = {}  # code -> {redirect_uri, code_challenge, client_id}
_access_tokens: set[str] = set()


@app.get("/.well-known/oauth-authorization-server")
async def oauth_metadata():
    return JSONResponse({
        "issuer": _OAUTH_ISSUER,
        "authorization_endpoint": f"{_OAUTH_ISSUER}/authorize",
        "token_endpoint": f"{_OAUTH_ISSUER}/token",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "token_endpoint_auth_methods_supported": ["client_secret_post", "none"],
        "code_challenge_methods_supported": ["S256"],
    })


@app.get("/authorize")
async def oauth_authorize(
    response_type: str = "code",
    client_id: str = "",
    redirect_uri: str = "",
    state: str = "",
    code_challenge: str = "",
    code_challenge_method: str = "S256",
    scope: str = "",
):
    """OAuth authorize endpoint — auto-approves for the known client."""
    if client_id != _OAUTH_CLIENT_ID:
        return JSONResponse({"error": "invalid_client"}, status_code=400)

    code = secrets.token_urlsafe(32)
    _auth_codes[code] = {
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "client_id": client_id,
    }

    params = {"code": code}
    if state:
        params["state"] = state
    separator = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(f"{redirect_uri}{separator}{urlencode(params)}")


@app.post("/token")
async def oauth_token(request: Request):
    """OAuth token endpoint — exchanges auth code for access token."""
    content_type = request.headers.get("content-type", "")
    if "json" in content_type:
        body = await request.json()
    else:
        # Parse form-urlencoded body manually (no python-multipart needed)
        raw = (await request.body()).decode()
        body = dict(pair.split("=", 1) for pair in raw.split("&") if "=" in pair)
    grant_type = body.get("grant_type")
    code = body.get("code", "")
    code_verifier = body.get("code_verifier", "")
    client_id = body.get("client_id", "")
    client_secret = body.get("client_secret", "")

    if grant_type == "authorization_code":
        if code not in _auth_codes:
            return JSONResponse({"error": "invalid_grant"}, status_code=400)

        auth_data = _auth_codes.pop(code)

        # Verify PKCE if code_challenge was provided
        if auth_data["code_challenge"] and code_verifier:
            expected = base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode()).digest()
            ).rstrip(b"=").decode()
            if expected != auth_data["code_challenge"]:
                return JSONResponse({"error": "invalid_grant", "error_description": "PKCE verification failed"}, status_code=400)

        token = secrets.token_urlsafe(48)
        _access_tokens.add(token)
        return JSONResponse({
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": 86400,
        })

    return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

_MCP_TOOLS = [
    {"name": "get_us_stocks", "description": "Query all US stock positions with P&L by account.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_tw_stocks", "description": "Query all Taiwan stock positions with P&L in TWD/USD.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_options", "description": "Query all options positions with P&L, DTE, urgency, actions.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_quote", "description": "Get real-time quote for a ticker (e.g. NVDA, 2330.TW).", "inputSchema": {"type": "object", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]}},
    {"name": "get_networth", "description": "Query net worth: assets, liabilities, bond income.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_fx_rate", "description": "Get USD/TWD exchange rate.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_trades", "description": "Query trade history with optional filters.", "inputSchema": {"type": "object", "properties": {"ticker": {"type": "string"}, "result": {"type": "string"}, "asset_type": {"type": "string"}, "limit": {"type": "integer"}}}},
    {"name": "add_trade", "description": "Add trade record. action: Buy/Sell/Open/Close/Roll.", "inputSchema": {"type": "object", "properties": {"date": {"type": "string"}, "ticker": {"type": "string"}, "action": {"type": "string"}, "asset_type": {"type": "string"}, "qty": {"type": "number"}, "price": {"type": "number"}, "total_amount": {"type": "number"}, "reason": {"type": "string"}, "account": {"type": "string"}, "pl": {"type": "number"}, "result": {"type": "string"}, "lesson": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}}, "required": ["date", "ticker", "action", "asset_type", "qty", "price", "total_amount", "reason", "account"]}},
    {"name": "analyze_stock", "description": "Financial analysis (Huang Kuo-Hua method for TW, fundamental for US). Pass numeric ticker for TW (e.g. 2330), alpha for US (e.g. NVDA).", "inputSchema": {"type": "object", "properties": {"ticker": {"type": "string", "description": "Stock ticker: numeric for TW (2330), alpha for US (NVDA)"}}, "required": ["ticker"]}},
    {"name": "get_five_lines", "description": "Happy Five Lines (樂活五線譜) analysis — linear regression ± σ bands with buy/sell signals. Works for TW (0050.TW) and US (VOO) stocks.", "inputSchema": {"type": "object", "properties": {"ticker": {"type": "string", "description": "Stock ticker (e.g. 0050.TW, VOO, 2330.TW)"}, "years": {"type": "number", "description": "Historical period in years (default 3.5)"}}, "required": ["ticker"]}},
]

_TOOL_ROUTES = {"get_us_stocks": "/api/stocks/us", "get_tw_stocks": "/api/stocks/tw", "get_options": "/api/options", "get_networth": "/api/networth", "get_fx_rate": "/api/fx"}


async def _mcp_call_tool(name: str, args: dict) -> str:
    _headers = {"x-api-key": _API_KEY} if _API_KEY else {}
    async with _httpx.AsyncClient(timeout=15, headers=_headers) as c:
        if name in _TOOL_ROUTES:
            r = await c.get(f"{_MCP_API}{_TOOL_ROUTES[name]}")
            r.raise_for_status()
            return json.dumps(r.json(), indent=2)
        if name == "get_quote":
            r = await c.get(f"{_MCP_API}/api/quote/{args.get('ticker', '')}")
            r.raise_for_status()
            return json.dumps(r.json(), indent=2)
        if name == "get_trades":
            p = {k: v for k, v in args.items() if v}
            r = await c.get(f"{_MCP_API}/api/trades", params=p)
            r.raise_for_status()
            return json.dumps(r.json(), indent=2)
        if name == "add_trade":
            r = await c.post(f"{_MCP_API}/api/trades", json=args)
            r.raise_for_status()
            return json.dumps(r.json(), indent=2)
        if name == "analyze_stock":
            r = await c.get(f"{_MCP_API}/api/financial/analyze/{args.get('ticker', '')}", timeout=30)
            r.raise_for_status()
            return json.dumps(r.json(), indent=2)
        if name == "get_five_lines":
            p = {"years": args.get("years", 3.5)}
            r = await c.get(f"{_MCP_API}/api/fivelines/{args.get('ticker', '')}", params=p, timeout=15)
            r.raise_for_status()
            return json.dumps(r.json(), indent=2)
    return json.dumps({"error": f"Unknown tool: {name}"})


@app.post("/mcp")
async def mcp_post(request: Request):
    body = await request.json()
    msgs = body if isinstance(body, list) else [body]

    # Notifications/responses only → 202
    if all(("id" not in m or "method" not in m) for m in msgs):
        has_request = any("id" in m and "method" in m for m in msgs)
        if not has_request:
            return Response(status_code=202)

    msg = msgs[0] if isinstance(body, list) else body
    method = msg.get("method")
    rid = msg.get("id")
    params = msg.get("params", {})

    if method == "initialize":
        sid = str(uuid.uuid4())
        return JSONResponse(
            {"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "portfolio", "version": "2.0.0"},
            }},
            media_type="application/json",
            headers={"Mcp-Session-Id": sid},
        )

    if method == "tools/list":
        return JSONResponse({"jsonrpc": "2.0", "id": rid, "result": {"tools": _MCP_TOOLS}}, media_type="application/json")

    if method == "tools/call":
        try:
            text = await _mcp_call_tool(params.get("name"), params.get("arguments", {}))
            return JSONResponse({"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": text}]}}, media_type="application/json")
        except Exception as e:
            return JSONResponse({"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}}, media_type="application/json")

    if method == "ping":
        return JSONResponse({"jsonrpc": "2.0", "id": rid, "result": {}}, media_type="application/json")

    # Notification (no id) → 202
    if "id" not in msg:
        return Response(status_code=202)

    return JSONResponse({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"Method not found: {method}"}}, status_code=400)


@app.get("/mcp")
async def mcp_get():
    return Response(status_code=405)


@app.delete("/mcp")
async def mcp_delete():
    return Response(status_code=200)


# --- AI Chat Endpoint ---

_AI_MODELS = {
    "sonnet": {"provider": "anthropic", "model": "claude-sonnet-4-20250514"},
    "opus": {"provider": "anthropic", "model": "claude-opus-4-20250514"},
    "gpt-4o": {"provider": "openai", "model": "gpt-4o"},
    "gpt-4o-mini": {"provider": "openai", "model": "gpt-4o-mini"},
    "gemini-flash": {"provider": "gemini", "model": "gemini-2.5-flash-preview-05-20"},
    "gemini-pro": {"provider": "gemini", "model": "gemini-2.5-pro-preview-05-06"},
}


class AIChatRequest(BaseModel):
    message: str
    images: list[str] = []
    encrypted_secrets: str
    spreadsheet_id: str
    portfolio_summary: str = ""
    conversation_history: list[dict] = []
    model: str = "sonnet"  # "sonnet" or "opus"


def _get_rsa_public_pem() -> str:
    from cryptography.hazmat.primitives import serialization
    pem = os.environ["RSA_PRIVATE_KEY"].replace("\\n", "\n").encode()
    private_key = serialization.load_pem_private_key(pem, password=None)
    pub_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return pub_pem.decode()


def _decrypt_secrets(encrypted_b64: str) -> dict:
    """Hybrid decryption: RSA-OAEP decrypts AES key, AES-GCM decrypts payload.
    Format: base64(rsa_encrypted_aes_key(256B) + iv(12B) + aes_ciphertext + tag)
    """
    from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    raw = base64.b64decode(encrypted_b64)
    rsa_block = raw[:256]  # RSA-2048 = 256 bytes
    iv = raw[256:268]       # 12 bytes IV
    ciphertext = raw[268:]  # AES-GCM ciphertext + tag

    pem = os.environ["RSA_PRIVATE_KEY"].replace("\\n", "\n").encode()
    private_key = serialization.load_pem_private_key(pem, password=None)
    aes_key = private_key.decrypt(
        rsa_block,
        asym_padding.OAEP(
            mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(), label=None
        )
    )
    aesgcm = AESGCM(aes_key)
    plaintext = aesgcm.decrypt(iv, ciphertext, None)
    return json.loads(plaintext)


async def _write_to_sheets(google_token: str, spreadsheet_id: str, sheet_name: str, headers: list, rows: list[list]):
    values = [headers] + rows
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{sheet_name}?valueInputOption=RAW"
    async with _httpx.AsyncClient(timeout=15) as client:
        r = await client.put(url, json={"values": values}, headers={
            "Authorization": f"Bearer {google_token}",
            "Content-Type": "application/json",
        })
        r.raise_for_status()
    return r.json()


_AI_TOOLS = [
    {
        "name": "get_quote",
        "description": "Get real-time stock quote for a ticker (e.g. NVDA, 2330.TW, AAPL)",
        "input_schema": {"type": "object", "properties": {"ticker": {"type": "string", "description": "Stock ticker"}}, "required": ["ticker"]},
    },
    {
        "name": "analyze_stock",
        "description": "Fundamental financial analysis. Pass numeric ticker for TW (e.g. 2330), alpha for US (e.g. NVDA).",
        "input_schema": {"type": "object", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]},
    },
    {
        "name": "five_lines",
        "description": "Happy Five Lines (樂活五線譜) technical analysis — linear regression ± σ bands with buy/sell signals.",
        "input_schema": {"type": "object", "properties": {"ticker": {"type": "string"}, "years": {"type": "number", "description": "Historical period in years, default 3.5"}}, "required": ["ticker"]},
    },
    {
        "name": "update_us_positions",
        "description": "Update US stock positions in Google Sheets. Use after user confirms parsed data.",
        "input_schema": {"type": "object", "properties": {"positions": {"type": "array", "items": {"type": "object", "properties": {"account": {"type": "string"}, "ticker": {"type": "string"}, "shares": {"type": "number"}, "avg_cost": {"type": "number"}}, "required": ["account", "ticker", "shares", "avg_cost"]}}}, "required": ["positions"]},
    },
    {
        "name": "update_tw_positions",
        "description": "Update Taiwan stock positions in Google Sheets. Use after user confirms parsed data.",
        "input_schema": {"type": "object", "properties": {"positions": {"type": "array", "items": {"type": "object", "properties": {"ticker": {"type": "string"}, "name": {"type": "string"}, "account": {"type": "string"}, "shares": {"type": "number"}, "avg_cost_twd": {"type": "number"}}, "required": ["ticker", "name", "account", "shares", "avg_cost_twd"]}}}, "required": ["positions"]},
    },
    {
        "name": "update_options",
        "description": "Update options positions in Google Sheets. Use after user confirms parsed data.",
        "input_schema": {"type": "object", "properties": {"positions": {"type": "array", "items": {"type": "object", "properties": {"account": {"type": "string"}, "ticker": {"type": "string"}, "expiry": {"type": "string"}, "strike": {"type": "number"}, "type": {"type": "string"}, "qty": {"type": "number"}, "cost": {"type": "number"}}, "required": ["account", "ticker", "expiry", "strike", "type", "qty", "cost"]}}}, "required": ["positions"]},
    },
    {
        "name": "save_notes_to_drive",
        "description": "Save discussion notes/strategy analysis to a text file in user's Google Drive portfolio folder.",
        "input_schema": {"type": "object", "properties": {"title": {"type": "string", "description": "File title"}, "content": {"type": "string", "description": "Content to save (markdown)"}}, "required": ["title", "content"]},
    },
]

def _build_system_prompt(today: str, portfolio_summary: str) -> str:
    # Load full investment strategy if available
    strategy = ""
    strategy_path = Path(__file__).parent / "docs" / "INVESTMENT_STRATEGY.md"
    if strategy_path.exists():
        strategy = strategy_path.read_text(encoding="utf-8")

    return f"""今天日期：{today}

你是一位專業的投資組合 AI 助手。你能夠：
1. 查詢即時股價、基本面分析、技術面分析（五線譜）
2. 解析券商截圖，確認後更新 Google Sheets
3. 根據持倉提供 Covered Call 策略建議
4. 回答一般投資問題

## 重要規則
- **所有日期必須基於今天日期**，Covered Call 到期日建議 30-45 天後的月份選擇權
- Covered Call Strike 選 15-20% OTM，DTE 30-45 天
- Sell Put Strike 選 ATM 或 5-10% OTM，DTE 30-45 天
- 更新 Google Sheets 前**必須先向使用者確認**解析結果
- 分析時**必須使用 get_quote 工具**取得即時價格，不要用記憶中的價格
- 建議 Covered Call 時，先用 get_quote 查現價，再根據現價算 Strike
- 用繁體中文回覆
- 回覆要簡潔有重點，用表格呈現比較數據

## 投資策略（完整版）
{strategy}

## 當前持倉摘要（即時）
{portfolio_summary}
"""


async def _handle_ai_tool(name: str, args: dict, google_token: str, spreadsheet_id: str) -> str:
    cache = PriceCache()

    if name == "get_quote":
        ticker = args["ticker"].upper()
        price = cache.get_price(ticker)
        if not price:
            return json.dumps({"error": f"Could not fetch price for {ticker}"})
        return json.dumps({"ticker": ticker, "price": price})

    if name == "analyze_stock":
        ticker = args["ticker"].strip()
        try:
            if ticker.isdigit():
                result = await analyze_tw_stock(ticker)
            else:
                result = await analyze_us_stock(ticker.upper())
            return json.dumps(result, default=str)
        except Exception as e:
            return json.dumps({"error": f"Analysis failed: {e}"})

    if name == "five_lines":
        ticker = args["ticker"].strip()
        if ticker.isdigit():
            ticker = f"{ticker}.TW"
        years = args.get("years", 3.5)
        try:
            result = five_lines_analyze(ticker, years=years)
            return json.dumps(result, default=str)
        except Exception as e:
            return json.dumps({"error": f"Five lines failed: {e}"})

    if name == "update_us_positions":
        rows = [[p["account"], p["ticker"], p["shares"], p["avg_cost"]] for p in args["positions"]]
        await _write_to_sheets(google_token, spreadsheet_id, "US_Stocks",
                               ["account", "ticker", "shares", "avg_cost"], rows)
        return json.dumps({"updated": "US_Stocks", "count": len(rows)})

    if name == "update_tw_positions":
        rows = [[p["ticker"], p["name"], p["account"], p["shares"], p["avg_cost_twd"]] for p in args["positions"]]
        await _write_to_sheets(google_token, spreadsheet_id, "TW_Stocks",
                               ["ticker", "name", "account", "shares", "avg_cost_twd"], rows)
        return json.dumps({"updated": "TW_Stocks", "count": len(rows)})

    if name == "update_options":
        rows = [[p["account"], p["ticker"], p["expiry"], p["strike"], p["type"], p["qty"], p["cost"]] for p in args["positions"]]
        await _write_to_sheets(google_token, spreadsheet_id, "Options",
                               ["account", "ticker", "expiry", "strike", "type", "qty", "cost"], rows)
        return json.dumps({"updated": "Options", "count": len(rows)})

    if name == "save_notes_to_drive":
        title = args["title"]
        content = args["content"]
        # Find or create portfolio folder, then create a Google Doc
        async with _httpx.AsyncClient(timeout=15) as client:
            headers = {"Authorization": f"Bearer {google_token}", "Content-Type": "application/json"}
            # Search for portfolio folder
            q = "name='Portfolio Dashboard' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            r = await client.get(f"https://www.googleapis.com/drive/v3/files?q={q}&fields=files(id)", headers=headers)
            files = r.json().get("files", [])
            folder_id = files[0]["id"] if files else None

            # Create doc
            metadata = {"name": title, "mimeType": "application/vnd.google-apps.document"}
            if folder_id:
                metadata["parents"] = [folder_id]
            r = await client.post("https://www.googleapis.com/drive/v3/files", json=metadata, headers=headers)
            doc_id = r.json().get("id")

            # Write content
            if doc_id:
                requests_body = [{"insertText": {"location": {"index": 1}, "text": content}}]
                await client.post(f"https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate",
                                  json={"requests": requests_body}, headers=headers)
                return json.dumps({"saved": True, "doc_id": doc_id, "title": title})
        return json.dumps({"error": "Failed to save to Drive"})

    return json.dumps({"error": f"Unknown tool: {name}"})


@app.get("/api/ai/pubkey")
def ai_pubkey():
    try:
        pem = _get_rsa_public_pem()
        return {"public_key": pem}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RSA key not configured: {e}")


async def _chat_anthropic(api_key: str, model_id: str, system: str, req: AIChatRequest, google_token: str):
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    messages = []
    for msg in req.conversation_history[-20:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    content = []
    for img in req.images:
        if "," in img:
            media_type = img.split(";")[0].split(":")[1] if ":" in img else "image/png"
            data = img.split(",", 1)[1]
        else:
            media_type, data = "image/png", img
        content.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}})
    content.append({"type": "text", "text": req.message})
    messages.append({"role": "user", "content": content})

    actions_taken, updated_sheets = [], []

    for _ in range(10):
        response = client.messages.create(
            model=model_id, max_tokens=4096, system=system,
            tools=_AI_TOOLS, messages=messages,
        )
        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    try:
                        result = await _handle_ai_tool(block.name, block.input, google_token, req.spreadsheet_id)
                        actions_taken.append({"tool": block.name, "input": block.input})
                        if "updated" in json.loads(result):
                            updated_sheets.append(json.loads(result)["updated"])
                    except Exception as e:
                        result = json.dumps({"error": str(e)})
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
            messages.append({"role": "user", "content": tool_results})
        else:
            text = "".join(b.text for b in response.content if hasattr(b, "text"))
            return {"response_text": text, "actions_taken": actions_taken, "updated_sheets": updated_sheets}

    return {"response_text": "（處理超時，請重試）", "actions_taken": actions_taken, "updated_sheets": updated_sheets}


async def _chat_openai_compat(api_key: str, base_url: str | None, model_id: str, system: str, req: AIChatRequest, google_token: str):
    from openai import OpenAI
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)

    oai_tools = [
        {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
        for t in _AI_TOOLS
    ]

    oai_msgs = [{"role": "system", "content": system}]
    for msg in req.conversation_history[-20:]:
        oai_msgs.append({"role": msg["role"], "content": msg["content"]})

    # Current message
    if req.images:
        parts = []
        for img in req.images:
            url = img if img.startswith("data:") else f"data:image/png;base64,{img}"
            parts.append({"type": "image_url", "image_url": {"url": url}})
        parts.append({"type": "text", "text": req.message})
        oai_msgs.append({"role": "user", "content": parts})
    else:
        oai_msgs.append({"role": "user", "content": req.message})

    actions_taken, updated_sheets = [], []

    for _ in range(10):
        response = client.chat.completions.create(
            model=model_id, messages=oai_msgs, tools=oai_tools, max_tokens=4096,
        )
        choice = response.choices[0]

        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            oai_msgs.append({"role": "assistant", "content": choice.message.content, "tool_calls": [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in choice.message.tool_calls
            ]})
            for tc in choice.message.tool_calls:
                try:
                    tool_args = json.loads(tc.function.arguments)
                    result = await _handle_ai_tool(tc.function.name, tool_args, google_token, req.spreadsheet_id)
                    actions_taken.append({"tool": tc.function.name, "input": tool_args})
                    if "updated" in json.loads(result):
                        updated_sheets.append(json.loads(result)["updated"])
                except Exception as e:
                    result = json.dumps({"error": str(e)})
                oai_msgs.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        else:
            return {"response_text": choice.message.content or "", "actions_taken": actions_taken, "updated_sheets": updated_sheets}

    return {"response_text": "（處理超時，請重試）", "actions_taken": actions_taken, "updated_sheets": updated_sheets}


_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


@app.post("/api/ai/chat")
async def ai_chat(req: AIChatRequest):
    try:
        secrets = _decrypt_secrets(req.encrypted_secrets)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to decrypt secrets: {e}")

    google_token = secrets.get("google_token", "")
    model_cfg = _AI_MODELS.get(req.model, _AI_MODELS["sonnet"])
    provider = model_cfg["provider"]
    model_id = model_cfg["model"]

    system = _build_system_prompt(
        today=datetime.now().strftime("%Y-%m-%d"),
        portfolio_summary=req.portfolio_summary or "（尚未載入）",
    )

    if provider == "anthropic":
        api_key = secrets.get("claude_api_key")
        if not api_key:
            raise HTTPException(status_code=400, detail="Missing Claude API key — 請在設定中輸入")
        return await _chat_anthropic(api_key, model_id, system, req, google_token)

    elif provider == "openai":
        api_key = secrets.get("openai_api_key")
        if not api_key:
            raise HTTPException(status_code=400, detail="Missing OpenAI API key — 請在設定中輸入")
        return await _chat_openai_compat(api_key, None, model_id, system, req, google_token)

    elif provider == "gemini":
        api_key = secrets.get("gemini_api_key")
        if not api_key:
            raise HTTPException(status_code=400, detail="Missing Gemini API key — 請在設定中輸入")
        return await _chat_openai_compat(api_key, _GEMINI_BASE_URL, model_id, system, req, google_token)

    raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
