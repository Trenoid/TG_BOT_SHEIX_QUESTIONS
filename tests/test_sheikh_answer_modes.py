from types import SimpleNamespace

import pytest

from app.database import Database
from app.handlers.admin import _show_sheikh_question, admin_send_answer, sheikh_answer_start


class FakeSentMessage:
    def __init__(self, message_id: int):
        self.message_id = message_id


class FakeBot:
    def __init__(self):
        self.calls: list[tuple] = []

    async def send_message(self, chat_id, text, **kwargs):
        self.calls.append(('message', chat_id, text, kwargs))
        return FakeSentMessage(len(self.calls))

    async def copy_message(self, chat_id, from_chat_id, message_id, **kwargs):
        self.calls.append(('copy', chat_id, from_chat_id, message_id, kwargs))
        return FakeSentMessage(len(self.calls))

    async def edit_message_reply_markup(self, **kwargs):
        self.calls.append(('edit_markup', kwargs))

    async def edit_message_text(self, text, **kwargs):
        self.calls.append(('edit_text', text, kwargs))


class FakeState:
    def __init__(self, data: dict):
        self.data = data
        self.cleared = False

    async def get_data(self):
        return dict(self.data)

    async def set_state(self, state):
        self.state = state

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def clear(self):
        self.cleared = True


class FakeAnswerMessage:
    def __init__(self, bot: FakeBot, text: str = 'Ответ шейха'):
        self.bot = bot
        self.from_user = SimpleNamespace(id=20, username='sheikh', full_name='Шейх')
        self.chat = SimpleNamespace(id=20)
        self.message_id = 700
        self.text = text
        self.caption = None
        self.content_type = 'text'
        self.photo = None
        self.document = None
        self.video = None
        self.voice = None
        self.audio = None
        self.sticker = None
        self.answers: list[tuple] = []

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs))
        return FakeSentMessage(len(self.answers))


class FakeCallbackMessage:
    def __init__(self):
        self.chat = SimpleNamespace(id=20)
        self.message_id = 600
        self.edits: list[tuple] = []
        self.answers: list[tuple] = []

    async def edit_text(self, text, **kwargs):
        self.edits.append((text, kwargs))

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs))
        return FakeSentMessage(len(self.answers))


class FakeCallback:
    def __init__(self, data: str):
        self.data = data
        self.from_user = SimpleNamespace(id=20)
        self.message = FakeCallbackMessage()
        self.callback_answers: list[tuple] = []

    async def answer(self, text=None, **kwargs):
        self.callback_answers.append((text, kwargs))


async def _create_ticket(db: Database, question: str = 'Полный вопрос') -> int:
    await db.upsert_user(user_id=100, username='asker', full_name='Asker', language='ru')
    ticket_id = await db.create_ticket(
        user_id=100,
        username='asker',
        full_name='Asker',
        category='aqida',
        language='ru',
    )
    await db.add_message(
        ticket_id=ticket_id,
        sender_type='user',
        sender_id=100,
        text=question,
        content_type='text',
    )
    return ticket_id


@pytest.mark.asyncio
async def test_long_question_is_fully_sent_to_sheikh_from_panel():
    start = 'НАЧАЛО '
    end = ' КОНЕЦ ВОПРОСА'
    question = start + ('а' * (4096 - len(start) - len(end))) + end
    callback = SimpleNamespace(message=FakeCallbackMessage())
    ticket = {'id': 7}
    messages = [{'sender_type': 'user', 'text': question, 'content_type': 'text', 'file_id': None}]

    await _show_sheikh_question(callback, ticket, messages)

    assert 'Полный текст вопроса' in callback.message.edits[0][0]
    assert ''.join(text for text, _ in callback.message.answers) == question
    assert callback.message.answers[-1][1]['reply_markup'] is not None
    assert callback.message.answers[-1][1]['parse_mode'] is None


@pytest.mark.asyncio
@pytest.mark.parametrize('answer_mode', ['publish', 'private'])
async def test_sheikh_answer_button_stores_selected_mode(tmp_path, answer_mode):
    db = Database(str(tmp_path / 'support_bot.db'))
    await db.init()
    ticket_id = await _create_ticket(db)
    callback = FakeCallback(f'sheikh:answer:{answer_mode}:{ticket_id}')
    state = FakeState({})

    await sheikh_answer_start(
        callback,
        state,
        db,
        admin_ids=set(),
        sheikh_ids={20},
    )

    assert state.data['ticket_id'] == ticket_id
    assert state.data['answer_mode'] == answer_mode
    assert callback.message.answers
    expected = 'опубликован' if answer_mode == 'publish' else 'только автор'
    assert expected in callback.message.answers[0][0]


@pytest.mark.asyncio
async def test_private_sheikh_answer_is_only_sent_to_user(tmp_path):
    db = Database(str(tmp_path / 'support_bot.db'))
    await db.init()
    ticket_id = await _create_ticket(db)
    bot = FakeBot()
    message = FakeAnswerMessage(bot)
    state = FakeState({
        'ticket_id': ticket_id,
        'source_chat_id': None,
        'source_message_id': None,
        'answer_mode': 'private',
    })

    await admin_send_answer(
        message,
        state,
        db,
        admin_ids=set(),
        sheikh_ids={20},
        publication_channel='@main_channel',
    )

    assert state.cleared is True
    assert all(call[1] == 100 for call in bot.calls if call[0] in {'message', 'copy'})
    assert not any(call[1] == '@main_channel' for call in bot.calls if call[0] == 'message')
    rows = await db.list_admin_answers(limit=10)
    assert rows[0]['publication_status'] == 'private'
    assert await db.list_sheikh_answers_for_publication(status='answered') == []
    assert (await db.get_ticket(ticket_id))['status'] == 'answered'
    assert any('не опубликован в канал' in text for text, _ in message.answers)

    await db.init()
    assert (await db.get_ticket(ticket_id))['status'] == 'answered'


@pytest.mark.asyncio
async def test_public_sheikh_answer_is_sent_to_main_channel(tmp_path):
    db = Database(str(tmp_path / 'support_bot.db'))
    await db.init()
    ticket_id = await _create_ticket(db)
    bot = FakeBot()
    message = FakeAnswerMessage(bot)
    state = FakeState({
        'ticket_id': ticket_id,
        'source_chat_id': None,
        'source_message_id': None,
        'answer_mode': 'publish',
    })

    await admin_send_answer(
        message,
        state,
        db,
        admin_ids=set(),
        sheikh_ids={20},
        publication_channel='@main_channel',
    )

    channel_messages = [call for call in bot.calls if call[0] == 'message' and call[1] == '@main_channel']
    assert len(channel_messages) == 1
    assert 'Ответ шейха' in channel_messages[0][2]
    rows = await db.list_admin_answers(limit=10)
    assert rows[0]['publication_status'] == 'published'
    assert (await db.get_ticket(ticket_id))['status'] == 'published'
