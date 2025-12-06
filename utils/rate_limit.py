import asyncio
from functools import wraps
from typing import Callable


def rate_limited(delay: float):
    def decorator(func: Callable):
        last_called = 0.0

        @wraps(func)
        async def wrapper(*args, **kwargs):
            nonlocal last_called
            now = asyncio.get_event_loop().time()
            if now - last_called < delay:
                await asyncio.sleep(delay - (now - last_called))
            last_called = asyncio.get_event_loop().time()
            return await func(*args, **kwargs)

        return wrapper

    return decorator


