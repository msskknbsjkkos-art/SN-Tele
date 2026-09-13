"""TG Board Bot — configuration from environment."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    telegram_token: str
    owner_ids: frozenset[int]
    log_level: str
    welcome_delete_seconds: int
    default_reaction_emojis: tuple[str, ...]

    @classmethod
    def from_env(cls) -> "Config":
        token = os.getenv("TOKEN", "").strip()
        if not token:
            raise RuntimeError("TOKEN missing")
        owners_raw = os.getenv("OWNER_IDS", "")
        owners = frozenset(
            int(x) for x in owners_raw.replace(" ", "").split(",") if x.strip().isdigit()
        )
        if not owners:
            raise RuntimeError("OWNER_IDS must contain at least one numeric ID")
        emojis = tuple(
            e.strip()
            for e in os.getenv(
                "DEFAULT_REACTION_EMOJIS",
                "🔥,❤️,👍,🎉,🥰,👏,💯,⚡",
            ).split(",")
            if e.strip()
        )
        return cls(
            telegram_token=token,
            owner_ids=owners,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            welcome_delete_seconds=_env_int("WELCOME_DELETE_SECONDS", 60),
            default_reaction_emojis=emojis,
        )


CFG = Config.from_env()