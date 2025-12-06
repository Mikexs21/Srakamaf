from typing import List
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.models import Player


def target_keyboard(players: List[Player], prefix: str) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    for p in players:
        kb.button(text=p.username, callback_data=f"{prefix}:{p.id}")
    kb.button(text="⬅️ Назад", callback_data=f"{prefix}:cancel")
    kb.adjust(2)
    return kb


def voting_keyboard(players: List[Player]):
    return target_keyboard(players, prefix="vote").as_markup()


def night_keyboard(players: List[Player]):
    return target_keyboard(players, prefix="night").as_markup()


def potato_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="🥔 Кинути", callback_data="potato_throw")
    kb.button(text="🙅‍♂️ Залишити", callback_data="potato_keep")
    kb.adjust(2)
    return kb.as_markup()


