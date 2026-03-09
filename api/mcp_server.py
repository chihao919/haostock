"""Remote MCP Server — Streamable HTTP transport (spec 2025-03-26).

Implements the MCP protocol over HTTP without the mcp SDK.
Single endpoint at /mcp supporting POST, GET, DELETE.
"""

import json
import uuid
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

router = APIRouter()

API_URL = "https://stock.cwithb.com"

# Simple in-memory session store (resets on cold start, which is fine for serverless)
_sessions: set[str] = set()

TOOLS = [
    {
        "name": "get_us_stocks",
        "description": "Query all US stock positions with P&L, grouped by account (Firstrade, TW_Brokerage, IBKR, Cathay_US).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_tw_stocks",
        "description": "Query all Taiwan stock positions with P&L in TWD/USD, grouped by account.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_options",
        "description": "Query all options positions with P&L, DTE, urgency, and suggested actions.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_quote",
        "description": "Get a real-time quote for a single stock ticker (e.g. NVDA, 2330.TW).",
        "inputSchema": {
            "type": "object",
            "properties": {"ticker": {"type": "string", "description": "Stock ticker"}},
            "required": ["ticker"],
        },
    },
    {
        "name": "get_networth",
        "description": "Query full net worth overview including assets, liabilities, and bond income.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_fx_rate",
        "description": "Get current USD/TWD exchange rate.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_trades",
        "description": "Query trade history. Optional filters: ticker, result (Win/Loss/Breakeven), asset_type (Stock/Option).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "result": {"type": "string"},
                "asset_type": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
    },
    {
        "name": "add_trade",
        "description": "Add a new trade record. action: Buy/Sell/Open/Close/Roll. asset_type: Stock/Option.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {"type": "string"},
                "ticker": {"type": "string"},
                "action": {"type": "string"},
                "asset_type": {"type": "string"},
                "qty": {"type": "number"},
                "price": {"type": "number"},
                "total_amount": {"type": "number"},
                "reason": {"type": "string"},
                "account": {"type": "string"},
                "pl": {"type": "number"},
                "result": {"type": "string"},
                "lesson": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["date", "ticker", "action", "asset_type", "qty", "price", "total_amount", "reason", "account"],
        },
    },
]

TOOL_MAP = {
    "get_us_stocks": "/api/stocks/us",
    "get_tw_stocks": "/api/stocks/tw",
    "get_options": "/api/options",
    "get_networth": "/api/networth",
    "get_fx_rate": "/api/fx",
}


async def call_tool(name: str, arguments: dict) -> str:
    async with httpx.AsyncClient(timeout=15) as client:
        if name in TOOL_MAP:
            resp = await client.get(f"{API_URL}{TOOL_MAP[name]}")
            resp.raise_for_status()
            return json.dumps(resp.json(), indent=2)

        if name == "get_quote":
            ticker = arguments.get("ticker", "")
            resp = await client.get(f"{API_URL}/api/quote/{ticker}")
            resp.raise_for_status()
            return json.dumps(resp.json(), indent=2)

        if name == "get_trades":
            params = {k: v for k, v in arguments.items() if v}
            resp = await client.get(f"{API_URL}/api/trades", params=params)
            resp.raise_for_status()
            return json.dumps(resp.json(), indent=2)

        if name == "add_trade":
            resp = await client.post(f"{API_URL}/api/trades", json=arguments)
            resp.raise_for_status()
            return json.dumps(resp.json(), indent=2)

    return json.dumps({"error": f"Unknown tool: {name}"})


def jsonrpc_result(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def jsonrpc_error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def is_notification(msg: dict) -> bool:
    return "method" in msg and "id" not in msg


def is_response(msg: dict) -> bool:
    return ("result" in msg or "error" in msg) and "method" not in msg


@router.post("/mcp")
async def mcp_post(request: Request):
    body = await request.json()

    # Handle batched messages
    messages = body if isinstance(body, list) else [body]

    # If all messages are notifications or responses, return 202
    if all(is_notification(m) or is_response(m) for m in messages):
        return Response(status_code=202)

    # Process the first request (simple non-batched for now)
    msg = body if not isinstance(body, list) else body[0]
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params", {})

    # Initialize — assign session
    if method == "initialize":
        session_id = str(uuid.uuid4())
        _sessions.add(session_id)
        result = jsonrpc_result(req_id, {
            "protocolVersion": "2025-03-26",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "portfolio", "version": "2.0.0"},
        })
        return JSONResponse(
            content=result,
            media_type="application/json",
            headers={"Mcp-Session-Id": session_id},
        )

    # tools/list
    if method == "tools/list":
        return JSONResponse(
            content=jsonrpc_result(req_id, {"tools": TOOLS}),
            media_type="application/json",
        )

    # tools/call
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        try:
            result_text = await call_tool(name, arguments)
            return JSONResponse(
                content=jsonrpc_result(req_id, {
                    "content": [{"type": "text", "text": result_text}],
                }),
                media_type="application/json",
            )
        except Exception as e:
            return JSONResponse(
                content=jsonrpc_result(req_id, {
                    "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                    "isError": True,
                }),
                media_type="application/json",
            )

    # ping
    if method == "ping":
        return JSONResponse(
            content=jsonrpc_result(req_id, {}),
            media_type="application/json",
        )

    # Unknown method
    return JSONResponse(
        content=jsonrpc_error(req_id, -32601, f"Method not found: {method}"),
        media_type="application/json",
        status_code=400,
    )


@router.get("/mcp")
async def mcp_get():
    """Server does not offer SSE stream via GET."""
    return Response(status_code=405)


@router.delete("/mcp")
async def mcp_delete(request: Request):
    """Client terminates session."""
    session_id = request.headers.get("mcp-session-id")
    if session_id:
        _sessions.discard(session_id)
    return Response(status_code=200)
