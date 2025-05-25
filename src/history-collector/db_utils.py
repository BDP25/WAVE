import psycopg2
import os
import dotenv

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
    """Create and return a database connection.

    Args:
        dbname (str, optional): Database name. Defaults to None.
        user (str, optional): Database username. Defaults to None.
        password (str, optional): Database password. Defaults to None.
        host (str, optional): Database host address. Defaults to None.
        port (str, optional): Database port. Defaults to None.

    Returns:
        psycopg2.connection: Database connection object if successful, None otherwise.

    Raises:
        Exception: If connection to the database fails.
    """
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
