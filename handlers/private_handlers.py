from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from sqlalchemy.ext.asyncio import AsyncSession

from db.base import async_session
from services import dm_routing, shop as shop_service, game_logic
import visuals

router = Router()


@router.message(Command("start"), F.chat.type == "private")
async def private_start(message: Message) -> None:
    async with async_session() as session:
        await dm_routing.handle_private_start(session, message.bot, message)
        await session.commit()


@router.message(Command("shop"), F.chat.type == "private")
async def open_shop(message: Message) -> None:
    async with async_session() as session:
        text, markup = await shop_service.render_shop(session, message.from_user.id, message.from_user.full_name)
        await shop_service_message(message, text, markup)
        await session.commit()


async def shop_service_message(message: Message, text: str, markup) -> None:
    await game_logic.send_screen(message.bot, message.from_user.id, "shop", text, reply_markup=markup)


@router.message(F.chat.type == "private", F.text)
async def catch_last_words(message: Message) -> None:
    async with async_session() as session:
        from sqlalchemy import select
        from db.models import Game, Player, GameState

        res = await session.execute(
            select(Game, Player)
            .join(Player, Player.game_id == Game.id)
            .where(Player.user_id == message.from_user.id)
            .where(Game.state != GameState.END)
        )
        row = res.first()
        if not row:
            return
        game, player = row
        if not player.is_alive and player.awaiting_last_words:
            player.last_words = message.text
            player.awaiting_last_words = False
            player.last_words_round = game.current_round + 1
            await session.commit()
            await message.answer("Твої останні слова збережено.")

