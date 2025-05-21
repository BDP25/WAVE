"""
Redis-based caching utilities for BTTF whois data and visualization HTML.
"""
import os
import json
import hashlib
import logging
import time
from datetime import datetime, timedelta
import redis
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Fix Redis host value by removing any DB_HOST= prefix if present
redis_host = os.getenv("REDIS_HOST", "localhost")
if "=" in redis_host:
    # Extract the part after the equals sign
    redis_host = redis_host.split("=", 1)[1]
    logger.warning(f"Fixed REDIS_HOST value by removing prefix. Using: {redis_host}")

# Redis connection parameters
REDIS_CONFIG = {
    "host": redis_host,
    "port": int(os.getenv("REDIS_PORT", 6379)),
    "db": 0,
    "password": os.getenv("REDIS_PASSWORD", None),
    "decode_responses": False,  # Keep binary for HTML content
    "socket_timeout": 3,        # Reduce timeout to fail faster
    "socket_connect_timeout": 3  # Reduce connection timeout
}

# Cache TTL (Time-To-Live) settings in seconds
WHOIS_CACHE_TTL = 60 * 60 * 24 * 7  # 7 days for whois data
VISUALIZATION_CACHE_TTL = 60 * 60 * 24 * 30  # 30 days for visualization HTML

# Flag to disable Redis after multiple connection failures
_REDIS_ENABLED = True
_REDIS_FAILURE_COUNT = 0
_MAX_REDIS_FAILURES = 3

def get_redis_connection():
    """
    Create and return a Redis connection using environment variables.
    Returns None if connection fails.
    """
    global _REDIS_ENABLED, _REDIS_FAILURE_COUNT

    # Skip connection attempts if Redis has been disabled due to repeated failures
    if not _REDIS_ENABLED:
        return None

    try:
        logger.debug(f"Attempting to connect to Redis at {REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}")
        conn = redis.Redis(**REDIS_CONFIG)
        # Test connection with a short timeout
        conn.ping()
        # Reset failure count on success
        _REDIS_FAILURE_COUNT = 0
        return conn
    except redis.RedisError as e:
        _REDIS_FAILURE_COUNT += 1
        logger.warning(f"Failed to connect to Redis ({_REDIS_FAILURE_COUNT}/{_MAX_REDIS_FAILURES}): {e}")

        # Disable Redis after multiple failures to avoid slowing down the application
        if _REDIS_FAILURE_COUNT >= _MAX_REDIS_FAILURES:
            logger.error(f"Disabling Redis after {_REDIS_FAILURE_COUNT} consecutive failures")
            _REDIS_ENABLED = False

        return None
    except Exception as e:
        _REDIS_FAILURE_COUNT += 1
        logger.warning(f"Unexpected error connecting to Redis ({_REDIS_FAILURE_COUNT}/{_MAX_REDIS_FAILURES}): {e}")

        if _REDIS_FAILURE_COUNT >= _MAX_REDIS_FAILURES:
            logger.error(f"Disabling Redis after {_REDIS_FAILURE_COUNT} consecutive failures")
            _REDIS_ENABLED = False

        return None

def test_redis_connection():
    """
    Test Redis connectivity and print detailed information.
    
    Returns:
        bool: True if connection was successful, False otherwise
    """
    conn = get_redis_connection()
    if conn:
        try:
            # Test setting and getting a value
            conn.setex("test_key", 10, "test_value")
            value = conn.get("test_key")
            if value:
                logger.info("✅ Redis connection and operations successful!")
                conn.delete("test_key")  # Clean up
                return True
            else:
                logger.error("❌ Redis connection successful but failed to retrieve test value")
                return False
        except Exception as e:
            logger.error(f"❌ Redis operation failed with error: {e}")
            return False
        finally:
            conn.close()
    else:
        logger.error("❌ Redis connection failed")
        return False

# BTTF Whois caching functions

def get_whois_cache_key(ip_address, date):
    """Generate a Redis key for whois data."""
    return f"whois:{ip_address}:{date}"

def get_cached_whois_data(ip_address, date):
    """
    Retrieve cached whois data for the specified IP and date.
    
    Args:
        ip_address (str): The IP address to lookup
        date (str): Date in YYYYMMDD format
        
    Returns:
        dict or None: The cached whois data or None if not in cache
    """
    # Skip Redis operations if disabled
    global _REDIS_ENABLED
    if not _REDIS_ENABLED:
        logger.debug("Redis is disabled, skipping cache lookup")
        return None

    key = get_whois_cache_key(ip_address, date)
    
    try:
        conn = get_redis_connection()
        if not conn:
            return None
            
        cached_data = conn.get(key)
        conn.close()
        
        if cached_data:
            logger.info(f"Cache hit for whois data: {ip_address}")
            return json.loads(cached_data)
        else:
            logger.info(f"Cache miss for whois data: {ip_address}")
            return None
    except Exception as e:
        logger.warning(f"Error retrieving whois data from cache: {e}")
        return None

def cache_whois_data(ip_address, date, data):
    """
    Store whois data in Redis cache.
    
    Args:
        ip_address (str): The IP address
        date (str): Date in YYYYMMDD format
        data (dict): The whois data to cache
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Skip Redis operations if disabled
    global _REDIS_ENABLED
    if not _REDIS_ENABLED:
        logger.debug("Redis is disabled, skipping cache storage")
        return False

    key = get_whois_cache_key(ip_address, date)
    
    try:
        conn = get_redis_connection()
        if not conn:
            return False
            
        conn.setex(key, WHOIS_CACHE_TTL, json.dumps(data))
        conn.close()
        logger.info(f"Cached whois data for {ip_address} with TTL {WHOIS_CACHE_TTL}s")
        return True
    except Exception as e:
        logger.warning(f"Error caching whois data: {e}")
        return False

# Visualization HTML caching functions

def get_visualization_cache_key(article_id, start_revid, end_revid, word_level=True, show_revision_info=True):
    """
    Generate a unique cache key for visualization HTML.
    
    Args:
        article_id (str): Wikipedia article ID
        start_revid (int): Starting revision ID
        end_revid (int): Ending revision ID
        word_level (bool): Whether word-level diffs are used
        show_revision_info (bool): Whether revision info is shown
        
    Returns:
        str: A unique cache key
    """
    # Create a string with all parameters
    params = f"{article_id}:{start_revid}:{end_revid}:{word_level}:{show_revision_info}"
    # Hash it to create a shorter, consistent key
    hashed = hashlib.md5(params.encode()).hexdigest()
    return f"vis:{hashed}"

def get_cached_visualization(article_id, start_revid, end_revid, word_level=True, show_revision_info=True):
    """
    Retrieve cached visualization HTML.
    
    Args:
        article_id (str): Wikipedia article ID
        start_revid (int): Starting revision ID
        end_revid (int): Ending revision ID
        word_level (bool): Whether word-level diffs are used
        show_revision_info (bool): Whether revision info is shown
        
    Returns:
        str or None: The cached HTML or None if not in cache
    """
    # Skip Redis operations if disabled
    global _REDIS_ENABLED
    if not _REDIS_ENABLED:
        logger.debug("Redis is disabled, skipping cache lookup")
        return None

    key = get_visualization_cache_key(article_id, start_revid, end_revid, word_level, show_revision_info)
    
    try:
        conn = get_redis_connection()
        if not conn:
            return None
            
        start_time = time.time()
        cached_html = conn.get(key)
        fetch_time = time.time() - start_time
        conn.close()
        
        if cached_html:
            logger.info(f"Cache hit for visualization (fetched in {fetch_time:.3f}s): {key}")
            return cached_html.decode('utf-8')
        else:
            logger.info(f"Cache miss for visualization: {key}")
            return None
    except Exception as e:
        logger.warning(f"Error retrieving visualization from cache: {e}")
        return None

def cache_visualization(article_id, start_revid, end_revid, html, word_level=True, show_revision_info=True):
    """
    Store visualization HTML in Redis cache.
    
    Args:
        article_id (str): Wikipedia article ID
        start_revid (int): Starting revision ID
        end_revid (int): Ending revision ID
        html (str): The HTML content to cache
        word_level (bool): Whether word-level diffs are used
        show_revision_info (bool): Whether revision info is shown
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Skip Redis operations if disabled
    global _REDIS_ENABLED
    if not _REDIS_ENABLED:
        logger.debug("Redis is disabled, skipping cache storage")
        return False

    key = get_visualization_cache_key(article_id, start_revid, end_revid, word_level, show_revision_info)
    
    try:
        conn = get_redis_connection()
        if not conn:
            return False
        
        start_time = time.time()
        conn.setex(key, VISUALIZATION_CACHE_TTL, html)
        cache_time = time.time() - start_time
        conn.close()
        
        logger.info(f"Cached visualization (in {cache_time:.3f}s) with TTL {VISUALIZATION_CACHE_TTL}s: {key}")
        return True
    except Exception as e:
        logger.warning(f"Error caching visualization: {e}")
        return False

# Utility function to clear all visualization cache
def clear_visualization_cache():
    """Clear all visualization cache entries."""
    try:
        conn = get_redis_connection()
        if not conn:
            return False
            
        # Find all keys with vis: prefix
        keys = conn.keys("vis:*")
        if keys:
            conn.delete(*keys)
            logger.info(f"Cleared {len(keys)} visualization cache entries")
        else:
            logger.info("No visualization cache entries to clear")
            
        conn.close()
        return True
    except Exception as e:
        logger.warning(f"Error clearing visualization cache: {e}")
        return False

# Examples of how to use these functions in the main app

def cached_query_bttf_whois(ip_address, date_str):
    """
    Cached version of query_bttf_whois that first checks Redis.
    Usage example for app.py.
    """
    # First check cache
    cached_data = get_cached_whois_data(ip_address, date_str)
    if cached_data is not None:
        return cached_data
        
    # Cache miss, query the API directly
    from app import query_bttf_whois
    whois_data = query_bttf_whois(ip_address, date_str)
    
    # Cache the result if successful
    if whois_data:
        cache_whois_data(ip_address, date_str, whois_data)
        
    return whois_data

def cached_visualize_wiki_versions(article_id, start_revid, end_revid, word_level=True, 
                                  verbose=True, db_config=None, show_revision_info=True):
    """
    Cached version of visualize_wiki_versions_with_deletions that first checks Redis.
    Usage example for app.py.
    """
    # First check cache
    cached_html = get_cached_visualization(article_id, start_revid, end_revid, 
                                          word_level, show_revision_info)
    if cached_html is not None:
        return cached_html
        
    # Cache miss, generate the visualization
    from visualisation import visualize_wiki_versions_with_deletions
    html = visualize_wiki_versions_with_deletions(
        article_id=article_id,
        start_revid=start_revid,
        end_revid=end_revid,
        word_level=word_level,
        verbose=verbose,
        db_config=db_config,
        redis_config=None,  # No need to pass redis config
        show_revision_info=show_revision_info
    )
    
    # Cache the result if successful
    if html:
        cache_visualization(article_id, start_revid, end_revid, html, 
                           word_level, show_revision_info)
        
    return html

# Add function to reset Redis connection state (for testing)
def reset_redis_state():
    """Reset the Redis connection state after failures."""
    global _REDIS_ENABLED, _REDIS_FAILURE_COUNT
    _REDIS_ENABLED = True
    _REDIS_FAILURE_COUNT = 0
    logger.info("Redis connection state has been reset")
    return test_redis_connection()

if __name__ == "__main__":
    # Set up console logging when run directly
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test Redis connection
    test_redis_connection()
