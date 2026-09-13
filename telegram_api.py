"""Telegram Bot API — raw HTTP helpers (no external library)."""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from config import CFG

LOG = logging.getLogger("board.telegram")
API = f"https://api.telegram.org/bot{CFG.telegram_token}"


def _call(method: str, data: dict[str, Any] | None = None,
          timeout: int = 45, max_bytes: int = 4 * 1024 * 1024) -> Any:
    payload = urlencode(data or {}).encode()
    request = Request(
        f"{API}/{method}",
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "BoardBot/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(max_bytes)
    except HTTPError as error:
        body = error.read(1024).decode(errors="replace")
        raise RuntimeError(f"HTTP {error.code}: {body[:180]}") from error
    except (URLError, TimeoutError) as error:
        raise RuntimeError(f"Network: {error}") from error

    result = json.loads(raw.decode("utf-8", errors="replace"))
    if not result.get("ok"):
        raise RuntimeError(result.get("description", "Telegram API error"))
    return result.get("result")


def _upload(method: str, field: str, file_name: str, file_bytes: bytes,
            fields: dict[str, str], timeout: int = 120) -> Any:
    boundary = f"----Board{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for key, value in fields.items():
        parts.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode(),
            str(value).encode(),
            b"\r\n",
        ])
    parts.extend([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="{field}"; '
        f'filename="{file_name}"\r\n'.encode(),
        b"Content-Type: application/octet-stream\r\n\r\n",
        file_bytes,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])
    request = Request(
        f"{API}/{method}",
        data=b"".join(parts),
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "BoardBot/1.0",
        },
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        raw = response.read(4 * 1024 * 1024)
    result = json.loads(raw.decode("utf-8", errors="replace"))
    if not result.get("ok"):
        raise RuntimeError(result.get("description", "Telegram upload error"))
    return result.get("result")


# ---------- public API ----------

def get_me() -> dict:
    return _call("getMe")


def get_updates(offset: int, timeout: int = 25,
                allowed: list[str] | None = None) -> list[dict]:
    return _call("getUpdates", {
        "offset": str(offset),
        "timeout": str(timeout),
        "allowed_updates": json.dumps(
            allowed or ["message", "callback_query", "chat_member", "my_chat_member"]
        ),
    })


def send_message(chat_id: int | str, text: str, **extra: Any) -> dict:
    return _call("sendMessage", {
        "chat_id": str(chat_id),
        "text": text,
        "parse_mode": "HTML",
        **extra,
    })


def edit_message(chat_id: int | str, message_id: int, text: str,
                 **extra: Any) -> dict | None:
    try:
        return _call("editMessageText", {
            "chat_id": str(chat_id),
            "message_id": str(message_id),
            "text": text,
            "parse_mode": "HTML",
            **extra,
        })
    except RuntimeError as error:
        if "not modified" not in str(error).lower():
            LOG.warning("edit failed: %s", error)
        return None


def delete_message(chat_id: int | str, message_id: int) -> bool:
    try:
        _call("deleteMessage", {"chat_id": str(chat_id), "message_id": str(message_id)})
        return True
    except RuntimeError as error:
        LOG.warning("delete failed: %s", error)
        return False


def answer_callback(callback_id: str, text: str = "") -> None:
    try:
        _call("answerCallbackQuery",
              {"callback_query_id": callback_id, "text": text})
    except RuntimeError as error:
        LOG.warning("callback ack failed: %s", error)


def send_photo(chat_id: int | str, photo: str, caption: str = "",
               **extra: Any) -> dict:
    return _call("sendPhoto", {
        "chat_id": str(chat_id), "photo": photo,
        "caption": caption, "parse_mode": "HTML", **extra,
    })


def send_video(chat_id: int | str, video: str, caption: str = "",
               **extra: Any) -> dict:
    return _call("sendVideo", {
        "chat_id": str(chat_id), "video": video,
        "caption": caption, "parse_mode": "HTML", **extra,
    })


def send_document(chat_id: int | str, document: str, caption: str = "",
                  **extra: Any) -> dict:
    return _call("sendDocument", {
        "chat_id": str(chat_id), "document": document,
        "caption": caption, "parse_mode": "HTML", **extra,
    })


def set_reaction(chat_id: int, message_id: int, emojis: list[str]) -> None:
    payload = [{"type": "emoji", "emoji": e} for e in emojis[:3]]
    _call("setMessageReaction", {
        "chat_id": str(chat_id),
        "message_id": str(message_id),
        "reaction": json.dumps(payload),
        "is_big": "false",
    })


def restrict_member(chat_id: int, user_id: int, until: int = 0) -> None:
    _call("restrictChatMember", {
        "chat_id": str(chat_id),
        "user_id": str(user_id),
        "permissions": json.dumps({
            "can_send_messages": False,
            "can_send_media_messages": False,
            "can_send_other_messages": False,
            "can_add_web_page_previews": False,
        }),
        "until_date": str(until),
    })


def ban_member(chat_id: int, user_id: int) -> None:
    try:
        _call("banChatMember", {"chat_id": str(chat_id), "user_id": str(user_id)})
    except RuntimeError as error:
        LOG.warning("ban failed: %s", error)


def get_chat(chat_id: int | str) -> dict:
    return _call("getChat", {"chat_id": str(chat_id)})


def get_chat_member(chat_id: int, user_id: int) -> dict:
    return _call("getChatMember", {"chat_id": str(chat_id), "user_id": str(user_id)})


def auto_delete_later(chat_id: int, message_id: int, delay: int) -> None:
    import threading

    def _worker() -> None:
        time.sleep(delay)
        delete_message(chat_id, message_id)

    threading.Thread(target=_worker, daemon=True).start()