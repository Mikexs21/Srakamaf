from __future__ import annotations
from datetime import datetime
from typing import List, Optional, Iterable
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from .base import Base, engine
from .models import (
    Game,
    GameState,
    GameSettings,
    Player,
    Role,
    UserAccount,
    ShopItem,
    Inventory,
    AIProfile,
    Suspicion,
    BuffUsage,
)
import config


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_schema()
    async with AsyncSession(engine) as session:
        await seed_shop(session)
        await seed_ai_profiles(session)
        await session.commit()


async def ensure_schema() -> None:
    """Lightweight migration for new columns when existing sqlite DB is present."""
    async with engine.begin() as conn:
        table_info = await conn.exec_driver_sql("PRAGMA table_info(players)")
        cols = {row[1] for row in table_info.fetchall()}
        alter_stmts = []
        if "night_action_done" not in cols:
            alter_stmts.append("ALTER TABLE players ADD COLUMN night_action_done BOOLEAN DEFAULT 0")
        if "vote_ready" not in cols:
            alter_stmts.append("ALTER TABLE players ADD COLUMN vote_ready BOOLEAN DEFAULT 0")
        if "last_words_round" not in cols:
            alter_stmts.append("ALTER TABLE players ADD COLUMN last_words_round INTEGER")
        if "awaiting_last_words" not in cols:
            alter_stmts.append("ALTER TABLE players ADD COLUMN awaiting_last_words BOOLEAN DEFAULT 0")
        for stmt in alter_stmts:
            try:
                await conn.exec_driver_sql(stmt)
            except Exception:
                # if column exists due to race, ignore
                pass


async def seed_shop(session: AsyncSession) -> None:
    existing = {item.code for item in (await session.execute(select(ShopItem))).scalars().all()}
    for item in config.SHOP_ITEMS:
        if item["code"] in existing:
            continue
        session.add(
            ShopItem(
                code=item["code"],
                name=item["name"],
                description=item["description"],
                price=item["price"],
                type=item["type"],
                extra=item.get("metadata", {}),
            )
        )


async def seed_ai_profiles(session: AsyncSession) -> None:
    existing = {p.name for p in (await session.execute(select(AIProfile))).scalars().all()}
    for profile in config.AI_PROFILES:
        if profile["name"] in existing:
            continue
        session.add(
            AIProfile(
                name=profile["name"],
                aggression=profile["aggression"],
                paranoia=profile["paranoia"],
                loyalty_to_majority=profile["loyalty_to_majority"],
                randomness=profile["randomness"],
            )
        )


async def get_or_create_user(session: AsyncSession, user_id: int, username: str) -> UserAccount:
    result = await session.execute(select(UserAccount).where(UserAccount.user_id == user_id))
    account = result.scalar_one_or_none()
    if account:
        return account
    account = UserAccount(user_id=user_id, coins=100, display_cosmetics={}, created_at=datetime.utcnow())
    session.add(account)
    await session.flush()
    return account


async def add_coins(session: AsyncSession, user_id: int, amount: int) -> None:
    account = await get_or_create_user(session, user_id, username="user")
    account.coins += amount


async def get_or_create_settings(session: AsyncSession, chat_id: int) -> GameSettings:
    result = await session.execute(select(GameSettings).where(GameSettings.chat_id == chat_id))
    settings = result.scalar_one_or_none()
    if settings:
        return settings
    settings = GameSettings(
        chat_id=chat_id,
        night_duration=config.NIGHT_DURATION,
        day_duration=config.DAY_DURATION,
        voting_duration=config.VOTING_DURATION,
        show_role_on_death=config.SHOW_ROLE_ON_DEATH_DEFAULT,
        buckovel_mode_enabled=config.BUKOVEL_MODE_DEFAULT,
    )
    session.add(settings)
    await session.flush()
    return settings


async def create_game(session: AsyncSession, chat_id: int) -> Game:
    settings = await get_or_create_settings(session, chat_id)
    game = Game(chat_id=chat_id, state=GameState.LOBBY, settings=settings,
                buckovel_mode_enabled=settings.buckovel_mode_enabled, current_round=0)
    session.add(game)
    await session.flush()
    return game


async def get_active_game(session: AsyncSession, chat_id: int) -> Optional[Game]:
    result = await session.execute(
        select(Game)
        .where(Game.chat_id == chat_id)
        .where(Game.state != GameState.END)
        .options(joinedload(Game.players), joinedload(Game.settings))
    )
    return result.unique().scalar_one_or_none()


async def get_game_by_id(session: AsyncSession, game_id: int) -> Optional[Game]:
    result = await session.execute(
        select(Game).where(Game.id == game_id).options(joinedload(Game.players), joinedload(Game.settings))
    )
    return result.unique().scalar_one_or_none()


async def add_player(
    session: AsyncSession,
    game: Game,
    user_id: int,
    username: str,
    is_bot: bool = False,
    role: Role = Role.CIVILIAN,
    ai_profile_id: Optional[int] = None,
) -> Player:
    player = Player(
        game_id=game.id,
        user_id=user_id,
        username=username,
        is_bot=is_bot,
        role=role,
        ai_profile_id=ai_profile_id,
    )
    session.add(player)
    await session.flush()
    return player


async def remove_player(session: AsyncSession, player_id: int) -> None:
    await session.execute(delete(Player).where(Player.id == player_id))


async def set_game_state(session: AsyncSession, game: Game, state: GameState) -> None:
    game.state = state
    game.updated_at = datetime.utcnow()


async def list_players(session: AsyncSession, game_id: int) -> List[Player]:
    res = await session.execute(select(Player).where(Player.game_id == game_id))
    return list(res.scalars().all())


async def set_role(session: AsyncSession, player: Player, role: Role) -> None:
    player.role = role


async def mark_dead(session: AsyncSession, player: Player) -> None:
    player.is_alive = False
    player.night_action_done = True
    player.vote_ready = True


async def set_message_id(session: AsyncSession, game: Game, field: str, message_id: int) -> None:
    setattr(game, field, message_id)


async def set_player_target(session: AsyncSession, player: Player, target_id: Optional[int]) -> None:
    player.night_target_id = target_id
    player.night_action_done = True


async def set_vote(session: AsyncSession, player: Player, target_id: Optional[int]) -> None:
    player.last_vote_target_id = target_id
    player.vote_ready = True


async def get_inventory(session: AsyncSession, user_id: int) -> List[Inventory]:
    res = await session.execute(select(Inventory).options(joinedload(Inventory.item)).where(Inventory.user_id == user_id))
    return list(res.scalars().all())


async def add_inventory(session: AsyncSession, user_id: int, item_code: str) -> Inventory:
    item_res = await session.execute(select(ShopItem).where(ShopItem.code == item_code))
    shop_item = item_res.scalar_one()
    inv_res = await session.execute(select(Inventory).where(Inventory.user_id == user_id, Inventory.item_id == shop_item.id))
    inv = inv_res.scalar_one_or_none()
    if inv:
        inv.quantity += 1
        return inv
    inv = Inventory(user_id=user_id, item_id=shop_item.id, quantity=1)
    session.add(inv)
    await session.flush()
    return inv


async def purchase_item(session: AsyncSession, user_id: int, item_code: str) -> bool:
    item_res = await session.execute(select(ShopItem).where(ShopItem.code == item_code))
    item = item_res.scalar_one_or_none()
    if not item:
        return False
    account = await get_or_create_user(session, user_id, username="user")
    if account.coins < item.price:
        return False
    account.coins -= item.price
    await add_inventory(session, user_id, item_code)
    return True


async def get_shop(session: AsyncSession) -> List[ShopItem]:
    res = await session.execute(select(ShopItem))
    return list(res.scalars().all())


async def set_buff_used(session: AsyncSession, user_id: int, game_id: int, code: str, metadata: Optional[dict] = None) -> None:
    usage = BuffUsage(user_id=user_id, game_id=game_id, buff_code=code, extra=metadata or {})
    session.add(usage)


async def list_buff_usages(session: AsyncSession, game_id: int, user_id: Optional[int] = None) -> List[BuffUsage]:
    stmt = select(BuffUsage).where(BuffUsage.game_id == game_id)
    if user_id:
        stmt = stmt.where(BuffUsage.user_id == user_id)
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def ensure_suspicions(session: AsyncSession, game: Game) -> None:
    bots = [p for p in game.players if p.is_bot]
    for bot in bots:
        for target in game.players:
            if bot.id == target.id:
                continue
            exists = await session.execute(
                select(Suspicion).where(
                    Suspicion.game_id == game.id,
                    Suspicion.bot_player_id == bot.id,
                    Suspicion.target_player_id == target.id,
                )
            )
            if exists.scalar_one_or_none():
                continue
            session.add(Suspicion(game_id=game.id, bot_player_id=bot.id, target_player_id=target.id, suspicion_score=0))
    await session.flush()


async def update_suspicion(session: AsyncSession, game_id: int, bot_id: int, target_id: int, delta: float) -> None:
    res = await session.execute(
        select(Suspicion).where(
            Suspicion.game_id == game_id,
            Suspicion.bot_player_id == bot_id,
            Suspicion.target_player_id == target_id,
        )
    )
    susp = res.scalar_one_or_none()
    if not susp:
        susp = Suspicion(game_id=game_id, bot_player_id=bot_id, target_player_id=target_id, suspicion_score=delta)
        session.add(susp)
    else:
        susp.suspicion_score += delta


async def get_suspicions(session: AsyncSession, game_id: int, bot_id: int) -> List[Suspicion]:
    res = await session.execute(select(Suspicion).where(Suspicion.game_id == game_id, Suspicion.bot_player_id == bot_id))
    return list(res.scalars().all())


async def toggle_inventory_activation(session: AsyncSession, user_id: int, item_code: str, active: bool) -> bool:
    res = await session.execute(
        select(Inventory)
        .join(ShopItem, ShopItem.id == Inventory.item_id)
        .where(Inventory.user_id == user_id)
        .where(ShopItem.code == item_code)
    )
    inv = res.scalar_one_or_none()
    if not inv:
        return False
    inv.is_active = active
    return True


async def remove_inventory(session: AsyncSession, user_id: int, item_code: str) -> None:
    res = await session.execute(
        select(Inventory)
        .join(ShopItem)
        .where(Inventory.user_id == user_id)
        .where(ShopItem.code == item_code)
    )
    inv = res.scalar_one_or_none()
    if inv:
        if inv.quantity > 1:
            inv.quantity -= 1
        else:
            await session.delete(inv)


async def clear_game(session: AsyncSession, game: Game) -> None:
    await session.delete(game)


async def set_last_words(session: AsyncSession, player: Player, text: str) -> None:
    player.last_words = text
    player.awaiting_last_words = False


async def alive_players(session: AsyncSession, game_id: int) -> List[Player]:
    res = await session.execute(select(Player).where(Player.game_id == game_id, Player.is_alive.is_(True)))
    return list(res.scalars().all())


async def reset_night_actions(session: AsyncSession, game: Game) -> None:
    for p in game.players:
        p.night_action_done = False
        p.night_target_id = None
        p.awaiting_last_words = False


async def reset_votes(session: AsyncSession, game: Game) -> None:
    for p in game.players:
        p.vote_ready = False
        p.last_vote_target_id = None


