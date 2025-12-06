import time
from typing import Dict, Tuple

class ButtonProtection:
    def __init__(self) -> None:
        self.cache: Dict[int, Tuple[str, float]] = {}

    def is_duplicate(self, user_id: int, data: str, cooldown: float = 0.5) -> bool:
        now = time.time()
        last = self.cache.get(user_id)
        if last and last[0] == data and now - last[1] < cooldown:
            return True
        self.cache[user_id] = (data, now)
        return False

button_protection = ButtonProtection()


