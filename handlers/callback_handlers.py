from __future__ import annotations
from typing import Optional
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

import config
from db.base import async_session
from db import crud
from db.models import Game, GameState, Player, Role
from services import shop as shop_service, voting, lynch_phase, buffs
from keyboards import private_keyboards
import visuals

router = Router()


async def find_player_game(session, user_id: int) -> tuple[Optional[Game], Optional[Player]]:
    res = await session.execute(
        select(Game, Player)
        .options(selectinload(Game.settings), selectinload(Game.players))
        .join(Player, Player.game_id == Game.id)
        .where(Player.user_id == user_id)
        .where(Game.state != GameState.END)
    )
    row = res.first()
    if not row:
        return None, None
    game, player = row
    return game, player


@router.callback_query(F.data.startswith("buy:"))
async def buy_item(callback: CallbackQuery) -> None:
    code = callback.data.split(":", 1)[1]
    async with async_session() as session:
        ok = await shop_service.buy_item(session, callback.from_user.id, code)
        if ok:
            await callback.answer(visuals.PURCHASE_SUCCESS, show_alert=True)
        else:
            await callback.answer(visuals.NOT_ENOUGH_COINS, show_alert=True)
        text, markup = await shop_service.render_shop(session, callback.from_user.id, callback.from_user.full_name)
        await callback.message.edit_text(text, reply_markup=markup)
        await session.commit()


@router.callback_query(F.data == "shop_back")
async def shop_back(callback: CallbackQuery) -> None:
    async with async_session() as session:
        text, markup = await shop_service.render_shop(session, callback.from_user.id, callback.from_user.full_name)
        try:
            await callback.message.edit_text(text, reply_markup=markup)
        except Exception:
            from utils.logging import logger
            logger.exception("Shop back edit failed for user %s", callback.from_user.id)
            await callback.answer()


@router.callback_query(F.data == "shop_cosmetics")
async def shop_cosmetics(callback: CallbackQuery) -> None:
    async with async_session() as session:
        text, markup = await shop_service.render_items(session, "COSMETIC")
        try:
            await callback.message.edit_text(text, reply_markup=markup)
        except Exception:
            from utils.logging import logger
            logger.exception("Shop cosmetics edit failed for user %s", callback.from_user.id)


@router.callback_query(F.data == "shop_perks")
async def shop_perks(callback: CallbackQuery) -> None:
    async with async_session() as session:
        text, markup = await shop_service.render_items(session, "PERK")
        try:
            await callback.message.edit_text(text, reply_markup=markup)
        except Exception:
            from utils.logging import logger
            logger.exception("Shop perks edit failed for user %s", callback.from_user.id)


@router.callback_query(F.data == "shop_inventory")
async def shop_inventory(callback: CallbackQuery) -> None:
    async with async_session() as session:
        text, markup = await shop_service.render_inventory(session, callback.from_user.id, callback.from_user.full_name)
        try:
            await callback.message.edit_text(text, reply_markup=markup)
        except Exception:
            from utils.logging import logger
            logger.exception("Shop inventory edit failed for user %s", callback.from_user.id)


@router.callback_query(F.data.startswith("activate:"))
async def activate_item(callback: CallbackQuery) -> None:
    code = callback.data.split(":", 1)[1]
    async with async_session() as session:
        ok = await shop_service.activate_item(session, callback.from_user.id, code)
        await session.commit()
        if ok:
            await callback.answer("Активовано")
        else:
            await callback.answer("Немає предмета")


@router.callback_query(F.data.startswith("vote:"))
async def vote_choice(callback: CallbackQuery) -> None:
    target_part = callback.data.split(":", 1)[1]
    if target_part == "cancel":
        await callback.answer("Скасовано")
        return
    target_id = int(target_part)
    async with async_session() as session:
        game, player = await find_player_game(session, callback.from_user.id)
        if not game or not player or not player.is_alive:
            await callback.answer("Немає активної гри")
            return
        await voting.register_vote(session, callback.bot, game, player, target_id)
        if buffs.has_buff(player, "SILENCE_VOTE"):
            player.buffs_state = player.buffs_state or {}
            player.buffs_state["silenced_target"] = target_id
            player.buffs_state["silence_used"] = True
        await session.commit()
        await callback.answer("Голос прийнято")


@router.callback_query(F.data.startswith("night:"))
async def night_choice(callback: CallbackQuery) -> None:
    target_part = callback.data.split(":", 1)[1]
    if target_part == "cancel":
        await callback.answer("Скасовано")
        return
    target_id = int(target_part)
    async with async_session() as session:
        game, player = await find_player_game(session, callback.from_user.id)
        if not game or not player or game.state != GameState.NIGHT:
            await callback.answer("Не час для дії")
            return
        player.night_target_id = target_id
        if player.role == Role.SUICIDE:
            player.used_suicide = True
        if player.role == Role.DETECTIVE:
            player.buffs_state = player.buffs_state or {}
            kb = InlineKeyboardBuilder()
            kb.button(text="Перевірити", callback_data=f"nightmode_inspect:{target_id}")
            kb.button(text="Вистрілити", callback_data=f"nightmode_shoot:{target_id}")
            kb.adjust(2)
            await callback.message.edit_text("Обери режим: перевірити чи вистрілити?", reply_markup=kb.as_markup())
        player.night_action_done = True
        await session.commit()
        from services import game_logic
        await game_logic.try_end_night(session, callback.bot, game, config.DAY_DURATION)
        await callback.answer("Ціль встановлено")


@router.callback_query(F.data.startswith("nightmode_inspect:"))
async def night_mode_inspect(callback: CallbackQuery) -> None:
    target_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        game, player = await find_player_game(session, callback.from_user.id)
        if not player:
            await callback.answer("Немає гри")
            return
        player.night_target_id = target_id
        player.buffs_state = player.buffs_state or {}
        player.buffs_state["night_mode"] = "inspect"
        player.night_action_done = True
        await session.commit()
        from utils.logging import logger, game_prefix
        logger.info("%s choose inspect %s -> %s", game_prefix(game.id, game.chat_id, game.current_round), player.username, target_id if game else target_id)
        from services import game_logic
        await game_logic.try_end_night(session, callback.bot, game, config.DAY_DURATION)
        try:
            await callback.message.edit_text("Перевірка вибрана.")
        except Exception:
            pass
        await callback.answer("Перевірка запланована")


@router.callback_query(F.data.startswith("nightmode_shoot:"))
async def night_mode_shoot(callback: CallbackQuery) -> None:
    target_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        game, player = await find_player_game(session, callback.from_user.id)
        if not player:
            await callback.answer("Немає гри")
            return
        player.night_target_id = target_id
        player.buffs_state = player.buffs_state or {}
        player.buffs_state["night_mode"] = "shoot"
        player.night_action_done = True
        await session.commit()
        from utils.logging import logger, game_prefix
        logger.info("%s choose shoot %s -> %s", game_prefix(game.id, game.chat_id, game.current_round), player.username, target_id if game else target_id)
        from services import game_logic
        await game_logic.try_end_night(session, callback.bot, game, config.DAY_DURATION)
        try:
            await callback.message.edit_text("Постріл вибрано.")
        except Exception:
            pass
        await callback.answer("Постріл запланований")


@router.callback_query(F.data == "vote_open")
async def vote_open(callback: CallbackQuery) -> None:
    async with async_session() as session:
        game, player = await find_player_game(session, callback.from_user.id)
        if not game or not player or not player.is_alive:
            await callback.answer("Недоступно")
            return
        alive = [p for p in game.players if p.is_alive and p.id != player.id]
        kb = private_keyboards.voting_keyboard(alive)
        await callback.answer("Відкрито у приваті", show_alert=True)
        await callback.bot.send_message(callback.from_user.id, "Кого лінчувати?", reply_markup=kb)


@router.callback_query(F.data == "potato_throw")
async def potato_throw(callback: CallbackQuery) -> None:
    async with async_session() as session:
        game, player = await find_player_game(session, callback.from_user.id)
        if player:
            player.potato_decision = True
            await session.commit()
            await callback.answer("Кинути")


@router.callback_query(F.data == "potato_keep")
async def potato_keep(callback: CallbackQuery) -> None:
    async with async_session() as session:
        game, player = await find_player_game(session, callback.from_user.id)
        if player:
            player.potato_decision = False
            await session.commit()
            await callback.answer("Не кидаю")


@router.callback_query(F.data == "lynch_yes")
async def lynch_yes(callback: CallbackQuery) -> None:
    async with async_session() as session:
        game = await crud.get_active_game(session, callback.message.chat.id)
        if not game:
            return
        player = next((p for p in game.players if p.user_id == callback.from_user.id), None)
        if not player or not player.is_alive:
            await callback.answer("Недоступно")
            return
        await lynch_phase.cast_vote(game, player, True)
        await callback.answer("Так")
        if len(lynch_phase.LYNCH_VOTES.get(game.id, {})) >= len([p for p in game.players if p.is_alive]):
            await lynch_phase.finalize(session, callback.bot, game)
            await session.commit()


@router.callback_query(F.data == "lynch_no")
async def lynch_no(callback: CallbackQuery) -> None:
    async with async_session() as session:
        game = await crud.get_active_game(session, callback.message.chat.id)
        if not game:
            return
        player = next((p for p in game.players if p.user_id == callback.from_user.id), None)
        if not player or not player.is_alive:
            await callback.answer("Недоступно")
            return
        await lynch_phase.cast_vote(game, player, False)
        await callback.answer("Ні")
        if len(lynch_phase.LYNCH_VOTES.get(game.id, {})) >= len([p for p in game.players if p.is_alive]):
            await lynch_phase.finalize(session, callback.bot, game)
            await session.commit()
