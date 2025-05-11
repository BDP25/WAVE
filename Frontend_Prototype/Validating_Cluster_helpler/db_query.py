import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_get_cluster_articles_by_index(cluster_index, date):
    """
    For a given date and cluster index, return the cluster_id and all articles (article_id, article_title) in that cluster.

    Args:
        cluster_index (int): Index of the cluster (0 = first entry of the day, etc.)
        date (str): Date in 'YYYY-MM-DD' format

    Returns:
        dict: { 'cluster_id': ..., 'articles': [ { 'article_id': ..., 'article_title': ... }, ... ] }
    """
    db_params = {
        "dbname": os.getenv("DB_NAME", "your_database"),
        "user": os.getenv("DB_USER", "your_username"),
        "password": os.getenv("DB_PASSWORD", "your_password"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432")
    }

    try:
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Step 1: Get cluster_id for the given index and date
        cursor.execute(
            """
            SELECT cluster_id
            FROM cluster
            WHERE date = %s
            """,
            (date,)
        )
        clusters = cursor.fetchall()


        cluster_id = clusters[cluster_index]["cluster_id"]

        # Step 2: Get articles for this cluster_id
        cursor.execute(
            """
            SELECT article_id, head
            FROM artikel
            WHERE cluster_id = %s
            """,
            (cluster_id,)
        )
        articles = cursor.fetchall()

        cursor.close()
        conn.close()

        return {
            "cluster_id": cluster_id,
            "articles": articles
        }

    except Exception as e:
        logger.error(f"Database error in test_get_cluster_articles_by_index: {e}", exc_info=True)
        return {"error": f"Error retrieving articles: {str(e)}"}