from aiogram.utils.keyboard import InlineKeyboardBuilder


def lobby_keyboard(join: bool = True, start: bool = True, add_bot: bool = True):
    kb = InlineKeyboardBuilder()
    if join:
        kb.button(text="Увійти", callback_data="lobby_join")
        kb.button(text="Вийти", callback_data="lobby_leave")
    if add_bot:
        kb.button(text="🤖 Додати бота", callback_data="lobby_add_bot")
    if start:
        kb.button(text="🚀 Старт гри", callback_data="lobby_start")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def voting_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="🗳️ Голосувати", callback_data="vote_open")
    return kb.as_markup()


def lynch_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Повісити", callback_data="lynch_yes")
    kb.button(text="❌ Пощадити", callback_data="lynch_no")
    kb.adjust(2)
    return kb.as_markup()
