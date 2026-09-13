"""Feature 10 + 12 — Admin control & settings."""
from __future__ import annotations

from typing import Any

from database import (
    add_admin,
    add_allowed_domain,
    add_bad_word,
    get_setting,
    is_db_admin,
    list_admins,
    list_allowed_domains,
    list_bad_words,
    remove_admin,
    remove_allowed_domain,
    remove_bad_word,
    set_reaction_emojis,
    set_setting,
    setting_on,
)
from keyboards import (
    badwords_menu,
    links_menu,
    main_menu,
    moderation_menu,
    settings_menu,
)
from telegram_api import edit_message, send_message


def is_admin(user_id: int) -> bool:
    from config import CFG
    return is_db_admin(user_id) or user_id in CFG.owner_ids


def open_menu(chat_id: int, user_id: int, message_id: int | None = None) -> None:
    text = "<b>🤖 Board Bot — Main Menu</b>\n\nChoose an option:"
    markup = main_menu(is_admin(user_id))
    if message_id:
        edit_message(chat_id, message_id, text, reply_markup=markup)
    else:
        send_message(chat_id, text, reply_markup=markup)


def handle_admin_callback(callback: dict[str, Any]) -> bool:
    data = callback.get("data", "")
    if not data.startswith(("menu:", "toggle:", "mod:", "badword:",
                            "domain:", "logs:", "admins:")):
        return False

    message = callback.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    message_id = message.get("message_id")
    user_id = (callback.get("from") or {}).get("id")
    if not chat_id:
        return True

    parts = data.split(":", 1)
    prefix, action = parts[0], parts[1] if len(parts) > 1 else ""

    # ---- menu ----
    if prefix == "menu":
        if action == "home":
            open_menu(chat_id, user_id, message_id)
        elif action == "settings":
            if not is_admin(user_id):
                return True
            edit_message(chat_id, message_id,
                         "<b>⚙️ Settings</b>\n\nToggle features:",
                         reply_markup=settings_menu(get_setting))
        elif action == "help":
            edit_message(
                chat_id, message_id,
                "<b>❓ Help</b>\n\n"
                "• <b>Post to Channel</b> — Send posts to channels\n"
                "• <b>Channels</b> — Add/remove channels\n"
                "• <b>Moderation</b> — Bad words & links\n"
                "• <b>Logs</b> — Recent activity\n"
                "• <b>Admins</b> — Manage admin list\n"
                "• <b>Settings</b> — Feature toggles",
                reply_markup=main_menu(is_admin(user_id)),
            )
        return True

    # ---- toggle ----
    if prefix == "toggle":
        if not is_admin(user_id):
            return True
        current = get_setting(action, "1")
        set_setting(action, "0" if current == "1" else "1")
        edit_message(chat_id, message_id,
                     "<b>⚙️ Settings</b>\n\nToggle features:",
                     reply_markup=settings_menu(get_setting))
        return True

    # ---- moderation ----
    if prefix == "mod":
        if not is_admin(user_id):
            return True
        if action == "menu":
            edit_message(chat_id, message_id,
                         "<b>🛡 Moderation</b>",
                         reply_markup=moderation_menu(get_setting))
        elif action == "badwords":
            words = list_bad_words()
            edit_message(chat_id, message_id,
                         f"<b>🚫 Bad Words ({len(words)})</b>\n\n"
                         "Tap to remove, or Add Word:",
                         reply_markup=badwords_menu(words))
        elif action == "links":
            domains = list_allowed_domains()
            edit_message(chat_id, message_id,
                         f"<b>🔗 Allowed Domains ({len(domains)})</b>\n\n"
                         "Only these domains are allowed in groups.",
                         reply_markup=links_menu(domains))
        return True

    # ---- badword ----
    if prefix == "badword":
        if not is_admin(user_id):
            return True
        if action.startswith("remove:"):
            word = action.split(":", 1)[1]
            remove_bad_word(word)
            words = list_bad_words()
            edit_message(chat_id, message_id,
                         f"<b>🚫 Bad Words ({len(words)})</b>",
                         reply_markup=badwords_menu(words))
        elif action == "add":
            edit_message(chat_id, message_id,
                         "<b>➕ Add Bad Word</b>\n\n"
                         "Send the word now (lowercase).")
        return True

    # ---- domain ----
    if prefix == "domain":
        if not is_admin(user_id):
            return True
        if action.startswith("remove:"):
            domain = action.split(":", 1)[1]
            remove_allowed_domain(domain)
            domains = list_allowed_domains()
            edit_message(chat_id, message_id,
                         f"<b>🔗 Allowed Domains ({len(domains)})</b>",
                         reply_markup=links_menu(domains))
        elif action == "add":
            edit_message(chat_id, message_id,
                         "<b>➕ Add Domain</b>\n\n"
                         "Send domain (e.g. <code>youtube.com</code>).")
        return True

    # ---- logs ----
    if prefix == "logs":
        if not is_admin(user_id):
            return True
        from database import recent_moderation_logs, recent_post_logs
        mods = recent_moderation_logs(10)
        posts = recent_post_logs(10)
        lines = ["<b>📊 Recent Logs</b>\n"]
        if mods:
            lines.append("<b>🛡 Moderation:</b>")
            for m in mods[:5]:
                lines.append(
                    f"• <code>{m['action']}</code> — {m['user_name']} "
                    f"({m['reason'][:30]})"
                )
        if posts:
            lines.append("\n<b>📢 Posts:</b>")
            for p in posts[:5]:
                lines.append(
                    f"• {p['channel_name'][:25]} ({p['message_type']})"
                )
        edit_message(chat_id, message_id, "\n".join(lines) or "No logs yet.",
                     reply_markup=main_menu(is_admin(user_id)))
        return True

    # ---- admins ----
    if prefix == "admins":
        if not is_admin(user_id):
            return True
        admins = list_admins()
        lines = [f"<b>👑 Admins ({len(admins)})</b>\n"]
        for a in admins:
            lines.append(f"• <code>{a['user_id']}</code> — {a['name']}")
        from keyboards import kb
        edit_message(chat_id, message_id, "\n".join(lines),
                     reply_markup=kb([
                         [{"text": "➕ Add Admin (reply)", "callback_data": "noop"}],
                         [{"text": "↩️ Back", "callback_data": "menu:home"}],
                     ]))
        return True

    return True