"""Telegram Board Bot — main entrypoint."""
from __future__ import annotations

import json
import logging
import os
import random
import re
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from config import CFG
from database import (
    add_admin,
    add_allowed_domain,
    add_bad_word,
    init_db,
    is_db_admin,
    save_group,
    set_reaction_emojis,
    set_welcome_template,
)
from handlers.admin import handle_admin_callback, is_admin, open_menu
from handlers.channels import handle_channel_callback
from handlers.moderation import handle_moderation
from handlers.posting import (
    handle_post_callback,
    handle_post_message,
)
from handlers.reactions import handle_reaction
from handlers.welcome import handle_chat_member
from keyboards import main_menu
from telegram_api import (
    answer_callback,
    delete_message,
    get_me,
    get_updates,
    send_message,
)
from telegram_api import _call as tg_call

logging.basicConfig(
    level=CFG.log_level,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
LOG = logging.getLogger("board")

SHUTDOWN = threading.Event()

# In-memory "what is admin typing" state
ADMIN_STATE: dict[int, str] = {}
STATE_LOCK = threading.RLock()


# ---------- state helper ----------

def set_state(user_id: int, state: str | None) -> None:
    with STATE_LOCK:
        if state is None:
            ADMIN_STATE.pop(user_id, None)
        else:
            ADMIN_STATE[user_id] = state


def get_state(user_id: int) -> str | None:
    with STATE_LOCK:
        return ADMIN_STATE.get(user_id)


# ---------- command routing ----------

def handle_message(message: dict[str, Any]) -> None:
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    chat_type = chat.get("type") or ""
    from_user = message.get("from") or {}
    user_id = from_user.get("id")
    text = (message.get("text") or "").strip()

    if chat_id is None or from_user.get("is_bot"):
        return

    # Track groups
    if chat_type in ("group", "supergroup"):
        save_group(chat_id, chat.get("title") or "")

    command = text.split(maxsplit=1)[0].lower().split("@", 1)[0] if text else ""

    # --- state-driven input (admin flows) ---
    state = get_state(user_id) if user_id else None

    if state == "add_badword" and user_id and is_admin(user_id):
        word = text.strip().lower()
        if word:
            add_bad_word(word)
            send_message(chat_id, f"✅ Added bad word: <code>{word}</code>")
        set_state(user_id, None)
        return

    if state == "add_domain" and user_id and is_admin(user_id):
        domain = text.strip().lower().lstrip("@")
        if domain:
            add_allowed_domain(domain)
            send_message(chat_id, f"✅ Added domain: <code>{domain}</code>")
        set_state(user_id, None)
        return

    if state == "add_channel" and user_id and is_admin(user_id):
        target = text.strip()
        try:
            info = tg_call("getChat", {"chat_id": target})
            add_channel(
                info["id"],
                info.get("title") or info.get("username") or target,
                info.get("username") or "",
            )
            send_message(chat_id, f"✅ Channel added: <b>{info.get('title')}</b>")
        except Exception as error:
            send_message(chat_id, f"❌ Failed: {error}")
        set_state(user_id, None)
        return

    if state == "add_admin" and user_id and is_admin(user_id):
        if text.lstrip("-").isdigit():
            add_admin(int(text), f"user_{text}")
            send_message(chat_id, f"✅ Admin added: <code>{text}</code>")
        set_state(user_id, None)
        return

    if state == "set_reaction" and user_id and is_admin(user_id):
        emojis = [e.strip() for e in re.split(r"[,\s]+", text) if e.strip()]
        if emojis:
            set_reaction_emojis(chat_id, emojis, True)
            send_message(chat_id, f"✅ Reaction emojis set: {' '.join(emojis)}")
        set_state(user_id, None)
        return

    if state == "set_welcome" and user_id and is_admin(user_id):
        set_welcome_template(chat_id, text, CFG.welcome_delete_seconds)
        send_message(chat_id, "✅ Welcome template updated.")
        set_state(user_id, None)
        return

    # --- admin post composition ---
    if user_id and is_db_admin(user_id) and handle_post_message(message):
        return

    # --- moderation (bad words / links) ---
    handle_moderation(message)

    # --- auto reaction ---
    handle_reaction(message)

    # --- commands ---
    if command == "/start":
        open_menu(chat_id, user_id)
        return

    if command == "/help":
        send_message(chat_id, "<b>❓ Help</b>\n\nUse /start to open the menu.")
        return

    if command == "/menu":
        open_menu(chat_id, user_id)
        return

    if command == "/addadmin" and user_id and is_admin(user_id):
        set_state(user_id, "add_admin")
        send_message(chat_id, "Send the user ID to add as admin.")
        return

    if command == "/addbadword" and user_id and is_admin(user_id):
        set_state(user_id, "add_badword")
        send_message(chat_id, "Send the bad word to add.")
        return

    if command == "/adddomain" and user_id and is_admin(user_id):
        set_state(user_id, "add_domain")
        send_message(chat_id, "Send the allowed domain (e.g. youtube.com).")
        return

    if command == "/addchannel" and user_id and is_admin(user_id):
        set_state(user_id, "add_channel")
        send_message(chat_id, "Send the channel @username or ID.")
        return

    if command == "/setreaction" and user_id and is_admin(user_id):
        set_state(user_id, "set_reaction")
        send_message(chat_id, "Send emojis separated by space or comma.")
        return

    if command == "/setwelcome" and user_id and is_admin(user_id):
        set_state(user_id, "set_welcome")
        send_message(chat_id,
                     "Send the welcome template.\n"
                     "Use <code>{name}</code> for the user's name.")
        return


# ---------- callback routing ----------

def handle_callback(callback: dict[str, Any]) -> None:
    answer_callback(callback.get("id", ""))

    # Order matters — first matching handler wins
    if handle_channel_callback(callback):
        return
    if handle_post_callback(callback):
        return
    if handle_admin_callback(callback):
        return


# ---------- chat_member routing ----------

def handle_chat_member_update(update: dict[str, Any]) -> None:
    handle_chat_member(update)


def handle_my_chat_member(update: dict[str, Any]) -> None:
    cm = update.get("my_chat_member") or {}
    chat = cm.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id and chat.get("type") in ("group", "supergroup"):
        save_group(chat_id, chat.get("title") or "")


# ---------- polling loop ----------

def polling_loop() -> None:
    offset = 0
    backoff = 2
    while not SHUTDOWN.is_set():
        try:
            updates = get_updates(offset)
            backoff = 2
            for update in updates or []:
                offset = max(offset, int(update.get("update_id", 0)) + 1)
                try:
                    if update.get("callback_query"):
                        handle_callback(update["callback_query"])
                    elif update.get("message"):
                        handle_message(update["message"])
                    elif update.get("chat_member"):
                        handle_chat_member_update(update)
                    elif update.get("my_chat_member"):
                        handle_my_chat_member(update)
                except Exception:
                    LOG.exception("Update failed")
        except Exception as error:
            LOG.error("Polling error: %s", error)
            SHUTDOWN.wait(backoff)
            backoff = min(backoff * 2, 30)


# ---------- health server ----------

class Health(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path not in {"/", "/healthz", "/health"}:
            self.send_response(404); self.end_headers(); return
        payload = json.dumps({"ok": True, "service": "board-bot"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args: Any) -> None:
        return


def start_health() -> ThreadingHTTPServer:
    port = int(os.getenv("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Health)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    LOG.info("Health server on 0.0.0.0:%s", port)
    return server


# ---------- keep-alive ----------

def keep_alive_loop() -> None:
    url = (os.getenv("KEEP_ALIVE_URL", "").strip()
           or os.getenv("RENDER_EXTERNAL_URL", "").strip())
    if not url:
        return
    url = url.rstrip("/") + "/healthz"
    LOG.info("Keep-alive: %s", url)
    while not SHUTDOWN.wait(random.uniform(12 * 60, 14 * 60)):
        try:
            from urllib.request import Request, urlopen
            with urlopen(Request(url, method="GET"), timeout=20) as r:
                LOG.info("Keep-alive ok (%s)", r.status)
        except Exception as error:
            LOG.warning("Keep-alive failed: %s", error)


# ---------- main ----------

def _shutdown(_s: int, _f: Any) -> None:
    LOG.info("Shutdown signal")
    SHUTDOWN.set()


def main() -> None:
    init_db()
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    health = start_health()
    threading.Thread(target=keep_alive_loop, daemon=True).start()

    try:
        tg_call("deleteWebhook", {"drop_pending_updates": "false"})
        me = get_me()
        LOG.info("Bot connected as @%s", me.get("username"))
        threading.Thread(target=polling_loop, daemon=True).start()
        while not SHUTDOWN.wait(1):
            pass
    finally:
        SHUTDOWN.set()
        health.shutdown()
        LOG.info("Stopped")


if __name__ == "__main__":
    main()