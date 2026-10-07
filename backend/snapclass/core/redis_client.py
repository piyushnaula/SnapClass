"""Shared Redis connection (job queue + rate limiting)."""

from functools import lru_cache

from redis import Redis

from snapclass.core.config import settings


@lru_cache
def get_redis() -> Redis:
    # Short timeouts so the API answers quickly (with 503) when Redis is down.
    return Redis.from_url(settings.redis_url, socket_timeout=2, socket_connect_timeout=2)
