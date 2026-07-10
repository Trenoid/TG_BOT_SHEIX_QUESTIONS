from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: set[int]
    sheikh_ids: set[int]
    database_path: str
    publication_channel: int | str | None
    russian_audio_url: str | None


def _parse_admin_ids(raw: str, *, env_name: str = 'ADMIN_IDS') -> set[int]:
    ids: set[int] = set()
    for item in re.split(r'[,;\s]+', raw):
        value = item.strip()
        if not value:
            continue
        if not value.isdigit():
            raise ValueError(f'{env_name} contains invalid Telegram ID: {value!r}')
        ids.add(int(value))
    return ids


def _normalize_optional_text(raw: str | None) -> str | None:
    value = (raw or '').strip()
    return value or None


def _normalize_publication_channel(raw: str | None) -> int | str | None:
    value = _normalize_optional_text(raw)
    if value is None:
        return None
    lowered = value.lower()
    for prefix in ('https://t.me/', 'http://t.me/', 't.me/'):
        if lowered.startswith(prefix):
            slug = value[len(prefix):].strip('/')
            if slug and not slug.startswith(('+', 'joinchat/', 'c/')):
                return f'@{slug}'
            return value
    if value.lstrip('-').isdigit():
        return int(value)
    return value


def load_config() -> Config:
    load_dotenv()

    bot_token = os.getenv('BOT_TOKEN', '').strip()
    admin_ids_raw = os.getenv('ADMIN_IDS', '').strip()
    sheikh_ids_raw = os.getenv('SHEIKH_IDS', '').strip()
    database_path = os.getenv('DATABASE_PATH', 'data/support_bot.db').strip()
    publication_channel = _normalize_publication_channel(os.getenv('PUBLICATION_CHANNEL'))
    russian_audio_url = _normalize_optional_text(os.getenv('RUSSIAN_AUDIO_URL'))

    if not bot_token or bot_token == 'PASTE_BOT_TOKEN_HERE':
        raise RuntimeError('BOT_TOKEN is empty. Put the token from @BotFather into .env')

    admin_ids = _parse_admin_ids(admin_ids_raw)
    if not admin_ids:
        raise RuntimeError('ADMIN_IDS is empty. Put at least one Telegram numeric ID into .env')

    sheikh_ids = _parse_admin_ids(sheikh_ids_raw, env_name='SHEIKH_IDS')

    Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    return Config(
        bot_token=bot_token,
        admin_ids=admin_ids,
        sheikh_ids=sheikh_ids,
        database_path=database_path,
        publication_channel=publication_channel,
        russian_audio_url=russian_audio_url,
    )
