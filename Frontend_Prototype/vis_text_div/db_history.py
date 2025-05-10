"""
Fetch revision history from the database.
"""
import pandas as pd
import sys
import os
from .logger_utils import setup_logger

# Add parent directory to path to allow importing db_utils
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db_utils import create_db_connection, test_db_connection

logger = setup_logger("db_history")

def get_revisions_by_article_id(article_id: int, db_config: dict) -> pd.DataFrame:
    """
    Retrieve revision history for an article via SQLAlchemy or fallback.
    """
    import sqlalchemy

    if not test_db_connection(db_config):
        logger.error("DB connection test failed.")
        return pd.DataFrame()

    try:
        # Ensure db_config has required keys
        db_config.setdefault("dialect", "postgresql")
        # Build connection string using 'dbname' instead of 'database'
        uri = "{dialect}://{user}:{password}@{host}:{port}/{dbname}".format(**db_config)
        engine = sqlalchemy.create_engine(uri)
        query = (
            "SELECT h.revid, h.timestamp, h.user_name, h.comment, h.content AS text "
            "FROM history h WHERE h.article_id = %(article_id)s ORDER BY h.timestamp"
        )
        df = pd.read_sql(query, engine, params={"article_id": article_id})
        df['minor'] = False
        logger.info(f"Fetched {len(df)} revisions for article {article_id}")
        return df
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        return pd.DataFrame()


def get_revisions_between(article_id: int, start_revid: int, end_revid: int, db_config: dict) -> list:
    """
    Return list of revision IDs between two given revisions (inclusive).
    """
    # Swap revisions if in descending order
    if start_revid > end_revid:
        logger.info(f"Swapping start ({start_revid}) and end ({end_revid}) revision IDs to maintain chronological order")
        start_revid, end_revid = end_revid, start_revid

    df = get_revisions_by_article_id(article_id, db_config)
    if df.empty:
        logger.error(f"No revisions found for article {article_id}")
        return []
    
    vals = df['revid'].tolist()
    
    # Check if the revisions exist in our dataset
    if start_revid not in vals:
        logger.error(f"Start revision {start_revid} not found in article {article_id}")
        # Try to find the closest revision that exists
        if vals:
            closest_rev = min(vals, key=lambda x: abs(x - start_revid))
            logger.info(f"Closest available revision to {start_revid} is {closest_rev}")
            start_revid = closest_rev
        else:
            return []
            
    if end_revid not in vals:
        logger.error(f"End revision {end_revid} not found in article {article_id}")
        # Try to find the closest revision that exists
        if vals:
            closest_rev = min(vals, key=lambda x: abs(x - end_revid))
            logger.info(f"Closest available revision to {end_revid} is {closest_rev}")
            end_revid = closest_rev
        else:
            return []
    
    # Check again after potential adjustments
    if start_revid not in vals or end_revid not in vals:
        logger.error(f"Could not find suitable revisions for {start_revid} and {end_revid}")
        return []
    
    try:
        i1, i2 = vals.index(start_revid), vals.index(end_revid)
    except ValueError as e:
        logger.error(f"Error finding revision indices: {e}")
        return []
        
    if i1 > i2:
        i1, i2 = i2, i1
        logger.info(f"Swapped start and end revisions to maintain chronological order")
    
    result = vals[i1:i2+1]
    logger.info(f"Found {len(result)} revisions between {start_revid} and {end_revid}")
    return result

