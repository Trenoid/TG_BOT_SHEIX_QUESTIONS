import pytest

from app.database import Database
from app.services import question_matches_selected_language


@pytest.mark.asyncio
async def test_question_cooldown_survives_spam_ticket_deletion(tmp_path):
    db = Database(str(tmp_path / 'support_bot.db'))
    await db.init()

    ticket_id, remaining = await db.create_ticket_with_cooldown(
        user_id=100,
        username='asker',
        full_name='Asker',
        category='other',
        language='ru',
        question_language='inh',
    )
    assert ticket_id is not None
    assert remaining == 0
    ticket = await db.get_ticket(ticket_id)
    assert ticket['question_language'] == 'inh'

    await db.add_staff_notification(ticket_id, 10, 20)
    assert await db.delete_ticket(ticket_id) is True
    assert await db.get_ticket(ticket_id) is None
    assert await db.list_staff_notifications(ticket_id) == []

    second_ticket_id, remaining = await db.create_ticket_with_cooldown(
        user_id=100,
        username='asker',
        full_name='Asker',
        category='other',
        language='ru',
        question_language='ru',
    )
    assert second_ticket_id is None
    assert 3500 <= remaining <= 3600


@pytest.mark.asyncio
async def test_temporary_and_forever_user_blocks(tmp_path):
    db = Database(str(tmp_path / 'support_bot.db'))
    await db.init()

    await db.block_user(100, blocked_by=10, duration_seconds=86400)
    temporary = await db.get_active_block(100)
    assert temporary is not None
    assert temporary['blocked_until'] is not None

    await db.block_user(100, blocked_by=10, duration_seconds=None)
    forever = await db.get_active_block(100)
    assert forever is not None
    assert forever['blocked_until'] is None
    blocks = await db.list_active_blocks()
    assert [block['user_id'] for block in blocks] == [100]

    await db.unblock_user(100)
    assert await db.get_active_block(100) is None
    assert await db.list_active_blocks() == []


@pytest.mark.asyncio
async def test_expired_user_block_is_removed_automatically(tmp_path):
    db = Database(str(tmp_path / 'support_bot.db'))
    await db.init()
    await db.block_user(100, blocked_by=10, duration_seconds=-1)
    assert await db.get_active_block(100) is None


def test_non_ai_question_language_check_is_conservative():
    assert question_matches_selected_language('Можно ли так делать?', 'ru') is True
    assert question_matches_selected_language('Можно ли так делать?', 'inh') is False
    assert question_matches_selected_language('Как держать пост?', 'inh') is False
    assert question_matches_selected_language('Со хулда воалавалар деза аз?', 'inh') is True
    assert question_matches_selected_language('ГӀалгӀай мотт', 'ru') is False
    assert question_matches_selected_language('Можно ли произносить «ГӀалгӀай мотт»?', 'ru') is True
    assert question_matches_selected_language('Акыда', 'inh') is True
    assert question_matches_selected_language('hello', 'ru') is False
