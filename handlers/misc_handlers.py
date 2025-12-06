from aiogram import Router
from aiogram.types import Message, CallbackQuery

router = Router()

@router.message()
async def ignore_messages(message: Message) -> None:
    # Catch-all handler to mark unrelated messages as handled and reduce log noise
    return

@router.callback_query()
async def ignore_callbacks(callback: CallbackQuery) -> None:
    try:
        await callback.answer()
    except Exception:
        pass
