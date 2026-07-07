from aiogram.fsm.state import State, StatesGroup


class UserTicketState(StatesGroup):
    choosing_category = State()
    waiting_question = State()


class AdminAnswerState(StatesGroup):
    waiting_answer = State()
