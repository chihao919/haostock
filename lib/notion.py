"""Notion API client for reading portfolio data."""

import os
import httpx

NOTION_API_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _headers():
    api_key = os.environ.get("NOTION_API_KEY", "")
    return {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _get_text(prop):
    """Extract text from a title or rich_text property."""
    items = prop.get("title") or prop.get("rich_text") or []
    return items[0]["plain_text"] if items else ""


def _get_number(prop):
    """Extract number value."""
    return prop.get("number")


def _get_select(prop):
    """Extract select value."""
    sel = prop.get("select")
    return sel["name"] if sel else None


def _get_multi_select(prop):
    """Extract multi_select values as list."""
    return [item["name"] for item in prop.get("multi_select", [])]


def _get_date(prop):
    """Extract date start value."""
    d = prop.get("date")
    return d["start"] if d else None


async def _query_database(database_id: str) -> list[dict]:
    """Query all pages from a Notion database (handles pagination)."""
    pages = []
    payload = {"page_size": 100}
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            resp = await client.post(
                f"{NOTION_API_URL}/databases/{database_id}/query",
                headers=_headers(),
                json=payload,
            )
            if resp.status_code != 200:
                raise NotionAPIError(resp.status_code, resp.text)
            data = resp.json()
            pages.extend(data["results"])
            if not data.get("has_more"):
                break
            payload["start_cursor"] = data["next_cursor"]
    return pages


class NotionAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Notion API error {status_code}: {message}")


async def get_us_stocks() -> dict[str, list[dict]]:
    """Read US stock positions grouped by account."""
    db_id = os.environ.get("NOTION_US_STOCKS_DB", "")
    pages = await _query_database(db_id)
    accounts: dict[str, list[dict]] = {}
    for page in pages:
        props = page["properties"]
        account = _get_select(props["Account"])
        position = {
            "ticker": _get_text(props["Ticker"]),
            "shares": _get_number(props["Shares"]),
            "avg_cost": _get_number(props["Avg Cost"]),
        }
        accounts.setdefault(account, []).append(position)
    return accounts


async def get_tw_stocks() -> dict[str, list[dict]]:
    """Read TW stock positions grouped by account."""
    db_id = os.environ.get("NOTION_TW_STOCKS_DB", "")
    pages = await _query_database(db_id)
    accounts: dict[str, list[dict]] = {}
    for page in pages:
        props = page["properties"]
        account = _get_select(props["Account"])
        position = {
            "ticker": _get_text(props["Ticker"]),
            "name": _get_text(props["Name"]),
            "shares": _get_number(props["Shares"]),
            "avg_cost": _get_number(props["Avg Cost"]),
        }
        accounts.setdefault(account, []).append(position)
    return accounts


async def get_options() -> list[dict]:
    """Read options positions."""
    db_id = os.environ.get("NOTION_OPTIONS_DB", "")
    pages = await _query_database(db_id)
    options = []
    for page in pages:
        props = page["properties"]
        options.append({
            "account": _get_select(props["Account"]),
            "ticker": _get_text(props["Ticker"]),
            "expiry": _get_date(props["Expiry"]),
            "strike": _get_number(props["Strike"]),
            "type": _get_select(props["Type"]),
            "qty": _get_number(props["Qty"]),
            "cost": _get_number(props["Cost"]),
        })
    return options


async def get_bonds() -> list[dict]:
    """Read bond positions."""
    db_id = os.environ.get("NOTION_BONDS_DB", "")
    pages = await _query_database(db_id)
    bonds = []
    for page in pages:
        props = page["properties"]
        bonds.append({
            "name": _get_text(props["Name"]),
            "face": _get_number(props["Face Value"]),
            "coupon": _get_number(props["Coupon Rate"]),
            "maturity": _get_date(props["Maturity"]),
            "cost": _get_number(props["Cost"]),
        })
    return bonds


async def get_loans() -> list[dict]:
    """Read loan data."""
    db_id = os.environ.get("NOTION_LOANS_DB", "")
    pages = await _query_database(db_id)
    loans = []
    for page in pages:
        props = page["properties"]
        loans.append({
            "name": _get_text(props["Name"]),
            "rate": _get_number(props["Rate"]),
            "balance": _get_number(props["Balance"]),
            "monthly": _get_number(props["Monthly Payment"]),
            "periods_done": _get_number(props["Periods Done"]),
            "total_periods": _get_number(props["Total Periods"]),
        })
    return loans


async def get_trades(
    ticker: str | None = None,
    result: str | None = None,
    asset_type: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Read trade journal entries with optional filters."""
    db_id = os.environ.get("NOTION_TRADES_DB", "")
    pages = await _query_database(db_id)
    trades = []
    for page in pages:
        props = page["properties"]
        trade = {
            "id": page["id"],
            "date": _get_date(props["Date"]),
            "ticker": _get_text(props["Ticker"]),
            "action": _get_select(props["Action"]),
            "asset_type": _get_select(props["Asset Type"]),
            "qty": _get_number(props["Qty"]),
            "price": _get_number(props["Price"]),
            "total_amount": _get_number(props["Total Amount"]),
            "pl": _get_number(props["P&L"]),
            "result": _get_select(props["Result"]),
            "reason": _get_text(props["Reason"]),
            "lesson": _get_text(props["Lesson"]),
            "tags": _get_multi_select(props["Tags"]),
            "account": _get_select(props["Account"]),
        }
        if ticker and trade["ticker"] != ticker.upper():
            continue
        if result and trade["result"] != result:
            continue
        if asset_type and trade["asset_type"] != asset_type:
            continue
        trades.append(trade)

    trades.sort(key=lambda t: t["date"] or "", reverse=True)
    return trades[:limit]


async def create_trade(trade: dict) -> str:
    """Create a new trade journal entry in Notion. Returns the page ID."""
    db_id = os.environ.get("NOTION_TRADES_DB", "")
    properties = {
        "Ticker": {"title": [{"text": {"content": trade["ticker"]}}]},
        "Date": {"date": {"start": trade["date"]}},
        "Action": {"select": {"name": trade["action"]}},
        "Asset Type": {"select": {"name": trade["asset_type"]}},
        "Qty": {"number": trade["qty"]},
        "Price": {"number": trade["price"]},
        "Total Amount": {"number": trade["total_amount"]},
        "Reason": {"rich_text": [{"text": {"content": trade.get("reason", "")}}]},
        "Account": {"select": {"name": trade["account"]}},
    }
    if trade.get("pl") is not None:
        properties["P&L"] = {"number": trade["pl"]}
    if trade.get("result"):
        properties["Result"] = {"select": {"name": trade["result"]}}
    if trade.get("lesson"):
        properties["Lesson"] = {"rich_text": [{"text": {"content": trade["lesson"]}}]}
    if trade.get("tags"):
        properties["Tags"] = {"multi_select": [{"name": t} for t in trade["tags"]]}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{NOTION_API_URL}/pages",
            headers=_headers(),
            json={"parent": {"database_id": db_id}, "properties": properties},
        )
        if resp.status_code not in (200, 201):
            raise NotionAPIError(resp.status_code, resp.text)
        return resp.json()["id"]
