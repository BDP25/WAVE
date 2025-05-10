import psycopg2
import os
import dotenv
import json
from psycopg2.extras import RealDictCursor
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
dotenv.load_dotenv()

db_params = {
        "dbname": os.getenv("DB_NAME", "your_database"),
        "user": os.getenv("DB_USER", "your_username"),
        "password": os.getenv("DB_PASSWORD", "your_password"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432")
    }

# Redis connection parameters
redis_params = {
    "host": os.getenv("REDIS_HOST", "localhost"),
    "port": int(os.getenv("REDIS_PORT", "6379")),
    "db": 0,
    "password": os.getenv("REDIS_PASSWORD", None)
}

def create_db_connection(db_config=None, dbname=None, user=None, password=None, host=None, port=None):
    """Create and return a database connection.
    
    Args:
        db_config (dict, optional): Dictionary containing connection parameters
        dbname, user, password, host, port: Individual connection parameters
        
    Returns:
        connection object or None if connection fails
    """
    try:
        # If db_config is provided as a dictionary, use it
        if isinstance(db_config, dict):
            conn = psycopg2.connect(
                dbname=db_config.get("dbname"),
                user=db_config.get("user"),
                password=db_config.get("password"),
                host=db_config.get("host"),
                port=db_config.get("port")
            )
        # Otherwise use individual parameters
        else:
            conn = psycopg2.connect(
                dbname=dbname,
                user=user,
                password=password,
                host=host,
                port=port
            )
        return conn
    except Exception as e:
        logger.error(f"Error connecting to the database: {e}")
        return None

def test_db_connection(db_config=None):
    """Test database connectivity and print detailed information.
    
    Args:
        db_config (dict, optional): Dictionary containing connection parameters
        
    Returns:
        bool: True if connection was successful, False otherwise
    """
    config = db_config or db_params
    
    logger.info("Testing database connection with the following parameters:")
    # Print connection details (hiding password)
    safe_config = config.copy()
    if 'password' in safe_config:
        safe_config['password'] = '********' 
    logger.info(safe_config)
    
    try:
        conn = create_db_connection(db_config=config)
        if conn:
            logger.info("✅ Database connection successful!")
            conn.close()
            return True
        else:
            logger.error("❌ Database connection failed!")
            return False
    except Exception as e:
        logger.error(f"❌ Database connection failed with error: {e}")
        return False


def get_article_history_by_title(article_title: str):
    db_params = {
        "dbname": os.getenv("DB_NAME", "your_database"),
        "user": os.getenv("DB_USER", "your_username"),
        "password": os.getenv("DB_PASSWORD", "your_password"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432")
    }

    try:
        logger.info(f"Fetching article history for title: {article_title}")
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # First verify if the article exists
        cursor.execute(
            "SELECT article_id FROM wp_article WHERE article_title = %s",
            (article_title,)
        )
        article_row = cursor.fetchone()

        if not article_row:
            logger.warning(f"No article found with title: {article_title}")
            return {"error": "Article not found in database", "article_title": article_title}

        article_id = article_row["article_id"]
        logger.info(f"Found article with ID: {article_id}")

        # Now get the history for this article
        cursor.execute(
            """
            SELECT h.revid, h.timestamp
            FROM history h 
            WHERE h.article_id = %s
            ORDER BY h.timestamp ASC
            """,
            (article_id,)
        )
        history = cursor.fetchall()

        cursor.close()
        conn.close()

        if history:
            logger.info(f"Found {len(history)} history entries for article ID {article_id}")
            # Format the result to include revid and timestamp
            return {
                "article_id": article_id,
                "history": [
                    {
                        "revid": record["revid"],
                        "timestamp": record["timestamp"].isoformat() if hasattr(record["timestamp"], "isoformat") else record["timestamp"]
                    }
                    for record in history
                ]
            }
        else:
            logger.warning(f"No history found for article ID: {article_id}")
            return {"error": "No history found for the given article", "article_id": article_id}

    except Exception as e:
        logger.error(f"Database error in get_article_history_by_title: {e}", exc_info=True)
        return {"error": str(e), "details": "Database error occurred while fetching article history"}

def get_min_max_date():
    try:
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get the oldest and newest date from the cluster table
        cursor.execute(
            "SELECT MIN(date) AS oldest_date, MAX(date) AS newest_date FROM cluster"
        )
        result = cursor.fetchone()

        cursor.close()
        conn.close()

        if result and result['oldest_date'] and result['newest_date']:
            return result['oldest_date'].isoformat(), result['newest_date'].isoformat()
        else:
            # Return default tuple to avoid unpacking error
            return "", ""
    except Exception as e:
        print(f"Database error: {e}")
        return "", ""

# TODO
def get_cluster_summary(cluster_index, date):
    """
    Retrieve the summary_text for the given cluster index on a specific date.

    Args:
        cluster_index (int): Index of the cluster (0 = first entry of the day, etc.)
        date (str): Date in 'YYYY-MM-DD' format

    Returns:
        str: Summary text or an error message
    """

    db_params = {
        "dbname": os.getenv("DB_NAME", "your_database"),
        "user": os.getenv("DB_USER", "your_username"),
        "password": os.getenv("DB_PASSWORD", "your_password"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432")
    }

    try:
        logger.info(f"Fetching summary for cluster index {cluster_index} on date {date}")
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Query all entries with that date
        cursor.execute(
            """
            SELECT summary_text
            FROM cluster
            WHERE date = %s
            """,
            (date,)
        )
        results = cursor.fetchall()

        cursor.close()
        conn.close()




        return results[cluster_index]["summary_text"]

    except Exception as e:
        logger.error(f"Database error in get_cluster_summary: {e}", exc_info=True)
        return f"Error retrieving summary: {str(e)}"


if __name__ == "__main__":
    # Run this file directly to test database connection
    test_db_connection()

    article_title = "Nintendo"
    history = get_article_history_by_title(article_title)

    print(json.dumps(history, indent=4, ensure_ascii=False))

