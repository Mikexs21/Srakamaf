from __future__ import annotations
import random
import asyncio
from typing import Dict, List

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import config
import visuals
from db import crud
from db.models import Game, GameState, Player, Role
from services import night_phase, day_phase, voting, timers, buffs, ai_logic
from keyboards import group_keyboards, private_keyboards
from ai import names
from utils.logging import logger, game_prefix

# Cache of last message per user per screen to avoid spam
SCREEN_CACHE: Dict[int, Dict[str, int]] = {}


def reset_screens(user_id: int) -> None:
    SCREEN_CACHE.pop(user_id, None)


async def send_screen(bot: Bot, user_id: int, screen: str, text: str, reply_markup=None) -> None:
    """Send/edit a single screen message for a user; silently ignore unreachable chats."""
    cache = SCREEN_CACHE.setdefault(user_id, {})
    message_id = cache.get(screen)
    try:
        if message_id:
            await bot.edit_message_text(text, chat_id=user_id, message_id=message_id, reply_markup=reply_markup)
        else:
            sent = await bot.send_message(user_id, text, reply_markup=reply_markup)
            cache[screen] = sent.message_id
    except TelegramBadRequest:
        logger.warning("DM failed to reach user %s for screen %s", user_id, screen)
        return
    except Exception:
        logger.exception("Unexpected DM error for user %s screen %s", user_id, screen)
        return


async def render_lobby(session: AsyncSession, bot: Bot, game: Game) -> None:
    players = await crud.list_players(session, game.id)
    text = visuals.lobby_text(players, game.buckovel_mode_enabled)
    markup = group_keyboards.lobby_keyboard()
    if game.lobby_message_id:
        try:
            await bot.edit_message_text(
                text,
                chat_id=game.chat_id,
                message_id=game.lobby_message_id,
                reply_markup=markup,
            )
            return
        except TelegramBadRequest as e:
            logger.warning("%s lobby edit failed: %s", game_prefix(game.id, game.chat_id), e)
        except Exception as e:
            logger.exception("%s unexpected lobby edit error", game_prefix(game.id, game.chat_id))
    msg = await bot.send_message(game.chat_id, text, reply_markup=markup)
    game.lobby_message_id = msg.message_id
    await session.commit()
    logger.info("%s lobby message set to %s", game_prefix(game.id, game.chat_id), msg.message_id)


async def add_ai_player(session: AsyncSession, game: Game) -> Player:
    from db.models import AIProfile

    used = {p.username for p in game.players}
    base_name = names.pick_name({u.replace("🤖 ", "") for u in used})
    name = f"🤖 {base_name}"
    profiles = (await session.execute(select(AIProfile))).scalars().all()
    profile = random.choice(profiles) if profiles else None
    ai_player = await crud.add_player(
        session,
        game,
        user_id=random.randint(10_000_000, 99_999_999),
        username=name,
        is_bot=True,
        ai_profile_id=profile.id if profile else None,
    )
    logger.info("AI player %s added", name)
    return ai_player


async def ensure_active_game(session: AsyncSession, chat_id: int) -> Game:
    game = await crud.get_active_game(session, chat_id)
    if game:
        return game
    return await crud.create_game(session, chat_id)


async def assign_roles(session: AsyncSession, game: Game) -> None:
    players = game.players
    total = len(players)
    roles: List[Role] = [Role.DON, Role.DOCTOR]
    while len(roles) < total:
        roles.append(Role.CIVILIAN)
    for rule in sorted(config.ROLE_RULES, key=lambda r: r["min_players"]):
        if total < rule["min_players"]:
            continue
        if "roles" in rule:
            for r in rule["roles"]:
                if len(roles) < total:
                    roles.append(Role[r])
        if "add" in rule:
            for r in rule["add"]:
                if len(roles) < total:
                    roles.append(Role[r])
        if "add_one_of" in rule:
            choice = random.choice(rule["add_one_of"])
            if len(roles) < total:
                roles.append(Role[choice])
        if "fill" in rule:
            while len(roles) < total:
                roles.append(Role[rule["fill"]])
    roles = roles[:total]
    random.shuffle(roles)
    actives = buffs.active_role_candidates(players)
    active_roles = [Role(r) for r in config.DEFAULT_ACTIVE_ROLES]
    for player in actives:
        if player in players and active_roles:
            role = active_roles.pop(0)
            player.role = role
            if role in roles:
                roles.remove(role)
    remaining_players = [p for p in players if p not in actives]
    random.shuffle(roles)
    for p, r in zip(remaining_players, roles):
        p.role = r
    logger.info("Roles assigned: %s", {p.username: p.role for p in players})


async def start_game(session: AsyncSession, bot: Bot, game: Game) -> None:
    await crud.set_game_state(session, game, GameState.ROLE_DISTRIBUTION)
    game.current_round = 1
    await session.commit()
    logger.info("%s state=ROLE_DISTRIBUTION", game_prefix(game.id, game.chat_id, game.current_round))
    for player in game.players:
        if player.is_bot:
            continue
        inv = await crud.get_inventory(session, player.user_id)
        for item in inv:
            if item.is_active:
                buffs.attach_buff(player, item.item.code)
                await crud.remove_inventory(session, player.user_id, item.item.code)
                if item.item.code == "BLIND_NIGHT":
                    game.blind_next_night = True
    await assign_roles(session, game)
    logger.info("%s roles assigned: %s", game_prefix(game.id, game.chat_id, game.current_round), {p.username: p.role for p in game.players})
    for player in game.players:
        if player.is_bot:
            continue
        try:
            await bot.send_message(player.user_id, visuals.role_dm(player.role))
        except Exception:
            logger.warning("%s Failed to DM player %s", game_prefix(game.id, game.chat_id), player.username)
    await start_night(session, bot, game)


async def start_night(session: AsyncSession, bot: Bot, game: Game) -> None:
    await crud.set_game_state(session, game, GameState.NIGHT)
    await crud.reset_night_actions(session, game)
    await session.commit()
    logger.info("%s state=NIGHT start", game_prefix(game.id, game.chat_id, game.current_round))
    night_duration = game.settings.night_duration if game.settings else config.NIGHT_DURATION
    day_duration = game.settings.day_duration if game.settings else config.DAY_DURATION
    alive_roles = ", ".join([f"{p.username}" for p in game.players if p.is_alive])
    logger.info("%s alive at night start: %s", game_prefix(game.id, game.chat_id, game.current_round), alive_roles)
    role_names = []
    alive_set = {p.role for p in game.players if p.is_alive}
    hint_map = {
        Role.DON: "Дон",
        Role.MAFIA: "Мафія",
        Role.DOCTOR: "Лікар",
        Role.DETECTIVE: "Детектив",
        Role.HOOKER: "Путана",
        Role.SUICIDE: "Самогубець",
    }
    if Role.DON in alive_set:
        role_names.append("Дон")
    if any(r in alive_set for r in {Role.MAFIA}):
        role_names.append("Мафія")
    if Role.DOCTOR in alive_set:
        role_names.append("Лікар")
    if Role.DETECTIVE in alive_set:
        role_names.append("Детектив")
    civilians_count = len([p for p in game.players if p.is_alive and p.role == Role.CIVILIAN])
    if civilians_count:
        role_names.append("Мирні")
    roles_hint = ", ".join(role_names)
    try:
        await bot.send_message(game.chat_id, visuals.night_group_start([p.username for p in game.players if p.is_alive], roles_hint))
    except Exception:
        logger.warning("%s failed to send night start to group", game_prefix(game.id, game.chat_id, game.current_round))
    for player in game.players:
        if not player.is_alive:
            continue
        if player.is_bot:
            continue
        if player.role in {Role.CIVILIAN, Role.EXECUTIONER, Role.MAYOR}:
            continue
        targets = [p for p in game.players if p.is_alive and p.id != player.id]
        markup = private_keyboards.night_keyboard(targets) if targets else None
        text = visuals.night_prompt(player.role)
        await send_screen(bot, player.user_id, "night", text, reply_markup=markup)
        if game.buckovel_mode_enabled and game.current_round == 1 and player.role in {Role.CIVILIAN, Role.MAYOR, Role.DEPUTY, Role.EXECUTIONER, Role.JESTER, Role.SUICIDE}:
            await send_screen(bot, player.user_id, "potato", visuals.potato_prompt(), reply_markup=private_keyboards.potato_keyboard())
    await handle_ai_moves(session, bot, game)
    await try_end_night(session, bot, game, day_duration)
    timers.timers.set_timer(game.id, night_duration, lambda: resolve_night_phase_task(bot, game.id, day_duration))
    logger.info("%s night timer set %ss", game_prefix(game.id, game.chat_id, game.current_round), night_duration)


async def resolve_night_phase(session: AsyncSession, bot: Bot, game: Game, day_duration: int | None = None) -> None:
    await crud.set_game_state(session, game, GameState.NIGHT_RESOLUTION)
    await session.commit()
    outcome = await night_phase.resolve_night(session, bot, game)
    await day_phase.start_day(session, bot, game, outcome)
    await session.commit()
    logger.info("%s state=DAY_DISCUSSION start", game_prefix(game.id, game.chat_id, game.current_round))
    if await check_victory(session, bot, game):
        return
    duration = day_duration if day_duration is not None else (game.settings.day_duration if game.settings else config.DAY_DURATION)
    timers.timers.set_timer(game.id, duration, lambda: start_voting_task(bot, game.id))
    logger.info("%s day timer set %ss", game_prefix(game.id, game.chat_id, game.current_round), duration)


async def resolve_night_phase_task(bot: Bot, game_id: int, day_duration: int) -> None:
    from db.base import async_session
    async with async_session() as session:
        game = await crud.get_game_by_id(session, game_id)
        if not game or game.state != GameState.NIGHT:
            return
        await resolve_night_phase(session, bot, game, day_duration)


async def start_voting_task(bot: Bot, game_id: int) -> None:
    from db.base import async_session
    async with async_session() as session:
        game = await crud.get_game_by_id(session, game_id)
        if not game or game.state != GameState.DAY_DISCUSSION:
            return
        await voting.start_voting(session, bot, game)
        await session.commit()


async def start_night_task(bot: Bot, game_id: int) -> None:
    from db.base import async_session
    async with async_session() as session:
        game = await crud.get_game_by_id(session, game_id)
        if not game or game.state not in {GameState.DAY_DISCUSSION, GameState.LYNCH_CONFIRMATION, GameState.VOTING, GameState.END}:
            return
        await start_night(session, bot, game)
        await session.commit()


async def check_victory(session: AsyncSession, bot: Bot, game: Game) -> bool:
    alive = [p for p in game.players if p.is_alive]
    mafia_alive = [p for p in alive if p.role in {Role.MAFIA, Role.DON}]
    city_alive = [p for p in alive if p.role not in {Role.MAFIA, Role.DON}]
    if not mafia_alive:
        await end_game(session, bot, game, "Місто")
        return True
    if len(mafia_alive) >= len(city_alive):
        await end_game(session, bot, game, "Мафія")
        return True
    return False


async def end_game(session: AsyncSession, bot: Bot, game: Game, winners: str) -> None:
    game.state = GameState.END
    await bot.send_message(game.chat_id, visuals.end_game_text(winners, game.players))
    for player in game.players:
        reward = config.COIN_REWARDS["loss"]
        if ((player.role in {Role.MAFIA, Role.DON} and winners == "Мафія") or (player.role not in {Role.MAFIA, Role.DON} and winners == "Місто")):
            reward = config.COIN_REWARDS["win"]
        await crud.add_coins(session, player.user_id, reward)
    await session.commit()
    logger.info("%s state=END winners=%s", game_prefix(game.id, game.chat_id, game.current_round), winners)


async def handle_ai_moves(session: AsyncSession, bot: Bot, game: Game) -> None:
    for player in game.players:
        if not player.is_bot or not player.is_alive:
            continue
        # додаємо невеликий рандомний час, щоб не видавати бота миттєвими діями
        await asyncio.sleep(random.uniform(1, 5))
        action = await ai_logic.decide_night_action(session, game, player)
        if action and "target_id" in action:
            player.night_target_id = action["target_id"]
            if "mode" in action:
                player.buffs_state = player.buffs_state or {}
                player.buffs_state["night_mode"] = action["mode"]
            player.night_action_done = True
            logger.info("%s AI action: %s -> %s (%s)", game_prefix(game.id, game.chat_id, game.current_round), player.username, action.get("target_id"), action.get("mode"))
        vote_target = await ai_logic.decide_vote(session, game, player)
        if vote_target:
            player.last_vote_target_id = vote_target
            logger.info("%s AI vote: %s -> %s", game_prefix(game.id, game.chat_id, game.current_round), player.username, vote_target)


def night_actors(game: Game) -> List[Player]:
    active_roles = {Role.DON, Role.MAFIA, Role.DOCTOR, Role.DETECTIVE, Role.HOOKER, Role.SUICIDE, Role.JESTER}
    return [p for p in game.players if p.is_alive and p.role in active_roles]


async def try_end_night(session: AsyncSession, bot: Bot, game: Game, day_duration: int) -> None:
    actors = night_actors(game)
    if not actors:
        return
    if all(p.night_action_done for p in actors):
        timers.timers.cancel(game.id)
        await resolve_night_phase(session, bot, game, day_duration)
        await session.commit()
