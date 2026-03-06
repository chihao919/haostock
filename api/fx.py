from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from lib.pricing import PriceCache

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


@app.get("/api/fx")
def fx_rate():
    cache = PriceCache()
    rate = cache.get_fx()
    return {"USDTWD": rate, "timestamp": datetime.now().isoformat()}
