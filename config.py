import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing in environment. Create .env with BOT_TOKEN=<token>.")

NIGHT_DURATION = int(os.getenv("NIGHT_DURATION", 60))
DAY_DURATION = int(os.getenv("DAY_DURATION", 30))
VOTING_DURATION = int(os.getenv("VOTING_DURATION", 30))
LAST_WORDS_ENABLED = os.getenv("LAST_WORDS_ENABLED", "true").lower() == "true"
LAST_WORDS_TIMEOUT = int(os.getenv("LAST_WORDS_TIMEOUT", 20))
BUKOVEL_MODE_DEFAULT = os.getenv("BUKOVEL_MODE_DEFAULT", "false").lower() == "true"
SHOW_ROLE_ON_DEATH_DEFAULT = os.getenv("SHOW_ROLE_ON_DEATH", "true").lower() == "true"

DEFAULT_ACTIVE_ROLES = [
    "DON",
    "MAFIA",
    "DOCTOR",
    "DETECTIVE",
    "HOOKER",
    "DEPUTY",
    "JESTER",
]

SHOP_ITEMS = [
    {
        "code": "ACTIVE_ROLE",
        "name": "Активна роль",
        "description": "Гарантовано отримаєш активну роль у наступній грі.",
        "price": 150,
        "type": "PERK",
        "metadata": {"effect": "force_active_role"},
    },
    {
        "code": "ALIBI",
        "name": "Алібі",
        "description": "Детектив бачить тебе як мирного.",
        "price": 120,
        "type": "PERK",
        "metadata": {"effect": "alibi"},
    },
    {
        "code": "PROTECTION",
        "name": "Захист",
        "description": "Перший раз, коли тебе намагаються вбити вночі, ти виживаєш.",
        "price": 200,
        "type": "PERK",
        "metadata": {"effect": "night_protection"},
    },
    {
        "code": "EXTRA_LIFE_LYNCH",
        "name": "Міцна шия",
        "description": "Перше повішення тебе не вбиває.",
        "price": 200,
        "type": "PERK",
        "metadata": {"effect": "lynch_protection"},
    },
    {
        "code": "SILENCE_VOTE",
        "name": "Тиша",
        "description": "Раз за гру блокує голос іншого гравця.",
        "price": 140,
        "type": "PERK",
        "metadata": {"effect": "silence_vote"},
    },
    {
        "code": "BLIND_NIGHT",
        "name": "Темна ніч",
        "description": "Наступна ніч буде без подробиць смертей у групі.",
        "price": 100,
        "type": "PERK",
        "metadata": {"effect": "blind_night"},
    },
    {
        "code": "POTATO",
        "name": "Картопля",
        "description": "Косметичний жартівливий предмет.",
        "price": 25,
        "type": "COSMETIC",
        "metadata": {"effect": "potato"},
    },
]

AI_PROFILES = [
    {
        "name": "aggressive",
        "aggression": 0.8,
        "paranoia": 0.4,
        "loyalty_to_majority": 0.4,
        "randomness": 0.1,
    },
    {
        "name": "cautious",
        "aggression": 0.3,
        "paranoia": 0.7,
        "loyalty_to_majority": 0.8,
        "randomness": 0.05,
    },
    {
        "name": "semi_random",
        "aggression": 0.5,
        "paranoia": 0.5,
        "loyalty_to_majority": 0.5,
        "randomness": 0.2,
    },
]

# Roles appearance thresholds; can be adjusted to tweak balance
ROLE_RULES = [
    {"min_players": 4, "roles": ["DON", "DOCTOR"], "fill": "CIVILIAN"},  # стартовий набір
    {"min_players": 5, "add": ["DETECTIVE"]},  # додається детектив
    {"min_players": 6, "add": ["MAFIA"]},  # друга мафія
    {"min_players": 7, "add_one_of": ["SUICIDE", "HOOKER"]},  # або самогубець, або путана
    {"min_players": 8, "add_one_of": ["MAYOR", "EXECUTIONER"]},  # мер або палач
    {"min_players": 9, "add": ["DEPUTY"]},  # заступник
]

BUKOVEL_POTATO_CHANCE = 0.5

COIN_REWARDS = {
    "participation": 20,
    "win": 80,
    "loss": 20,
    "doctor_save": 15,
    "detective_find": 15,
}

# Comment: to add new role, register it in ROLE_RULES, extend visuals descriptions, update services/night_phase logic for actions.


