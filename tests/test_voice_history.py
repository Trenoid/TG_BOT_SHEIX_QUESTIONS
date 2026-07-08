import pytest

from app.database import Database
from app.keyboards import admin_answer_full_kb
from app.services import answer_prompt_text, admin_answer_full_text, admin_answers_history_text, content_type_label, is_text_question_content, normalize_content_type_value, publication_text, user_answer_intro_text


def _callback_data(markup):
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def test_content_type_normalizes_aiogram_enum_string():
    assert normalize_content_type_value('ContentType.VOICE') == 'voice'
    assert content_type_label('ContentType.VOICE') == '🎙 Голосовое сообщение'


def test_user_questions_accept_only_plain_text():
    assert is_text_question_content('text', 'Вопрос текстом') is True
    assert is_text_question_content('voice', None) is False
    assert is_text_question_content('photo', 'caption should not count') is False
    assert is_text_question_content('text', '   ') is False


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


def test_publication_text_matches_channel_shape():
    row = {
        'ticket_id': 723,
        'category': 'fiqh',
        'question_text': 'Ас-Саляму алейкум уа рахматулЛахи уа баракатух',
        'question_content_type': 'text',
        'question_file_id': None,
        'answer_text': 'Уа алейкум ассалям. Ответ шейха.',
        'content_type': 'text',
        'answer_file_id': None,
    }

    text = publication_text(row, publication_channel='@answers_channel')

    assert 'Ответы на вопросы | Шейх Абдул-Малик Хайров' in text
    assert 'ВОПРОС ❓ №723' in text
    assert 'ОТВЕТ✅:' in text
    assert 'Прослушать на русском' not in text
    assert 'https://t.me/answers_channel' in text


def test_publication_voice_answer_has_clean_media_label():
    row = {
        'ticket_id': 14,
        'category': 'fiqh',
        'question_text': 'вопрос вопрос',
        'question_content_type': 'text',
        'question_file_id': None,
        'answer_text': None,
        'content_type': 'voice',
        'answer_file_id': 'voice_file_id',
    }

    text = publication_text(row, publication_channel='https://t.me/test_channel_questions')

    assert '🎙 Голосовое сообщение' in text
    assert 'Оригинал вложения доступен' not in text
    assert '<a href="https://t.me/test_channel_questions">Ответы Шейха</a>' in text


def test_answer_prompt_contains_question_text_without_question_number():
    ticket = {'id': 6}
    messages = [{
        'sender_type': 'user',
        'text': 'Тестовый вопрос про финансы',
        'content_type': 'text',
        'file_id': None,
    }]

    text = answer_prompt_text(ticket, messages)

    assert 'Напишите ответ для вопроса' in text
    assert 'Тестовый вопрос про финансы' in text
    assert '#6' not in text
    assert '№6' not in text


def test_user_answer_intro_contains_original_question_without_number():
    ticket = {'id': 21}
    messages = [{
        'sender_type': 'user',
        'text': 'акыда',
        'content_type': 'text',
        'file_id': None,
    }]

    text = user_answer_intro_text(ticket, messages)

    assert 'Ответ на ваш вопрос' in text
    assert 'акыда' in text
    assert '#21' not in text
    assert '№21' not in text
