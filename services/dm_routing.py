from aiogram import Bot
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

import visuals
from db import crud
from utils.logging import logger


async def handle_private_start(session: AsyncSession, bot: Bot, message: Message) -> None:
    await crud.get_or_create_user(session, message.from_user.id, message.from_user.full_name)
    await message.answer(visuals.WELCOME_PRIVATE)
    logger.info("User %s started private chat", message.from_user.id)

