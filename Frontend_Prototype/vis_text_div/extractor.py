"""
Extract and cache revision texts from DataFrames.
"""
import pandas as pd
from .redis_utils import get_redis_connection, cache_get, cache_set
from .logger_utils import setup_logger

logger = setup_logger("extractor")

def extract_revision_texts(history_df: pd.DataFrame, redis_config: dict = None) -> dict:
    """
    Extract text content for each revision and cache in Redis if available.
    Returns a dict mapping rev_id to text.
    """
    revision_texts = {}
    if redis_config is None:
        redis_config = {'host': 'localhost', 'port': 6379, 'db': 0, 'password': None}

    conn = get_redis_connection(**redis_config)
    using_redis = conn is not None
    if not using_redis:
        logger.warning("Redis unavailable; using in-memory cache only.")

    for _, row in history_df.iterrows():
        rev_id = row['revid']
        cache_key = f"revision:{rev_id}:text"
        text = None

        if using_redis:
            text = cache_get(conn, cache_key)

        if text is None:
            text = row.get('text', '') or ''
            revision_texts[rev_id] = text
            if using_redis:
                cache_set(conn, cache_key, text, expire=86400)
        else:
            revision_texts[rev_id] = text

    logger.info(f"Extracted {len(revision_texts)} revision texts.")
    return revision_texts