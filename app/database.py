import asyncio
import os

import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str | None = os.getenv("DATABASE_URL")
_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        last_error = None
        for attempt in range(1, 6):
            try:
                _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
                break
            except Exception as e:
                last_error = e
                if attempt < 5:
                    await asyncio.sleep(2)
        else:
            raise last_error
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def is_postgres_enabled() -> bool:
    return DATABASE_URL is not None and DATABASE_URL != ""
