"""Fixed-window rate limiting with a Redis counter."""

import logging

from redis.exceptions import RedisError

from snapclass.core.redis_client import get_redis

logger = logging.getLogger(__name__)


def is_rate_limited(key: str, limit: int, window_seconds: int) -> bool:
    """Count one hit for `key`. Return True when the limit for this window is exceeded.

    If Redis is down we allow the request (fail open) and log a warning: login
    must keep working during a Redis outage. The trade-off is that brute-force
    protection is off until Redis is back.
    """
    try:
        redis = get_redis()
        count = redis.incr(key)
        if count == 1:
            redis.expire(key, window_seconds)  # the window starts at the first hit
        return int(count) > limit
    except RedisError:
        logger.warning("Rate limiter unavailable, allowing request", extra={"fields": {"key": key}})
        return False
