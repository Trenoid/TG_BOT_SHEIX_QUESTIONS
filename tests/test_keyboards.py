from app.keyboards import admin_answer_sent_kb, admin_publication_review_kb, admin_ticket_kb, sheikh_panel_kb, sheikh_question_kb, user_menu_kb, user_ticket_kb, user_tickets_list_kb


def _callback_data(markup):
    data = []
    for row in markup.inline_keyboard:
        for button in row:
            data.append(button.callback_data)
    return data


def test_user_ticket_keyboard_has_no_open_question_button():
    callbacks = _callback_data(user_ticket_kb(ticket_id=5, status='open', lang='ru'))
    assert 'user:ticket:5' not in callbacks
    assert all(not cb.startswith('user:ticket:') for cb in callbacks if cb)


def test_user_tickets_list_keyboard_has_no_open_question_buttons():
    markup = user_tickets_list_kb([{'id': 5, 'status': 'open'}], lang='ru')
    callbacks = _callback_data(markup)
    assert all(not cb.startswith('user:ticket:') for cb in callbacks if cb)


def test_user_menu_has_only_user_actions():
    callbacks = _callback_data(user_menu_kb(lang='ru'))
    assert callbacks == ['user:new_ticket', 'user:my_tickets', 'user:language', 'user:help']
    assert all(not cb.startswith(('admin:', 'sheikh:')) for cb in callbacks if cb)

from app.keyboards import admin_answers_history_kb


def test_admin_ticket_keyboard_has_no_close_button():
    callbacks = _callback_data(admin_ticket_kb(ticket_id=5, status='open'))
    assert 'admin:close:5' not in callbacks
    assert all(not cb.startswith('admin:close:') for cb in callbacks if cb)


def test_sheikh_panel_is_minimal():
    callbacks = _callback_data(sheikh_panel_kb())
    assert callbacks == ['sheikh:list:open', 'sheikh:list:answered']


def test_sheikh_question_keyboard_has_only_answer_button():
    callbacks = _callback_data(sheikh_question_kb(ticket_id=7))
    assert callbacks == ['admin:answer:7']


def test_publication_review_keyboard_has_publish_only_when_allowed():
    publishable = _callback_data(admin_publication_review_kb(ticket_id=10, answer_message_id=55, can_publish=True))
    already_published = _callback_data(admin_publication_review_kb(ticket_id=10, answer_message_id=55, can_publish=False))
    assert 'admin:publish:55' in publishable
    assert 'admin:publish:55' not in already_published


def test_publication_review_keyboard_has_mark_button_when_manual_publication_needed():
    callbacks = _callback_data(admin_publication_review_kb(
        ticket_id=10,
        answer_message_id=55,
        can_publish=False,
        can_mark_published=True,
    ))
    assert 'admin:publish:55' not in callbacks
    assert 'admin:mark_published:55' in callbacks


def test_admin_answer_sent_keyboard_has_publish_button():
    callbacks = _callback_data(admin_answer_sent_kb(ticket_id=16, answer_message_id=17))
    assert 'admin:publish:17' in callbacks
    assert 'admin:view:16' in callbacks


def test_admin_answer_sent_keyboard_has_mark_button_when_manual_publication_needed():
    callbacks = _callback_data(admin_answer_sent_kb(
        ticket_id=16,
        answer_message_id=17,
        can_publish=False,
        can_mark_published=True,
    ))
    assert 'admin:publish:17' not in callbacks
    assert 'admin:mark_published:17' in callbacks


def test_admin_answers_history_keyboard_has_pagination_buttons():
    callbacks = _callback_data(admin_answers_history_kb(page=1, total_pages=3))
    assert 'admin:answers_history:0' in callbacks
    assert 'admin:answers_history:2' in callbacks
    assert 'admin:panel' in callbacks


def test_admin_answers_history_keyboard_has_full_answer_buttons():
    rows = [{'ticket_id': 10, 'message_id': 55}]
    callbacks = _callback_data(admin_answers_history_kb(page=0, total_pages=1, answer_rows=rows))
    assert 'admin:answer_full:55:0' in callbacks
