"""SQLite storage for the board bot."""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

DB_PATH = Path("data/board.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_LOCK = threading.RLock()
_CONN: sqlite3.Connection | None = None


def _conn() -> sqlite3.Connection:
    global _CONN
    if _CONN is None:
        _CONN = sqlite3.connect(DB_PATH, check_same_thread=False)
        _CONN.row_factory = sqlite3.Row
        _CONN.execute("PRAGMA journal_mode=WAL")
    return _CONN


SCHEMA = """
CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    added_at REAL
);

CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER UNIQUE,
    channel_name TEXT,
    channel_username TEXT,
    is_active INTEGER DEFAULT 1,
    added_at REAL
);

CREATE TABLE IF NOT EXISTS groups (
    chat_id INTEGER PRIMARY KEY,
    title TEXT,
    is_active INTEGER DEFAULT 1,
    added_at REAL
);

CREATE TABLE IF NOT EXISTS bot_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS bad_words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT UNIQUE,
    added_at REAL
);

CREATE TABLE IF NOT EXISTS allowed_domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT UNIQUE,
    added_at REAL
);

CREATE TABLE IF NOT EXISTS warnings (
    user_id INTEGER,
    chat_id INTEGER,
    count INTEGER DEFAULT 0,
    updated_at REAL,
    PRIMARY KEY (user_id, chat_id)
);

CREATE TABLE IF NOT EXISTS moderation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER,
    user_id INTEGER,
    user_name TEXT,
    action TEXT,
    reason TEXT,
    message_text TEXT,
    created_at REAL
);

CREATE TABLE IF NOT EXISTS post_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER,
    channel_id INTEGER,
    channel_name TEXT,
    message_type TEXT,
    created_at REAL
);

CREATE TABLE IF NOT EXISTS reaction_settings (
    chat_id INTEGER PRIMARY KEY,
    emojis TEXT,
    enabled INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS welcome_settings (
    chat_id INTEGER PRIMARY KEY,
    template TEXT,
    delete_seconds INTEGER DEFAULT 60,
    enabled INTEGER DEFAULT 1
);
"""


def init_db() -> None:
    with _LOCK:
        _conn().executescript(SCHEMA)
        # default settings
        defaults = {
            "welcome_system": "1",
            "auto_reaction": "1",
            "bad_word_protection": "1",
            "link_protection": "1",
            "auto_delete": "1",
            "channel_posting": "1",
            "button_system": "1",
        }
        for k, v in defaults.items():
            _conn().execute(
                "INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)", (k, v)
            )
        _conn().commit()


# ---------------- admins ----------------

def add_admin(user_id: int, name: str) -> None:
    with _LOCK:
        _conn().execute(
            "INSERT OR REPLACE INTO admins (user_id, name, added_at) VALUES (?, ?, ?)",
            (user_id, name, time.time()),
        )
        _conn().commit()


def remove_admin(user_id: int) -> None:
    with _LOCK:
        _conn().execute("DELETE FROM admins WHERE user_id=?", (user_id,))
        _conn().commit()


def is_db_admin(user_id: int) -> bool:
    with _LOCK:
        row = _conn().execute(
            "SELECT 1 FROM admins WHERE user_id=?", (user_id,)
        ).fetchone()
    return row is not None


def list_admins() -> list[dict[str, Any]]:
    with _LOCK:
        rows = _conn().execute("SELECT * FROM admins ORDER BY added_at").fetchall()
    return [dict(r) for r in rows]


# ---------------- channels ----------------

def add_channel(channel_id: int, name: str, username: str = "") -> None:
    with _LOCK:
        _conn().execute(
            """INSERT OR REPLACE INTO channels
               (channel_id, channel_name, channel_username, is_active, added_at)
               VALUES (?, ?, ?, 1, ?)""",
            (channel_id, name, username, time.time()),
        )
        _conn().commit()


def remove_channel(channel_id: int) -> None:
    with _LOCK:
        _conn().execute("DELETE FROM channels WHERE channel_id=?", (channel_id,))
        _conn().commit()


def set_channel_active(channel_id: int, active: bool) -> None:
    with _LOCK:
        _conn().execute(
            "UPDATE channels SET is_active=? WHERE channel_id=?",
            (int(active), channel_id),
        )
        _conn().commit()


def list_channels(active_only: bool = False) -> list[dict[str, Any]]:
    with _LOCK:
        q = "SELECT * FROM channels"
        if active_only:
            q += " WHERE is_active=1"
        q += " ORDER BY added_at"
        rows = _conn().execute(q).fetchall()
    return [dict(r) for r in rows]


def get_channel(channel_id: int) -> dict[str, Any] | None:
    with _LOCK:
        row = _conn().execute(
            "SELECT * FROM channels WHERE channel_id=?", (channel_id,)
        ).fetchone()
    return dict(row) if row else None


# ---------------- groups ----------------

def save_group(chat_id: int, title: str) -> None:
    with _LOCK:
        _conn().execute(
            """INSERT OR REPLACE INTO groups (chat_id, title, is_active, added_at)
               VALUES (?, ?, 1, ?)""",
            (chat_id, title, time.time()),
        )
        _conn().commit()


# ---------------- settings ----------------

def get_setting(key: str, default: str = "") -> str:
    with _LOCK:
        row = _conn().execute(
            "SELECT value FROM bot_settings WHERE key=?", (key,)
        ).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with _LOCK:
        _conn().execute(
            """INSERT INTO bot_settings (key, value) VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
            (key, value),
        )
        _conn().commit()


def setting_on(key: str) -> bool:
    return get_setting(key, "1") == "1"


# ---------------- bad words ----------------

def add_bad_word(word: str) -> None:
    with _LOCK:
        _conn().execute(
            "INSERT OR IGNORE INTO bad_words (word, added_at) VALUES (?, ?)",
            (word.lower().strip(), time.time()),
        )
        _conn().commit()


def remove_bad_word(word: str) -> None:
    with _LOCK:
        _conn().execute("DELETE FROM bad_words WHERE word=?", (word.lower().strip(),))
        _conn().commit()


def list_bad_words() -> list[str]:
    with _LOCK:
        rows = _conn().execute("SELECT word FROM bad_words ORDER BY word").fetchall()
    return [r["word"] for r in rows]


# ---------------- allowed domains ----------------

def add_allowed_domain(domain: str) -> None:
    with _LOCK:
        _conn().execute(
            "INSERT OR IGNORE INTO allowed_domains (domain, added_at) VALUES (?, ?)",
            (domain.lower().strip(), time.time()),
        )
        _conn().commit()


def remove_allowed_domain(domain: str) -> None:
    with _LOCK:
        _conn().execute(
            "DELETE FROM allowed_domains WHERE domain=?", (domain.lower().strip(),)
        )
        _conn().commit()


def list_allowed_domains() -> list[str]:
    with _LOCK:
        rows = _conn().execute(
            "SELECT domain FROM allowed_domains ORDER BY domain"
        ).fetchall()
    return [r["domain"] for r in rows]


# ---------------- warnings ----------------

def add_warning(user_id: int, chat_id: int) -> int:
    with _LOCK:
        _conn().execute(
            """INSERT INTO warnings (user_id, chat_id, count, updated_at)
               VALUES (?, ?, 1, ?)
               ON CONFLICT(user_id, chat_id) DO UPDATE SET
                 count=count+1, updated_at=excluded.updated_at""",
            (user_id, chat_id, time.time()),
        )
        _conn().commit()
        row = _conn().execute(
            "SELECT count FROM warnings WHERE user_id=? AND chat_id=?",
            (user_id, chat_id),
        ).fetchone()
    return int(row["count"]) if row else 0


def reset_warning(user_id: int, chat_id: int) -> None:
    with _LOCK:
        _conn().execute(
            "DELETE FROM warnings WHERE user_id=? AND chat_id=?",
            (user_id, chat_id),
        )
        _conn().commit()


def get_warning(user_id: int, chat_id: int) -> int:
    with _LOCK:
        row = _conn().execute(
            "SELECT count FROM warnings WHERE user_id=? AND chat_id=?",
            (user_id, chat_id),
        ).fetchone()
    return int(row["count"]) if row else 0


# ---------------- logs ----------------

def log_moderation(chat_id: int, user_id: int, user_name: str,
                   action: str, reason: str, message_text: str = "") -> None:
    with _LOCK:
        _conn().execute(
            """INSERT INTO moderation_logs
               (chat_id, user_id, user_name, action, reason, message_text, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (chat_id, user_id, user_name, action, reason,
             message_text[:200], time.time()),
        )
        _conn().commit()


def log_post(admin_id: int, channel_id: int, channel_name: str,
             message_type: str) -> None:
    with _LOCK:
        _conn().execute(
            """INSERT INTO post_logs
               (admin_id, channel_id, channel_name, message_type, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (admin_id, channel_id, channel_name, message_type, time.time()),
        )
        _conn().commit()


def recent_moderation_logs(limit: int = 20) -> list[dict[str, Any]]:
    with _LOCK:
        rows = _conn().execute(
            "SELECT * FROM moderation_logs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def recent_post_logs(limit: int = 20) -> list[dict[str, Any]]:
    with _LOCK:
        rows = _conn().execute(
            "SELECT * FROM post_logs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------- reaction settings ----------------

def set_reaction_emojis(chat_id: int, emojis: list[str], enabled: bool = True) -> None:
    with _LOCK:
        _conn().execute(
            """INSERT INTO reaction_settings (chat_id, emojis, enabled)
               VALUES (?, ?, ?)
               ON CONFLICT(chat_id) DO UPDATE SET
                 emojis=excluded.emojis, enabled=excluded.enabled""",
            (chat_id, ",".join(emojis), int(enabled)),
        )
        _conn().commit()


def get_reaction_emojis(chat_id: int) -> tuple[list[str], bool]:
    with _LOCK:
        row = _conn().execute(
            "SELECT emojis, enabled FROM reaction_settings WHERE chat_id=?",
            (chat_id,),
        ).fetchone()
    if not row:
        return [], True
    return ([e.strip() for e in (row["emojis"] or "").split(",") if e.strip()],
            bool(row["enabled"]))


# ---------------- welcome settings ----------------

def set_welcome_template(chat_id: int, template: str, delete_seconds: int) -> None:
    with _LOCK:
        _conn().execute(
            """INSERT INTO welcome_settings (chat_id, template, delete_seconds, enabled)
               VALUES (?, ?, ?, 1)
               ON CONFLICT(chat_id) DO UPDATE SET
                 template=excluded.template,
                 delete_seconds=excluded.delete_seconds""",
            (chat_id, template, delete_seconds),
        )
        _conn().commit()


def get_welcome_template(chat_id: int) -> tuple[str, int, bool]:
    with _LOCK:
        row = _conn().execute(
            "SELECT template, delete_seconds, enabled FROM welcome_settings WHERE chat_id=?",
            (chat_id,),
        ).fetchone()
    if not row:
        return ("👋 Welcome {name}!\n\nআমাদের গ্রুপে স্বাগতম ❤️",
                CFG.welcome_delete_seconds, True)
    return (row["template"] or "", int(row["delete_seconds"]), bool(row["enabled"]))