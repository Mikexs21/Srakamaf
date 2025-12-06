from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from db.base import async_session
from db import crud
from db.models import GameState
from services import game_logic

router = Router()


@router.message(Command("start"), F.chat.type.in_({"group", "supergroup"}))
async def start_group(message: Message) -> None:
    async with async_session() as session:
        game = await game_logic.ensure_active_game(session, message.chat.id)
        await session.commit()
        await game_logic.render_lobby(session, message.bot, game)


@router.callback_query(F.data == "lobby_join")
async def lobby_join(callback: CallbackQuery) -> None:
    async with async_session() as session:
        game = await crud.get_active_game(session, callback.message.chat.id)
        if not game or game.state != GameState.LOBBY:
            await callback.answer("Гра вже йде")
            return
        existing = next((p for p in game.players if p.user_id == callback.from_user.id), None)
        if existing:
            await callback.answer("Ти вже в лобі")
        else:
            await crud.add_player(session, game, callback.from_user.id, callback.from_user.full_name)
            await session.commit()
            await game_logic.render_lobby(session, callback.bot, game)
            from utils.logging import logger, game_prefix
            logger.info("%s joined lobby %s", game_prefix(game.id, game.chat_id), callback.from_user.full_name)
            await callback.answer("Додано")


@router.callback_query(F.data == "lobby_leave")
async def lobby_leave(callback: CallbackQuery) -> None:
    async with async_session() as session:
        game = await crud.get_active_game(session, callback.message.chat.id)
        if not game:
            return
        player = next((p for p in game.players if p.user_id == callback.from_user.id), None)
        if player:
            await crud.remove_player(session, player.id)
            await session.commit()
            await game_logic.render_lobby(session, callback.bot, game)
            from utils.logging import logger, game_prefix
            logger.info("%s left lobby %s", game_prefix(game.id, game.chat_id), callback.from_user.full_name)
        await callback.answer("Вийшов")


@router.callback_query(F.data == "lobby_add_bot")
async def lobby_add_bot(callback: CallbackQuery) -> None:
    async with async_session() as session:
        game = await crud.get_active_game(session, callback.message.chat.id)
        if not game or game.state != GameState.LOBBY:
            await callback.answer("Гра вже почалась")
            return
        await game_logic.add_ai_player(session, game)
        await session.commit()
        await game_logic.render_lobby(session, callback.bot, game)
        from utils.logging import logger, game_prefix
        logger.info("%s bot added by %s", game_prefix(game.id, game.chat_id), callback.from_user.full_name)
        await callback.answer("Бота додано")


@router.callback_query(F.data == "lobby_start")
async def lobby_start(callback: CallbackQuery) -> None:
    async with async_session() as session:
        game = await crud.get_active_game(session, callback.message.chat.id)
        if not game or game.state != GameState.LOBBY:
            await callback.answer("Гра недоступна")
            return
        if len(game.players) < 4:
            await callback.answer("Мінімум 4 гравці")
            return
        await game_logic.start_game(session, callback.bot, game)
        await session.commit()
        await callback.answer("Гра почалась")
