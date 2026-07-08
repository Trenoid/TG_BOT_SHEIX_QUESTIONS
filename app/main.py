from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot_commands import setup_bot_commands
from app.config import load_config
from app.database import Database
from app.handlers import admin, user


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    )

    config = load_config()
    db = Database(config.database_path)
    await db.init()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Прокидываем зависимости в хендлеры aiogram.
    dp['db'] = db
    dp['admin_ids'] = config.admin_ids
    dp['sheikh_ids'] = config.sheikh_ids
    dp['publication_channel'] = config.publication_channel
    dp['russian_audio_url'] = config.russian_audio_url

    # Важно: admin router подключён первым, чтобы состояния админа срабатывали раньше user fallback.
    dp.include_router(admin.router)
    dp.include_router(user.router)

    await setup_bot_commands(bot, config.admin_ids, config.sheikh_ids)

    logging.info('Bot started')
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
