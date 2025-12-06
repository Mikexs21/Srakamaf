import random

UK_NAMES = [
    "Олег",
    "Марина",
    "Іван",
    "Катя",
    "Сергій",
    "Аліна",
    "Юра",
    "Настя",
    "Артем",
    "Даша",
    "Леся",
    "Тарас",
    "Данило",
    "Мирослава",
    "Софія",
    "Влад",
    "Анна",
    "Роман",
    "Максим",
]


def pick_name(used: set) -> str:
    pool = list(UK_NAMES)
    random.shuffle(pool)
    for name in pool:
        if name not in used:
            return name
    return f"Player{random.randint(100,999)}"


