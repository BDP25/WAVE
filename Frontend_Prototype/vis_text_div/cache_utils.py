"""
Functions for retrieving and storing single revision text from cache or memory.
"""
from .extractor import extract_revision_texts
from .redis_utils import get_redis_connection, cache_get, cache_set
from .logger_utils import setup_logger

logger = setup_logger("cache_utils")
revision_texts = {}

def get_revision_text(rev_id: int, redis_config: dict = None) -> str:
    """
    Retrieve revision text from memory or Redis cache.
    """
    global revision_texts
    if rev_id in revision_texts:
        return revision_texts[rev_id]

    if redis_config is None:
        redis_config = {'host': 'localhost','port': 6379,'db': 0,'password': None}
    conn = get_redis_connection(**redis_config)
    cache_key = f"revision:{rev_id}:text"
    text = cache_get(conn, cache_key)
    if text:
        revision_texts[rev_id] = text
        return text

    logger.warning(f"Revision {rev_id} not cached; fetch via extractor.")
    return None