import pytest

from app.database import Database


@pytest.mark.asyncio
async def test_admin_answer_history_contains_admin_and_question_data(tmp_path):
    db = Database(str(tmp_path / 'support_bot.db'))
    await db.init()

    await db.upsert_user(user_id=100, username='user100', full_name='Regular User', language='ru')
    await db.upsert_user(user_id=200, username='admin200', full_name='Sheikh Admin', language='ru')

    ticket_id = await db.create_ticket(
        user_id=100,
        username='user100',
        full_name='Regular User',
        category='quran_hadith',
        language='ru',
    )
    await db.add_message(
        ticket_id=ticket_id,
        sender_type='user',
        sender_id=100,
        text='Что такое хадис?',
        content_type='text',
    )
    await db.add_message(
        ticket_id=ticket_id,
        sender_type='admin',
        sender_id=200,
        text='Хадис — это сообщение о словах, делах или одобрении Пророка ﷺ.',
        content_type='text',
    )
    await db.set_status(ticket_id, 'answered')

    rows = await db.list_admin_answers(limit=10)
    assert len(rows) == 1
    row = rows[0]
    assert row['ticket_id'] == ticket_id
    assert row['admin_id'] == 200
    assert row['admin_username'] == 'admin200'
    assert row['user_id'] == 100
    assert row['user_username'] == 'user100'
    assert row['category'] == 'quran_hadith'


@pytest.mark.asyncio
async def test_admin_answer_history_contains_original_question_text_and_pagination(tmp_path):
    db = Database(str(tmp_path / 'support_bot.db'))
    await db.init()

    await db.upsert_user(user_id=101, username='user101', full_name='User One', language='ru')
    await db.upsert_user(user_id=201, username='admin201', full_name='Admin One', language='ru')

    ids = []
    for i in range(3):
        ticket_id = await db.create_ticket(
            user_id=101,
            username='user101',
            full_name='User One',
            category='fiqh',
            language='ru',
        )
        ids.append(ticket_id)
        await db.add_message(
            ticket_id=ticket_id,
            sender_type='user',
            sender_id=101,
            text=f'Вопрос пользователя номер {i}',
            content_type='text',
        )
        await db.add_message(
            ticket_id=ticket_id,
            sender_type='admin',
            sender_id=201,
            text=f'Ответ админа номер {i}',
            content_type='text',
        )

    assert await db.count_admin_answers() == 3
    first_page = await db.list_admin_answers(limit=2, offset=0)
    second_page = await db.list_admin_answers(limit=2, offset=2)

    assert len(first_page) == 2
    assert len(second_page) == 1
    assert first_page[0]['question_text'].startswith('Вопрос пользователя номер')
    assert first_page[0]['answer_text'].startswith('Ответ админа номер')

@pytest.mark.asyncio
async def test_get_admin_answer_returns_full_texts(tmp_path):
    db = Database(str(tmp_path / 'support_bot.db'))
    await db.init()

    await db.upsert_user(user_id=111, username='asker', full_name='Asker', language='ru')
    await db.upsert_user(user_id=222, username='sheikh', full_name='Sheikh', language='ru')
    ticket_id = await db.create_ticket(
        user_id=111,
        username='asker',
        full_name='Asker',
        category='aqida',
        language='ru',
    )
    long_question = 'Полный длинный вопрос ' * 80
    long_answer = 'Полный длинный ответ ' * 80
    await db.add_message(ticket_id=ticket_id, sender_type='user', sender_id=111, text=long_question, content_type='text')
    await db.add_message(ticket_id=ticket_id, sender_type='admin', sender_id=222, text=long_answer, content_type='text')

    rows = await db.list_admin_answers(limit=1)
    full = await db.get_admin_answer(rows[0]['message_id'])

    assert full is not None
    assert full['question_text'] == long_question
    assert full['answer_text'] == long_answer
    assert full['admin_username'] == 'sheikh'
