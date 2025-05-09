import nest_asyncio
nest_asyncio.apply()

import pandas as pd
from psycopg2.extras import execute_batch
from datetime import datetime


# Import from new db_utils module instead of defining locally
from db_utils import create_db_connection, db_params

def initialize_tables(conn):
    """Create tables if they don't exist."""
    try:
        cursor = conn.cursor()

        # Create WP_article table - using BIGINT for article_id instead of SERIAL
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS WP_article (
                article_id BIGINT PRIMARY KEY,
                article_title TEXT NOT NULL,
                language_code TEXT NOT NULL,
                last_updated TIMESTAMP,
                UNIQUE(article_title, language_code)
            )
        """)

        # Create history table with content column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS history (
                history_id SERIAL PRIMARY KEY,
                article_id BIGINT REFERENCES WP_article(article_id),
                revid BIGINT,
                timestamp TIMESTAMP,
                user_name TEXT,
                comment TEXT,
                content TEXT,
                UNIQUE(article_id, revid)
            )
        """)

        conn.commit()
        cursor.close()
        return True
    except Exception as e:
        print(f"Error initializing tables: {e}")
        conn.rollback()
        return False


def save_article_to_db(conn, article_title, language_code, page_id):
    """Save article to WP_article table and return the article_id."""
    try:
        cursor = conn.cursor()

        # Check if article exists
        cursor.execute(
            "SELECT article_id FROM WP_article WHERE article_id = %s",
            (page_id,)
        )
        result = cursor.fetchone()

        if result:
            # Article exists, update last_updated and ensure title/language match
            article_id = result[0]
            cursor.execute(
                "UPDATE WP_article SET last_updated = %s, article_title = %s, language_code = %s WHERE article_id = %s",
                (datetime.now(), article_title, language_code, article_id)
            )
        else:
            # Insert new article using Wikipedia's page ID
            cursor.execute(
                """INSERT INTO WP_article (article_id, article_title, language_code, last_updated) 
                   VALUES (%s, %s, %s, %s)""",
                (page_id, article_title, language_code, datetime.now())
            )
            article_id = page_id

        conn.commit()
        cursor.close()
        return article_id
    except Exception as e:
        print(f"Error saving article to database: {e}")
        conn.rollback()
        return None


def save_article_history_to_db(conn, article_id, history_df):
    """Save article history data to history table."""
    if history_df.empty:
        print("No history data to save")
        return False

    try:
        cursor = conn.cursor()

        # Prepare data for batch insert
        history_data = []
        for _, row in history_df.iterrows():
            # Convert timestamp string to datetime if needed
            timestamp = row.get('time')  # Look for 'time' instead of 'timestamp'
            if isinstance(timestamp, str):
                try:
                    # Attempt to parse timestamp (adjust format as needed)
                    timestamp = pd.to_datetime(timestamp)
                except:
                    timestamp = None

            history_data.append((
                article_id,
                row.get('revid'),
                timestamp,
                row.get('user'),
                row.get('comment'),
                row.get('text')  # Add content field
            ))

        # Batch insert using execute_batch with content field
        execute_batch(cursor, """
            INSERT INTO history (article_id, revid, timestamp, user_name, comment, content)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (article_id, revid) DO NOTHING
        """, history_data)

        conn.commit()
        cursor.close()
        return True
    except Exception as e:
        print(f"Error saving history to database: {e}")
        conn.rollback()
        return False


def update_article_history(article_title, language_code, db_config=None):
    """
    Main function to update article history in the database.

    Args:
        article_title: Title of the Wikipedia article
        language_code: Language code for Wikipedia domain
        db_config: Dictionary with database connection parameters

    Returns:
        Boolean indicating success or failure
    """
    # Set default db_config if not provided
    if db_config is None:
        db_config = db_params
        
    # Use runtime import to avoid circular dependency
    from get_or_update_articel import download_wiki_history
        
    # Download article history and get page_id
    history_df, page_id = download_wiki_history(article_title, language_code)

    if history_df.empty or page_id is None:
        print(f"Failed to retrieve history or page ID for {article_title}")
        return False

    # Connect to database
    conn = create_db_connection(**db_config)
    if not conn:
        return False

    try:
        # Initialize tables if needed
        initialize_tables(conn)

        # Save article and get article_id
        article_id = save_article_to_db(conn, article_title, language_code, page_id)
        if not article_id:
            conn.close()
            return False

        # Save history data
        success = save_article_history_to_db(conn, article_id, history_df)

        conn.close()
        return success
    except Exception as e:
        print(f"Error in update_article_history: {e}")
        if conn:
            conn.close()
        return False

