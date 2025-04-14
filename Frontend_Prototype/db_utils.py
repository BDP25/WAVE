import psycopg2
import os
import dotenv
import json
from psycopg2.extras import RealDictCursor  # Import RealDictCursor


# Load environment variables from .env file
dotenv.load_dotenv()

db_params = {
        "dbname": os.getenv("DB_NAME", "your_database"),
        "user": os.getenv("DB_USER", "your_username"),
        "password": os.getenv("DB_PASSWORD", "your_password"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432")
    }

def create_db_connection(dbname=None, user=None, password=None, host=None, port=None):
    """Create and return a database connection."""
    try:
        conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        return conn
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        return None



def get_article_history_by_title(article_title: str):
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

        # Optimierte Abfrage mit JOIN
        cursor.execute(
            """
            SELECT h.timestamp
            FROM wp_article w
            JOIN history h ON w.article_id = h.article_id
            WHERE w.article_title = %s
            ORDER BY h.timestamp ASC
            """,
            (article_title,)
        )
        timestamps = cursor.fetchall()

        cursor.close()
        conn.close()

        if timestamps:
            # Extrahiere und gebe die Liste der Timestamps zurück
            return [ts['timestamp'].isoformat() for ts in timestamps]
        else:
            return {"error": "No history found for the given article_title"}

    except Exception as e:
        print(f"Database error: {e}")
        return {"error": str(e)}



if __name__ == "__main__":
    article_title = "Donald Trump"
    history = get_article_history_by_title(article_title)

    # Print the result
    print(json.dumps(history, indent=4, ensure_ascii=False))