import pytest

from app.handlers.admin import _send_publication_to_channel
from app.services import send_answer_media_preview


class FakeMessage:
    def __init__(self, message_id):
        self.message_id = message_id


class FakeChat:
    def __init__(self, linked_chat_id=None):
        self.linked_chat_id = linked_chat_id


class FakeBot:
    def __init__(self, *, linked_chat_id=None, fail_message_to=None):
        self.calls = []
        self.linked_chat_id = linked_chat_id
        self.fail_message_to = set(fail_message_to or set())

    async def get_chat(self, chat_id):
        return FakeChat(self.linked_chat_id)

    async def send_message(self, chat_id, text, **kwargs):
        if chat_id in self.fail_message_to:
            raise RuntimeError(f'cannot send to {chat_id}')
        self.calls.append(('message', chat_id, text, kwargs))
        return FakeMessage(len(self.calls))

    async def edit_message_caption(self, chat_id, message_id, caption):
        self.calls.append(('edit_caption', chat_id, message_id, caption))

    async def send_voice(self, chat_id, file_id, caption=None):
        self.calls.append(('voice', chat_id, file_id, caption))
        return FakeMessage(len(self.calls))

    async def send_audio(self, chat_id, file_id, caption=None):
        self.calls.append(('audio', chat_id, file_id, caption))
        return FakeMessage(len(self.calls))

    async def send_photo(self, chat_id, file_id, caption=None):
        self.calls.append(('photo', chat_id, file_id, caption))
        return FakeMessage(len(self.calls))

    async def send_video(self, chat_id, file_id, caption=None):
        self.calls.append(('video', chat_id, file_id, caption))
        return FakeMessage(len(self.calls))

    async def send_document(self, chat_id, file_id, caption=None):
        self.calls.append(('document', chat_id, file_id, caption))
        return FakeMessage(len(self.calls))

    async def send_sticker(self, chat_id, file_id):
        self.calls.append(('sticker', chat_id, file_id))
        return FakeMessage(len(self.calls))


class FakeCallback:
    def __init__(self):
        self.bot = FakeBot()


def _row(answer_text: str | None, *, question_text: str = 'Как правильно держать пост?') -> dict:
    return {
        'ticket_id': 5,
        'category': 'ibadah',
        'question_text': question_text,
        'question_content_type': 'text',
        'question_file_id': None,
        'answer_text': answer_text,
        'content_type': 'voice',
        'answer_file_id': 'voice_file_id',
    }


@pytest.mark.asyncio
async def test_short_publication_is_sent_together_as_voice_caption():
    callback = FakeCallback()

    await _send_publication_to_channel(callback.bot, _row('Короткий ответ.'), publication_channel='@channel')

    assert len(callback.bot.calls) == 1
    assert callback.bot.calls[0][0] == 'voice'
    assert 'Ответы Шейха' in callback.bot.calls[0][3]


@pytest.mark.asyncio
async def test_long_voice_publication_is_sent_as_single_caption_message():
    callback = FakeCallback()

    await _send_publication_to_channel(
        callback.bot,
        _row(None, question_text='Длинный вопрос. ' * 160),
        publication_channel='@channel',
    )

    assert len(callback.bot.calls) == 1
    assert callback.bot.calls[0][0] == 'voice'
    assert callback.bot.calls[0][2] == 'voice_file_id'
    assert len(callback.bot.calls[0][3]) <= 1024
    assert 'Ответы Шейха' in callback.bot.calls[0][3]


@pytest.mark.asyncio
async def test_long_voice_publication_moves_question_remainder_to_comments():
    bot = FakeBot(linked_chat_id=-100777)
    question = ('Длинный вопрос с подробностями. ' * 80) + 'ФИНАЛЬНАЯ ЧАСТЬ ВОПРОСА'

    await _send_publication_to_channel(
        bot,
        _row(None, question_text=question),
        publication_channel='@channel',
    )

    assert bot.calls[0][0] == 'voice'
    assert len(bot.calls[0][3]) <= 800
    assert 'Продолжение вопроса' in bot.calls[0][3]

    comment = bot.calls[1]
    assert comment[0] == 'message'
    assert comment[1] == -100777
    assert 'Продолжение вопроса №5' in comment[2]
    assert 'ФИНАЛЬНАЯ ЧАСТЬ ВОПРОСА' in comment[2]
    assert comment[3]['reply_to_message_id'] == 1


@pytest.mark.asyncio
async def test_long_voice_publication_falls_back_to_channel_message_when_comment_fails():
    bot = FakeBot(linked_chat_id=-100777, fail_message_to={-100777})
    question = ('Длинный вопрос с подробностями. ' * 80) + 'ФИНАЛЬНАЯ ЧАСТЬ ВОПРОСА'

    await _send_publication_to_channel(
        bot,
        _row(None, question_text=question),
        publication_channel='@channel',
    )

    assert bot.calls[0][0] == 'voice'

    edit = bot.calls[1]
    assert edit[0] == 'edit_caption'
    assert 'следующим сообщением' in edit[3]

    fallback_message = bot.calls[2]
    assert fallback_message[0] == 'message'
    assert fallback_message[1] == '@channel'
    assert 'Продолжение вопроса №5' in fallback_message[2]
    assert 'ФИНАЛЬНАЯ ЧАСТЬ ВОПРОСА' in fallback_message[2]


@pytest.mark.asyncio
async def test_answer_media_preview_sends_voice_to_admin_chat():
    bot = FakeBot()

    sent = await send_answer_media_preview(bot, 12345, _row('Короткий ответ.'))

    assert sent is True
    assert bot.calls[0][0] == 'voice'
    assert bot.calls[0][1] == 12345
    assert bot.calls[0][2] == 'voice_file_id'
    assert 'Оригинал ответа шейха' in bot.calls[0][3]
