from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault, MenuButtonCommands

USER_COMMANDS = [
    BotCommand(command='start', description='Открыть меню'),
    BotCommand(command='new', description='Задать вопрос шейху'),
    BotCommand(command='my', description='Мои вопросы'),
    BotCommand(command='language', description='Сменить язык'),
    BotCommand(command='help', description='Помощь'),
]

ADMIN_COMMANDS = [
    BotCommand(command='start', description='Панель шейха'),
    BotCommand(command='panel', description='Панель шейха'),
    BotCommand(command='answer', description='Ответить на вопрос'),
    BotCommand(command='close', description='Закрыть вопрос'),
    BotCommand(command='language', description='Язык панели'),
    BotCommand(command='help', description='Помощь'),
    BotCommand(command='cancel', description='Отмена действия'),
]


async def setup_bot_commands(bot: Bot, admin_ids: set[int]) -> None:
    """Настраивает кнопку меню Telegram рядом с полем ввода.

    У обычных пользователей в меню будут /start, /new, /my, /language, /help.
    У админов/шейхов будет отдельный набор команд панели.
    """
    await bot.set_my_commands(USER_COMMANDS, scope=BotCommandScopeDefault())
    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    except Exception as exc:  # pragma: no cover - зависит от Telegram API/прав бота
        logging.warning('Could not set default chat menu button: %s', exc)

    for admin_id in admin_ids:
        try:
            await bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id))
            await bot.set_chat_menu_button(chat_id=admin_id, menu_button=MenuButtonCommands())
        except Exception as exc:  # pragma: no cover - админ мог ещё не открыть бота
            logging.warning('Could not set admin commands for %s: %s', admin_id, exc)
