"""Single FastAPI app for all Vercel serverless endpoints."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from datetime import datetime

app = FastAPI(title="Portfolio Quotes API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
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
