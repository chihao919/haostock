from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from datetime import datetime
from lib.notion import get_trades, create_trade, NotionAPIError
from lib.calculator import calc_trade_summary

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])

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
    return {
        "trades": trades,
        "summary": summary,
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/trades", status_code=201)
async def add_trade(trade: TradeCreate):
    try:
        page_id = await create_trade(trade.model_dump())
    except NotionAPIError as e:
        raise HTTPException(status_code=502, detail="Notion API unavailable")

    return {
        "id": page_id,
        "status": "created",
        "timestamp": datetime.now().isoformat(),
    }
