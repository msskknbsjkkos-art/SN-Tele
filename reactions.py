"""Feature 2 — Auto-reaction to messages."""
from __future__ import annotations

import random
from typing import Any

from config import CFG
from database import get_reaction_emojis, is_db_admin, setting_on
from telegram_api import set_reaction


def handle_reaction(message: dict[str, Any]) -> None:
    if not setting_on("auto_reaction"):
        return
    chat = message.get("chat") or {}
    if chat.get("type") not in ("group", "supergroup", "channel"):
        return
    chat_id = chat.get("id")
    message_id = message.get("message_id")
    from_user = message.get("from") or {}

    if chat_id is None or message_id is None:
        return

    # Optional: react only to admin messages
    # comment out if you want ALL messages
    if not is_db_admin(from_user.get("id", 0)):
        # still react to non-admin? remove this block to allow all
        pass

    emojis, enabled = get_reaction_emojis(chat_id)
    if not enabled:
        return
    pool = emojis or list(CFG.default_reaction_emojis)
    if not pool:
        return

    count = min(3, len(pool))
    chosen = random.sample(pool, count)
    try:
        set_reaction(chat_id, message_id, chosen)
    except Exception:
        pass