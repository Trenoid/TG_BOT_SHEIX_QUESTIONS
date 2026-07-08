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


@pytest.mark.asyncio
async def test_sheikh_answers_move_from_publication_queue_to_published(tmp_path):
    db = Database(str(tmp_path / 'support_bot.db'))
    await db.init()

    await db.upsert_user(user_id=300, username='asker300', full_name='Asker 300', language='ru')
    await db.upsert_user(user_id=400, username='sheikh400', full_name='Sheikh Isa', language='ru')

    ticket_id = await db.create_ticket(
        user_id=300,
        username='asker300',
        full_name='Asker 300',
        category='fiqh',
        language='ru',
    )
    await db.add_message(
        ticket_id=ticket_id,
        sender_type='user',
        sender_id=300,
        text='Можно ли вернуть товар?',
        content_type='text',
    )
    first_answer_id = await db.add_message(
        ticket_id=ticket_id,
        sender_type='sheikh',
        sender_id=400,
        text='Первый ответ.',
        content_type='text',
    )
    latest_answer_id = await db.add_message(
        ticket_id=ticket_id,
        sender_type='sheikh',
        sender_id=400,
        text='Последний ответ.',
        content_type='text',
    )
    await db.set_status(ticket_id, 'answered')

    assert first_answer_id != latest_answer_id
    rows = await db.list_sheikh_answers_for_publication(status='answered')
    assert len(rows) == 1
    assert rows[0]['message_id'] == latest_answer_id
    assert rows[0]['answer_text'] == 'Последний ответ.'
    assert await db.count_sheikh_answers_for_publication(status='answered') == 1

    await db.set_status(ticket_id, 'published')
    assert await db.list_sheikh_answers_for_publication(status='answered') == []
    published = await db.list_sheikh_answers_for_publication(status='published')
    assert len(published) == 1
    assert published[0]['message_id'] == latest_answer_id


@pytest.mark.asyncio
async def test_admin_answers_are_available_for_publication(tmp_path):
    db = Database(str(tmp_path / 'support_bot.db'))
    await db.init()

    await db.upsert_user(user_id=301, username='asker301', full_name='Asker 301', language='ru')
    await db.upsert_user(user_id=401, username='admin401', full_name='Admin 401', language='ru')

    ticket_id = await db.create_ticket(
        user_id=301,
        username='asker301',
        full_name='Asker 301',
        category='fiqh',
        language='ru',
    )
    await db.add_message(
        ticket_id=ticket_id,
        sender_type='user',
        sender_id=301,
        text='Новый вопрос',
        content_type='text',
    )
    answer_id = await db.add_message(
        ticket_id=ticket_id,
        sender_type='admin',
        sender_id=401,
        text='Ответ администратора',
        content_type='text',
    )
    await db.set_status(ticket_id, 'answered')

    rows = await db.list_sheikh_answers_for_publication(status='answered')
    assert len(rows) == 1
    assert rows[0]['message_id'] == answer_id
    assert rows[0]['answer_sender_type'] == 'admin'

    row = await db.get_sheikh_answer_for_publication(answer_id)
    assert row is not None
    assert row['answer_text'] == 'Ответ администратора'
