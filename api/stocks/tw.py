from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from lib.notion import get_tw_stocks, NotionAPIError
from lib.pricing import PriceCache
from lib.calculator import calc_stock_pl

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


@app.get("/api/stocks/tw")
async def tw_stocks():
    try:
        accounts_data = await get_tw_stocks()
    except NotionAPIError as e:
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
