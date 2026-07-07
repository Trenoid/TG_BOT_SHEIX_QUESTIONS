import pytest

from app.database import Database
from app.keyboards import admin_answer_full_kb
from app.services import admin_answer_full_text, admin_answers_history_text, content_type_label, normalize_content_type_value


def _callback_data(markup):
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def test_content_type_normalizes_aiogram_enum_string():
    assert normalize_content_type_value('ContentType.VOICE') == 'voice'
    assert content_type_label('ContentType.VOICE') == '🎙 Голосовое сообщение'


@pytest.mark.asyncio
async def test_voice_answer_history_has_file_id_and_human_label(tmp_path):
    db = Database(str(tmp_path / 'support_bot.db'))
    await db.init()
    await db.upsert_user(user_id=10, username='asker', full_name='Asker', language='ru')
    await db.upsert_user(user_id=20, username='sheikh', full_name='Sheikh', language='ru')
    ticket_id = await db.create_ticket(user_id=10, username='asker', full_name='Asker', category='fiqh', language='ru')
    await db.add_message(ticket_id=ticket_id, sender_type='user', sender_id=10, text=None, content_type='voice', file_id='voice_question_file_id')
    await db.add_message(ticket_id=ticket_id, sender_type='admin', sender_id=20, text=None, content_type='voice', file_id='voice_answer_file_id')

    rows = await db.list_admin_answers(limit=1)
    assert rows[0]['question_file_id'] == 'voice_question_file_id'
    assert rows[0]['answer_file_id'] == 'voice_answer_file_id'
    assert '🎙 Голосовое сообщение' in admin_answers_history_text(rows)

    full = await db.get_admin_answer(rows[0]['message_id'])
    text = admin_answer_full_text(full)
    assert '[ContentType.VOICE]' not in text
    assert '🎙 Голосовое сообщение' in text
    assert 'Оригинал вложения доступен кнопкой' in text


def test_full_answer_keyboard_has_media_buttons():
    markup = admin_answer_full_kb(
        ticket_id=1,
        page=0,
        answer_message_id=44,
        has_question_media=True,
        has_answer_media=True,
    )
    callbacks = _callback_data(markup)
    assert 'admin:send_media:44:question' in callbacks
    assert 'admin:send_media:44:answer' in callbacks
