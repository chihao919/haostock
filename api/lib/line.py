"""LINE Messaging API — push message to a user."""

import httpx

_LINE_API = "https://api.line.me/v2/bot/message/push"


async def push_message(channel_token: str, user_id: str, message: str) -> bool:
    """Send a push message via LINE Bot. Returns True on success."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {channel_token}",
    }
    body = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}],
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(_LINE_API, json=body, headers=headers)
    return resp.status_code == 200
