import asyncpg
from api.core.config import get_settings

_pool: asyncpg.Pool | None = None


async def init_pool():
    global _pool
    settings = get_settings()
    _pool = await asyncpg.create_pool(
        settings.database_url,
        min_size=3,
        max_size=20,
        command_timeout=60,
    )


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialised — call init_pool() at startup")
    return _pool
