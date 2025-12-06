from __future__ import annotations
from collections import defaultdict
from typing import Dict
import random
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

import config
from db import crud
from db.models import Game, GameState, Player, Role
from services import timers, buffs
from utils.logging import logger


LYNCH_VOTES: Dict[int, Dict[int, bool]] = {}
LYNCH_CANDIDATE: Dict[int, int] = {}


async def cast_vote(game: Game, player: Player, vote_yes: bool) -> None:
    votes = LYNCH_VOTES.setdefault(game.id, {})
    votes[player.id] = vote_yes


async def finalize(session: AsyncSession, bot: Bot, game: Game) -> None:
    votes = LYNCH_VOTES.pop(game.id, {})
    yes = 0
    no = 0
    for pid, val in votes.items():
        weight = 2 if any(p.id == pid and p.role == Role.MAYOR for p in game.players) else 1
        if val:
            yes += weight
        else:
            no += weight
    target_id = LYNCH_CANDIDATE.get(game.id)
    target = next((p for p in game.players if p.is_alive and p.id == target_id), None)
    if yes > no and target:
        if buffs.consume_buff(target, "EXTRA_LIFE_LYNCH"):
            await bot.send_message(game.chat_id, f"{target.username} дивом вижив! Баф спрацював.")
        elif target.role == Role.EXECUTIONER and random.random() < 0.5:
            await bot.send_message(game.chat_id, f"{target.username} вирвався з петлі!")
        else:
            await crud.mark_dead(session, target)
            await bot.send_message(game.chat_id, f"{target.username} повішено.")
            if game.settings.show_role_on_death:
                await bot.send_message(game.chat_id, f"{target.username} був: {target.role.name}")
    else:
        await bot.send_message(game.chat_id, "Повішення скасовано.")
    game.state = GameState.DAY_DISCUSSION
    logger.info("Lynch finished in chat %s", game.chat_id)
    from services import game_logic
    if await game_logic.check_victory(session, bot, game):
        return
    await game_logic.start_night(session, bot, game)


async def schedule_finalize(session: AsyncSession, bot: Bot, game: Game):
    timers.timers.set_timer(game.id, config.VOTING_DURATION, lambda: finalize_task(bot, game.id))


async def finalize_task(bot: Bot, game_id: int) -> None:
    from db.base import async_session
    async with async_session() as session:
        game = await session.get(Game, game_id)
        if not game or game.state != GameState.LYNCH_CONFIRMATION:
            return
        await finalize(session, bot, game)
        await session.commit()


