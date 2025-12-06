import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

import config
from db import crud
from handlers import group_handlers, private_handlers, callback_handlers, misc_handlers
from utils.logging import logger


async def main() -> None:
    bot = Bot(token=config.BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    dp.include_router(group_handlers.router)
    dp.include_router(private_handlers.router)
    dp.include_router(callback_handlers.router)
    dp.include_router(misc_handlers.router)
    await crud.init_db()
    logger.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

