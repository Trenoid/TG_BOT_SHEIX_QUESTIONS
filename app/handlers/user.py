from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import BaseFilter, CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.database import Database
from app.keyboards import admin_panel_kb, cancel_kb, categories_kb, language_kb, user_menu_kb, user_ticket_kb, user_tickets_list_kb
from app.services import is_text_question_content, message_content_type, message_file_id, message_text_preview, notify_staff_about_ticket
from app.states import UserTicketState
from app.utils import category_name, format_dt, language_name, normalize_lang, status_name, t

router = Router(name='user')


class NonAdminFilter(BaseFilter):
    async def __call__(self, event: TelegramObject, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> bool:
        user = getattr(event, 'from_user', None)
        staff_ids = admin_ids | (sheikh_ids or set())
        return bool(user and user.id not in staff_ids)


# Важно: весь пользовательский роутер обрабатывает только обычных пользователей.
# Администраторы/шейхи полностью обслуживаются app.handlers.admin.
# Так мы исключаем конфликт маршрутов и ситуацию, когда пользовательские действия
# случайно перехватываются админской логикой.
router.message.filter(NonAdminFilter())
router.callback_query.filter(NonAdminFilter())


def _staff_ids(admin_ids: set[int], sheikh_ids: set[int] | None = None) -> set[int]:
    return admin_ids | (sheikh_ids or set())


def _is_private(message: Message) -> bool:
    return message.chat.type == 'private'


async def _remember_user(message: Message, db: Database) -> str:
    user = message.from_user
    lang = await db.get_user_language(user.id)
    await db.upsert_user(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        language=None,
    )
    return lang


async def _lang(db: Database, user_id: int) -> str:
    return await db.get_user_language(user_id)


def _tickets_summary(tickets: list[dict], lang: str) -> str:
    lines = [t(lang, 'your_tickets'), '']
    for ticket in tickets:
        lines.append(
            f"#{ticket['id']} · {category_name(ticket.get('category'), lang)} · "
            f"{status_name(ticket.get('status', 'open'))} · {format_dt(ticket.get('created_at'))}"
        )
    lines.append('')
    lines.append(t(lang, 'tickets_note'))
    return '\n'.join(lines)


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, db: Database, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> None:
    await state.clear()
    if message.from_user.id in _staff_ids(admin_ids, sheikh_ids):
        await message.answer(
            '<b>Панель шейха · Вопросы шейху</b> 🕌\n\n'
            'Вы вошли как шейх/администратор. Здесь будут вопросы пользователей.',
            reply_markup=admin_panel_kb(),
        )
        return
    lang = await _remember_user(message, db)
    await message.answer(t(lang, 'welcome'), reply_markup=user_menu_kb(lang))


@router.message(Command('language'))
async def language_command(message: Message, db: Database) -> None:
    await _remember_user(message, db)
    lang = await db.get_user_language(message.from_user.id)
    await message.answer(t(lang, 'choose_language'), reply_markup=language_kb())


@router.message(Command('help'))
async def help_command(message: Message, db: Database) -> None:
    lang = await _remember_user(message, db)
    await message.answer(t(lang, 'help'), reply_markup=user_menu_kb(lang))


@router.message(Command('new'))
async def new_command(message: Message, state: FSMContext, db: Database) -> None:
    lang = await _remember_user(message, db)
    await state.set_state(UserTicketState.choosing_category)
    await message.answer(t(lang, 'choose_category'), reply_markup=categories_kb(lang))


@router.message(Command('my'))
async def my_command(message: Message, db: Database) -> None:
    lang = await _remember_user(message, db)
    tickets = await db.list_tickets(user_id=message.from_user.id, limit=10)
    if not tickets:
        await message.answer(t(lang, 'no_tickets'), reply_markup=user_menu_kb(lang))
        return
    await message.answer(_tickets_summary(tickets, lang), reply_markup=user_tickets_list_kb(tickets, lang))


@router.callback_query(F.data == 'user:language')
async def user_language(callback: CallbackQuery, db: Database) -> None:
    lang = await _lang(db, callback.from_user.id)
    await callback.message.edit_text(t(lang, 'choose_language'), reply_markup=language_kb())
    await callback.answer()


@router.callback_query(F.data.startswith('user:lang:'))
async def set_language(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
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
        t(lang, 'language_saved', language=language_name(lang)) + '\n\n' + t(lang, 'welcome'),
        reply_markup=user_menu_kb(lang),
    )
    await callback.answer()


@router.callback_query(F.data == 'user:menu')
async def user_menu(callback: CallbackQuery, state: FSMContext, db: Database, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> None:
    await state.clear()
    if callback.from_user.id in _staff_ids(admin_ids, sheikh_ids):
        await callback.message.edit_text(
            '<b>Панель шейха · Вопросы шейху</b> 🕌\n\n'
            'Вы вошли как шейх/администратор. Здесь будут вопросы пользователей.',
            reply_markup=admin_panel_kb(),
        )
        await callback.answer()
        return
    lang = await _lang(db, callback.from_user.id)
    await callback.message.edit_text(t(lang, 'welcome'), reply_markup=user_menu_kb(lang))
    await callback.answer()


@router.callback_query(F.data == 'user:help')
async def user_help(callback: CallbackQuery, db: Database) -> None:
    lang = await _lang(db, callback.from_user.id)
    await callback.message.edit_text(t(lang, 'help'), reply_markup=user_menu_kb(lang))
    await callback.answer()


@router.callback_query(F.data == 'user:new_ticket')
async def new_ticket(callback: CallbackQuery, state: FSMContext, db: Database, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> None:
    if callback.from_user.id in _staff_ids(admin_ids, sheikh_ids):
        await state.clear()
        await callback.message.edit_text(
            'Вы вошли как <b>шейх/администратор</b>. Кнопка «Задать вопрос шейху» для вас скрыта.',
            reply_markup=admin_panel_kb(),
        )
        await callback.answer()
        return
    lang = await _lang(db, callback.from_user.id)
    await state.set_state(UserTicketState.choosing_category)
    await callback.message.edit_text(t(lang, 'choose_category'), reply_markup=categories_kb(lang))
    await callback.answer()


@router.callback_query(F.data == 'user:cancel')
async def cancel(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    lang = await _lang(db, callback.from_user.id)
    await state.clear()
    await callback.message.edit_text(t(lang, 'cancelled'), reply_markup=user_menu_kb(lang))
    await callback.answer()


@router.callback_query(F.data.startswith('user:category:'))
async def choose_category(callback: CallbackQuery, state: FSMContext, db: Database, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> None:
    if callback.from_user.id in _staff_ids(admin_ids, sheikh_ids):
        await state.clear()
        await callback.message.edit_text('Это действие доступно только обычному пользователю.', reply_markup=admin_panel_kb())
        await callback.answer()
        return
    lang = await _lang(db, callback.from_user.id)
    category = callback.data.split(':', 2)[2]
    await state.update_data(category=category, language=lang)
    await state.set_state(UserTicketState.waiting_question)
    await callback.message.edit_text(
        t(lang, 'category_selected', category=category_name(category, lang)),
        reply_markup=cancel_kb(lang),
    )
    await callback.answer()


@router.message(UserTicketState.waiting_question)
async def receive_question(message: Message, state: FSMContext, db: Database, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> None:
    if not _is_private(message):
        return
    data = await state.get_data()
    lang = data.get('language') or await db.get_user_language(message.from_user.id)
    category = data.get('category') or 'other'
    if not is_text_question_content(message_content_type(message), message.text):
        await message.answer(t(lang, 'text_question_only'), reply_markup=cancel_kb(lang))
        return
    user = message.from_user
    full_name = user.full_name if user else 'Unknown'
    username = user.username if user else None

    ticket_id = await db.create_ticket(
        user_id=user.id,
        username=username,
        full_name=full_name,
        category=category,
        language=lang,
    )
    await db.add_message(
        ticket_id=ticket_id,
        sender_type='user',
        sender_id=user.id,
        text=message_text_preview(message),
        content_type=message_content_type(message),
        file_id=message_file_id(message),
    )
    await state.clear()

    await message.answer(
        t(lang, 'ticket_created', ticket_id=ticket_id),
        reply_markup=user_ticket_kb(ticket_id, 'open', lang),
    )
    await notify_staff_about_ticket(message.bot, db, admin_ids, sheikh_ids or set(), ticket_id, message)


@router.callback_query(F.data == 'user:my_tickets')
async def my_tickets(callback: CallbackQuery, db: Database) -> None:
    lang = await _lang(db, callback.from_user.id)
    tickets = await db.list_tickets(user_id=callback.from_user.id, limit=10)
    if not tickets:
        await callback.message.edit_text(t(lang, 'no_tickets'), reply_markup=user_menu_kb(lang))
    else:
        await callback.message.edit_text(_tickets_summary(tickets, lang), reply_markup=user_tickets_list_kb(tickets, lang))
    await callback.answer()


@router.callback_query(F.data.startswith('user:ticket:'))
async def view_my_ticket(callback: CallbackQuery, db: Database) -> None:
    # Старые кнопки из прошлых версий больше не открывают карточку вопроса пользователю.
    lang = await _lang(db, callback.from_user.id)
    await callback.answer(t(lang, 'ticket_open_disabled'), show_alert=True)


@router.message()
async def fallback(message: Message, db: Database, admin_ids: set[int], sheikh_ids: set[int] | None = None) -> None:
    if not _is_private(message):
        return
    if message.from_user.id in _staff_ids(admin_ids, sheikh_ids):
        await message.answer(
            'Вы вошли как <b>шейх/администратор</b>. Откройте панель, чтобы видеть вопросы пользователей:',
            reply_markup=admin_panel_kb(),
        )
        return
    lang = await _remember_user(message, db)
    await message.answer(t(lang, 'fallback'), reply_markup=user_menu_kb(lang))
