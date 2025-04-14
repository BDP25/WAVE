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

if __name__ == "__main__":
    # Run this file directly to test database connection
    test_db_connection()
