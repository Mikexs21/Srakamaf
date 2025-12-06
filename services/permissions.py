from aiogram.types import CallbackQuery
from db.models import Game, GameState, Player


def ensure_phase(game: Game, allowed: list[GameState]) -> bool:
    return game.state in allowed


def ensure_alive(player: Player) -> bool:
    return player.is_alive


def can_act(game: Game, player: Player, allowed: list[GameState]) -> bool:
    return ensure_phase(game, allowed) and ensure_alive(player)


