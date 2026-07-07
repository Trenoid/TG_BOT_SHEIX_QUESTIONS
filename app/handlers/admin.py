from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import BaseFilter, Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.database import Database
from app.keyboards import admin_answer_full_kb, admin_answers_history_kb, admin_panel_kb, admin_ticket_kb, admin_tickets_list_kb, language_kb
from app.services import admin_answer_full_text, admin_answers_history_text, content_type_label, message_content_type, message_file_id, message_text_preview, normalize_content_type_value, notify_admins_status, split_telegram_text, ticket_card, ticket_history_text
from app.states import AdminAnswerState
from app.utils import h, language_name, normalize_lang, status_name, t

router = Router(name='admin')


def is_admin(user_id: int | None, admin_ids: set[int]) -> bool:
    return bool(user_id and user_id in admin_ids)


class AdminFilter(BaseFilter):
    async def __call__(self, event: TelegramObject, admin_ids: set[int]) -> bool:
        user = getattr(event, 'from_user', None)
        return bool(user and user.id in admin_ids)


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


async def _send_sheikh_panel(message: Message, db: Database) -> None:
    stats = await db.stats()
    await message.answer(
        '<b>Панель шейха · Вопросы шейху</b> 🕌\n\n'
        'Здесь вы видите вопросы, которые отправили пользователи. '\
        'Вы можете открыть вопрос, ответить на него и закрыть обращение.\n\n'
        f'🟢 Новых вопросов: <b>{stats["open"]}</b>\n'
        f'🟡 Отвеченных: <b>{stats["answered"]}</b>\n'
        f'⚫ Закрытых: <b>{stats["closed"]}</b>\n'
        f'📚 Всего вопросов: <b>{stats["all"]}</b>\n\n'
        'Выберите раздел ниже:',
        reply_markup=admin_panel_kb(),
    )


async def _edit_sheikh_panel(callback: CallbackQuery, db: Database) -> None:
    stats = await db.stats()
    await callback.message.edit_text(
        '<b>Панель шейха · Вопросы шейху</b> 🕌\n\n'
        'Здесь вы видите вопросы, которые отправили пользователи. '\
        'Вы можете открыть вопрос, ответить на него и закрыть обращение.\n\n'
        f'🟢 Новых вопросов: <b>{stats["open"]}</b>\n'
        f'🟡 Отвеченных: <b>{stats["answered"]}</b>\n'
        f'⚫ Закрытых: <b>{stats["closed"]}</b>\n'
        f'📚 Всего вопросов: <b>{stats["all"]}</b>\n\n'
        'Выберите раздел ниже:',
        reply_markup=admin_panel_kb(),
    )


@router.message(CommandStart(), AdminFilter())
async def sheikh_start(message: Message, state: FSMContext, db: Database, admin_ids: set[int]) -> None:
    if not is_admin(message.from_user.id, admin_ids):
        return
    await state.clear()
    await _remember_sheikh(message, db)
    await _send_sheikh_panel(message, db)


@router.message(Command('panel'), AdminFilter())
async def panel(message: Message, db: Database, admin_ids: set[int]) -> None:
    if not is_admin(message.from_user.id, admin_ids):
        return
    await _remember_sheikh(message, db)
    await _send_sheikh_panel(message, db)


@router.message(Command('help'), AdminFilter())
async def sheikh_help(message: Message, db: Database, admin_ids: set[int]) -> None:
    if not is_admin(message.from_user.id, admin_ids):
        return
    await _remember_sheikh(message, db)
    await message.answer(
        '<b>Помощь для шейха</b>\n\n'
        '🟢 <b>Новые вопросы</b> — вопросы, на которые ещё не отвечали.\n'
        '🟡 <b>Отвеченные</b> — вопросы, по которым уже был отправлен ответ.\n'
        '⚫ <b>Закрытые</b> — завершённые обращения.\n\n'
        'Команды:\n'
        '/start — открыть панель шейха\n'
        '/panel — открыть панель шейха\n'
        '/answer 123 — ответить на вопрос #123\n'
        '/close 123 — закрыть вопрос #123\n'
        '/cancel — отменить ввод ответа',
        reply_markup=admin_panel_kb(),
    )


@router.message(Command('new'), AdminFilter())
@router.message(Command('my'), AdminFilter())
async def sheikh_no_user_actions(message: Message, db: Database, admin_ids: set[int]) -> None:
    if not is_admin(message.from_user.id, admin_ids):
        return
    await message.answer(
        'Вы вошли как <b>шейх/администратор</b>. Кнопка «Задать вопрос шейху» для вас скрыта.\n\n'
        'Откройте панель и выберите вопросы пользователей:',
        reply_markup=admin_panel_kb(),
    )


@router.message(Command('language'), AdminFilter())
async def admin_language_command(message: Message, db: Database, admin_ids: set[int]) -> None:
    if not is_admin(message.from_user.id, admin_ids):
        return
    await _remember_sheikh(message, db)
    await message.answer('Выберите язык интерфейса:', reply_markup=language_kb(prefix='admin'))


@router.callback_query(F.data == 'admin:panel', AdminFilter())
async def panel_callback(callback: CallbackQuery, db: Database, admin_ids: set[int]) -> None:
    if not is_admin(callback.from_user.id, admin_ids):
        await callback.answer('Недостаточно прав.', show_alert=True)
        return
    await _edit_sheikh_panel(callback, db)
    await callback.answer()


@router.callback_query(F.data == 'admin:language', AdminFilter())
async def admin_language(callback: CallbackQuery, admin_ids: set[int]) -> None:
    if not is_admin(callback.from_user.id, admin_ids):
        await callback.answer('Недостаточно прав.', show_alert=True)
        return
    await callback.message.edit_text('Выберите язык интерфейса:', reply_markup=language_kb(prefix='admin'))
    await callback.answer()


@router.callback_query(F.data.startswith('admin:lang:'), AdminFilter())
async def admin_set_language(callback: CallbackQuery, db: Database, state: FSMContext, admin_ids: set[int]) -> None:
    if not is_admin(callback.from_user.id, admin_ids):
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
    await callback.message.edit_text(
        f'✅ Язык панели сохранён: <b>{language_name(lang)}</b>\n\n'
        'Откройте панель шейха:',
        reply_markup=admin_panel_kb(),
    )
    await callback.answer()


@router.message(Command('answer'), AdminFilter())
async def answer_command(message: Message, state: FSMContext, db: Database, admin_ids: set[int]) -> None:
    if not is_admin(message.from_user.id, admin_ids):
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
    if ticket['status'] == 'closed':
        await message.answer('Этот вопрос уже закрыт.')
        return
    await state.set_state(AdminAnswerState.waiting_answer)
    await state.update_data(ticket_id=ticket_id)
    await message.answer(f'Напишите ответ для вопроса <b>#{ticket_id}</b>. Можно отправить текст, фото, документ, видео или голосовое.')


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
        f'Новых: {stats["open"]}\nОтвеченных: {stats["answered"]}\nЗакрытых: {stats["closed"]}\nВсего: {stats["all"]}',
        show_alert=True,
    )


@router.callback_query(F.data.startswith('admin:list:'), AdminFilter())
async def admin_list(callback: CallbackQuery, db: Database, admin_ids: set[int]) -> None:
    if not is_admin(callback.from_user.id, admin_ids):
        await callback.answer('Недостаточно прав.', show_alert=True)
        return
    status = callback.data.split(':', 2)[2]
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
async def admin_answer_start(callback: CallbackQuery, state: FSMContext, db: Database, admin_ids: set[int]) -> None:
    if not is_admin(callback.from_user.id, admin_ids):
        await callback.answer('Недостаточно прав.', show_alert=True)
        return
    ticket_id = int(callback.data.split(':', 2)[2])
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        await callback.answer('Вопрос не найден.', show_alert=True)
        return
    if ticket['status'] == 'closed':
        await callback.answer('Вопрос уже закрыт.', show_alert=True)
        return
    await state.set_state(AdminAnswerState.waiting_answer)
    await state.update_data(ticket_id=ticket_id)
    await callback.message.answer(
        f'✍️ Напишите ответ для вопроса <b>#{ticket_id}</b>.\n\n'
        'Можно отправить текст, фото, документ, видео или голосовое. Чтобы отменить: /cancel'
    )
    await callback.answer()


@router.message(Command('cancel'), AdminFilter())
async def cancel_admin_state(message: Message, state: FSMContext, admin_ids: set[int]) -> None:
    if not is_admin(message.from_user.id, admin_ids):
        return
    await state.clear()
    await message.answer('Отменено.', reply_markup=admin_panel_kb())


@router.message(AdminAnswerState.waiting_answer, AdminFilter())
async def admin_send_answer(message: Message, state: FSMContext, db: Database, admin_ids: set[int]) -> None:
    if not is_admin(message.from_user.id, admin_ids):
        return
    data = await state.get_data()
    ticket_id = int(data['ticket_id'])
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        await state.clear()
        await message.answer('Вопрос не найден.', reply_markup=admin_panel_kb())
        return
    if ticket['status'] == 'closed':
        await state.clear()
        await message.answer('Вопрос уже закрыт.', reply_markup=admin_panel_kb())
        return

    await db.upsert_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        language=None,
    )
    await db.add_message(
        ticket_id=ticket_id,
        sender_type='admin',
        sender_id=message.from_user.id,
        text=message_text_preview(message),
        content_type=message_content_type(message),
        file_id=message_file_id(message),
    )
    await db.set_status(ticket_id, 'answered')
    ticket = await db.get_ticket(ticket_id)
    await state.clear()

    try:
        await message.bot.send_message(ticket['user_id'], t(ticket.get('language'), 'admin_answer_title', ticket_id=ticket_id))
        await message.bot.copy_message(ticket['user_id'], message.chat.id, message.message_id)
        await message.bot.send_message(ticket['user_id'], t(ticket.get('language'), 'after_answer'))
    except Exception:
        await message.answer('Ответ сохранён, но не удалось отправить его пользователю. Возможно, пользователь заблокировал бота.', reply_markup=admin_panel_kb())
        return

    await message.answer(f'✅ Ответ отправлен пользователю по вопросу <b>#{ticket_id}</b>.', reply_markup=admin_ticket_kb(ticket_id, ticket['status']))
    await notify_admins_status(
        message.bot,
        admin_ids - {message.from_user.id},
        ticket,
        f'🕌 Шейх {h(message.from_user.full_name)} ответил по вопросу <b>#{ticket_id}</b>.',
    )


@router.callback_query(F.data.startswith('admin:close:'), AdminFilter())
async def admin_close_ticket(callback: CallbackQuery, db: Database, admin_ids: set[int]) -> None:
    if not is_admin(callback.from_user.id, admin_ids):
        await callback.answer('Недостаточно прав.', show_alert=True)
        return
    ticket_id = int(callback.data.split(':', 2)[2])
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        await callback.answer('Вопрос не найден.', show_alert=True)
        return
    await db.set_status(ticket_id, 'closed')
    ticket = await db.get_ticket(ticket_id)
    await callback.message.edit_text(ticket_card(ticket), reply_markup=admin_ticket_kb(ticket_id, 'closed'))
    try:
        await callback.bot.send_message(ticket['user_id'], t(ticket.get('language'), 'closed', ticket_id=ticket_id))
    except Exception:
        pass
    await callback.answer('Вопрос закрыт.')
