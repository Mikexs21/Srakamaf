from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.models import ShopItem


def shop_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="🎭 Косметика", callback_data="shop_cosmetics")
    kb.button(text="🎯 Перки / бафи", callback_data="shop_perks")
    kb.button(text="📦 Мої предмети", callback_data="shop_inventory")
    kb.button(text="🔙 Назад", callback_data="shop_back")
    kb.adjust(2, 2)
    return kb.as_markup()


def shop_items(items: list[ShopItem]):
    kb = InlineKeyboardBuilder()
    for item in items:
        kb.button(text=f"{item.name} • {item.price}💰", callback_data=f"buy:{item.code}")
    kb.button(text="🔙 Назад", callback_data="shop_back")
    kb.adjust(1)
    return kb.as_markup()


def inventory_keyboard(inventory: list[str]):
    kb = InlineKeyboardBuilder()
    for code in inventory:
        kb.button(text=f"Активувати {code}", callback_data=f"activate:{code}")
    kb.button(text="🔙 Назад", callback_data="shop_back")
    kb.adjust(1)
    return kb.as_markup()
