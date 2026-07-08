from __future__ import annotations

from datetime import datetime, timezone, timedelta
from html import escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    MOSCOW_TZ = ZoneInfo('Europe/Moscow')
except ZoneInfoNotFoundError:
    # Fallback for Windows environments without the tzdata package.
    MOSCOW_TZ = timezone(timedelta(hours=3), name='MSK')
DEFAULT_LANG = 'ru'
LANGUAGES = {
    'ru': '🇷🇺 Русский',
    'en': '🇬🇧 English',
    'ar': '🇸🇦 العربية',
}

STATUS_NAMES_RU = {
    'open': '🟢 открыт',
    'answered': '🟡 отвечен',
    'published': '✅ опубликован',
    'closed': '⚫ закрыт',
}

CATEGORY_NAMES = {
    'ru': {
        'aqidah': '🕌 Акыда / основы веры',
        'ibadah': '🤲 Намаз, пост, закят, хадж',
        'fiqh': '📚 Фикх / бытовые вопросы',
        'family': '👨‍👩‍👧‍👦 Семья и брак',
        'finance': '💰 Работа, бизнес и деньги',
        'quran_hadith': '📖 Коран и хадисы',
        'manners': '🌿 Нравственность и поведение',
        'other': '✨ Другое',
    },
    'en': {
        'aqidah': '🕌 Aqeedah / creed',
        'ibadah': '🤲 Prayer, fasting, zakat, hajj',
        'fiqh': '📚 Fiqh / daily matters',
        'family': '👨‍👩‍👧‍👦 Family and marriage',
        'finance': '💰 Work, business and money',
        'quran_hadith': '📖 Qur’an and Hadith',
        'manners': '🌿 Manners and character',
        'other': '✨ Other',
    },
    'ar': {
        'aqidah': '🕌 العقيدة وأصول الإيمان',
        'ibadah': '🤲 الصلاة والصيام والزكاة والحج',
        'fiqh': '📚 الفقه والمسائل اليومية',
        'family': '👨‍👩‍👧‍👦 الأسرة والزواج',
        'finance': '💰 العمل والتجارة والمال',
        'quran_hadith': '📖 القرآن والحديث',
        'manners': '🌿 الأخلاق والسلوك',
        'other': '✨ أخرى',
    },
}

TEXTS = {
    'ru': {
        'welcome': '<b>Ас-саляму алейкум! 👋</b>\n\nЭто бот <b>«Вопросы шейху»</b>. Здесь вы можете отправить вопрос по исламской теме, а администратор/шейх ответит вам прямо в Telegram.\n\nВыберите действие ниже:',
        'help': '<b>Как пользоваться ботом</b>\n\n1. Нажмите <b>«Задать вопрос шейху»</b>.\n2. Выберите тему вопроса.\n3. Напишите вопрос одним текстовым сообщением.\n4. Когда ответ будет готов, он придёт сюда же в бот.\n\nКоманды:\n/start — открыть меню\n/new — задать вопрос\n/my — мои вопросы\n/language — сменить язык\n/help — помощь',
        'choose_language': 'Выберите язык интерфейса:',
        'language_saved': '✅ Язык сохранён: {language}',
        'choose_category': 'Выберите тему вопроса:',
        'category_selected': 'Тема: <b>{category}</b>\n\nТеперь отправьте ваш вопрос одним текстовым сообщением.',
        'text_question_only': 'Пожалуйста, отправьте вопрос обычным текстовым сообщением. Голосовые, фото, видео и файлы для вопросов не принимаются.',
        'cancelled': 'Действие отменено.',
        'ticket_created': '✅ Ваш вопрос <b>#{ticket_id}</b> отправлен.\n\nКогда ответ будет готов, он придёт вам здесь.',
        'no_tickets': 'У вас пока нет вопросов.',
        'your_tickets': 'Ваши последние вопросы:',
        'tickets_note': 'Карточки вопросов скрыты. Ответ от шейха придёт прямо сюда в чат.',
        'ticket_open_disabled': 'Открытие карточки вопроса скрыто. Ответ придёт прямо в чат.',
        'not_found': 'Вопрос не найден.',
        'fallback': 'Чтобы задать вопрос шейху, нажмите кнопку ниже или используйте команду /new.',
        'admin_answer_title': '💬 <b>Ответ по вашему вопросу #{ticket_id}</b>',
        'after_answer': 'Если хотите задать ещё один вопрос, используйте /new.',
        'closed': '✅ Ваш вопрос <b>#{ticket_id}</b> закрыт администратором.',
        'btn_new': '✍️ Задать вопрос шейху',
        'btn_my': '📋 Мои вопросы',
        'btn_help': 'ℹ️ Помощь',
        'btn_language': '🌐 Язык / Language / اللغة',
        'btn_back': '⬅️ Назад',
        'btn_cancel': '❌ Отменить',
        'btn_open_ticket': '📄 Открыть вопрос',
        'btn_new_more': '✍️ Задать ещё вопрос',
        'btn_menu': '🏠 Меню',
        'btn_to_menu': '⬅️ В меню',
    },
    'en': {
        'welcome': '<b>Assalamu alaikum! 👋</b>\n\nThis is <b>“Questions to the Sheikh”</b>. You can send an Islamic question here, and the admin/sheikh will answer you directly in Telegram.\n\nChoose an action below:',
        'help': '<b>How to use the bot</b>\n\n1. Tap <b>“Ask the Sheikh”</b>.\n2. Choose the topic.\n3. Send your question as one text message.\n4. When the answer is ready, it will arrive here in the bot.\n\nCommands:\n/start — open menu\n/new — ask a question\n/my — my questions\n/language — change language\n/help — help',
        'choose_language': 'Choose interface language:',
        'language_saved': '✅ Language saved: {language}',
        'choose_category': 'Choose the topic of your question:',
        'category_selected': 'Topic: <b>{category}</b>\n\nNow send your question as one text message.',
        'text_question_only': 'Please send your question as a regular text message. Voice messages, photos, videos and files are not accepted for questions.',
        'cancelled': 'Action cancelled.',
        'ticket_created': '✅ Your question <b>#{ticket_id}</b> has been sent.\n\nWhen the answer is ready, it will arrive here.',
        'no_tickets': 'You do not have any questions yet.',
        'your_tickets': 'Your latest questions:',
        'tickets_note': 'Question cards are hidden. The sheikh’s answer will arrive directly in this chat.',
        'ticket_open_disabled': 'Opening the question card is hidden. The answer will arrive directly in chat.',
        'not_found': 'Question not found.',
        'fallback': 'To ask the sheikh a question, tap the button below or use /new.',
        'admin_answer_title': '💬 <b>Answer to your question #{ticket_id}</b>',
        'after_answer': 'To ask another question, use /new.',
        'closed': '✅ Your question <b>#{ticket_id}</b> has been closed by the administrator.',
        'btn_new': '✍️ Ask the Sheikh',
        'btn_my': '📋 My questions',
        'btn_help': 'ℹ️ Help',
        'btn_language': '🌐 Language',
        'btn_back': '⬅️ Back',
        'btn_cancel': '❌ Cancel',
        'btn_open_ticket': '📄 Open question',
        'btn_new_more': '✍️ Ask another question',
        'btn_menu': '🏠 Menu',
        'btn_to_menu': '⬅️ To menu',
    },
    'ar': {
        'welcome': '<b>السلام عليكم ورحمة الله وبركاته 👋</b>\n\nهذا بوت <b>«أسئلة للشيخ»</b>. يمكنك إرسال سؤال شرعي، وسيصلك جواب المشرف/الشيخ هنا في تيليجرام.\n\nاختر من القائمة:',
        'help': '<b>طريقة استخدام البوت</b>\n\n1. اضغط <b>«اسأل الشيخ»</b>.\n2. اختر موضوع السؤال.\n3. أرسل السؤال في رسالة نصية واحدة.\n4. عند جاهزية الجواب سيصلك هنا في البوت.\n\nالأوامر:\n/start — فتح القائمة\n/new — إرسال سؤال\n/my — أسئلتي\n/language — تغيير اللغة\n/help — المساعدة',
        'choose_language': 'اختر لغة الواجهة:',
        'language_saved': '✅ تم حفظ اللغة: {language}',
        'choose_category': 'اختر موضوع السؤال:',
        'category_selected': 'الموضوع: <b>{category}</b>\n\nالآن أرسل سؤالك في رسالة نصية واحدة.',
        'text_question_only': 'يرجى إرسال السؤال كرسالة نصية عادية. لا تُقبل الرسائل الصوتية أو الصور أو الفيديو أو الملفات للأسئلة.',
        'cancelled': 'تم إلغاء العملية.',
        'ticket_created': '✅ تم إرسال سؤالك <b>#{ticket_id}</b>.\n\nعند جاهزية الجواب سيصلك هنا.',
        'no_tickets': 'ليس لديك أسئلة بعد.',
        'your_tickets': 'آخر أسئلتك:',
        'tickets_note': 'بطاقات الأسئلة مخفية. سيصل جواب الشيخ مباشرة في هذه المحادثة.',
        'ticket_open_disabled': 'فتح بطاقة السؤال مخفي. سيصلك الجواب مباشرة في المحادثة.',
        'not_found': 'لم يتم العثور على السؤال.',
        'fallback': 'لإرسال سؤال للشيخ اضغط الزر بالأسفل أو استخدم /new.',
        'admin_answer_title': '💬 <b>جواب على سؤالك #{ticket_id}</b>',
        'after_answer': 'إذا أردت إرسال سؤال آخر استخدم /new.',
        'closed': '✅ تم إغلاق سؤالك <b>#{ticket_id}</b> بواسطة المشرف.',
        'btn_new': '✍️ اسأل الشيخ',
        'btn_my': '📋 أسئلتي',
        'btn_help': 'ℹ️ المساعدة',
        'btn_language': '🌐 اللغة',
        'btn_back': '⬅️ رجوع',
        'btn_cancel': '❌ إلغاء',
        'btn_open_ticket': '📄 فتح السؤال',
        'btn_new_more': '✍️ إرسال سؤال آخر',
        'btn_menu': '🏠 القائمة',
        'btn_to_menu': '⬅️ إلى القائمة',
    },
}


def normalize_lang(lang: str | None) -> str:
    return lang if lang in LANGUAGES else DEFAULT_LANG


def t(lang: str | None, key: str, **kwargs: object) -> str:
    lang = normalize_lang(lang)
    template = TEXTS[lang].get(key) or TEXTS[DEFAULT_LANG].get(key) or key
    return template.format(**kwargs)


def h(text: object) -> str:
    return escape(str(text), quote=True)


def now_iso() -> str:
    return datetime.now(MOSCOW_TZ).isoformat(timespec='seconds')


def format_dt(value: str | None) -> str:
    if not value:
        return '—'
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime('%d.%m.%Y %H:%M')
    except ValueError:
        return value


def status_name(status: str) -> str:
    return STATUS_NAMES_RU.get(status, status)


def category_name(category: str | None, lang: str | None = DEFAULT_LANG) -> str:
    lang = normalize_lang(lang)
    if not category:
        return CATEGORY_NAMES[lang]['other']
    return CATEGORY_NAMES[lang].get(category, CATEGORY_NAMES[DEFAULT_LANG].get(category, category))


def language_name(lang: str | None) -> str:
    return LANGUAGES.get(normalize_lang(lang), LANGUAGES[DEFAULT_LANG])


def user_link(user_id: int, full_name: str | None) -> str:
    name = h(full_name or str(user_id))
    return f'<a href="tg://user?id={user_id}">{name}</a>'


def ticket_title(ticket: dict) -> str:
    return f"#{ticket['id']} · {category_name(ticket.get('category'), 'ru')} · {status_name(ticket.get('status', 'open'))}"
