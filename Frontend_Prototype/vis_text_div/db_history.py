"""
Fetch revision history from the database.
"""
import pandas as pd
import sys
import os
from logger_utils import setup_logger

# Add parent directory to path to allow importing db_utils
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db_utils import create_db_connection, test_db_connection

def get_revisions_by_article_id(article_id: int, db_config: dict) -> pd.DataFrame:
    """
    Retrieve revision history for an article via SQLAlchemy or fallback.
    """
    import sqlalchemy

    logger = setup_logger("db_history")
    if not test_db_connection(db_config):
        logger.error("DB connection test failed.")
        return pd.DataFrame()

    try:
        # Build connection string
        fmt = "{type}://{user}:{password}@{host}:{port}/{database}"
        uri = fmt.format(**db_config)
        engine = sqlalchemy.create_engine(uri)
        query = (
            "SELECT h.revid, h.timestamp, h.user_name AS userid, "
            "h.comment, h.content AS text FROM history h "
            "WHERE h.article_id = %s ORDER BY h.timestamp"
        )
        df = pd.read_sql(query, engine, params=[article_id])
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
    df = get_revisions_by_article_id(article_id, db_config)
    if df.empty:
        return []
    vals = df['revid'].tolist()
    try:
        i1, i2 = vals.index(start_revid), vals.index(end_revid)
    except ValueError:
        return []
    if i1 > i2:
        i1, i2 = i2, i1
    return vals[i1:i2+1]
