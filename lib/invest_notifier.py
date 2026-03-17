"""Investment notifier — formats messages and dispatches to LINE/Trello."""

from datetime import datetime

from lib.line import push_message
from lib.trello import ensure_list, get_cards, create_card, delete_card
from lib.invest_scanner import Action

_MAX_TRELLO_CARDS = 7


def format_daily_report(actions: list[Action]) -> str:
    """Format daily stop-loss + option expiry report for LINE."""
    if not actions:
        return "✅ 今日無警報，持倉一切正常。"

    red = [a for a in actions if a.urgency == "red"]
    yellow = [a for a in actions if a.urgency == "yellow"]
    green = [a for a in actions if a.urgency == "green"]

    lines = [f"📊 每日投資掃描 ({datetime.now().strftime('%Y-%m-%d')})", ""]
    if red:
        lines.append(f"🔴 緊急 ({len(red)})")
        for a in red:
            lines.append(f"  {a.detail}")
        lines.append("")
    if yellow:
        lines.append(f"⚠️ 注意 ({len(yellow)})")
        for a in yellow:
            lines.append(f"  {a.detail}")
        lines.append("")
    if green:
        lines.append(f"✅ 可執行 ({len(green)})")
        for a in green:
            lines.append(f"  {a.detail}")

    return "\n".join(lines)


def format_weekly_cc(tasks: list[Action]) -> str:
    """Format weekly covered call task list for LINE."""
    if not tasks:
        return "📋 本週 CC 清單：所有標的已有 open call，無需操作。"

    lines = [f"📋 本週 CC 寫入清單 ({datetime.now().strftime('%Y-%m-%d')})", ""]
    for t in tasks:
        lines.append(f"  {t.detail}")
    lines.append("")
    lines.append(f"共 {len(tasks)} 檔需要寫入 Covered Call")

    return "\n".join(lines)


def format_completion(ticker: str) -> str:
    """Format trade completion notification."""
    return f"✅ {ticker} 交易完成，Focus Board 卡片已清除。"


async def send_line(user_config: dict, message: str) -> bool:
    """Send LINE notification to user. Returns True on success."""
    token = user_config.get("line_channel_token", "")
    user_id = user_config.get("line_user_id", "")
    if not token or not user_id:
        return False
    return await push_message(token, user_id, message)


def _urgency_to_color(urgency: str) -> str:
    """Map urgency to Trello label color."""
    return {"red": "red", "yellow": "yellow", "green": "blue"}.get(urgency, "blue")


async def sync_trello(user_config: dict, actions: list[Action]) -> dict:
    """Sync actions to Trello Focus Board. Returns summary."""
    api_key = user_config.get("trello_api_key", "")
    token = user_config.get("trello_token", "")
    board_id = user_config.get("trello_board_id", "")
    if not api_key or not token or not board_id:
        return {"status": "skipped", "reason": "no_trello_config"}

    # Ensure list exists
    list_id = user_config.get("trello_list_id", "")
    if not list_id:
        list_id = await ensure_list(api_key, token, board_id, "本週投資")

    # Get existing cards to avoid duplicates
    existing = await get_cards(api_key, token, list_id)
    existing_tickers = set()
    for card in existing:
        name = card.get("name", "").upper()
        for action in actions:
            if action.ticker.upper() in name:
                existing_tickers.add(action.ticker.upper())

    # Enforce max cards limit
    current_count = len(existing)
    created = 0

    for action in actions:
        if action.ticker.upper() in existing_tickers:
            continue
        if current_count + created >= _MAX_TRELLO_CARDS:
            break
        await create_card(
            api_key, token, list_id,
            name=action.detail,
            desc=f"Type: {action.type}\nAccount: {action.account}\nCreated: {datetime.now().isoformat()}",
            label_color=_urgency_to_color(action.urgency),
        )
        created += 1
        existing_tickers.add(action.ticker.upper())

    return {"status": "ok", "created": created, "existing": len(existing), "list_id": list_id}


async def cleanup_completed(
    user_config: dict, card_ids: list[str],
) -> int:
    """Delete completed cards from Trello. Returns count deleted."""
    api_key = user_config.get("trello_api_key", "")
    token = user_config.get("trello_token", "")
    if not api_key or not token:
        return 0
    deleted = 0
    for card_id in card_ids:
        try:
            await delete_card(api_key, token, card_id)
            deleted += 1
        except Exception:
            pass
    return deleted
