from __future__ import annotations
from collections import defaultdict
from typing import Optional
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

import config
import visuals
from db import crud
from db.models import Game, GameState, Player, Role
from keyboards import group_keyboards
from services import timers, lynch_phase, game_logic
from utils.logging import logger, game_prefix


async def start_voting(session: AsyncSession, bot: Bot, game: Game) -> None:
    await crud.set_game_state(session, game, GameState.VOTING)
    await crud.reset_votes(session, game)
    msg = await bot.send_message(game.chat_id, visuals.voting_group(), reply_markup=group_keyboards.voting_keyboard())
    await crud.set_message_id(session, game, "voting_message_id", msg.message_id)
    duration = game.settings.voting_duration if game.settings else config.VOTING_DURATION
    timers.timers.set_timer(game.id, duration, lambda: finalize_voting_task(bot, game.id))
    logger.info("%s state=VOTING start", game_prefix(game.id, game.chat_id, game.current_round))


async def finalize_voting(session: AsyncSession, bot: Bot, game: Game) -> None:
    await session.refresh(game)
    votes: defaultdict[int, int] = defaultdict(int)
    silenced = {
        p.buffs_state.get("silenced_target")
        for p in game.players
        if p.buffs_state and p.buffs_state.get("silence_used")
    }
    for player in game.players:
        if not player.is_alive or not player.last_vote_target_id:
            continue
        if player.id in silenced:
            continue
        weight = 2 if player.role == Role.MAYOR else 1
        votes[player.last_vote_target_id] += weight
    if not votes:
        await bot.send_message(game.chat_id, "Ніхто не проголосував.")
        await crud.set_game_state(session, game, GameState.DAY_DISCUSSION)
        duration = game.settings.day_duration if game.settings else config.DAY_DURATION
        timers.timers.set_timer(game.id, duration, lambda: game_logic.start_night_task(bot, game.id))
        logger.info("%s voting ended: no votes", game_prefix(game.id, game.chat_id, game.current_round))
        return
    top_target_id = max(votes, key=votes.get)
    top_target = next((p for p in game.players if p.id == top_target_id), None)
    if not top_target:
        await bot.send_message(game.chat_id, "Кандидат не знайдений.")
        duration = game.settings.day_duration if game.settings else config.DAY_DURATION
        timers.timers.set_timer(game.id, duration, lambda: game_logic.start_night_task(bot, game.id))
        logger.info("%s voting ended: candidate missing", game_prefix(game.id, game.chat_id, game.current_round))
        return
    game.state = GameState.LYNCH_CONFIRMATION
    lynch_phase.LYNCH_CANDIDATE[game.id] = top_target.id
    msg = await bot.send_message(game.chat_id, visuals.lynch_confirmation(top_target.username), reply_markup=group_keyboards.lynch_keyboard())
    await crud.set_message_id(session, game, "lynch_confirm_message_id", msg.message_id)
    await lynch_phase.schedule_finalize(session, bot, game)
    logger.info("%s lynch candidate %s", game_prefix(game.id, game.chat_id, game.current_round), top_target.username)


async def finalize_voting_task(bot: Bot, game_id: int) -> None:
    from db.base import async_session
    async with async_session() as session:
        game = await crud.get_game_by_id(session, game_id)
        if not game or game.state != GameState.VOTING:
            return
        await finalize_voting(session, bot, game)
        await session.commit()


async def register_vote(session: AsyncSession, bot: Bot, game: Game, player: Player, target_id: int) -> None:
    await crud.set_vote(session, player, target_id)
    logger.info("%s vote: %s -> %s", game_prefix(game.id, game.chat_id, game.current_round), player.username, target_id)
    alive_voters = [p for p in game.players if p.is_alive]
    voted = [p for p in alive_voters if p.last_vote_target_id]
    if len(voted) == len(alive_voters):
        timers.timers.cancel(game.id)
        await finalize_voting(session, bot, game)
        await session.commit()

