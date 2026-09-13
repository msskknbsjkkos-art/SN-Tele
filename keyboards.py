"""All inline keyboard builders."""
from __future__ import annotations

import json
from typing import Any


def kb(rows: list[list[dict[str, str]]]) -> str:
    return json.dumps({"inline_keyboard": rows})


def main_menu(is_admin: bool = False) -> str:
    rows = [
        [{"text": "⚙️ Settings", "callback_data": "menu:settings"},
         {"text": "❓ Help", "callback_data": "menu:help"}],
    ]
    if is_admin:
        rows.insert(0, [
            {"text": "📢 Post to Channel", "callback_data": "post:start"},
            {"text": "📡 Channels", "callback_data": "channels:list"},
        ])
        rows.append([
            {"text": "🛡 Moderation", "callback_data": "mod:menu"},
            {"text": "📊 Logs", "callback_data": "logs:menu"},
        ])
        rows.append([
            {"text": "👑 Admins", "callback_data": "admins:menu"},
        ])
    return kb(rows)


def settings_menu(get_setting) -> str:
    def mark(key: str) -> str:
        return "🟢" if get_setting(key, "1") == "1" else "🔴"

    return kb([
        [{"text": f"{mark('welcome_system')} Welcome",
          "callback_data": "toggle:welcome_system"},
         {"text": f"{mark('auto_reaction')} Reaction",
          "callback_data": "toggle:auto_reaction"}],
        [{"text": f"{mark('bad_word_protection')} Bad Words",
          "callback_data": "toggle:bad_word_protection"},
         {"text": f"{mark('link_protection')} Link Protection",
          "callback_data": "toggle:link_protection"}],
        [{"text": f"{mark('auto_delete')} Auto Delete",
          "callback_data": "toggle:auto_delete"},
         {"text": f"{mark('channel_posting')} Channel Posting",
          "callback_data": "toggle:channel_posting"}],
        [{"text": f"{mark('button_system')} Button System",
          "callback_data": "toggle:button_system"}],
        [{"text": "↩️ Back", "callback_data": "menu:home"}],
    ])


def channels_menu(channels: list[dict[str, Any]]) -> str:
    rows: list[list[dict[str, str]]] = []
    for c in channels[:10]:
        mark = "🟢" if c["is_active"] else "🔴"
        rows.append([
            {"text": f"{mark} {c['channel_name'][:30]}",
             "callback_data": f"channel:view:{c['channel_id']}"},
        ])
    rows.append([
        {"text": "➕ Add Channel", "callback_data": "channel:add"},
        {"text": "↩️ Back", "callback_data": "menu:home"},
    ])
    return kb(rows)


def channel_actions(channel_id: int, is_active: bool) -> str:
    toggle = "🔴 Disable" if is_active else "🟢 Enable"
    return kb([
        [{"text": toggle, "callback_data": f"channel:toggle:{channel_id}"}],
        [{"text": "🗑 Remove", "callback_data": f"channel:remove:{channel_id}"}],
        [{"text": "↩️ Back", "callback_data": "channels:list"}],
    ])


def post_channels_select(channels: list[dict[str, Any]],
                        selected: set[int]) -> str:
    rows: list[list[dict[str, str]]] = []
    for c in channels:
        mark = "✅" if c["channel_id"] in selected else "⬜"
        rows.append([
            {"text": f"{mark} {c['channel_name'][:28]}",
             "callback_data": f"post:toggle:{c['channel_id']}"},
        ])
    rows.append([
        {"text": "➡️ Next", "callback_data": "post:compose"},
        {"text": "❌ Cancel", "callback_data": "post:cancel"},
    ])
    return kb(rows)


def post_edit_menu() -> str:
    return kb([
        [{"text": "🔘 Add Button", "callback_data": "post:addbutton"}],
        [{"text": "👁 Preview", "callback_data": "post:preview"}],
        [{"text": "✅ Publish", "callback_data": "post:publish"}],
        [{"text": "❌ Cancel", "callback_data": "post:cancel"}],
    ])


def post_preview_menu() -> str:
    return kb([
        [{"text": "✅ Publish", "callback_data": "post:confirm"}],
        [{"text": "✏️ Edit", "callback_data": "post:compose"}],
        [{"text": "❌ Cancel", "callback_data": "post:cancel"}],
    ])


def moderation_menu(get_setting) -> str:
    def mark(key: str) -> str:
        return "🟢" if get_setting(key, "1") == "1" else "🔴"
    return kb([
        [{"text": f"{mark('bad_word_protection')} Bad Words",
          "callback_data": "mod:badwords"}],
        [{"text": f"{mark('link_protection')} Link Protection",
          "callback_data": "mod:links"}],
        [{"text": "↩️ Back", "callback_data": "menu:home"}],
    ])


def badwords_menu(words: list[str]) -> str:
    rows: list[list[dict[str, str]]] = []
    for w in words[:15]:
        rows.append([
            {"text": f"🗑 {w}", "callback_data": f"badword:remove:{w}"},
        ])
    rows.append([
        {"text": "➕ Add Word", "callback_data": "badword:add"},
        {"text": "↩️ Back", "callback_data": "mod:menu"},
    ])
    return kb(rows)


def links_menu(domains: list[str]) -> str:
    rows: list[list[dict[str, str]]] = []
    for d in domains[:15]:
        rows.append([
            {"text": f"🗑 {d}", "callback_data": f"domain:remove:{d}"},
        ])
    rows.append([
        {"text": "➕ Add Domain", "callback_data": "domain:add"},
        {"text": "↩️ Back", "callback_data": "mod:menu"},
    ])
    return kb(rows)


def confirm_cancel(action: str) -> str:
    return kb([
        [{"text": "✅ Confirm", "callback_data": f"{action}:confirm"},
         {"text": "❌ Cancel", "callback_data": "menu:home"}],
    ])