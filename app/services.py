from __future__ import annotations

from aiogram import Bot
from aiogram.types import Message

from app.database import Database
from app.keyboards import admin_ticket_kb
from app.utils import category_name, format_dt, h, language_name, status_name, ticket_title, user_link


def normalize_content_type_value(value: object | None) -> str:
    if value is None:
        return 'message'
    raw = getattr(value, 'value', None) or str(value)
    raw = raw.strip()
    if raw.startswith('ContentType.'):
        raw = raw.split('.', 1)[1]
    return raw.lower()


def message_content_type(message: Message) -> str:
    return normalize_content_type_value(message.content_type)


def _is_placeholder_text(text: str | None, content_type: object | None) -> bool:
    if not text:
        return True
    stripped = text.strip()
    if not stripped:
        return True
    ct = normalize_content_type_value(content_type)
    placeholders = {
        f'[{ct}]',
        f'[contenttype.{ct}]',
        f'[ContentType.{ct.upper()}]',
        '[message]',
    }
    return stripped.lower() in {p.lower() for p in placeholders}


def message_text_preview(message: Message) -> str | None:
    text = message.text or message.caption
    if text and text.strip():
        return text.strip()[:1000]
    # Для голосовых/файлов/видео не сохраняем искусственный текст вроде
    # [ContentType.VOICE], иначе история выглядит сломанной. Тип и file_id
    # сохраняются отдельно.
    return None


def message_file_id(message: Message) -> str | None:
    if message.photo:
        return message.photo[-1].file_id
    if message.document:
        return message.document.file_id
    if message.video:
        return message.video.file_id
    if message.voice:
        return message.voice.file_id
    if message.audio:
        return message.audio.file_id
    if message.sticker:
        return message.sticker.file_id
    return None


def sender_label(item: dict) -> str:
    full_name = item.get('sender_full_name')
    username = item.get('sender_username')
    sender_id = item.get('sender_id')
    if item.get('sender_type') == 'user':
        base = '👤 Пользователь'
    else:
        base = '🕌 Шейх/админ'
    name = full_name or (f'@{username}' if username else str(sender_id or '—'))
    return f'{base}: {h(name)}'


def ticket_card(ticket: dict, last_messages: list[dict] | None = None) -> str:
    username = ticket.get('username')
    username_line = f'@{h(username)}' if username else '—'
    lang = ticket.get('language') or 'ru'
    lines = [
        f"<b>{ticket_title(ticket)}</b>",
        '',
        f"👤 Пользователь: {user_link(ticket['user_id'], ticket.get('full_name'))}",
        f"🆔 User ID: <code>{ticket['user_id']}</code>",
        f"🔗 Username: {username_line}",
        f"🌐 Язык: {language_name(lang)}",
        f"🏷 Тема: {category_name(ticket.get('category'), 'ru')}",
        f"📌 Статус: {status_name(ticket.get('status', 'open'))}",
        f"🕒 Создано: {format_dt(ticket.get('created_at'))}",
        f"🔄 Обновлено: {format_dt(ticket.get('updated_at'))}",
    ]
    if last_messages:
        lines.extend(['', '<b>Последние сообщения:</b>'])
        for item in last_messages:
            who = sender_label(item) if item.get('sender_full_name') or item.get('sender_username') else ('👤 Пользователь' if item['sender_type'] == 'user' else '🕌 Шейх/админ')
            text = h(item.get('text') or f"[{item.get('content_type') or 'message'}]")
            lines.append(f"{format_dt(item.get('created_at'))} · {who}\n{text}")
    return '\n'.join(lines)


def ticket_history_text(ticket: dict, messages: list[dict]) -> str:
    lines = [
        f"📜 <b>История вопроса #{ticket['id']}</b>",
        '',
        f"👤 Кем задан: {user_link(ticket['user_id'], ticket.get('full_name'))}",
        f"🔗 Username: @{h(ticket['username'])}" if ticket.get('username') else '🔗 Username: —',
        f"🌐 Язык: {language_name(ticket.get('language'))}",
        f"🏷 Тема: {category_name(ticket.get('category'), 'ru')}",
        f"📌 Статус: {status_name(ticket.get('status', 'open'))}",
        f"🕒 Вопрос создан: {format_dt(ticket.get('created_at'))}",
        '',
        '<b>Сообщения и ответы:</b>',
    ]
    if not messages:
        lines.append('— сообщений пока нет')
        return '\n'.join(lines)
    for item in messages:
        text = h(item.get('text') or f"[{item.get('content_type') or 'message'}]")
        lines.extend([
            '',
            f"<b>{format_dt(item.get('created_at'))} · {sender_label(item)}</b>",
            text,
        ])
    return '\n'.join(lines)


def _plain_preview(value: str | None, limit: int = 120) -> str:
    text = (value or '').strip().replace('\n', ' ')
    if not text:
        return '—'
    return text if len(text) <= limit else text[:limit].rstrip() + '…'


CONTENT_TYPE_LABELS = {
    'text': '📝 Текстовое сообщение',
    'photo': '🖼 Фото',
    'document': '📎 Документ',
    'video': '🎬 Видео',
    'voice': '🎙 Голосовое сообщение',
    'audio': '🎧 Аудио',
    'sticker': '🏷 Стикер',
    'message': '📩 Сообщение',
}


def content_type_label(content_type: object | None) -> str:
    ct = normalize_content_type_value(content_type)
    return CONTENT_TYPE_LABELS.get(ct, f'📎 Вложение: {h(ct)}')


def media_note(text: str | None, content_type: object | None, file_id: str | None = None) -> str:
    ct = normalize_content_type_value(content_type)
    if not _is_placeholder_text(text, ct):
        return h(text.strip())
    label = content_type_label(ct)
    if file_id and ct in {'photo', 'document', 'video', 'voice', 'audio', 'sticker'}:
        return f'{label}\n<i>Оригинал вложения доступен кнопкой под полной карточкой.</i>'
    return label


def _message_body(text: str | None, content_type: str | None, file_id: str | None = None) -> str:
    return media_note(text, content_type, file_id)


def admin_answers_history_text(rows: list[dict], *, page: int = 0, total_pages: int = 1, total: int | None = None) -> str:
    """Compact answers history list.

    Full questions and answers are intentionally not printed here: long texts make
    Telegram truncate the message and admins cannot forward it reliably. Each row
    has a separate button that opens a full, non-truncated card.
    """
    if not rows:
        return '📜 <b>История ответов</b>\n\nОтветов пока нет.'

    header = f'📜 <b>История ответов админов/шейхов</b> · стр. {page + 1}/{max(total_pages, 1)}'
    if total is not None:
        header += f' · всего: {total}'
    lines = [header, '', 'Ниже краткий список. Для полного вопроса и полного ответа нажмите кнопку под сообщением.']

    for row in rows:
        admin_name = row.get('admin_full_name') or (f"@{row.get('admin_username')}" if row.get('admin_username') else str(row.get('admin_id')))
        user_name = row.get('user_full_name') or (f"@{row.get('user_username')}" if row.get('user_username') else str(row.get('user_id')))
        question_preview_source = row.get('question_text')
        if _is_placeholder_text(question_preview_source, row.get('question_content_type')):
            question_preview_source = content_type_label(row.get('question_content_type'))
        answer_preview_source = row.get('answer_text')
        if _is_placeholder_text(answer_preview_source, row.get('content_type')):
            answer_preview_source = content_type_label(row.get('content_type'))
        question_preview = h(_plain_preview(question_preview_source, 120))
        answer_preview = h(_plain_preview(answer_preview_source, 120))
        lines.extend([
            '',
            f"<b>#{row['ticket_id']} · ответ #{row['message_id']} · {category_name(row.get('category'), 'ru')}</b>",
            f"📌 Статус: {status_name(row.get('status', 'open'))}",
            f"🕒 Вопрос: {format_dt(row.get('question_created_at'))}",
            f"👤 Задал: {h(user_name)} · <code>{row.get('user_id')}</code>",
            f"✅ Ответил: {h(admin_name)} · <code>{row.get('admin_id')}</code>",
            f"🕒 Ответ: {format_dt(row.get('answered_at'))}",
            f"❓ {question_preview}",
            f"💬 {answer_preview}",
        ])
    return '\n'.join(lines).strip()


def admin_answer_full_text(row: dict) -> str:
    """Full answer card for admins. Designed to be forwarded to a group."""
    admin_name = row.get('admin_full_name') or (f"@{row.get('admin_username')}" if row.get('admin_username') else str(row.get('admin_id')))
    user_name = row.get('user_full_name') or (f"@{row.get('user_username')}" if row.get('user_username') else str(row.get('user_id')))
    username = f"@{h(row.get('user_username'))}" if row.get('user_username') else '—'
    admin_username = f"@{h(row.get('admin_username'))}" if row.get('admin_username') else '—'
    question = _message_body(row.get('question_text'), row.get('question_content_type'), row.get('question_file_id'))
    answer = _message_body(row.get('answer_text'), row.get('content_type'), row.get('answer_file_id'))

    return '\n'.join([
        f"📄 <b>Полная карточка ответа #{row['message_id']}</b>",
        '',
        f"🧾 Вопрос: <b>#{row['ticket_id']}</b>",
        f"🏷 Тема: {category_name(row.get('category'), 'ru')}",
        f"📌 Статус: {status_name(row.get('status', 'open'))}",
        f"🌐 Язык: {language_name(row.get('language'))}",
        '',
        '<b>Кем задан вопрос</b>',
        f"👤 Имя: {h(user_name)}",
        f"🔗 Username: {username}",
        f"🆔 User ID: <code>{row.get('user_id')}</code>",
        f"🕒 Вопрос задан: {format_dt(row.get('question_created_at'))}",
        '',
        '<b>Полный вопрос</b>',
        question,
        '',
        '<b>Кем дан ответ</b>',
        f"✅ Ответил: {h(admin_name)}",
        f"🔗 Username: {admin_username}",
        f"🆔 Admin ID: <code>{row.get('admin_id')}</code>",
        f"🕒 Ответ дан: {format_dt(row.get('answered_at'))}",
        '',
        '<b>Полный ответ</b>',
        answer,
    ])


def split_telegram_text(text: str, limit: int = 3900) -> list[str]:
    """Split long Telegram HTML text into chunks without cutting too aggressively."""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ''
    for block in text.split('\n\n'):
        candidate = block if not current else current + '\n\n' + block
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ''
        if len(block) <= limit:
            current = block
        else:
            for i in range(0, len(block), limit):
                chunks.append(block[i:i + limit])
    if current:
        chunks.append(current)
    return chunks


async def notify_admins_about_ticket(bot: Bot, db: Database, admin_ids: set[int], ticket_id: int, user_message: Message) -> None:
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        return
    text = ticket_card(ticket)
    for admin_id in admin_ids:
        try:
            await bot.send_message(
                admin_id,
                f'🔔 <b>Новый вопрос шейху</b>\n\n{text}',
                reply_markup=admin_ticket_kb(ticket_id, ticket['status']),
            )
            await bot.copy_message(admin_id, user_message.chat.id, user_message.message_id)
        except Exception:
            continue


async def notify_admins_status(bot: Bot, admin_ids: set[int], ticket: dict, text: str) -> None:
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=admin_ticket_kb(ticket['id'], ticket['status']))
        except Exception:
            continue
