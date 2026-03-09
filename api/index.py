"""Single FastAPI app for all Vercel serverless endpoints."""

import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, field_validator
from datetime import datetime

app = FastAPI(title="Portfolio Quotes API", version="2.0.0")

_API_KEY = os.environ.get("FINANCIAL_API_KEY", "")

# Paths that don't require API key
_PUBLIC_PATHS = {"/api/health", "/api/auth", "/api/fivelines/auth", "/", "/fivelines"}


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

# Import lib modules
from lib.notion import (
    get_us_stocks, get_tw_stocks, get_options, get_bonds, get_loans,
    get_trades, create_trade, NotionAPIError,
)
from lib.pricing import PriceCache
from lib.calculator import (
    calc_stock_pl, calc_account_totals, dte, urgency, itm_otm,
    suggest_action, calc_option_pl, calc_bond_income, calc_net_worth,
    calc_trade_summary,
)
from lib.tw_financial import analyze_stock as analyze_tw_stock
from lib.us_financial import analyze_stock as analyze_us_stock
from lib.five_lines import analyze as five_lines_analyze


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
def dashboard():
    html_path = Path(__file__).parent / "templates" / "index.html"
    return html_path.read_text(encoding="utf-8")


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
async def us_stocks():
    try:
        accounts_data = await get_us_stocks()
    except NotionAPIError:
        raise HTTPException(status_code=502, detail="Notion API unavailable")

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
async def tw_stocks():
    try:
        accounts_data = await get_tw_stocks()
    except NotionAPIError:
        raise HTTPException(status_code=502, detail="Notion API unavailable")

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
async def options_positions():
    try:
        options_data = await get_options()
    except NotionAPIError:
        raise HTTPException(status_code=502, detail="Notion API unavailable")

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
async def net_worth():
    try:
        us_data = await get_us_stocks()
        tw_data = await get_tw_stocks()
        bonds = await get_bonds()
        loans = await get_loans()
    except NotionAPIError:
        raise HTTPException(status_code=502, detail="Notion API unavailable")

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


@app.get("/api/trades")
async def list_trades(
    ticker: str | None = None,
    result: str | None = None,
    asset_type: str | None = None,
    limit: int = 50,
):
    try:
        trades = await get_trades(ticker=ticker, result=result, asset_type=asset_type, limit=limit)
    except NotionAPIError:
        raise HTTPException(status_code=502, detail="Notion API unavailable")

    summary = calc_trade_summary(trades)
    return {"trades": trades, "summary": summary, "timestamp": datetime.now().isoformat()}


@app.post("/api/trades", status_code=201)
async def add_trade(trade: TradeCreate):
    try:
        page_id = await create_trade(trade.model_dump())
    except NotionAPIError:
        raise HTTPException(status_code=502, detail="Notion API unavailable")
    return {"id": page_id, "status": "created", "timestamp": datetime.now().isoformat()}


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
_OAUTH_CLIENT_SECRET = "pf-mcp-2026-s3cret-key"
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
