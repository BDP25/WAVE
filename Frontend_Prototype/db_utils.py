import psycopg2
import os
import dotenv
import json
from psycopg2.extras import RealDictCursor

# Load environment variables from .env file
dotenv.load_dotenv()

db_params = {
        "dbname": os.getenv("DB_NAME", "your_database"),
        "user": os.getenv("DB_USER", "your_username"),
        "password": os.getenv("DB_PASSWORD", "your_password"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432")
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
        print(f"Error connecting to the database: {e}")
        return None

def test_db_connection(db_config=None):
    """Test database connectivity and print detailed information.
    
    Args:
        db_config (dict, optional): Dictionary containing connection parameters
        
    Returns:
        bool: True if connection was successful, False otherwise
    """
    config = db_config or db_params
    
    print("Testing database connection with the following parameters:")
    # Print connection details (hiding password)
    safe_config = config.copy()
    if 'password' in safe_config:
        safe_config['password'] = '********' 
    print(safe_config)
    
    try:
        conn = create_db_connection(db_config=config)
        if conn:
            print("✅ Database connection successful!")
            conn.close()
            return True
        else:
            print("❌ Database connection failed!")
            return False
    except Exception as e:
        print(f"❌ Database connection failed with error: {e}")
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
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

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
            return [ts['timestamp'].isoformat() for ts in timestamps]
        else:
            return {"error": "No history found for the given article_title"}

    except Exception as e:
        print(f"Database error: {e}")
        return {"error": str(e)}




if __name__ == "__main__":
    # Run this file directly to test database connection
    test_db_connection()

    article_title = "Refugiados"
    history = get_article_history_by_title(article_title)

    # Print the result
    print(json.dumps(history, indent=4, ensure_ascii=False))
