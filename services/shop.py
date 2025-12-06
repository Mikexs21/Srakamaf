from __future__ import annotations
from typing import Tuple
from aiogram.types import InlineKeyboardMarkup

import visuals
from db import crud
from db.models import ShopItem
from keyboards import shop_keyboards
from utils.logging import logger, game_prefix


async def render_shop(session, user_id: int, username: str) -> tuple[str, InlineKeyboardMarkup]:
    account = await crud.get_or_create_user(session, user_id, username)
    text = f"{visuals.SHOP_HEADER}\nБаланс: {account.coins} монет"
    logger.info("shop open user=%s balance=%s", user_id, account.coins)
    return text, shop_keyboards.shop_menu()


async def render_items(session, item_type: str):
    items = await crud.get_shop(session)
    filtered = [item for item in items if item.type == item_type]
    text = visuals.SHOP_HEADER + "\n" + "\n".join(
        [visuals.shop_item_line(i.name, i.price, i.description) for i in filtered]
    )
    logger.info("shop list type=%s count=%s", item_type, len(filtered))
    return text, shop_keyboards.shop_items(filtered)


async def render_inventory(session, user_id: int, username: str) -> tuple[str, InlineKeyboardMarkup]:
    inv = await crud.get_inventory(session, user_id)
    if not inv:
        text = "Інвентар порожній."
        return text, shop_keyboards.shop_menu()
    lines = [f"{item.item.name} x{item.quantity} ({item.item.code})" for item in inv]
    text = visuals.INVENTORY_HEADER + "\n" + "\n".join(lines)
    codes = [item.item.code for item in inv]
    logger.info("inventory user=%s items=%s", user_id, codes)
    return text, shop_keyboards.inventory_keyboard(codes)


async def buy_item(session, user_id: int, code: str) -> bool:
    ok = await crud.purchase_item(session, user_id, code)
    logger.info("shop purchase user=%s code=%s success=%s", user_id, code, ok)
    return ok


async def activate_item(session, user_id: int, code: str) -> bool:
    ok = await crud.toggle_inventory_activation(session, user_id, code, True)
    logger.info("inventory activate user=%s code=%s success=%s", user_id, code, ok)
    return ok


