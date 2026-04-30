import asyncio
from functools import wraps
from typing import Any, Callable


def run_async(func: Callable) -> Callable:
    """Wrapper to run async functions synchronously."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            # Try to get existing event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, create a new one
                import nest_asyncio
                nest_asyncio.apply()
                return loop.run_until_complete(func(*args, **kwargs))
        except RuntimeError:
            pass

        # Create new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(func(*args, **kwargs))
        finally:
            loop.close()

    return wrapper
