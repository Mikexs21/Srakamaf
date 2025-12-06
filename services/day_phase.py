from __future__ import annotations
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Game, Player
from utils.logging import logger, game_prefix
import visuals
from utils.logging import logger


async def start_day(session: AsyncSession, bot: Bot, game: Game, outcome) -> None:
    game.current_round += 1
    game.state = GameState.DAY_DISCUSSION
    killed_names = []
    for p in outcome.killed:
        label = p.username
        if game.settings.show_role_on_death:
            label = f"{p.username} ({visuals.ROLE_NAMES.get(p.role, p.role.name)})"
        killed_names.append(label)
        if p.last_words and p.last_words_round == game.current_round:
            await bot.send_message(game.chat_id, visuals.last_words_public(p.username, p.last_words))
            logger.info("%s last words from %s: %s", game_prefix(game.id, game.chat_id, game.current_round), p.username, p.last_words)
    summary = visuals.night_summary(killed_names, outcome.saved.username if outcome.saved else None, blind=game.blind_next_night)
    game.blind_next_night = False
    await bot.send_message(game.chat_id, summary)
    live_count = len([p for p in game.players if p.is_alive])
    await bot.send_message(game.chat_id, visuals.day_header(game.current_round) + f"\nЖиві: {live_count}")
    logger.info("%s state=DAY_DISCUSSION start", game_prefix(game.id, game.chat_id, game.current_round))

