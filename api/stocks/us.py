from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from lib.notion import get_us_stocks, NotionAPIError
from lib.pricing import PriceCache
from lib.calculator import calc_stock_pl, calc_account_totals

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


@app.get("/api/stocks/us")
async def us_stocks():
    try:
        accounts_data = await get_us_stocks()
    except NotionAPIError as e:
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
    return {
        "accounts": result,
        "summary": summary,
        "timestamp": datetime.now().isoformat(),
    }
