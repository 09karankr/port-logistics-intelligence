import redis.asyncio as aioredis
from api.core.config import get_settings

_client: aioredis.Redis | None = None


async def init_redis():
    global _client
    settings = get_settings()
    _client = aioredis.from_url(settings.redis_url, decode_responses=True)


async def close_redis():
    global _client
    if _client:
        await _client.aclose()


def get_redis() -> aioredis.Redis:
    if _client is None:
        raise RuntimeError("Redis client not initialised — call init_redis() at startup")
    return _client
