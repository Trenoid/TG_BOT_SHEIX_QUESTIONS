from app.keyboards import user_ticket_kb, user_tickets_list_kb


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

from app.keyboards import admin_answers_history_kb


def test_admin_answers_history_keyboard_has_pagination_buttons():
    callbacks = _callback_data(admin_answers_history_kb(page=1, total_pages=3))
    assert 'admin:answers_history:0' in callbacks
    assert 'admin:answers_history:2' in callbacks
    assert 'admin:panel' in callbacks


def test_admin_answers_history_keyboard_has_full_answer_buttons():
    rows = [{'ticket_id': 10, 'message_id': 55}]
    callbacks = _callback_data(admin_answers_history_kb(page=0, total_pages=1, answer_rows=rows))
    assert 'admin:answer_full:55:0' in callbacks
