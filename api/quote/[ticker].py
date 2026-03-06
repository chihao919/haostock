from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from lib.pricing import PriceCache

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


@app.get("/api/quote/{ticker}")
def single_quote(ticker: str):
    cache = PriceCache()
    price = cache.get_price(ticker.upper())
    if not price:
        raise HTTPException(status_code=404, detail=f"Could not fetch price for {ticker}")
    return {"ticker": ticker.upper(), "price": price, "timestamp": datetime.now().isoformat()}
