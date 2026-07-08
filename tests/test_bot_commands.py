import pytest
from aiogram.types import BotCommandScopeAllPrivateChats, BotCommandScopeChat, BotCommandScopeDefault

from app.bot_commands import ADMIN_COMMANDS, SHEIKH_COMMANDS, USER_COMMANDS, set_user_commands_for_chat, setup_bot_commands


class FakeBot:
    def __init__(self):
        self.command_calls = []
        self.menu_calls = []

    async def set_my_commands(self, commands, scope):
        self.command_calls.append((commands, scope))

    async def set_chat_menu_button(self, **kwargs):
        self.menu_calls.append(kwargs)


def _command_names(commands):
    return [command.command for command in commands]


@pytest.mark.asyncio
async def test_setup_bot_commands_keeps_regular_private_scope_user_only():
    bot = FakeBot()

    await setup_bot_commands(bot, admin_ids={100}, sheikh_ids={200})

    default_commands, default_scope = bot.command_calls[0]
    private_commands, private_scope = bot.command_calls[1]
    admin_commands, admin_scope = bot.command_calls[2]
    sheikh_commands, sheikh_scope = bot.command_calls[3]

    assert isinstance(default_scope, BotCommandScopeDefault)
    assert isinstance(private_scope, BotCommandScopeAllPrivateChats)
    assert _command_names(default_commands) == _command_names(USER_COMMANDS)
    assert _command_names(private_commands) == _command_names(USER_COMMANDS)
    assert isinstance(admin_scope, BotCommandScopeChat)
    assert admin_scope.chat_id == 100
    assert _command_names(admin_commands) == _command_names(ADMIN_COMMANDS)
    assert isinstance(sheikh_scope, BotCommandScopeChat)
    assert sheikh_scope.chat_id == 200
    assert _command_names(sheikh_commands) == _command_names(SHEIKH_COMMANDS)


@pytest.mark.asyncio
async def test_set_user_commands_for_chat_overrides_stale_admin_menu():
    bot = FakeBot()

    await set_user_commands_for_chat(bot, user_id=555)

    commands, scope = bot.command_calls[0]
    assert isinstance(scope, BotCommandScopeChat)
    assert scope.chat_id == 555
    assert _command_names(commands) == ['start', 'new', 'my', 'language', 'help']
