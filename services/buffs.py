from __future__ import annotations
from typing import List
from db.models import Player


def ensure_buff_state(player: Player) -> None:
    if player.buffs_state is None:
        player.buffs_state = {}


def attach_buff(player: Player, code: str) -> None:
    ensure_buff_state(player)
    player.buffs_state[code] = True


def has_buff(player: Player, code: str) -> bool:
    ensure_buff_state(player)
    return bool(player.buffs_state.get(code))


def consume_buff(player: Player, code: str) -> bool:
    ensure_buff_state(player)
    if player.buffs_state.get(code):
        player.buffs_state[code] = False
        return True
    return False


def active_role_candidates(players: List[Player]) -> List[Player]:
    return [p for p in players if has_buff(p, "ACTIVE_ROLE")]


