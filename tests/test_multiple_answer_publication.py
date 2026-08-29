from types import SimpleNamespace

import pytest

from app.database import Database
from app.handlers.admin import admin_publish_all_answers, admin_publish_answer, answer_access_error


class FakeSentMessage:
    def __init__(self, message_id: int):
        self.message_id = message_id


class FakeBot:
    def __init__(self):
        self.calls: list[tuple] = []

    async def send_message(self, chat_id, text, **kwargs):
        self.calls.append(('message', chat_id, text, kwargs))
        return FakeSentMessage(len(self.calls))


class FakeCallbackMessage:
    def __init__(self):
        self.answers: list[str] = []
        self.edits: list[tuple] = []

    async def answer(self, text, **kwargs):
        self.answers.append(text)

    async def edit_text(self, text, **kwargs):
        self.edits.append((text, kwargs))


class FakeCallback:
    def __init__(self, data: str, *, admin_id: int = 900):
        self.data = data
        self.from_user = SimpleNamespace(id=admin_id)
        self.bot = FakeBot()
        self.message = FakeCallbackMessage()
        self.callback_answers: list[tuple] = []

    async def answer(self, text=None, **kwargs):
        self.callback_answers.append((text, kwargs))


async def create_ticket_with_two_answers(db: Database) -> tuple[int, int, int]:
    ticket_id = await db.create_ticket(
        user_id=100,
        username='asker',
        full_name='Asker',
        category='fiqh',
        language='ru',
    )
    await db.add_message(
        ticket_id=ticket_id,
        sender_type='user',
        sender_id=100,
        text='Можно ли так делать?',
        content_type='text',
    )
    first_answer_id = await db.add_message(
        ticket_id=ticket_id,
        sender_type='admin',
        sender_id=900,
        text='Первая часть ответа.',
        content_type='text',
    )
    second_answer_id = await db.add_message(
        ticket_id=ticket_id,
        sender_type='admin',
        sender_id=900,
        text='Вторая часть ответа.',
        content_type='text',
    )
    await db.set_status(ticket_id, 'answered')
    return ticket_id, first_answer_id, second_answer_id


def test_only_regular_admin_can_add_answers_after_first_answer_or_publication():
    assert answer_access_error('open', sheikh_role=False) is None
    assert answer_access_error('answered', sheikh_role=False) is None
    assert answer_access_error('published', sheikh_role=False) is None
    assert answer_access_error('closed', sheikh_role=False) is not None

    assert answer_access_error('open', sheikh_role=True) is None
    assert answer_access_error('answered', sheikh_role=True) is not None
    assert answer_access_error('published', sheikh_role=True) is not None


@pytest.mark.asyncio
async def test_admin_can_publish_one_selected_answer(tmp_path):
    db = Database(str(tmp_path / 'support_bot.db'))
    await db.init()
    ticket_id, first_answer_id, second_answer_id = await create_ticket_with_two_answers(db)
    callback = FakeCallback(f'admin:publish:{second_answer_id}')

    await admin_publish_answer(
        callback,
        db,
        {900},
        publication_channel='@answers',
    )

    assert len(callback.bot.calls) == 1
    assert 'ВОПРОС ❓' in callback.bot.calls[0][2]
    assert 'ПРОДОЛЖЕНИЕ ОТВЕТА' not in callback.bot.calls[0][2]
    pending = await db.list_ticket_answers_for_publication(ticket_id, status='answered')
    assert [row['message_id'] for row in pending] == [first_answer_id]
    assert pending[0]['published_answer_count'] == 1
    assert (await db.get_ticket(ticket_id))['status'] == 'answered'

    continuation_callback = FakeCallback(f'admin:publish:{first_answer_id}')
    await admin_publish_answer(
        continuation_callback,
        db,
        {900},
        publication_channel='@answers',
    )

    assert len(continuation_callback.bot.calls) == 1
    assert 'ПРОДОЛЖЕНИЕ ОТВЕТА К ВОПРОСУ ❓' in continuation_callback.bot.calls[0][2]
    assert (await db.get_ticket(ticket_id))['status'] == 'published'


@pytest.mark.asyncio
async def test_admin_can_publish_all_answers_as_separate_ordered_posts(tmp_path):
    db = Database(str(tmp_path / 'support_bot.db'))
    await db.init()
    ticket_id, _, _ = await create_ticket_with_two_answers(db)
    callback = FakeCallback(f'admin:publish_all:{ticket_id}')

    await admin_publish_all_answers(
        callback,
        db,
        {900},
        publication_channel='@answers',
    )

    assert len(callback.bot.calls) == 2
    assert 'Первая часть ответа.' in callback.bot.calls[0][2]
    assert 'ВОПРОС ❓' in callback.bot.calls[0][2]
    assert 'Вторая часть ответа.' in callback.bot.calls[1][2]
    assert 'ПРОДОЛЖЕНИЕ ОТВЕТА К ВОПРОСУ ❓' in callback.bot.calls[1][2]
    assert await db.list_ticket_answers_for_publication(ticket_id, status='answered') == []
    assert len(await db.list_ticket_answers_for_publication(ticket_id, status='published')) == 2
    assert (await db.get_ticket(ticket_id))['status'] == 'published'
