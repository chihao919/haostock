from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from lib.notion import get_us_stocks, get_tw_stocks, get_bonds, get_loans, NotionAPIError
from lib.pricing import PriceCache
from lib.calculator import calc_bond_income, calc_net_worth

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


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
