from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.utils import CATEGORY_NAMES, LANGUAGES, category_name, status_name, t


def language_kb(prefix: str = 'user') -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f'{prefix}:lang:{code}')]
        for code, name in LANGUAGES.items()
    ])


def user_menu_kb(lang: str = 'ru') -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, 'btn_new'), callback_data='user:new_ticket')],
        [InlineKeyboardButton(text=t(lang, 'btn_my'), callback_data='user:my_tickets')],
        [InlineKeyboardButton(text=t(lang, 'btn_language'), callback_data='user:language')],
        [InlineKeyboardButton(text=t(lang, 'btn_help'), callback_data='user:help')],
    ])


def categories_kb(lang: str = 'ru') -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=name, callback_data=f'user:category:{code}')] for code, name in CATEGORY_NAMES[lang].items()]
    rows.append([InlineKeyboardButton(text=t(lang, 'btn_back'), callback_data='user:menu')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_kb(lang: str = 'ru') -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, 'btn_cancel'), callback_data='user:cancel')]])


def user_ticket_kb(ticket_id: int, status: str, lang: str = 'ru') -> InlineKeyboardMarkup:
    # Пользователю не показываем кнопку открытия карточки вопроса.
    # Он получает ответ прямо в чат, а история обращений доступна только в кратком виде.
    rows = []
    if status != 'closed':
        rows.append([InlineKeyboardButton(text=t(lang, 'btn_new_more'), callback_data='user:new_ticket')])
    rows.append([InlineKeyboardButton(text=t(lang, 'btn_menu'), callback_data='user:menu')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def user_tickets_list_kb(tickets: list[dict], lang: str = 'ru') -> InlineKeyboardMarkup:
    # Без кнопок открытия отдельных вопросов для обычных пользователей.
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, 'btn_new_more'), callback_data='user:new_ticket')],
        [InlineKeyboardButton(text=t(lang, 'btn_to_menu'), callback_data='user:menu')],
    ])


def admin_ticket_kb(ticket_id: int, status: str = 'open') -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text='✍️ Ответить', callback_data=f'admin:answer:{ticket_id}')]]
    if status != 'closed':
        rows.append([InlineKeyboardButton(text='✅ Закрыть', callback_data=f'admin:close:{ticket_id}')])
    rows.append([InlineKeyboardButton(text='📄 Карточка', callback_data=f'admin:view:{ticket_id}')])
    rows.append([InlineKeyboardButton(text='📜 История вопроса', callback_data=f'admin:history:{ticket_id}')])
    rows.append([InlineKeyboardButton(text='⬅️ Панель шейха', callback_data='admin:panel')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🟢 Новые вопросы', callback_data='admin:list:open')],
        [InlineKeyboardButton(text='🟡 Отвеченные вопросы', callback_data='admin:list:answered')],
        [InlineKeyboardButton(text='⚫ Закрытые вопросы', callback_data='admin:list:closed')],
        [InlineKeyboardButton(text='📜 История ответов', callback_data='admin:answers_history:0')],
        [InlineKeyboardButton(text='📊 Статистика', callback_data='admin:stats')],
        [InlineKeyboardButton(text='🌐 Язык панели', callback_data='admin:language')],
    ])


def admin_tickets_list_kb(tickets: list[dict], status: str) -> InlineKeyboardMarkup:
    rows = []
    for ticket in tickets:
        rows.append([InlineKeyboardButton(
            text=f"#{ticket['id']} · {category_name(ticket.get('category'), 'ru')} · {ticket.get('full_name') or ticket['user_id']}",
            callback_data=f"admin:view:{ticket['id']}",
        )])
    rows.append([InlineKeyboardButton(text='⬅️ Панель шейха', callback_data='admin:panel')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_answers_history_kb(page: int, total_pages: int, answer_rows: list[dict] | None = None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in answer_rows or []:
        rows.append([InlineKeyboardButton(
            text=f"📄 Полный текст: вопрос #{item['ticket_id']} / ответ #{item['message_id']}",
            callback_data=f"admin:answer_full:{item['message_id']}:{page}",
        )])

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text='⬅️ Назад', callback_data=f'admin:answers_history:{page - 1}'))
    if page + 1 < total_pages:
        nav.append(InlineKeyboardButton(text='Вперёд ➡️', callback_data=f'admin:answers_history:{page + 1}'))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text='⬅️ Панель шейха', callback_data='admin:panel')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_answer_full_kb(
    ticket_id: int,
    page: int = 0,
    *,
    answer_message_id: int | None = None,
    has_question_media: bool = False,
    has_answer_media: bool = False,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if answer_message_id is not None and has_question_media:
        rows.append([InlineKeyboardButton(
            text='📎 Отправить оригинал вопроса',
            callback_data=f'admin:send_media:{answer_message_id}:question',
        )])
    if answer_message_id is not None and has_answer_media:
        rows.append([InlineKeyboardButton(
            text='🎙/📎 Отправить оригинал ответа',
            callback_data=f'admin:send_media:{answer_message_id}:answer',
        )])
    rows.extend([
        [InlineKeyboardButton(text='📄 Карточка вопроса', callback_data=f'admin:view:{ticket_id}')],
        [InlineKeyboardButton(text='📜 Назад к истории ответов', callback_data=f'admin:answers_history:{page}')],
        [InlineKeyboardButton(text='⬅️ Панель шейха', callback_data='admin:panel')],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)
