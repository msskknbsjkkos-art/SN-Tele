"""Feature 6 + 7 + 8 + 9 — Post to channels with preview."""
from __future__ import annotations

import json
import threading
from typing import Any

from database import (
    is_db_admin,
    list_channels,
    log_post,
)
from keyboards import (
    post_channels_select,
    post_edit_menu,
    post_preview_menu,
)
from telegram_api import (
    edit_message,
    send_document,
    send_message,
    send_photo,
    send_video,
)

# In-memory per-admin post draft
POST_DRAFTS: dict[int, dict[str, Any]] = {}
POST_LOCK = threading.RLock()


def _draft(user_id: int) -> dict[str, Any]:
    with POST_LOCK:
        if user_id not in POST_DRAFTS:
            POST_DRAFTS[user_id] = {
                "text": "",
                "media_type": None,     # photo / video / document
                "media_file_id": None,
                "media_caption": "",
                "buttons": [],          # list[list[{"text":..., "url":...}]]
                "selected_channels": set(),
                "step": "channels",
            }
        return POST_DRAFTS[user_id]


def _clear(user_id: int) -> None:
    with POST_LOCK:
        POST_DRAFTS.pop(user_id, None)


def start_post(chat_id: int, user_id: int) -> None:
    if not is_db_admin(user_id):
        send_message(chat_id, "❌ Admin only.")
        return
    channels = [c for c in list_channels(active_only=True)]
    if not channels:
        send_message(chat_id, "❌ No active channels. Add one first.")
        return
    d = _draft(user_id)
    d.clear()
    d.update({
        "text": "", "media_type": None, "media_file_id": None,
        "media_caption": "", "buttons": [],
        "selected_channels": set(), "step": "channels",
    })
    text = "<b>📢 New Post</b>\n\nSelect channels to publish:"
    send_message(chat_id, text, reply_markup=post_channels_select(channels, set()))


def handle_post_callback(callback: dict[str, Any]) -> bool:
    data = callback.get("data", "")
    if not data.startswith("post:"):
        return False

    message = callback.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    message_id = message.get("message_id")
    user_id = (callback.get("from") or {}).get("id")
    if not chat_id or not _is_admin(user_id):
        return True

    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    d = _draft(user_id)

    if action == "start":
        start_post(chat_id, user_id)
    elif action == "toggle" and len(parts) >= 3:
        cid = int(parts[2])
        if cid in d["selected_channels"]:
            d["selected_channels"].discard(cid)
        else:
            d["selected_channels"].add(cid)
        channels = list_channels(active_only=True)
        edit_message(chat_id, message_id,
                     "<b>📢 New Post</b>\n\nSelect channels:",
                     reply_markup=post_channels_select(channels, d["selected_channels"]))
    elif action == "compose":
        if not d["selected_channels"]:
            edit_message(chat_id, message_id, "⚠️ Select at least one channel.")
            return True
        d["step"] = "compose"
        edit_message(
            chat_id, message_id,
            "<b>✍️ Compose Post</b>\n\n"
            "Send text, photo, video, or document.\n"
            "Captions supported.\n\n"
            "When done, press 👁 Preview.",
            reply_markup=post_edit_menu(),
        )
    elif action == "addbutton":
        d["step"] = "button_text"
        edit_message(
            chat_id, message_id,
            "<b>🔘 Add Button</b>\n\n"
            "Send button in this format:\n"
            "<code>Button Name | https://url.com</code>\n\n"
            "Multiple buttons: separate with new lines.",
            reply_markup=None,
        )
    elif action == "preview":
        _show_preview(chat_id, message_id, user_id, d)
    elif action == "publish":
        _show_preview(chat_id, message_id, user_id, d)
    elif action == "confirm":
        _publish(chat_id, message_id, user_id, d)
    elif action == "cancel":
        _clear(user_id)
        edit_message(chat_id, message_id, "❌ Post cancelled.")
    return True


def _is_admin(user_id: int) -> bool:
    return is_db_admin(user_id)


def _draft_markup(d: dict[str, Any]) -> str:
    rows = []
    for row in d["buttons"]:
        rows.append([{"text": b["text"], "url": b["url"]} for b in row])
    return json.dumps({"inline_keyboard": rows}) if rows else ""


def _show_preview(chat_id: int, message_id: int, user_id: int,
                 d: dict[str, Any]) -> None:
    if not d["text"] and not d["media_file_id"]:
        edit_message(chat_id, message_id, "⚠️ Nothing to preview yet.")
        return
    text = d["text"] or d["media_caption"] or "(no text)"
    info = (
        f"<b>👁 Preview</b>\n\n"
        f"<b>Channels:</b> {len(d['selected_channels'])}\n"
        f"<b>Buttons:</b> {sum(len(r) for r in d['buttons'])}\n\n"
        f"<b>Content:</b>\n{text[:400]}"
    )
    edit_message(chat_id, message_id, info, reply_markup=post_preview_menu())


def _publish(chat_id: int, message_id: int, user_id: int,
            d: dict[str, Any]) -> None:
    channels = list_channels(active_only=True)
    selected = [c for c in channels if c["channel_id"] in d["selected_channels"]]
    if not selected:
        edit_message(chat_id, message_id, "❌ No channels selected.")
        return

    markup = _draft_markup(d)
    sent, failed = 0, 0

    for c in selected:
        try:
            cid = c["channel_id"]
            if d["media_type"] == "photo" and d["media_file_id"]:
                send_photo(cid, d["media_file_id"], d["media_caption"] or d["text"],
                           reply_markup=markup or None)
            elif d["media_type"] == "video" and d["media_file_id"]:
                send_video(cid, d["media_file_id"], d["media_caption"] or d["text"],
                           reply_markup=markup or None)
            elif d["media_type"] == "document" and d["media_file_id"]:
                send_document(cid, d["media_file_id"], d["media_caption"] or d["text"],
                              reply_markup=markup or None)
            else:
                send_message(cid, d["text"], reply_markup=markup or None)
            sent += 1
            log_post(user_id, cid, c["channel_name"],
                     d["media_type"] or "text")
        except Exception:
            failed += 1

    edit_message(
        chat_id, message_id,
        f"<b>✅ Post published</b>\n\n"
        f"Sent: {sent}\nFailed: {failed}",
    )
    _clear(user_id)


def handle_post_message(message: dict[str, Any]) -> bool:
    """Handle admin composing a post (text/media/buttons)."""
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    from_user = message.get("from") or {}
    user_id = from_user.get("id")
    if not chat_id or not user_id or not is_db_admin(user_id):
        return False

    d = POST_DRAFTS.get(user_id)
    if not d or d.get("step") not in ("compose", "button_text"):
        return False

    text = message.get("text") or message.get("caption") or ""

    # Button input
    if d["step"] == "button_text":
        rows = []
        for line in text.split("\n"):
            if "|" in line:
                name, url = line.split("|", 1)
                name, url = name.strip(), url.strip()
                if name and url.startswith(("http://", "https://", "tg://")):
                    rows.append({"text": name, "url": url})
        if rows:
            d["buttons"].append(rows)
            send_message(chat_id, f"✅ {len(rows)} button(s) added.",
                         reply_markup=post_edit_menu())
        else:
            send_message(chat_id, "❌ Invalid format. Use <code>Name | URL</code>.")
        d["step"] = "compose"
        return True

    # Media / text
    if message.get("photo"):
        d["media_type"] = "photo"
        d["media_file_id"] = message["photo"][-1]["file_id"]
        d["media_caption"] = message.get("caption") or ""
    elif message.get("video"):
        d["media_type"] = "video"
        d["media_file_id"] = message["video"]["file_id"]
        d["media_caption"] = message.get("caption") or ""
    elif message.get("document"):
        d["media_type"] = "document"
        d["media_file_id"] = message["document"]["file_id"]
        d["media_caption"] = message.get("caption") or ""
    elif text:
        d["text"] = text

    send_message(chat_id, "✅ Content saved.",
                 reply_markup=post_edit_menu())
    return True