import pytest

from app.database import Database
from app.handlers.user import _question_access_error
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
async def test_question_cooldown_exemption_allows_repeated_questions_but_not_blocks(tmp_path):
    db = Database(str(tmp_path / 'support_bot.db'))
    await db.init()

    first_ticket_id, _ = await db.create_ticket_with_cooldown(
        user_id=731354094,
        username='owner',
        full_name='Owner',
        category='other',
        language='ru',
        question_language='ru',
    )
    assert first_ticket_id is not None
    assert await _question_access_error(db, 731354094, 'ru', {731354094}) is None

    second_ticket_id, remaining = await db.create_ticket_with_cooldown(
        user_id=731354094,
        username='owner',
        full_name='Owner',
        category='other',
        language='ru',
        question_language='ru',
        interval_seconds=0,
    )
    assert second_ticket_id is not None
    assert remaining == 0

    await db.block_user(731354094, blocked_by=100, duration_seconds=86400)
    assert await _question_access_error(db, 731354094, 'ru', {731354094}) is not None


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
    assert question_matches_selected_language('Вопрос 1: как держать пост?', 'ru') is True
    assert question_matches_selected_language('hello', 'ru') is False


def test_ingush_text_with_digit_one_is_not_accepted_as_russian():
    text = '''
    Ассаламу алейкум
    Цхьа хаттар дар са
    Кхори гаьна херх хьакх мегаш бий, бусулба дын оаг1ора? Миштад из хьакхар?
    Нах ба вайн яхаш, кхори гаьна херх хьакхачул т1ехьаг1а, саг къелуг ва яхаш къа хул яхаш.
    Бакъ да из? Е Харц да из?
    Есть ещё один вопрос
    Борз зе деш ели а, еци а. Берза топ техачул т1ехьаг1а, из саг даькъаз ваг ва яхар бакъ ди?
    Нах дукх къамаьлаш дувц. Дын оаг1ара миштад из? Хьайн ховр ал сог.
    '''
    assert question_matches_selected_language(text, 'inh') is True
    assert question_matches_selected_language(text, 'ru') is False
