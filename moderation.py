"""Feature 3 + 4 — Bad word & link protection."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from database import (
    add_warning,
    get_warning,
    is_db_admin,
    list_allowed_domains,
    list_bad_words,
    log_moderation,
    setting_on,
)
from telegram_api import (
    ban_member,
    delete_message,
    restrict_member,
    send_message,
)

URL_PATTERN = re.compile(
    r"(https?://[^\s]+|www\.[^\s]+|t\.me/[^\s]+|telegram\.me/[^\s]+)",
    re.IGNORECASE,
)


def _domain_allowed(url: str) -> bool:
    host = (urlparse(url if url.startswith("http") else f"http://{url}").hostname or "")
    host = host.lower().removeprefix("www.")
    for d in list_allowed_domains():
        d = d.lower()
        if host == d or host.endswith(f".{d}"):
            return True
    return False


def _find_bad_word(text: str) -> str | None:
    low = text.lower()
    for word in list_bad_words():
        if not word:
            continue
        if re.search(rf"\b{re.escape(word)}\b", low):
            return word
    return None


def _find_bad_link(text: str) -> str | None:
    for match in URL_PATTERN.finditer(text or ""):
        url = match.group(0)
        if _domain_allowed(url):
            continue
        return url
    return None


def _handle_violation(message: dict[str, Any], reason: str,
                     matched: str) -> None:
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    from_user = message.get("from") or {}
    user_id = from_user.get("id")
    user_name = from_user.get("first_name") or ""
    text = message.get("text") or message.get("caption") or ""

    if not chat_id or not user_id:
        return
    if is_db_admin(user_id):
        return

    delete_message(chat_id, message.get("message_id"))

    count = add_warning(user_id, chat_id)
    log_moderation(chat_id, user_id, user_name, "delete", reason, text)

    if count >= 3:
        restrict_member(chat_id, user_id, until=0)
        try:
            notice = send_message(
                chat_id,
                f"🚫 <b>{user_name}</b> কে ৩ warning এর কারণে mute করা হয়েছে।",
            )
            from telegram_api import auto_delete_later
            auto_delete_later(chat_id, notice["message_id"], 30)
        except Exception:
            pass
    else:
        try:
            notice = send_message(
                chat_id,
                f"⚠️ <b>{user_name}</b> — {reason} ({count}/3)\n"
                f"<i>{matched[:60]}</i>",
            )
            from telegram_api import auto_delete_later
            auto_delete_later(chat_id, notice["message_id"], 15)
        except Exception:
            pass


def handle_moderation(message: dict[str, Any]) -> None:
    chat = message.get("chat") or {}
    if chat.get("type") not in ("group", "supergroup"):
        return
    text = message.get("text") or message.get("caption") or ""
    if not text:
        return

    if setting_on("bad_word_protection"):
        bad = _find_bad_word(text)
        if bad:
            _handle_violation(message, "Bad word detected", bad)
            return

    if setting_on("link_protection"):
        link = _find_bad_link(text)
        if link:
            _handle_violation(message, "Unauthorized link", link)
            return