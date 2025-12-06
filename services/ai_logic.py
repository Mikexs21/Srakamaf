from __future__ import annotations
import random
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Player, Role, Game
from db import crud
from ai.profiles import PROFILE_MAP
from utils.logging import logger, game_prefix


class GameView:
    def __init__(self, game: Game, players: List[Player]):
        self.game = game
        self.players = players


async def update_memory(session: AsyncSession, game: Game, votes: List[tuple[int, int]]) -> None:
    # votes: list of (voter_id, target_id)
    await crud.ensure_suspicions(session, game)
    for voter_id, target_id in votes:
        voter = next(p for p in game.players if p.id == voter_id)
        target = next(p for p in game.players if p.id == target_id)
        if voter.is_bot:
            delta = 0.1 if target.is_alive else -0.2
            await crud.update_suspicion(session, game.id, voter.id, target.id, delta)
            logger.info("%s AI suspicion update %s -> %s (delta %.2f)", game_prefix(game.id, game.chat_id, game.current_round), voter.username, target.username, delta)


async def decide_night_action(
    session: AsyncSession,
    game: Game,
    player: Player,
) -> Optional[dict]:
    if not player.is_alive:
        return None
    await crud.ensure_suspicions(session, game)
    from db.models import AIProfile  # imported here to avoid circular import in typing tools
    profile_obj = await session.get(AIProfile, player.ai_profile_id) if player.ai_profile_id else None
    profile_data = PROFILE_MAP.get(profile_obj.name if profile_obj else "semi_random")
    alive_targets = [p for p in game.players if p.is_alive and p.id != player.id]
    if not alive_targets:
        return None
    choice = random.choice(alive_targets)
    if player.role in {Role.DON, Role.MAFIA}:
        suspicions = await crud.get_suspicions(session, game.id, player.id)
        if suspicions:
            suspicions = sorted(suspicions, key=lambda s: s.suspicion_score, reverse=True)
            choice = next((t for t in alive_targets if t.id == suspicions[0].target_player_id), choice)
        logger.info("%s AI %s chooses mafia target %s", game_prefix(game.id, game.chat_id, game.current_round), player.username, choice.username)
        return {"target_id": choice.id, "mode": "kill"}
    if player.role == Role.DOCTOR:
        if random.random() < 0.5:
            choice = player
        logger.info("%s AI %s heals %s", game_prefix(game.id, game.chat_id, game.current_round), player.username, choice.username)
        return {"target_id": choice.id, "mode": "heal"}
    if player.role == Role.DETECTIVE:
        target = random.choice(alive_targets)
        mode = "shoot" if random.random() < profile_data.aggression else "inspect"
        logger.info("%s AI %s detective %s %s", game_prefix(game.id, game.chat_id, game.current_round), player.username, mode, target.username)
        return {"target_id": target.id, "mode": mode}
    if player.role == Role.HOOKER:
        target = random.choice(alive_targets)
        logger.info("%s AI %s blocks %s", game_prefix(game.id, game.chat_id, game.current_round), player.username, target.username)
        return {"target_id": target.id, "mode": "block"}
    if player.role == Role.SUICIDE and not player.used_suicide:
        if random.random() < 0.5:
            target = random.choice(alive_targets)
            logger.info("%s AI %s suicide targets %s", game_prefix(game.id, game.chat_id, game.current_round), player.username, target.username)
            return {"target_id": target.id, "mode": "suicide"}
    if player.role == Role.JESTER:
        if random.random() < 0.3:
            target = random.choice(alive_targets)
            logger.info("%s AI %s jester swaps %s", game_prefix(game.id, game.chat_id, game.current_round), player.username, target.username)
            return {"target_id": target.id, "mode": "swap"}
    if player.role == Role.DEPUTY:
        target = random.choice(alive_targets)
        logger.info("%s AI %s deputy inspects %s", game_prefix(game.id, game.chat_id, game.current_round), player.username, target.username)
        return {"target_id": target.id, "mode": "inspect"}
    return None


async def decide_vote(session: AsyncSession, game: Game, player: Player) -> Optional[int]:
    if not player.is_alive:
        return None
    await crud.ensure_suspicions(session, game)
    suspicions = await crud.get_suspicions(session, game.id, player.id)
    alive_targets = [p for p in game.players if p.is_alive and p.id != player.id]
    if not alive_targets:
        return None
    if suspicions:
        suspicions = sorted(suspicions, key=lambda s: s.suspicion_score, reverse=True)
        for s in suspicions:
            target = next((t for t in alive_targets if t.id == s.target_player_id), None)
            if target:
                logger.info("%s AI %s votes (suspicion) %s", game_prefix(game.id, game.chat_id, game.current_round), player.username, target.username)
                return target.id
    target = random.choice(alive_targets)
    logger.info("%s AI %s votes (random) %s", game_prefix(game.id, game.chat_id, game.current_round), player.username, target.username)
    return target.id


