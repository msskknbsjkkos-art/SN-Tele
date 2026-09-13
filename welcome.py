"""Feature 1 — Welcome system with auto-delete."""
from __future__ import annotations

from typing import Any

from config import CFG
from database import (
    get_welcome_template,
    is_db_admin,
    setting_on,
)
from telegram_api import auto_delete_later, send_message


def handle_chat_member(update: dict[str, Any]) -> None:
    if not setting_on("welcome_system"):
        return
    cm = update.get("chat_member") or {}
    chat = cm.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return

    old = (cm.get("old_chat_member") or {}).get("status")
    new = (cm.get("new_chat_member") or {}).get("status")
    user = (cm.get("new_chat_member") or {}).get("user") or {}
    user_id = user.get("id")
    name = user.get("first_name") or "বন্ধু"
    username = user.get("username")

    # Only brand-new joins
    if not (new == "member" and old in ("left", "kicked")):
        return

    template, delete_seconds, enabled = get_welcome_template(chat_id)
    if not enabled:
        return

    display = f"@{username}" if username else name
    text = template.format(name=display, username=username or name)

    try:
        sent = send_message(chat_id, text)
        if delete_seconds > 0 and setting_on("auto_delete"):
            auto_delete_later(chat_id, sent["message_id"], delete_seconds)
    except Exception:
        pass