"""
Portfolio Quotes API Server
Endpoints:
  GET /stocks/us          - All US stock positions with P&L
  GET /stocks/tw          - All Taiwan stock positions with P&L
  GET /options            - All options positions with P&L + action
  GET /quote/{ticker}     - Single stock quote
  GET /networth           - Full net worth summary
  GET /fx                 - USD/TWD exchange rate
  GET /health             - Health check
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import date, datetime
import yfinance as yf

app = FastAPI(title="Portfolio Quotes API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

TODAY = date.today()

# ============================================================
# PORTFOLIO DATA
# ============================================================

US_STOCKS = {
    "Firstrade": [
        {"ticker": "CCJ",   "shares": 100.15563, "avg_cost": 92.34},
        {"ticker": "GOOG",  "shares": 200,       "avg_cost": 307.61},
        {"ticker": "MU",    "shares": 100,       "avg_cost": 370.90},
        {"ticker": "POOL",  "shares": 10,        "avg_cost": 386.07},
        {"ticker": "QQQ",   "shares": 20,        "avg_cost": 627.47},
        {"ticker": "SHOP",  "shares": 100,       "avg_cost": 146.00},
        {"ticker": "VOO",   "shares": 5,         "avg_cost": 630.35},
    ],
    "TW_Brokerage": [
        {"ticker": "CCJ",   "shares": 600,  "avg_cost": 88.55},
        {"ticker": "GOOG",  "shares": 100,  "avg_cost": 241.65},
        {"ticker": "GRAB",  "shares": 100,  "avg_cost": 6.14},
        {"ticker": "HIMS",  "shares": 100,  "avg_cost": 49.20},
        {"ticker": "TSM",   "shares": 100,  "avg_cost": 297.35},
    ],
    "IBKR": [
        {"ticker": "AGGU",  "shares": 172.4102, "avg_cost": 5.81},
        {"ticker": "AMD",   "shares": 21.0223,  "avg_cost": 227.26},
        {"ticker": "BND",   "shares": 13.4831,  "avg_cost": 74.22},
        {"ticker": "BRK-B", "shares": 9.0328,   "avg_cost": 498.30},
        {"ticker": "EQQS",  "shares": 25.0737,  "avg_cost": 79.83},
        {"ticker": "IBKR",  "shares": 4.1016,   "avg_cost": 68.51},
        {"ticker": "MSFT",  "shares": 5.1177,   "avg_cost": 488.82},
        {"ticker": "NVDA",  "shares": 26.9983,  "avg_cost": 185.26},
        {"ticker": "QQQ",   "shares": 3.2014,   "avg_cost": 624.93},
        {"ticker": "VOO",   "shares": 3.1889,   "avg_cost": 627.38},
        {"ticker": "VTI",   "shares": 14.893,   "avg_cost": 335.77},
    ],
    "Cathay_US": [
        {"ticker": "AMD",   "shares": 45.7954,  "avg_cost": 137.18},
        {"ticker": "BND",   "shares": 90.32766, "avg_cost": 73.09},
        {"ticker": "BRK-B", "shares": 41.49714, "avg_cost": 457.76},
        {"ticker": "MSFT",  "shares": 22.55277, "avg_cost": 435.08},
        {"ticker": "NVDA",  "shares": 75.26315, "avg_cost": 119.36},
        {"ticker": "QQQ",   "shares": 3.36585,  "avg_cost": 594.26},
        {"ticker": "TSLA",  "shares": 2.44403,  "avg_cost": 409.20},
        {"ticker": "VOO",   "shares": 17.56014, "avg_cost": 546.76},
        {"ticker": "VTI",   "shares": 15.27099, "avg_cost": 327.43},
    ],
}

TW_STOCKS = {
    "Yongfeng_A": [
        {"ticker": "0050.TW",   "name": "元大台灣50", "shares": 24782, "avg_cost": 46.35},
        {"ticker": "1301.TW",   "name": "台塑",       "shares": 1000,  "avg_cost": 99.76},
        {"ticker": "2454.TW",   "name": "聯發科",     "shares": 1000,  "avg_cost": 794.53},
        {"ticker": "8926.TW",   "name": "台汽電",     "shares": 3610,  "avg_cost": 27.54},
    ],
    "Yongfeng_B": [
        {"ticker": "0050.TW",   "name": "元大台灣50", "shares": 16000, "avg_cost": 43.82},
        {"ticker": "1301.TW",   "name": "台塑",       "shares": 4000,  "avg_cost": 77.41},
        {"ticker": "1303.TW",   "name": "南亞",       "shares": 7161,  "avg_cost": 66.02},
        {"ticker": "2002.TW",   "name": "中鋼",       "shares": 4000,  "avg_cost": 35.28},
        {"ticker": "2012.TW",   "name": "春雨",       "shares": 2000,  "avg_cost": 26.24},
        {"ticker": "2317.TW",   "name": "鴻海",       "shares": 8406,  "avg_cost": 201.68},
        {"ticker": "2330.TW",   "name": "台積電",     "shares": 5000,  "avg_cost": 854.56},
        {"ticker": "2344.TW",   "name": "華邦電",     "shares": 1000,  "avg_cost": 90.93},
        {"ticker": "2606.TW",   "name": "裕民",       "shares": 3000,  "avg_cost": 59.89},
        {"ticker": "2612.TW",   "name": "中航",       "shares": 3000,  "avg_cost": 58.08},
        {"ticker": "2887.TW",   "name": "台新新光金", "shares": 3360,  "avg_cost": 17.50},
        {"ticker": "2890.TW",   "name": "永豐金",     "shares": 1005,  "avg_cost": 24.91},
        {"ticker": "3033.TW",   "name": "威健",       "shares": 6000,  "avg_cost": 33.69},
        {"ticker": "5009.TW",   "name": "榮剛",       "shares": 2000,  "avg_cost": 37.55},
        {"ticker": "5222.TW",   "name": "全訊",       "shares": 1000,  "avg_cost": 147.71},
        {"ticker": "5903.TW",   "name": "全家",       "shares": 2000,  "avg_cost": 228.87},
        {"ticker": "6023.TW",   "name": "元大期",     "shares": 3082,  "avg_cost": 77.63},
        {"ticker": "6770.TW",   "name": "力積電",     "shares": 1000,  "avg_cost": 49.52},
        {"ticker": "8499.TW",   "name": "鼎炫-KY",    "shares": 73,    "avg_cost": 316.93},
    ],
    "Cathay_TW": [
        {"ticker": "0050.TW",   "name": "元大台灣50", "shares": 4075, "avg_cost": 61.26},
        {"ticker": "006208.TW", "name": "富邦台50",   "shares": 2898, "avg_cost": 93.99},
        {"ticker": "2330.TW",   "name": "台積電",     "shares": 2023, "avg_cost": 953.16},
    ],
}

OPTIONS = [
    {"account": "Firstrade",    "ticker": "CCJ",  "expiry": "2026-03-13", "strike": 110, "type": "put",  "qty": -1, "cost": 479.98},
    {"account": "Firstrade",    "ticker": "CCJ",  "expiry": "2026-03-21", "strike": 140, "type": "call", "qty": -1, "cost": 225.98},
    {"account": "Firstrade",    "ticker": "CCJ",  "expiry": "2026-04-17", "strike": 115, "type": "put",  "qty": -1, "cost": 899.98},
    {"account": "Firstrade",    "ticker": "GOOG", "expiry": "2026-03-21", "strike": 330, "type": "call", "qty": -1, "cost": 244.98},
    {"account": "Firstrade",    "ticker": "MU",   "expiry": "2026-04-02", "strike": 440, "type": "call", "qty": -1, "cost": 1800.00},
    {"account": "Firstrade",    "ticker": "ONDS", "expiry": "2026-04-02", "strike": 8,   "type": "put",  "qty": -1, "cost": 50.00},
    {"account": "Firstrade",    "ticker": "SHOP", "expiry": "2026-03-21", "strike": 150, "type": "call", "qty": -1, "cost": 116.98},
    {"account": "TW_Brokerage", "ticker": "AMZN", "expiry": "2026-04-02", "strike": 190, "type": "put",  "qty": -1, "cost": 229.98},
    {"account": "TW_Brokerage", "ticker": "CCJ",  "expiry": "2026-03-27", "strike": 145, "type": "call", "qty": -2, "cost": 279.95},
    {"account": "TW_Brokerage", "ticker": "HIMS", "expiry": "2026-03-21", "strike": 20,  "type": "call", "qty": -1, "cost": 58.98},
    {"account": "TW_Brokerage", "ticker": "MU",   "expiry": "2026-03-21", "strike": 310, "type": "put",  "qty": -1, "cost": 429.98},
    {"account": "TW_Brokerage", "ticker": "TSM",  "expiry": "2026-03-21", "strike": 400, "type": "call", "qty": -1, "cost": 699.98},
]

BONDS = [
    {"name": "UBS 5.699%",    "face": 280000,  "coupon": 0.05699, "maturity": "2035-02-08", "cost": 299040},
    {"name": "BAC 5.468%",    "face": 480000,  "coupon": 0.05468, "maturity": "2035-01-23", "cost": 503400},
    {"name": "SOCGEN 6.221%", "face": 500000,  "coupon": 0.06221, "maturity": "2033-06-15", "cost": 523900},
    {"name": "BAC 5.015%",    "face": 450000,  "coupon": 0.05015, "maturity": "2033-07-22", "cost": 449100},
    {"name": "BAC 5.288%",    "face": 250000,  "coupon": 0.05288, "maturity": "2034-04-25", "cost": 252250},
]

LOANS_TWD = [
    {"name": "房屋貸款", "rate": 0.022, "balance": 19600000, "monthly": 33078, "periods_done": 37,  "total_periods": 360},
    {"name": "其他貸款", "rate": 0.022, "balance": 39450000, "monthly": 66579, "periods_done": 22,  "total_periods": 84},
]

# ============================================================
# HELPERS
# ============================================================

def get_price(ticker: str):
    try:
        t = yf.Ticker(ticker)
        return round(t.fast_info.last_price, 4)
    except:
        return None

def get_fx():
    p = get_price("USDTWD=X")
    return p if p else 32.0

def dte(expiry_str: str):
    exp = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    return (exp - TODAY).days

def suggest_action(days, pl_pct, itm_otm):
    if days <= 0:
        return "EXPIRED"
    if days <= 7 and "OTM" in itm_otm:
        return "Let expire"
    if days <= 7 and "ITM" in itm_otm:
        return "Close/Roll URGENT"
    if pl_pct >= 75:
        return "Close (75%+ profit)"
    if days <= 21:
        return "Monitor"
    return "Hold"

# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/fx")
def fx_rate():
    rate = get_fx()
    return {"USDTWD": rate, "timestamp": datetime.now().isoformat()}


@app.get("/quote/{ticker}")
def single_quote(ticker: str):
    price = get_price(ticker.upper())
    if not price:
        raise HTTPException(status_code=404, detail=f"Could not fetch price for {ticker}")
    return {"ticker": ticker.upper(), "price": price, "timestamp": datetime.now().isoformat()}


@app.get("/stocks/us")
def us_stocks():
    result = {}
    price_cache = {}
    grand_value = 0
    grand_cost = 0

    for account, positions in US_STOCKS.items():
        acct_data = []
        acct_value = 0
        acct_cost = 0

        for pos in positions:
            ticker = pos["ticker"]
            if ticker not in price_cache:
                price_cache[ticker] = get_price(ticker)
            price = price_cache[ticker]

            row = {
                "ticker": ticker,
                "shares": pos["shares"],
                "avg_cost": pos["avg_cost"],
                "current_price": price,
            }

            if price:
                mkt_val = round(price * pos["shares"], 2)
                cost_basis = round(pos["avg_cost"] * pos["shares"], 2)
                pl = round(mkt_val - cost_basis, 2)
                pl_pct = round((pl / cost_basis) * 100, 2) if cost_basis else 0
                row.update({
                    "market_value": mkt_val,
                    "cost_basis": cost_basis,
                    "unrealized_pl": pl,
                    "pl_pct": pl_pct,
                })
                acct_value += mkt_val
                acct_cost += cost_basis

            acct_data.append(row)

        acct_pl = round(acct_value - acct_cost, 2)
        grand_value += acct_value
        grand_cost += acct_cost

        result[account] = {
            "positions": acct_data,
            "total_market_value": round(acct_value, 2),
            "total_cost_basis": round(acct_cost, 2),
            "total_pl": acct_pl,
            "total_pl_pct": round((acct_pl / acct_cost * 100) if acct_cost else 0, 2),
        }

    grand_pl = round(grand_value - grand_cost, 2)
    return {
        "accounts": result,
        "summary": {
            "total_market_value": round(grand_value, 2),
            "total_cost_basis": round(grand_cost, 2),
            "total_pl": grand_pl,
            "total_pl_pct": round((grand_pl / grand_cost * 100) if grand_cost else 0, 2),
        },
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/stocks/tw")
def tw_stocks():
    fx = get_fx()
    result = {}
    price_cache = {}
    grand_twd = 0
    grand_cost_twd = 0

    for account, positions in TW_STOCKS.items():
        acct_data = []
        acct_value_twd = 0
        acct_cost_twd = 0

        for pos in positions:
            ticker = pos["ticker"]
            if ticker not in price_cache:
                price_cache[ticker] = get_price(ticker)
            price = price_cache[ticker]

            row = {
                "ticker": ticker,
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

            acct_data.append(row)

        acct_pl_twd = round(acct_value_twd - acct_cost_twd, 0)
        grand_twd += acct_value_twd
        grand_cost_twd += acct_cost_twd

        result[account] = {
            "positions": acct_data,
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


@app.get("/options")
def options_positions():
    result = []
    price_cache = {}

    for opt in OPTIONS:
        ticker = opt["ticker"]
        if ticker not in price_cache:
            price_cache[ticker] = get_price(ticker)
        underlying = price_cache[ticker]

        days = dte(opt["expiry"])
        urgency = "red" if days <= 7 else ("yellow" if days <= 21 else "green")

        itm_otm = "unknown"
        if underlying:
            if opt["type"] == "put":
                diff = underlying - opt["strike"]
                itm_otm = f"OTM ${diff:.1f}" if diff > 0 else f"ITM ${abs(diff):.1f}"
            else:
                diff = opt["strike"] - underlying
                itm_otm = f"OTM ${diff:.1f}" if diff > 0 else f"ITM ${abs(diff):.1f}"

        curr_val = None
        try:
            t = yf.Ticker(ticker)
            exp_dates = t.options
            closest = min(exp_dates, key=lambda d: abs(
                (datetime.strptime(d, "%Y-%m-%d").date() -
                 datetime.strptime(opt["expiry"], "%Y-%m-%d").date()).days
            ))
            chain = t.option_chain(closest)
            df = chain.puts if opt["type"] == "put" else chain.calls
            row = df[df["strike"] == opt["strike"]]
            if not row.empty:
                mid = (row["bid"].values[0] + row["ask"].values[0]) / 2
                curr_val = round(mid * 100 * abs(opt["qty"]), 2)
        except:
            pass

        pl = round(opt["cost"] - curr_val, 2) if curr_val is not None else None
        pl_pct = round((pl / opt["cost"]) * 100, 1) if (pl is not None and opt["cost"]) else None
        action = suggest_action(days, pl_pct or 0, itm_otm) if pl_pct is not None else "Check manually"

        result.append({
            "account": opt["account"],
            "ticker": ticker,
            "expiry": opt["expiry"],
            "strike": opt["strike"],
            "type": opt["type"],
            "qty": opt["qty"],
            "underlying_price": underlying,
            "itm_otm": itm_otm,
            "dte": days,
            "urgency": urgency,
            "cost_basis": opt["cost"],
            "current_value": curr_val,
            "unrealized_pl": pl,
            "pl_pct": pl_pct,
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


@app.get("/networth")
def net_worth():
    fx = get_fx()
    price_cache = {}

    def get_cached(ticker):
        if ticker not in price_cache:
            price_cache[ticker] = get_price(ticker)
        return price_cache[ticker]

    us_value = sum(
        (get_cached(p["ticker"]) or 0) * p["shares"]
        for acct in US_STOCKS.values() for p in acct
    )
    tw_value_twd = sum(
        (get_cached(p["ticker"]) or 0) * p["shares"]
        for acct in TW_STOCKS.values() for p in acct
    )
    tw_value_usd = tw_value_twd / fx

    bonds_cost = sum(b["cost"] for b in BONDS)
    bonds_annual_interest_gross = sum(b["face"] * b["coupon"] for b in BONDS)
    bonds_annual_interest_net = round(bonds_annual_interest_gross * 0.70, 2)

    loans_twd = sum(l["balance"] for l in LOANS_TWD)
    loans_usd = loans_twd / fx
    monthly_payments_twd = sum(l["monthly"] for l in LOANS_TWD)

    total_assets = us_value + tw_value_usd + bonds_cost
    net_worth_usd = total_assets - loans_usd

    return {
        "usdtwd_rate": fx,
        "assets": {
            "us_stocks_usd": round(us_value, 2),
            "tw_stocks_twd": round(tw_value_twd, 2),
            "tw_stocks_usd": round(tw_value_usd, 2),
            "bonds_cost_usd": bonds_cost,
            "total_assets_usd": round(total_assets, 2),
        },
        "liabilities": {
            "total_loans_twd": loans_twd,
            "total_loans_usd": round(loans_usd, 2),
            "monthly_payments_twd": monthly_payments_twd,
        },
        "income": {
            "bonds_annual_gross_usd": round(bonds_annual_interest_gross, 2),
            "bonds_annual_net_usd": bonds_annual_interest_net,
            "bonds_monthly_net_usd": round(bonds_annual_interest_net / 12, 2),
            "withholding_tax_rate": "30%",
        },
        "net_worth_usd": round(net_worth_usd, 2),
        "net_worth_twd": round(net_worth_usd * fx, 0),
        "timestamp": datetime.now().isoformat(),
    }
