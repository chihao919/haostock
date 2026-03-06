from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from lib.notion import get_options, NotionAPIError
from lib.pricing import PriceCache
from lib.calculator import dte, urgency, itm_otm, suggest_action, calc_option_pl

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


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
