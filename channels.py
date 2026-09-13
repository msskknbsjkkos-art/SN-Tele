"""Feature 5 — Channel add/remove/toggle."""
from __future__ import annotations

from typing import Any

from database import (
    add_channel,
    get_channel,
    is_db_admin,
    list_channels,
    remove_channel,
    set_channel_active,
)
from keyboards import channel_actions, channels_menu
from telegram_api import edit_message, get_chat, send_message


def _is_admin(user_id: int) -> bool:
    return is_db_admin(user_id)


def show_channels(chat_id: int, message_id: int | None, user_id: int) -> None:
    if not _is_admin(user_id):
        send_message(chat_id, "❌ Admin only.")
        return
    channels = list_channels()
    text = f"<b>📡 Channels ({len(channels)})</b>\n\n" \
           "Manage your channels below."
    markup = channels_menu(channels)
    if message_id:
        edit_message(chat_id, message_id, text, reply_markup=markup)
    else:
        send_message(chat_id, text, reply_markup=markup)


def handle_channel_callback(callback: dict[str, Any]) -> bool:
    data = callback.get("data", "")
    if not data.startswith("channel:"):
        return False

    message = callback.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    message_id = message.get("message_id")
    user_id = (callback.get("from") or {}).get("id")
    if not chat_id or not _is_admin(user_id):
        return True

    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "list":
        show_channels(chat_id, message_id, user_id)
    elif action == "view" and len(parts) >= 3:
        target = int(parts[2])
        ch = get_channel(target)
        if not ch:
            edit_message(chat_id, message_id, "❌ Channel not found.")
            return True
        text = (
            f"<b>📡 {ch['channel_name']}</b>\n\n"
            f"ID: <code>{ch['channel_id']}</code>\n"
            f"Username: {ch.get('channel_username') or '—'}\n"
            f"Status: {'🟢 Active' if ch['is_active'] else '🔴 Inactive'}"
        )
        edit_message(chat_id, message_id, text,
                     reply_markup=channel_actions(target, bool(ch["is_active"])))
    elif action == "toggle" and len(parts) >= 3:
        target = int(parts[2])
        ch = get_channel(target)
        if ch:
            set_channel_active(target, not ch["is_active"])
        show_channels(chat_id, message_id, user_id)
    elif action == "remove" and len(parts) >= 3:
        remove_channel(int(parts[2]))
        show_channels(chat_id, message_id, user_id)
    elif action == "add":
        edit_message(
            chat_id, message_id,
            "<b>➕ Add Channel</b>\n\n"
            "Send the channel ID or @username now.\n"
            "Example: <code>-1001234567890</code> or <code>@mychannel</code>\n\n"
            "⚠️ Bot must be an admin of that channel.",
            reply_markup=None,
        )
        # Actual add handled in message handler (state-driven)
    return True