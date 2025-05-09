"""
Utilities for connecting to and interacting with Redis.
"""
import redis
from logger_utils import setup_logger

logger = setup_logger("redis_utils")

def get_redis_connection(host: str = 'localhost', port: int = 6379, db: int = 0, password: str = None) -> redis.Redis:
    """
    Establish and return a Redis connection, or None on failure.
    """
    try:
        conn = redis.Redis(
            host=host, port=port, db=db, password=password, decode_responses=True
        )
        conn.ping()
        return conn
    except redis.ConnectionError as e:
        logger.error(f"Redis connection error: {e}")
        return None


def cache_set(conn: redis.Redis, key: str, value: str, expire: int = None) -> None:
    """Set a value in Redis with optional TTL."""
    if not conn:
        return
    if expire:
        conn.setex(key, expire, value)
    else:
        conn.set(key, value)


def cache_get(conn: redis.Redis, key: str) -> str:
    """Get a value from Redis, return None if not found."""
    if not conn:
        return None
    return conn.get(key)


def sadd(conn: redis.Redis, key: str, value: str) -> None:
    """Add a value to a Redis set."""
    if not conn:
        return
    conn.sadd(key, value)


def expire(conn: redis.Redis, key: str, seconds: int) -> None:
    """Set expiration on a Redis key."""
    if not conn:
        return
    conn.expire(key, seconds)
