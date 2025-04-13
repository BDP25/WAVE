import nest_asyncio
nest_asyncio.apply()

from datetime import datetime, timedelta
# Import from the new db_utils module
from db_utils import create_db_connection

from wikipedia_histories import get_history
from wikipedia_histories import to_df
import pandas as pd
import io
import csv
import re
import requests


def get_page_id(article_title, language_code):
    """Get Wikipedia page ID for an article."""
    try:
        url = f"https://{language_code}.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "titles": article_title,
            "prop": "info"
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        # Extract page ID from response
        if 'query' in data and 'pages' in data['query']:
            pages = data['query']['pages']
            # Get the first page ID (should only be one)
            for page_id in pages:
                # Convert string ID to int, skip -1 which means not found
                if int(page_id) > 0:
                    return int(page_id)
        
        print(f"Could not find page ID for {article_title} in {language_code} Wikipedia")
        return None
    except Exception as e:
        print(f"Error getting page ID: {e}")
        return None


def download_wiki_history(article_title, language_code):
    """Download Wikipedia history and return history dataframe and page ID."""
    # Get the Wikipedia page ID
    page_id = get_page_id(article_title, language_code)
    
    if page_id is None:
        print(f"Warning: Could not retrieve page ID for {article_title}")
    
    history = get_history(article_title, domain=f"{language_code}.wikipedia.org")

    def fix_unterminated_quotes(text):
        """Fix unterminated quotes in CSV data."""
        # Count quotes in each line
        lines = text.split('\n')
        fixed_lines = []

        for line in lines:
            # Count non-escaped quotes
            quote_count = line.count('"') - line.count('\\"')

            # If odd number of quotes, add a closing quote
            if quote_count % 2 != 0:
                line += '"'

            fixed_lines.append(line)

        return '\n'.join(fixed_lines)

    def preprocess_history_data(history_data):
        """Preprocess history data to fix common CSV parsing issues."""
        # Convert to string format if it's a list of objects
        if isinstance(history_data, list):
            # Join with newlines to create a CSV-like string
            history_str = "\n".join([str(entry) for entry in history_data])
        else:
            history_str = str(history_data)

        # Fix quote issues
        history_str = history_str.replace('""', '\\"')  # Handle escaped quotes
        history_str = re.sub(r'(?<!")("(?!")|(?<!\\)")', r'""', history_str)  # Properly escape quotes

        # Fix unterminated quotes
        history_str = fix_unterminated_quotes(history_str)

        return history_str

    try:
        # Try with default settings
        print("Attempting default parsing...")
        history_df = to_df(history)
        # Ensure column is named 'time' if it exists as 'timestamp'
        if 'timestamp' in history_df.columns and 'time' not in history_df.columns:
            history_df = history_df.rename(columns={'timestamp': 'time'})
        print("Default parsing succeeded")
    except Exception as e:
        print(f"Error with default parsing: {e}")

        try:
            # Try with custom parameters
            print("Attempting custom parsing...")
            history_df = to_df(history, quoting=csv.QUOTE_ALL, escapechar='\\', doublequote=True)
            # Ensure column is named 'time' if it exists as 'timestamp'
            if 'timestamp' in history_df.columns and 'time' not in history_df.columns:
                history_df = history_df.rename(columns={'timestamp': 'time'})
        except Exception as e:
            print(f"Error with custom parsing: {e}")

            try:
                # Preprocess the data to handle quote issues
                print("Preprocessing and parsing data...")
                history_str = preprocess_history_data(history)

                # Try parsing with more flexible options
                history_df = pd.read_csv(
                    io.StringIO(history_str),
                    quoting=csv.QUOTE_NONE,  # Try with no quoting
                    escapechar='\\',
                    doublequote=False,
                    on_bad_lines='warn'  # Warn but don't fail on bad lines
                )
            except Exception as e:
                print(f"Advanced parsing failed: {e}")

                # Try one more approach - directly extract the data
                try:
                    print("Attempting direct extraction...")
                    # Extract data directly from the history objects
                    data = []
                    for item in history:
                        try:
                            # Assuming each history item has these attributes
                            # Adjust these based on the actual structure
                            entry = {
                                'revid': getattr(item, 'revid', ''),
                                'time': getattr(item, 'time', ''),  # Use 'time' consistently
                                'user': getattr(item, 'user', ''),
                                'comment': getattr(item, 'comment', '')
                            }
                            data.append(entry)
                        except Exception as inner_e:
                            print(f"Error extracting item: {inner_e}")

                    history_df = pd.DataFrame(data)
                except Exception as e:
                    print(f"All parsing methods failed: {e}")
                    # Create empty DataFrame with expected columns as last resort
                    history_df = pd.DataFrame(columns=["revid", "time", "user", "comment"])

    # Return both the history dataframe and the page ID
    return history_df, page_id


def get_or_update_article(article_title, language_code, max_age_days=7, db_config=None):
    """
    Get article data from database if it exists and is recent, otherwise update it.

    Args:
        article_title: Title of the Wikipedia article
        language_code: Language code for Wikipedia domain (e.g., 'en', 'de')
        max_age_days: Maximum age in days before forcing an update
        db_config: Dictionary with database connection parameters

    Returns:
        tuple: (article_data, history_data) where:
            - article_data is a dict with article information
            - history_data is a pandas DataFrame with the article revision history
    """
    # Import at runtime to avoid circular dependency
    from safe_wiki_to_db import update_article_history
    
    # Set default db_config if not provided
    if db_config is None:
        db_config = {
            "host": "localhost",
            "database": "wikipedia_db",
            "user": "postgres",
            "password": "postgres",
            "port": 5432
        }

    # Connect to database
    conn = create_db_connection(**db_config)
    if not conn:
        print("Database connection failed, downloading data directly")
        # If we can't connect to DB, just download and return without saving
        history_df, page_id = download_wiki_history(article_title, language_code)
        return {"title": article_title, "language": language_code, "article_id": page_id}, history_df

    try:
        # Get the Wikipedia page ID (needed for checking if it exists in DB)
        page_id = get_page_id(article_title, language_code)
        
        cursor = conn.cursor()

        # Check if article exists and is recent - now using page_id for lookup
        cursor.execute("""
            SELECT article_id, article_title, language_code, last_updated 
            FROM WP_article 
            WHERE article_id = %s
        """, (page_id,))

        article_result = cursor.fetchone()
        needs_update = True

        if article_result:
            article_id, title, lang, last_updated = article_result
            # Check if update is needed based on age
            if last_updated and (datetime.now() - last_updated) < timedelta(days=max_age_days):
                needs_update = False
                print(f"Article '{title}' is up-to-date (last updated: {last_updated})")
            else:
                print(f"Article '{title}' needs update (last updated: {last_updated})")
        else:
            print(f"Article '{article_title}' not found in database")

        # If update needed, download and save new data
        if needs_update:
            success = update_article_history(article_title, language_code, db_config)
            if not success:
                print("Warning: Failed to update article history")

            # Get the article ID (it should be the Wikipedia page_id now)
            article_id = page_id
            
            # Verify it exists in our database
            cursor.execute("""
                SELECT article_id, article_title, language_code, last_updated 
                FROM WP_article 
                WHERE article_id = %s
            """, (article_id,))

            article_result = cursor.fetchone()
            if article_result:
                article_id, title, lang, last_updated = article_result
            else:
                print("Error: Article not found after update attempt")
                conn.close()
                return None, None

        # Retrieve article data
        article_data = {
            "article_id": article_id,
            "title": title,
            "language": lang,
            "last_updated": last_updated
        }

        # Retrieve history data
        cursor.execute("""
            SELECT revid, timestamp, user_name, comment
            FROM history
            WHERE article_id = %s
            ORDER BY timestamp DESC
        """, (article_id,))

        history_rows = cursor.fetchall()
        # Use 'time' for the column name instead of 'timestamp'
        history_data = pd.DataFrame(history_rows, columns=["revid", "time", "user", "comment"])

        cursor.close()
        conn.close()

        return article_data, history_data

    except Exception as e:
        print(f"Error in get_or_update_article: {e}")
        if conn:
            conn.close()

        # Fallback: Download data directly if DB operations fail
        print("Falling back to direct download")
        history_df, page_id = download_wiki_history(article_title, language_code)
        return {"title": article_title, "language": language_code, "article_id": page_id}, history_df

