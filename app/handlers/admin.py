from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import BaseFilter, Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyParameters, TelegramObject

from app.database import Database
from app.keyboards import (
    admin_answer_full_kb,
    admin_answer_sent_kb,
    admin_answers_history_kb,
    admin_panel_kb,
    admin_publication_list_kb,
    admin_publication_review_kb,
    admin_ticket_kb,
    admin_tickets_list_kb,
    language_kb,
    sheikh_panel_kb,
    sheikh_question_kb,
    sheikh_tickets_list_kb,
)
from app.services import (
    admin_answer_full_text,
    admin_answers_history_text,
    answer_prompt_text,
    can_auto_publish_via_bot,
    can_publish_via_bot,
    content_type_label,
    message_content_type,
    message_file_id,
    message_text_preview,
    normalize_content_type_value,
    publication_caption_parts,
    notify_admins_about_publication_ready,
    notify_admins_status,
    publication_caption_text,
    publication_text,
    send_answer_media_preview,
    sheikh_answered_text,
    sheikh_question_text,
    split_telegram_text,
    ticket_card,
    ticket_history_text,
    user_answer_intro_text,
)
from app.states import AdminAnswerState
from app.utils import h, language_name, normalize_lang, status_name, t

router = Router(name='admin')
MEDIA_CAPTION_LIMIT = 1024
MEDIA_CAPTION_COMMENT_LIMIT = 800


def is_admin(user_id: int | None, admin_ids: set[int]) -> bool:
    return bool(user_id and user_id in admin_ids)


def is_sheikh(user_id: int | None, sheikh_ids: set[int] | None = None) -> bool:
    return bool(user_id and user_id in (sheikh_ids or set()))


def is_staff(user_id: int | None, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> bool:
    return is_admin(user_id, admin_ids) or is_sheikh(user_id, sheikh_ids)


def is_sheikh_only(user_id: int | None, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> bool:
    return is_sheikh(user_id, sheikh_ids) and not is_admin(user_id, admin_ids)


class AdminFilter(BaseFilter):
    async def __call__(self, event: TelegramObject, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> bool:
        user = getattr(event, 'from_user', None)
        return bool(user and is_staff(user.id, admin_ids, sheikh_ids))


async def _remember_sheikh(message: Message, db: Database) -> str:
    user = message.from_user
    lang = await db.get_user_language(user.id)
    await db.upsert_user(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        language=None,
    )
    return lang


async def _send_admin_panel(message: Message, db: Database) -> None:
    stats = await db.stats()
    await message.answer(
        '<b>Панель администратора · Вопросы шейху</b> 🕌\n\n'
        'Здесь вы видите вопросы, которые отправили пользователи. '\
        'Вы можете открыть вопрос, ответить на него и подготовить ответы шейха к публикации.\n\n'
        f'🟢 Новых вопросов: <b>{stats["open"]}</b>\n'
        f'🟡 Ожидают публикации: <b>{stats["answered"]}</b>\n'
        f'✅ Опубликованных: <b>{stats["published"]}</b>\n'
        f'⚫ Закрытых: <b>{stats["closed"]}</b>\n'
        f'📚 Всего вопросов: <b>{stats["all"]}</b>\n\n'
        'Выберите раздел ниже:',
        reply_markup=admin_panel_kb(),
    )


async def _edit_admin_panel(callback: CallbackQuery, db: Database) -> None:
    stats = await db.stats()
    await callback.message.edit_text(
        '<b>Панель администратора · Вопросы шейху</b> 🕌\n\n'
        'Здесь вы видите вопросы, которые отправили пользователи. '\
        'Вы можете открыть вопрос, ответить на него и подготовить ответы шейха к публикации.\n\n'
        f'🟢 Новых вопросов: <b>{stats["open"]}</b>\n'
        f'🟡 Ожидают публикации: <b>{stats["answered"]}</b>\n'
        f'✅ Опубликованных: <b>{stats["published"]}</b>\n'
        f'⚫ Закрытых: <b>{stats["closed"]}</b>\n'
        f'📚 Всего вопросов: <b>{stats["all"]}</b>\n\n'
        'Выберите раздел ниже:',
        reply_markup=admin_panel_kb(),
    )


async def _send_sheikh_panel(message: Message, db: Database) -> None:
    stats = await db.stats()
    await message.answer(
        '<b>Вопросы шейху</b> 🕌\n\n'
        f'🟢 Неотвеченных: <b>{stats["open"]}</b>\n'
        f'🟡 Отвеченных: <b>{stats["answered"] + stats["published"]}</b>',
        reply_markup=sheikh_panel_kb(),
    )


async def _edit_sheikh_panel(callback: CallbackQuery, db: Database) -> None:
    stats = await db.stats()
    await callback.message.edit_text(
        '<b>Вопросы шейху</b> 🕌\n\n'
        f'🟢 Неотвеченных: <b>{stats["open"]}</b>\n'
        f'🟡 Отвеченных: <b>{stats["answered"] + stats["published"]}</b>',
        reply_markup=sheikh_panel_kb(),
    )


async def _send_role_panel(message: Message, db: Database, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> None:
    if is_sheikh_only(message.from_user.id, admin_ids, sheikh_ids):
        await _send_sheikh_panel(message, db)
    else:
        await _send_admin_panel(message, db)


async def _edit_role_panel(callback: CallbackQuery, db: Database, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> None:
    if is_sheikh_only(callback.from_user.id, admin_ids, sheikh_ids):
        await _edit_sheikh_panel(callback, db)
    else:
        await _edit_admin_panel(callback, db)


async def _send_publication_to_channel(
    bot,
    row: dict,
    *,
    publication_channel: int | str,
    russian_audio_url: str | None = None,
) -> None:
    text = publication_text(row, publication_channel=publication_channel, russian_audio_url=russian_audio_url)
    file_id = row.get('answer_file_id')
    content_type = normalize_content_type_value(row.get('content_type'))
    media_caption = f"Ответ шейха по вопросу №{row['ticket_id']}"

    async def send_saved_media(caption: str | None = None):
        if content_type == 'voice':
            return await bot.send_voice(publication_channel, file_id, caption=caption)
        elif content_type == 'audio':
            return await bot.send_audio(publication_channel, file_id, caption=caption)
        elif content_type == 'photo':
            return await bot.send_photo(publication_channel, file_id, caption=caption)
        elif content_type == 'video':
            return await bot.send_video(publication_channel, file_id, caption=caption)
        elif content_type == 'document':
            return await bot.send_document(publication_channel, file_id, caption=caption)
        elif content_type == 'sticker':
            return await bot.send_sticker(publication_channel, file_id)
        return None

    if file_id:
        can_caption = content_type in {'voice', 'audio', 'photo', 'video', 'document'}
        if can_caption:
            linked_chat_id = await _linked_discussion_chat_id(bot, publication_channel)
            if linked_chat_id:
                caption, question_remainder = publication_caption_parts(
                    row,
                    publication_channel=publication_channel,
                    russian_audio_url=russian_audio_url,
                    limit=MEDIA_CAPTION_COMMENT_LIMIT,
                )
            else:
                caption = publication_caption_text(
                    row,
                    publication_channel=publication_channel,
                    russian_audio_url=russian_audio_url,
                    limit=MEDIA_CAPTION_LIMIT,
                )
                question_remainder = None
            sent_message = await send_saved_media(caption=caption)
            message_id = getattr(sent_message, 'message_id', None)
            if linked_chat_id and question_remainder and message_id:
                await _send_question_remainder_comment(
                    bot,
                    linked_chat_id=linked_chat_id,
                    publication_channel=publication_channel,
                    channel_message_id=message_id,
                    ticket_id=row['ticket_id'],
                    question_remainder=question_remainder,
                )
            return

    for chunk in split_telegram_text(text):
        await bot.send_message(publication_channel, chunk, disable_web_page_preview=True)
    if file_id:
        await send_saved_media(caption=media_caption if content_type != 'sticker' else None)


async def _linked_discussion_chat_id(bot, publication_channel: int | str) -> int | None:
    try:
        chat = await bot.get_chat(publication_channel)
    except Exception:
        return None
    return getattr(chat, 'linked_chat_id', None)


async def _send_question_remainder_comment(
    bot,
    *,
    linked_chat_id: int,
    publication_channel: int | str,
    channel_message_id: int,
    ticket_id: int,
    question_remainder: str,
) -> bool:
    reply_parameters = ReplyParameters(
        message_id=channel_message_id,
        chat_id=publication_channel,
        allow_sending_without_reply=True,
    )
    chunks = split_telegram_text(question_remainder, limit=3600)
    try:
        for index, chunk in enumerate(chunks, start=1):
            prefix = f'Продолжение вопроса №{ticket_id}:'
            if len(chunks) > 1:
                prefix = f'Продолжение вопроса №{ticket_id}, часть {index}/{len(chunks)}:'
            await bot.send_message(
                linked_chat_id,
                f'{prefix}\n\n{chunk}',
                parse_mode=None,
                disable_web_page_preview=True,
                reply_parameters=reply_parameters,
            )
    except Exception:
        return False
    return True


@router.message(CommandStart(), AdminFilter())
async def sheikh_start(message: Message, state: FSMContext, db: Database, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> None:
    if not is_staff(message.from_user.id, admin_ids, sheikh_ids):
        return
    await state.clear()
    await _remember_sheikh(message, db)
    await _send_role_panel(message, db, admin_ids, sheikh_ids)


@router.message(Command('panel'), AdminFilter())
async def panel(message: Message, db: Database, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> None:
    if not is_staff(message.from_user.id, admin_ids, sheikh_ids):
        return
    await _remember_sheikh(message, db)
    await _send_role_panel(message, db, admin_ids, sheikh_ids)


@router.message(Command('help'), AdminFilter())
async def sheikh_help(message: Message, db: Database, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> None:
    if not is_staff(message.from_user.id, admin_ids, sheikh_ids):
        return
    await _remember_sheikh(message, db)
    if is_sheikh_only(message.from_user.id, admin_ids, sheikh_ids):
        await message.answer(
            '<b>Помощь для шейха</b>\n\n'
            '🟢 <b>Неотвеченные вопросы</b> — вопросы, на которые ещё нужно ответить.\n'
            '🟡 <b>Отвеченные вопросы</b> — вопросы, по которым уже был дан ответ.\n\n'
            'Команды:\n'
            '/start — открыть меню\n'
            '/panel — открыть меню\n'
            '/answer 123 — ответить на вопрос #123\n'
            '/cancel — отменить ввод ответа',
            reply_markup=sheikh_panel_kb(),
        )
        return
    await message.answer(
        '<b>Помощь для администратора</b>\n\n'
        '🟢 <b>Новые вопросы</b> — вопросы, на которые ещё не отвечали.\n'
        '🟡 <b>Отвеченные</b> — ответы шейха, ожидающие публикации.\n'
        '✅ <b>Опубликованные</b> — ответы, уже отправленные в канал.\n'
        '⚫ <b>Закрытые</b> — завершённые обращения.\n\n'
        'Команды:\n'
        '/start — открыть панель администратора\n'
        '/panel — открыть панель администратора\n'
        '/answer 123 — ответить на вопрос #123\n'
        '/cancel — отменить ввод ответа',
        reply_markup=admin_panel_kb(),
    )


@router.message(Command('new'), AdminFilter())
@router.message(Command('my'), AdminFilter())
async def sheikh_no_user_actions(message: Message, db: Database, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> None:
    if not is_staff(message.from_user.id, admin_ids, sheikh_ids):
        return
    await message.answer(
        'Вы вошли как <b>шейх/администратор</b>. Кнопка «Задать вопрос шейху» для вас скрыта.\n\n'
        'Откройте панель и выберите вопросы пользователей:',
        reply_markup=sheikh_panel_kb() if is_sheikh_only(message.from_user.id, admin_ids, sheikh_ids) else admin_panel_kb(),
    )


@router.message(Command('language'), AdminFilter())
async def admin_language_command(message: Message, db: Database, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> None:
    if not is_staff(message.from_user.id, admin_ids, sheikh_ids):
        return
    await _remember_sheikh(message, db)
    await message.answer('Выберите язык интерфейса:', reply_markup=language_kb(prefix='admin'))


@router.callback_query(F.data == 'admin:panel', AdminFilter())
async def panel_callback(callback: CallbackQuery, db: Database, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> None:
    if not is_staff(callback.from_user.id, admin_ids, sheikh_ids):
        await callback.answer('Недостаточно прав.', show_alert=True)
        return
    await _edit_role_panel(callback, db, admin_ids, sheikh_ids)
    await callback.answer()


@router.callback_query(F.data == 'admin:language', AdminFilter())
async def admin_language(callback: CallbackQuery, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> None:
    if not is_staff(callback.from_user.id, admin_ids, sheikh_ids):
        await callback.answer('Недостаточно прав.', show_alert=True)
        return
    await callback.message.edit_text('Выберите язык интерфейса:', reply_markup=language_kb(prefix='admin'))
    await callback.answer()


@router.callback_query(F.data.startswith('admin:lang:'), AdminFilter())
async def admin_set_language(callback: CallbackQuery, db: Database, state: FSMContext, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> None:
    if not is_staff(callback.from_user.id, admin_ids, sheikh_ids):
        await callback.answer('Недостаточно прав.', show_alert=True)
        return
    lang = normalize_lang(callback.data.split(':', 2)[2])
    await db.set_user_language(callback.from_user.id, lang)
    await db.upsert_user(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=callback.from_user.full_name,
        language=lang,
    )
    await state.clear()
    markup = sheikh_panel_kb() if is_sheikh_only(callback.from_user.id, admin_ids, sheikh_ids) else admin_panel_kb()
    await callback.message.edit_text(
        f'✅ Язык панели сохранён: <b>{language_name(lang)}</b>\n\n'
        'Откройте панель:',
        reply_markup=markup,
    )
    await callback.answer()


@router.callback_query(F.data == 'sheikh:panel', AdminFilter())
async def sheikh_panel_callback(callback: CallbackQuery, db: Database, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> None:
    if not is_sheikh_only(callback.from_user.id, admin_ids, sheikh_ids):
        await callback.answer('Недостаточно прав.', show_alert=True)
        return
    await _edit_sheikh_panel(callback, db)
    await callback.answer()


@router.callback_query(F.data.startswith('sheikh:list:'), AdminFilter())
async def sheikh_list(callback: CallbackQuery, db: Database, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> None:
    if not is_sheikh_only(callback.from_user.id, admin_ids, sheikh_ids):
        await callback.answer('Недостаточно прав.', show_alert=True)
        return
    status = callback.data.split(':', 2)[2]
    if status == 'answered':
        tickets = await db.list_tickets_by_statuses(statuses=('answered', 'published'), limit=10)
        text = 'Отвеченных вопросов пока нет.' if not tickets else 'Отвеченные вопросы:'
    else:
        tickets = await db.list_tickets(status='open', limit=10)
        text = 'Неотвеченных вопросов пока нет.' if not tickets else 'Неотвеченные вопросы:'
    await callback.message.edit_text(text, reply_markup=sheikh_tickets_list_kb(tickets, status))
    await callback.answer()


@router.callback_query(F.data.startswith('sheikh:view:'), AdminFilter())
async def sheikh_view_ticket(callback: CallbackQuery, db: Database, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> None:
    if not is_sheikh_only(callback.from_user.id, admin_ids, sheikh_ids):
        await callback.answer('Недостаточно прав.', show_alert=True)
        return
    ticket_id = int(callback.data.split(':', 2)[2])
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        await callback.answer('Вопрос не найден.', show_alert=True)
        return
    messages = await db.get_messages_with_senders(ticket_id, limit=30)
    if ticket['status'] == 'open':
        await callback.message.edit_text(sheikh_question_text(ticket, messages), reply_markup=sheikh_question_kb(ticket_id))
    else:
        await callback.message.edit_text(sheikh_answered_text(ticket, messages))
    await callback.answer()


@router.message(Command('answer'), AdminFilter())
async def answer_command(message: Message, state: FSMContext, db: Database, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> None:
    if not is_staff(message.from_user.id, admin_ids, sheikh_ids):
        return
    parts = (message.text or '').split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer('Использование: <code>/answer 123</code>')
        return
    ticket_id = int(parts[1])
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        await message.answer('Вопрос не найден.')
        return
    if ticket['status'] in {'closed', 'published'}:
        await message.answer('Этот вопрос уже закрыт или опубликован.')
        return
    if is_sheikh_only(message.from_user.id, admin_ids, sheikh_ids) and ticket['status'] != 'open':
        await message.answer('На этот вопрос уже был дан ответ.')
        return
    await state.set_state(AdminAnswerState.waiting_answer)
    await state.update_data(ticket_id=ticket_id, source_chat_id=None, source_message_id=None)
    messages = await db.get_messages_with_senders(ticket_id, limit=30)
    await message.answer(answer_prompt_text(ticket, messages))


@router.message(Command('close'), AdminFilter())
async def close_command(message: Message, db: Database, admin_ids: set[int]) -> None:
    if not is_admin(message.from_user.id, admin_ids):
        return
    parts = (message.text or '').split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer('Использование: <code>/close 123</code>')
        return
    ticket_id = int(parts[1])
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        await message.answer('Вопрос не найден.')
        return
    await db.set_status(ticket_id, 'closed')
    ticket = await db.get_ticket(ticket_id)
    await message.answer(f'✅ Вопрос <b>#{ticket_id}</b> закрыт.', reply_markup=admin_panel_kb())
    try:
        await message.bot.send_message(ticket['user_id'], t(ticket.get('language'), 'closed', ticket_id=ticket_id))
    except Exception:
        pass


@router.callback_query(F.data == 'admin:stats', AdminFilter())
async def stats_callback(callback: CallbackQuery, db: Database, admin_ids: set[int]) -> None:
    if not is_admin(callback.from_user.id, admin_ids):
        await callback.answer('Недостаточно прав.', show_alert=True)
        return
    stats = await db.stats()
    await callback.answer(
        f'Новых: {stats["open"]}\nОжидают публикации: {stats["answered"]}\nОпубликованных: {stats["published"]}\nЗакрытых: {stats["closed"]}\nВсего: {stats["all"]}',
        show_alert=True,
    )


@router.callback_query(F.data.startswith('admin:list:'), AdminFilter())
async def admin_list(callback: CallbackQuery, db: Database, admin_ids: set[int]) -> None:
    if not is_admin(callback.from_user.id, admin_ids):
        await callback.answer('Недостаточно прав.', show_alert=True)
        return
    status = callback.data.split(':', 2)[2]
    if status in {'answered', 'published'}:
        rows = await db.list_sheikh_answers_for_publication(status=status, limit=10)
        if not rows:
            text = 'Ответов, ожидающих публикации, нет.' if status == 'answered' else 'Опубликованных ответов пока нет.'
        elif status == 'answered':
            text = 'Ответы, ожидающие публикации:\n\nНажмите на ответ, чтобы открыть предпросмотр.'
        else:
            text = 'Опубликованные ответы:\n\nНажмите на ответ, чтобы открыть публикацию.'
        await callback.message.edit_text(text, reply_markup=admin_publication_list_kb(rows, status))
        await callback.answer()
        return
    tickets = await db.list_tickets(status=status, limit=10)
    if not tickets:
        text = f'Вопросов со статусом <b>{status_name(status)}</b> нет.'
    else:
        text = f'Последние вопросы: <b>{status_name(status)}</b>\n\nНажмите на вопрос, чтобы открыть карточку.'
    await callback.message.edit_text(text, reply_markup=admin_tickets_list_kb(tickets, status))
    await callback.answer()


@router.callback_query(F.data.startswith('admin:view:'), AdminFilter())
async def admin_view_ticket(callback: CallbackQuery, db: Database, admin_ids: set[int]) -> None:
    if not is_admin(callback.from_user.id, admin_ids):
        await callback.answer('Недостаточно прав.', show_alert=True)
        return
    ticket_id = int(callback.data.split(':', 2)[2])
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        await callback.answer('Вопрос не найден.', show_alert=True)
        return
    last_messages = await db.get_messages_with_senders(ticket_id, limit=8)
    await callback.message.edit_text(ticket_card(ticket, last_messages), reply_markup=admin_ticket_kb(ticket_id, ticket['status']))
    await callback.answer()


@router.callback_query(F.data.startswith('admin:review:'), AdminFilter())
async def admin_review_publication(
    callback: CallbackQuery,
    db: Database,
    admin_ids: set[int],
    publication_channel: int | str | None = None,
    russian_audio_url: str | None = None,
) -> None:
    if not is_admin(callback.from_user.id, admin_ids):
        await callback.answer('Недостаточно прав.', show_alert=True)
        return
    parts = callback.data.split(':')
    if len(parts) < 3 or not parts[2].isdigit():
        await callback.answer('Ответ не найден.', show_alert=True)
        return
    message_id = int(parts[2])
    row = await db.get_sheikh_answer_for_publication(message_id)
    if not row:
        await callback.answer('Ответ не найден.', show_alert=True)
        return

    text = publication_text(row, publication_channel=publication_channel, russian_audio_url=russian_audio_url)
    chunks = split_telegram_text(text)
    can_publish = row.get('status') == 'answered' and can_publish_via_bot(row)
    markup = admin_publication_review_kb(
        row['ticket_id'],
        row['message_id'],
        can_publish=can_publish,
        can_mark_published=row.get('status') == 'answered' and not can_publish,
    )
    await callback.message.edit_text(chunks[0], reply_markup=markup, disable_web_page_preview=True)
    for index, chunk in enumerate(chunks[1:], start=2):
        await callback.message.answer(f'<b>Часть {index}/{len(chunks)}</b>\n\n{chunk}')
    await send_answer_media_preview(callback.bot, callback.message.chat.id, row)
    await callback.answer()


@router.callback_query(F.data.startswith('admin:publish:'), AdminFilter())
async def admin_publish_answer(
    callback: CallbackQuery,
    db: Database,
    admin_ids: set[int],
    publication_channel: int | str | None = None,
    russian_audio_url: str | None = None,
) -> None:
    if not is_admin(callback.from_user.id, admin_ids):
        await callback.answer('Недостаточно прав.', show_alert=True)
        return
    if publication_channel is None:
        await callback.answer('В .env не указан PUBLICATION_CHANNEL.', show_alert=True)
        return
    parts = callback.data.split(':')
    if len(parts) < 3 or not parts[2].isdigit():
        await callback.answer('Ответ не найден.', show_alert=True)
        return
    message_id = int(parts[2])
    row = await db.get_sheikh_answer_for_publication(message_id)
    if not row:
        await callback.answer('Ответ не найден.', show_alert=True)
        return
    if row.get('status') == 'published':
        await callback.answer('Этот ответ уже опубликован.', show_alert=True)
        return
    if row.get('status') != 'answered':
        await callback.answer('Опубликовать можно только отвеченный и ещё не опубликованный вопрос.', show_alert=True)
        return
    if not can_publish_via_bot(row):
        await callback.answer('Этот ответ нужно опубликовать вручную, затем отметить как опубликованный.', show_alert=True)
        return

    try:
        await _send_publication_to_channel(
            callback.bot,
            row,
            publication_channel=publication_channel,
            russian_audio_url=russian_audio_url,
        )
    except Exception:
        await callback.answer('Не удалось опубликовать в канал. Проверьте PUBLICATION_CHANNEL и права бота.', show_alert=True)
        return

    await db.set_status(row['ticket_id'], 'published')
    row['status'] = 'published'
    text = publication_text(row, publication_channel=publication_channel, russian_audio_url=russian_audio_url)
    chunks = split_telegram_text(text)
    await callback.message.edit_text(
        chunks[0],
        reply_markup=admin_publication_review_kb(row['ticket_id'], row['message_id'], can_publish=False),
        disable_web_page_preview=True,
    )
    await callback.message.answer(f"✅ Вопрос №<b>{row['ticket_id']}</b> успешно опубликован в канал.")
    await callback.answer('Ответ опубликован.')


@router.callback_query(F.data.startswith('admin:mark_published:'), AdminFilter())
async def admin_mark_answer_published(
    callback: CallbackQuery,
    db: Database,
    admin_ids: set[int],
    publication_channel: int | str | None = None,
    russian_audio_url: str | None = None,
) -> None:
    if not is_admin(callback.from_user.id, admin_ids):
        await callback.answer('Недостаточно прав.', show_alert=True)
        return
    parts = callback.data.split(':')
    if len(parts) < 3 or not parts[2].isdigit():
        await callback.answer('Ответ не найден.', show_alert=True)
        return
    message_id = int(parts[2])
    row = await db.get_sheikh_answer_for_publication(message_id)
    if not row:
        await callback.answer('Ответ не найден.', show_alert=True)
        return
    if row.get('status') == 'published':
        await callback.answer('Этот ответ уже отмечен опубликованным.', show_alert=True)
        return
    if row.get('status') != 'answered':
        await callback.answer('Отметить можно только отвеченный и ещё не опубликованный вопрос.', show_alert=True)
        return

    await db.set_status(row['ticket_id'], 'published')
    row['status'] = 'published'
    text = publication_text(row, publication_channel=publication_channel, russian_audio_url=russian_audio_url)
    chunks = split_telegram_text(text)
    await callback.message.edit_text(
        chunks[0],
        reply_markup=admin_publication_review_kb(row['ticket_id'], row['message_id'], can_publish=False, can_mark_published=False),
        disable_web_page_preview=True,
    )
    await callback.message.answer(f"✅ Вопрос №<b>{row['ticket_id']}</b> отмечен как опубликованный.")
    await callback.answer('Отмечено как опубликованное.')



@router.callback_query(F.data.startswith('admin:history:'), AdminFilter())
async def admin_ticket_history(callback: CallbackQuery, db: Database, admin_ids: set[int]) -> None:
    if not is_admin(callback.from_user.id, admin_ids):
        await callback.answer('Недостаточно прав.', show_alert=True)
        return
    ticket_id = int(callback.data.split(':', 2)[2])
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        await callback.answer('Вопрос не найден.', show_alert=True)
        return
    messages = await db.get_messages_with_senders(ticket_id, limit=30)
    await callback.message.edit_text(ticket_history_text(ticket, messages), reply_markup=admin_ticket_kb(ticket_id, ticket['status']))
    await callback.answer()


@router.callback_query(F.data.startswith('admin:answers_history'), AdminFilter())
async def admin_answers_history(callback: CallbackQuery, db: Database, admin_ids: set[int]) -> None:
    if not is_admin(callback.from_user.id, admin_ids):
        await callback.answer('Недостаточно прав.', show_alert=True)
        return
    parts = callback.data.split(':')
    page = 0
    if len(parts) >= 3 and parts[-1].isdigit():
        page = int(parts[-1])

    per_page = 4
    total = await db.count_admin_answers()
    total_pages = max((total + per_page - 1) // per_page, 1)
    page = min(max(page, 0), total_pages - 1)
    rows = await db.list_admin_answers(limit=per_page, offset=page * per_page)
    await callback.message.edit_text(
        admin_answers_history_text(rows, page=page, total_pages=total_pages, total=total),
        reply_markup=admin_answers_history_kb(page, total_pages, rows),
    )
    await callback.answer()


@router.callback_query(F.data.startswith('admin:answer_full:'), AdminFilter())
async def admin_answer_full(callback: CallbackQuery, db: Database, admin_ids: set[int]) -> None:
    if not is_admin(callback.from_user.id, admin_ids):
        await callback.answer('Недостаточно прав.', show_alert=True)
        return

    parts = callback.data.split(':')
    if len(parts) < 3 or not parts[2].isdigit():
        await callback.answer('Ответ не найден.', show_alert=True)
        return

    message_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
    row = await db.get_admin_answer(message_id)
    if not row:
        await callback.answer('Ответ не найден.', show_alert=True)
        return

    text = admin_answer_full_text(row)
    chunks = split_telegram_text(text)
    if len(chunks) == 1:
        await callback.message.edit_text(chunks[0], reply_markup=admin_answer_full_kb(
                row['ticket_id'],
                page,
                answer_message_id=message_id,
                has_question_media=bool(row.get('question_file_id')),
                has_answer_media=bool(row.get('answer_file_id')),
            ))
    else:
        await callback.message.edit_text(
            f"📄 Полная карточка ответа #{message_id} слишком большая, поэтому отправляю её несколькими сообщениями ниже.",
            reply_markup=admin_answer_full_kb(
                row['ticket_id'],
                page,
                answer_message_id=message_id,
                has_question_media=bool(row.get('question_file_id')),
                has_answer_media=bool(row.get('answer_file_id')),
            ),
        )
        for index, chunk in enumerate(chunks, start=1):
            await callback.message.answer(f'<b>Часть {index}/{len(chunks)}</b>\n\n{chunk}')
    await callback.answer()


@router.callback_query(F.data.startswith('admin:send_media:'), AdminFilter())
async def admin_send_saved_media(callback: CallbackQuery, db: Database, admin_ids: set[int]) -> None:
    if not is_admin(callback.from_user.id, admin_ids):
        await callback.answer('Недостаточно прав.', show_alert=True)
        return

    parts = callback.data.split(':')
    if len(parts) < 4 or not parts[2].isdigit() or parts[3] not in {'question', 'answer'}:
        await callback.answer('Вложение не найдено.', show_alert=True)
        return

    message_id = int(parts[2])
    kind = parts[3]
    row = await db.get_admin_answer(message_id)
    if not row:
        await callback.answer('Ответ не найден.', show_alert=True)
        return

    if kind == 'question':
        file_id = row.get('question_file_id')
        content_type = normalize_content_type_value(row.get('question_content_type'))
        caption = f"Оригинал вопроса #{row['ticket_id']} · {content_type_label(content_type)}"
    else:
        file_id = row.get('answer_file_id')
        content_type = normalize_content_type_value(row.get('content_type'))
        caption = f"Оригинал ответа #{row['message_id']} по вопросу #{row['ticket_id']} · {content_type_label(content_type)}"

    if not file_id:
        await callback.answer('У этого сообщения нет сохранённого вложения.', show_alert=True)
        return

    if content_type == 'voice':
        await callback.message.answer_voice(file_id, caption=caption)
    elif content_type == 'photo':
        await callback.message.answer_photo(file_id, caption=caption)
    elif content_type == 'video':
        await callback.message.answer_video(file_id, caption=caption)
    elif content_type == 'document':
        await callback.message.answer_document(file_id, caption=caption)
    elif content_type == 'audio':
        await callback.message.answer_audio(file_id, caption=caption)
    elif content_type == 'sticker':
        await callback.message.answer_sticker(file_id)
        await callback.message.answer(caption)
    else:
        await callback.message.answer(f'{caption}\n\n<code>{file_id}</code>')

    await callback.answer('Оригинал отправлен отдельным сообщением.')


@router.callback_query(F.data.startswith('admin:answer:'), AdminFilter())
async def admin_answer_start(callback: CallbackQuery, state: FSMContext, db: Database, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> None:
    if not is_staff(callback.from_user.id, admin_ids, sheikh_ids):
        await callback.answer('Недостаточно прав.', show_alert=True)
        return
    ticket_id = int(callback.data.split(':', 2)[2])
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        await callback.answer('Вопрос не найден.', show_alert=True)
        return
    if ticket['status'] in {'closed', 'published'}:
        await callback.answer('Вопрос уже закрыт или опубликован.', show_alert=True)
        return
    if is_sheikh_only(callback.from_user.id, admin_ids, sheikh_ids) and ticket['status'] != 'open':
        await callback.answer('На этот вопрос уже был дан ответ.', show_alert=True)
        return
    await state.set_state(AdminAnswerState.waiting_answer)
    await state.update_data(
        ticket_id=ticket_id,
        source_chat_id=callback.message.chat.id,
        source_message_id=callback.message.message_id,
    )
    messages = await db.get_messages_with_senders(ticket_id, limit=30)
    await callback.message.answer(answer_prompt_text(ticket, messages))
    await callback.answer()


@router.message(Command('cancel'), AdminFilter())
async def cancel_admin_state(message: Message, state: FSMContext, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> None:
    if not is_staff(message.from_user.id, admin_ids, sheikh_ids):
        return
    await state.clear()
    markup = sheikh_panel_kb() if is_sheikh_only(message.from_user.id, admin_ids, sheikh_ids) else admin_panel_kb()
    await message.answer('Отменено.', reply_markup=markup)


@router.message(AdminAnswerState.waiting_answer, AdminFilter())
async def admin_send_answer(
    message: Message,
    state: FSMContext,
    db: Database,
    admin_ids: set[int],
    sheikh_ids: set[int] | None = None,
    publication_channel: int | str | None = None,
    russian_audio_url: str | None = None,
) -> None:
    if not is_staff(message.from_user.id, admin_ids, sheikh_ids):
        return
    sheikh_role = is_sheikh_only(message.from_user.id, admin_ids, sheikh_ids)
    panel_markup = sheikh_panel_kb() if sheikh_role else admin_panel_kb()
    data = await state.get_data()
    ticket_id = int(data['ticket_id'])
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        await state.clear()
        await message.answer('Вопрос не найден.', reply_markup=panel_markup)
        return
    if ticket['status'] in {'closed', 'published'}:
        await state.clear()
        await message.answer('Вопрос уже закрыт или опубликован.', reply_markup=panel_markup)
        return
    if sheikh_role and ticket['status'] != 'open':
        await state.clear()
        await message.answer('На этот вопрос уже был дан ответ.', reply_markup=panel_markup)
        return

    await db.upsert_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        language=None,
    )
    sender_type = 'sheikh' if sheikh_role else 'admin'
    answer_text = message_text_preview(message)
    answer_content_type = message_content_type(message)
    answer_file_id = message_file_id(message)
    answer_message_id = await db.add_message(
        ticket_id=ticket_id,
        sender_type=sender_type,
        sender_id=message.from_user.id,
        text=answer_text,
        content_type=answer_content_type,
        file_id=answer_file_id,
    )
    await db.set_status(ticket_id, 'answered')
    ticket = await db.get_ticket(ticket_id)
    await state.clear()
    messages_for_user = await db.get_messages_with_senders(ticket_id, limit=30)

    try:
        await message.bot.send_message(ticket['user_id'], user_answer_intro_text(ticket, messages_for_user))
        await message.bot.copy_message(ticket['user_id'], message.chat.id, message.message_id)
        await message.bot.send_message(ticket['user_id'], t(ticket.get('language'), 'after_answer'))
    except Exception:
        await message.answer('Ответ сохранён, но не удалось отправить его пользователю. Возможно, пользователь заблокировал бота.', reply_markup=panel_markup)
        return

    if sheikh_role:
        source_chat_id = data.get('source_chat_id')
        source_message_id = data.get('source_message_id')
        if source_chat_id and source_message_id:
            messages = await db.get_messages_with_senders(ticket_id, limit=30)
            try:
                await message.bot.edit_message_text(
                    sheikh_answered_text(ticket, messages),
                    chat_id=source_chat_id,
                    message_id=source_message_id,
                    reply_markup=None,
                )
            except Exception:
                pass
        row = await db.get_sheikh_answer_for_publication(answer_message_id)
        if row and publication_channel is not None and can_auto_publish_via_bot(row):
            try:
                await _send_publication_to_channel(
                    message.bot,
                    row,
                    publication_channel=publication_channel,
                    russian_audio_url=russian_audio_url,
                )
                await db.set_status(ticket_id, 'published')
                await message.answer(f'✅ Вы ответили на вопрос №<b>{ticket_id}</b>. Текстовый ответ опубликован в канал.', reply_markup=sheikh_panel_kb())
            except Exception:
                await message.answer(f'✅ Вы ответили на вопрос №<b>{ticket_id}</b>. Не удалось автоматически опубликовать ответ в канал, отправил его администратору.', reply_markup=sheikh_panel_kb())
                await notify_admins_about_publication_ready(
                    message.bot,
                    admin_ids,
                    row,
                    publication_channel=publication_channel,
                    russian_audio_url=russian_audio_url,
                )
        elif row:
            await message.answer(f'✅ Вы ответили на вопрос №<b>{ticket_id}</b>.', reply_markup=sheikh_panel_kb())
            await notify_admins_about_publication_ready(
                message.bot,
                admin_ids,
                row,
                publication_channel=publication_channel,
                russian_audio_url=russian_audio_url,
            )
        else:
            await message.answer(f'✅ Вы ответили на вопрос №<b>{ticket_id}</b>.', reply_markup=sheikh_panel_kb())
    else:
        row = await db.get_sheikh_answer_for_publication(answer_message_id)
        can_publish_answer = bool(row and can_publish_via_bot(row))
        await message.answer(
            f'✅ Ответ отправлен пользователю по вопросу <b>#{ticket_id}</b>.',
            reply_markup=admin_answer_sent_kb(
                ticket_id,
                answer_message_id,
                can_publish=can_publish_answer,
                can_mark_published=bool(row and not can_publish_answer),
            ),
        )
        await notify_admins_status(
            message.bot,
            admin_ids - {message.from_user.id},
            ticket,
            f'✅ Администратор {h(message.from_user.full_name)} ответил по вопросу <b>#{ticket_id}</b>.',
        )


@router.callback_query(F.data.startswith('admin:close:'), AdminFilter())
async def admin_close_ticket(callback: CallbackQuery, db: Database, admin_ids: set[int]) -> None:
    if not is_admin(callback.from_user.id, admin_ids):
        await callback.answer('Недостаточно прав.', show_alert=True)
        return
    await callback.answer('Кнопка закрытия отключена, чтобы вопрос не закрыли случайно.', show_alert=True)
