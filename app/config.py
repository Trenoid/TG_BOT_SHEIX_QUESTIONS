from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: set[int]
    database_path: str


def _parse_admin_ids(raw: str) -> set[int]:
    ids: set[int] = set()
    for item in raw.replace(';', ',').split(','):
        value = item.strip()
        if not value:
            continue
        if not value.isdigit():
            raise ValueError(f'ADMIN_IDS contains invalid Telegram ID: {value!r}')
        ids.add(int(value))
    return ids


def load_config() -> Config:
    load_dotenv()

    bot_token = os.getenv('BOT_TOKEN', '').strip()
    admin_ids_raw = os.getenv('ADMIN_IDS', '').strip()
    database_path = os.getenv('DATABASE_PATH', 'data/support_bot.db').strip()

    if not bot_token or bot_token == 'PASTE_BOT_TOKEN_HERE':
        raise RuntimeError('BOT_TOKEN is empty. Put the token from @BotFather into .env')

    admin_ids = _parse_admin_ids(admin_ids_raw)
    if not admin_ids:
        raise RuntimeError('ADMIN_IDS is empty. Put at least one Telegram numeric ID into .env')

    Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    return Config(bot_token=bot_token, admin_ids=admin_ids, database_path=database_path)
