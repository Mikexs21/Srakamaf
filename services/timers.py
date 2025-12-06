import asyncio
from typing import Callable, Awaitable, Dict
from utils.logging import logger


class TimerManager:
    def __init__(self) -> None:
        self.tasks: Dict[int, asyncio.Task] = {}

    def set_timer(self, game_id: int, delay: int, callback: Callable[[], Awaitable[None]]):
        if game_id in self.tasks:
            self.tasks[game_id].cancel()
        self.tasks[game_id] = asyncio.create_task(self._run(game_id, delay, callback))

    async def _run(self, game_id: int, delay: int, callback: Callable[[], Awaitable[None]]):
        try:
            await asyncio.sleep(delay)
            await callback()
        except asyncio.CancelledError:
            logger.debug("Timer for game %s cancelled", game_id)
        except Exception as exc:
            logger.exception("Timer for game %s failed: %s", game_id, exc)
        finally:
            self.tasks.pop(game_id, None)

    def cancel(self, game_id: int):
        task = self.tasks.pop(game_id, None)
        if task:
            task.cancel()


timers = TimerManager()


