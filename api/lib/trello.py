"""Trello REST API client for Focus Board management."""

import httpx

_TRELLO_API = "https://api.trello.com/1"


def _auth_params(api_key: str, token: str) -> dict:
    return {"key": api_key, "token": token}


async def ensure_list(api_key: str, token: str, board_id: str, list_name: str) -> str:
    """Find or create a list on a board. Returns list ID."""
    params = _auth_params(api_key, token)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{_TRELLO_API}/boards/{board_id}/lists", params=params)
        resp.raise_for_status()
        for lst in resp.json():
            if lst["name"] == list_name:
                return lst["id"]
        # Create new list
        resp = await client.post(
            f"{_TRELLO_API}/lists",
            params={**params, "name": list_name, "idBoard": board_id},
        )
        resp.raise_for_status()
        return resp.json()["id"]


async def get_cards(api_key: str, token: str, list_id: str) -> list[dict]:
    """Get all cards in a list."""
    params = _auth_params(api_key, token)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{_TRELLO_API}/lists/{list_id}/cards", params=params)
        resp.raise_for_status()
        return resp.json()


async def create_card(
    api_key: str, token: str, list_id: str,
    name: str, desc: str = "", label_color: str | None = None,
) -> str:
    """Create a card on a list. Returns card ID."""
    params = {
        **_auth_params(api_key, token),
        "idList": list_id,
        "name": name,
        "desc": desc,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{_TRELLO_API}/cards", params=params)
        resp.raise_for_status()
        card = resp.json()
        # Add label if specified
        if label_color:
            await client.post(
                f"{_TRELLO_API}/cards/{card['id']}/labels",
                params={**_auth_params(api_key, token), "color": label_color},
            )
        return card["id"]


async def delete_card(api_key: str, token: str, card_id: str) -> None:
    """Delete a card."""
    params = _auth_params(api_key, token)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.delete(f"{_TRELLO_API}/cards/{card_id}", params=params)
        resp.raise_for_status()
