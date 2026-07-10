import pytest

from app.database import Database
from app.services import notify_staff_about_ticket


class DummyChat:
    id = 900
    type = 'private'


class DummyUser:
    id = 100
    username = 'asker'
    full_name = 'Asker'


class DummyMessage:
    chat = DummyChat()
    from_user = DummyUser()
    message_id = 55
    text = 'Тестовый вопрос'
    caption = None
    content_type = 'text'
    photo = None
    document = None
    video = None
    voice = None
    audio = None
    sticker = None


class FakeBot:
    def __init__(self, *, fail_send_to=None):
        self.fail_send_to = set(fail_send_to or set())
        self.sent_messages = []
        self.copied_messages = []

    async def send_message(self, chat_id, text, **kwargs):
        if chat_id in self.fail_send_to:
            raise RuntimeError(f'cannot send to {chat_id}')
        self.sent_messages.append((chat_id, text, kwargs))

    async def copy_message(self, chat_id, from_chat_id, message_id):
        self.copied_messages.append((chat_id, from_chat_id, message_id))


async def _create_ticket(db: Database) -> int:
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
        text='Тестовый вопрос',
        content_type='text',
    )
    return ticket_id


@pytest.mark.asyncio
async def test_new_ticket_is_sent_to_all_sheikhs(tmp_path):
    db = Database(str(tmp_path / 'support_bot.db'))
    await db.init()
    ticket_id = await _create_ticket(db)
    bot = FakeBot()

    await notify_staff_about_ticket(
        bot,
        db,
        admin_ids={10},
        sheikh_ids={20, 30},
        ticket_id=ticket_id,
        user_message=DummyMessage(),
    )

    recipients = [chat_id for chat_id, _, _ in bot.sent_messages]
    assert recipients == [10, 20, 30]
    assert any('Вопрос №1' in text for chat_id, text, _ in bot.sent_messages if chat_id == 20)
    assert any('Вопрос №1' in text for chat_id, text, _ in bot.sent_messages if chat_id == 30)


@pytest.mark.asyncio
async def test_failed_sheikh_delivery_does_not_block_other_sheikhs(tmp_path):
    db = Database(str(tmp_path / 'support_bot.db'))
    await db.init()
    ticket_id = await _create_ticket(db)
    bot = FakeBot(fail_send_to={20})

    await notify_staff_about_ticket(
        bot,
        db,
        admin_ids=set(),
        sheikh_ids={20, 30},
        ticket_id=ticket_id,
        user_message=DummyMessage(),
    )

    recipients = [chat_id for chat_id, _, _ in bot.sent_messages]
    assert recipients == [30]
