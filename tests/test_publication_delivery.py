import pytest

from app.handlers.admin import _send_publication_to_channel
from app.services import send_answer_media_preview


class FakeBot:
    def __init__(self):
        self.calls = []

    async def send_message(self, chat_id, text):
        self.calls.append(('message', chat_id, text))

    async def send_voice(self, chat_id, file_id, caption=None):
        self.calls.append(('voice', chat_id, file_id, caption))

    async def send_audio(self, chat_id, file_id, caption=None):
        self.calls.append(('audio', chat_id, file_id, caption))

    async def send_photo(self, chat_id, file_id, caption=None):
        self.calls.append(('photo', chat_id, file_id, caption))

    async def send_video(self, chat_id, file_id, caption=None):
        self.calls.append(('video', chat_id, file_id, caption))

    async def send_document(self, chat_id, file_id, caption=None):
        self.calls.append(('document', chat_id, file_id, caption))

    async def send_sticker(self, chat_id, file_id):
        self.calls.append(('sticker', chat_id, file_id))


class FakeCallback:
    def __init__(self):
        self.bot = FakeBot()


def _row(answer_text: str) -> dict:
    return {
        'ticket_id': 5,
        'category': 'ibadah',
        'question_text': 'Как правильно держать пост?',
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
    assert 'Ответы на вопросы' in callback.bot.calls[0][3]


@pytest.mark.asyncio
async def test_long_publication_sends_post_before_voice():
    callback = FakeCallback()

    await _send_publication_to_channel(callback.bot, _row('Длинный ответ. ' * 120), publication_channel='@channel')

    assert callback.bot.calls[0][0] == 'message'
    assert callback.bot.calls[-1][0] == 'voice'
    assert callback.bot.calls[-1][2] == 'voice_file_id'


@pytest.mark.asyncio
async def test_answer_media_preview_sends_voice_to_admin_chat():
    bot = FakeBot()

    sent = await send_answer_media_preview(bot, 12345, _row('Короткий ответ.'))

    assert sent is True
    assert bot.calls[0][0] == 'voice'
    assert bot.calls[0][1] == 12345
    assert bot.calls[0][2] == 'voice_file_id'
    assert 'Оригинал ответа шейха' in bot.calls[0][3]
