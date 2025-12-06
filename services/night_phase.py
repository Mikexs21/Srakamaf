from __future__ import annotations
import random
from typing import List, Optional, Dict
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

import visuals
import config
from db import crud
from db.models import Game, Player, Role
from services import buffs
from utils.logging import logger, game_prefix


class NightOutcome:
    def __init__(self) -> None:
        self.killed: List[Player] = []
        self.saved: Optional[Player] = None
        self.messages: List[str] = []


async def resolve_night(session: AsyncSession, bot: Bot, game: Game) -> NightOutcome:
    outcome = NightOutcome()
    players = [p for p in game.players if p.is_alive]

    blocked: Dict[int, Player] = {}
    hookers = [p for p in players if p.role == Role.HOOKER]
    for hooker in hookers:
        target = next((t for t in players if t.id == hooker.night_target_id), None)
        if target and hooker.id not in blocked:
            blocked[target.id] = hooker
            logger.info("%s HOOKER %s blocked %s", game_prefix(game.id, game.chat_id, game.current_round), hooker.username, target.username)

    # Apply Jester swap
    for jester in [p for p in players if p.role == Role.JESTER]:
        if jester.night_target_id and jester.id not in blocked:
            target = next((t for t in players if t.id == jester.night_target_id), None)
            if target:
                await perform_role_swap(session, game, jester, target)
                outcome.messages.append(f"{jester.username} змінив роль {target.username}")
                logger.info("%s JESTER %s swapped %s", game_prefix(game.id, game.chat_id, game.current_round), jester.username, target.username)

    # Suicide
    suicide_targets: List[Player] = []
    for suicider in [p for p in players if p.role == Role.SUICIDE]:
        if suicider.used_suicide and suicider.night_target_id and suicider.id not in blocked:
            target = next((t for t in players if t.id == suicider.night_target_id), None)
            outcome.killed.append(suicider)
            if target:
                suicide_targets.append(target)
                logger.info("%s SUICIDE %s targets %s", game_prefix(game.id, game.chat_id, game.current_round), suicider.username, target.username)

    # Mafia decision
    mafia_targets: List[int] = []
    don = next((p for p in players if p.role == Role.DON), None)
    mafia_members = [p for p in players if p.role in {Role.MAFIA, Role.DON} and p.id not in blocked]
    for m in mafia_members:
        if m.night_target_id:
            mafia_targets.append(m.night_target_id)
    target_id = None
    if don and don.id not in blocked and don.night_target_id:
        target_id = don.night_target_id
    elif mafia_targets:
        target_id = max(set(mafia_targets), key=mafia_targets.count)
    mafia_target_player = next((p for p in players if p.id == target_id), None)
    if mafia_target_player:
        logger.info("%s MAFIA target %s", game_prefix(game.id, game.chat_id, game.current_round), mafia_target_player.username)

    # Doctor
    doctor = next((p for p in players if p.role == Role.DOCTOR), None)
    doctor_target = None
    if doctor and doctor.id not in blocked and doctor.night_target_id:
        doctor_target = next((p for p in players if p.id == doctor.night_target_id), None)
        if doctor_target:
            logger.info("%s DOCTOR heals %s", game_prefix(game.id, game.chat_id, game.current_round), doctor_target.username)

    # Detective / Deputy
    investigators = [p for p in players if p.role in {Role.DETECTIVE, Role.DEPUTY} and p.id not in blocked]
    for inv in investigators:
        target = next((t for t in players if t.id == inv.night_target_id), None)
        if not target:
            continue
        mode = inv.buffs_state.get("night_mode", "inspect") if inv.buffs_state else "inspect"
        if mode == "inspect":
            seen_role = target.role
            if buffs.has_buff(target, "ALIBI"):
                seen_role = Role.CIVILIAN
            await bot.send_message(inv.user_id, f"Результат перевірки: {visuals.ROLE_NAMES[seen_role]}")
            logger.info("%s %s inspects %s -> %s", game_prefix(game.id, game.chat_id, game.current_round), inv.username, target.username, seen_role.name)
        else:
            if doctor_target and doctor_target.id == target.id:
                outcome.saved = target
            else:
                outcome.killed.append(target)
            logger.info("%s %s shoots %s", game_prefix(game.id, game.chat_id, game.current_round), inv.username, target.username)

    # Mafia kill resolution
    if mafia_target_player:
        if doctor_target and doctor_target.id == mafia_target_player.id:
            outcome.saved = mafia_target_player
        else:
            if buffs.consume_buff(mafia_target_player, "PROTECTION"):
                logger.info("%s PROTECTION consumed for %s", game_prefix(game.id, game.chat_id, game.current_round), mafia_target_player.username)
                outcome.saved = mafia_target_player
            else:
                outcome.killed.append(mafia_target_player)

    # Suicide targets applied
    for target in suicide_targets:
        if doctor_target and doctor_target.id == target.id:
            outcome.saved = target
        else:
            if buffs.consume_buff(target, "PROTECTION"):
                outcome.saved = target
            else:
                outcome.killed.append(target)

    # Potato (Bucovel)
    if game.buckovel_mode_enabled and game.current_round == 1:
        civilians = [p for p in players if p.role in {Role.CIVILIAN, Role.MAYOR, Role.DEPUTY, Role.EXECUTIONER, Role.JESTER, Role.SUICIDE}]
        for civ in civilians:
            if civ.potato_decision:
                if random.random() < 0.5 and players:
                    target = random.choice(players)
                    if doctor_target and doctor_target.id == target.id:
                        outcome.saved = target
                    else:
                        outcome.killed.append(target)

    # Deduplicate killed and respect protection
    final_dead = []
    seen_ids = set()
    for p in outcome.killed:
        if p.id in seen_ids:
            continue
        seen_ids.add(p.id)
        final_dead.append(p)
    outcome.killed = final_dead

    for victim in outcome.killed:
        await crud.mark_dead(session, victim)
        victim.awaiting_last_words = True
        victim.last_words_round = game.current_round + 1  # show on next day
        if victim.is_bot:
            continue
        if config.LAST_WORDS_ENABLED:
            await bot.send_message(victim.user_id, visuals.last_words_request(config.LAST_WORDS_TIMEOUT))
            logger.info("%s last words requested from %s", game_prefix(game.id, game.chat_id, game.current_round), victim.username)
    return outcome


async def perform_role_swap(session: AsyncSession, game: Game, jester: Player, target: Player) -> None:
    civilians = [p for p in game.players if p.role == Role.CIVILIAN and p.id != target.id]
    if not civilians:
        return
    new_owner = random.choice(civilians)
    stolen_role = target.role
    target.role = Role.CIVILIAN
    new_owner.role = stolen_role
    logger.info("%s JESTER %s swapped role %s -> %s", game_prefix(game.id, game.chat_id, game.current_round), jester.username, target.username, new_owner.username)

