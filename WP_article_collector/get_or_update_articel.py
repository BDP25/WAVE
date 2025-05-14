import nest_asyncio
nest_asyncio.apply()

from datetime import datetime, timedelta
# Import from the new db_utils module
from db_utils import create_db_connection

from wikipedia_histories import get_history, to_df
import pandas as pd
import io
import csv
import re
import requests
from bs4 import BeautifulSoup  # Add this import for HTML parsing


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


def remove_edit_sections(raw_html):
    """Remove elements with specific classes, IDs, or tags from raw HTML."""
    try:
        soup = BeautifulSoup(raw_html, 'html.parser')

        # Classes to remove
        classes_to_remove = ['mw-editsection', 'sisterproject', 'coordinates plainlinks-print', 'references', "NavFrame erweiterte-navigationsleiste navigation-not-searchable erw-nav-farbschema-blau"]
        for class_name in classes_to_remove:
            for element in soup.find_all(class_=class_name):
                element.decompose()  # Remove the element

        # IDs to remove
        ids_to_remove = ['Weblinks', 'Einzelnachweise', 'Vorlage_Begriffsklärungshinweis', "Literatur", "normdaten"]
        for id_name in ids_to_remove:
            element = soup.find(id=id_name)
            if element:
                element.decompose()  # Remove the element

        # Tags to remove
        tags_to_remove = ['li']
        for tag_name in tags_to_remove:
            for element in soup.find_all(tag_name):
                element.decompose()  # Remove the element

        return str(soup)
    except Exception as e:
        print(f"Error removing sections: {e}")
        return raw_html

def remove_source_notes(raw_html):
    """Remove source notes from raw HTML."""
    try:
        soup = BeautifulSoup(raw_html, 'html.parser')
        # Find and remove all <sup> tags
        for sup in soup.find_all('sup'):
            sup.decompose()  # Remove the <sup> tag

        return str(soup)
    except Exception as e:
        print(f"Error removing source notes: {e}")
        return raw_html

# New function to compute diffs wrapping inserted text with a custom tag using the revision id.
def clean_internal_links(html):
    """Remove internal same-page links (<a> tags with href starting with '/wiki/' or '/w/')
       but keep image links and external links.
    """
    try:
        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.find_all('a', href=True):
            # Only remove internal links if no image is contained
            if a.find('img'):
                continue
            if (a['href'].startswith("/wiki/") and not a['href'].startswith("/wiki/File:")) \
               or (a['href'].startswith("/w/") and "File:" not in a['href']):
                a.replace_with(a.get_text())
        return str(soup)
    except Exception as e:
        print(f"Error cleaning internal links: {e}")
        return html

def download_wiki_history(article_title, language_code):
    """Download Wikipedia history with raw HTML and return history dataframe and page ID."""
    # Get the Wikipedia page ID
    page_id = get_page_id(article_title, language_code)

    if page_id is None:
        print(f"Warning: Could not retrieve page ID for {article_title}")

    # Fetch history with raw HTML
    history = get_history(article_title, domain=f"{language_code}.wikipedia.org", raw_html=True)

    try:
        # Extract data directly from the history objects
        print("Extracting raw HTML data...")
        data = []
        for item in history:
            try:
                raw_html = getattr(item, 'raw_html', '').replace('\n', '')
                raw_html_cleaned = remove_edit_sections(raw_html)  # Remove edit sections
                raw_html_cleaned = remove_source_notes(raw_html_cleaned)  # Remove source notes
                raw_html_cleaned = clean_internal_links(raw_html_cleaned)  # Remove links
                entry = {
                    'revid': getattr(item, 'revid', ''),
                    'time': getattr(item, 'time', ''),  # Use 'time' consistently
                    'user': getattr(item, 'user', ''),
                    'comment': getattr(item, 'comment', ''),
                    'raw_html': raw_html_cleaned
                }
                data.append(entry)
            except Exception as inner_e:
                print(f"Error extracting item: {inner_e}")

        history_df = pd.DataFrame(data)
    except Exception as e:
        print(f"Error extracting raw HTML data: {e}")
        # Create empty DataFrame with expected columns as last resort
        history_df = pd.DataFrame(columns=["revid", "time", "user", "comment", "raw_html"])

    # Return both the history dataframe and the page ID
    return history_df, page_id


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
    # Note: This function isn't defined - you may need to implement it
    # history_str = fix_unterminated_quotes(history_str)

    return history_str


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

    if db_config is None:
        db_config = {
            "host": "localhost",
            "dbname": "wikipedia_db",
            "user": "postgres",
            "password": "postgres",
            "port": 5432
        }

    conn = create_db_connection(**db_config)
    if not conn:
        print("Database connection failed, downloading data directly")
        history_df, page_id = download_wiki_history(article_title, language_code)
        return {"title": article_title, "language": language_code, "article_id": page_id}, history_df

    try:
        page_id = get_page_id(article_title, language_code)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT article_id, article_title, language_code, last_updated 
            FROM WP_article 
            WHERE article_id = %s
        """, (page_id,))
        article_result = cursor.fetchone()
        needs_update = True

        if article_result:
            article_id, title, lang, last_updated = article_result
            if last_updated and (datetime.now() - last_updated) < timedelta(days=max_age_days):
                needs_update = False
                print(f"Article '{title}' is up-to-date (last updated: {last_updated})")
            else:
                print(f"Article '{title}' needs update (last updated: {last_updated})")
        else:
            print(f"Article '{article_title}' not found in database")

        # Remove duplicate download: rely solely on update_article_history if update is needed.
        if needs_update:
            success = update_article_history(article_title, language_code, db_config)
            if not success:
                print("Warning: Failed to update article history")
            # Query updated history from the database.
            cursor.execute("""
                SELECT revid, timestamp, user_name, comment, diff_content as raw_html
                FROM history
                WHERE article_id = %s
                ORDER BY timestamp DESC
            """, (page_id,))
            history_rows = cursor.fetchall()
            history_df = pd.DataFrame(history_rows, columns=["revid", "time", "user", "comment", "raw_html"])
            article_id = page_id
        else:
            cursor.execute("""
                SELECT revid, timestamp, user_name, comment, diff_content as raw_html
                FROM history
                WHERE article_id = %s
                ORDER BY timestamp DESC
            """, (article_id,))
            history_rows = cursor.fetchall()
            history_df = pd.DataFrame(history_rows, columns=["revid", "time", "user", "comment", "raw_html"])

        article_data = {
            "article_id": article_id,
            "title": title if article_result else article_title,
            "language": lang if article_result else language_code,
            "last_updated": last_updated if article_result else None
        }

        cursor.close()
        conn.close()

        return article_data, history_df

    except Exception as e:
        print(f"Error in get_or_update_article: {e}")
        if conn:
            conn.close()
        print("Falling back to direct download")
        history_df, page_id = download_wiki_history(article_title, language_code)
        return {"title": article_title, "language": language_code, "article_id": page_id}, history_df

def delete_article(article_title, language_code, db_config=None):
    """
    Delete an article and its history from the database.

    Args:
        article_title (str): Title of the Wikipedia article.
        language_code (str): Language code of the article (e.g., 'en', 'de').
        db_config (dict, optional): Database connection parameters.

    Returns:
        bool: True if deletion was successful, False otherwise.
    """
    # Set default db_config if not provided
    if db_config is None:
        db_config = {
            "host": "localhost",
            "dbname": "wikipedia_db",
            "user": "postgres",
            "password": "postgres",
            "port": 5432
        }

    from db_utils import create_db_connection
    try:
        # Connect to database
        conn = create_db_connection(**db_config)
        if not conn:
            print("Database connection failed.")
            return False

        page_id = get_page_id(article_title, language_code)
        if not page_id:
            print(f"Article '{article_title}' not found (invalid page_id).")
            conn.close()
            return False

        cursor = conn.cursor()
        # Delete article history first (if it exists)
        cursor.execute("DELETE FROM history WHERE article_id = %s", (page_id,))
        # Delete article record
        cursor.execute("DELETE FROM WP_article WHERE article_id = %s", (page_id,))
        conn.commit()
        print(f"Article '{article_title}' and its history deleted successfully.")
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error deleting article: {e}")
        if conn:
            conn.close()
        return False

def download_latest_revision(article_title, language_code):
    """Download only the latest Wikipedia revision to check raw HTML content.

    Returns a dict with revision info or None if no revisions found.
    """
    try:
        history = get_history(article_title, domain=f"{language_code}.wikipedia.org", raw_html=True)
        if not history:
            print("No revisions found for", article_title)
            return None
        # Pick the revision with the latest time. Assume item.time is a datetime object.
        latest_revision = max(history, key=lambda item: getattr(item, 'time', datetime.min))
        revision_data = {
            'revid': getattr(latest_revision, 'revid', ''),
            'time': getattr(latest_revision, 'time', ''),
            'user': getattr(latest_revision, 'user', ''),
            'comment': getattr(latest_revision, 'comment', ''),
            'raw_html': getattr(latest_revision, 'raw_html', '').replace('\n', '')
        }
        return revision_data
    except Exception as e:
        print(f"Error downloading latest revision: {e}")
        return None

if __name__ == "__main__":
    from dotenv import load_dotenv
    import os

    # Load environment variables from .env file
    load_dotenv("../.env")

    db_config = {
        "dbname": os.getenv("DB_NAME", "your_database"),
        "user": os.getenv("DB_USER", "your_username"),
        "password": os.getenv("DB_PASSWORD", "your_password"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432")
    }

    # Example usage
    article_title = "David Degen"
    language_code = "de"

    task = ("replace") # can be "del", "get", "get-latest", "replace"

    if task == "get":
        article_data, history_data = get_or_update_article(article_title, language_code, db_config=db_config)

        print("Article Data:", article_data)
        print("History Data:", history_data.head(5))

    # Example use of download_latest_revision function
    if task == "get-latest":
        latest_revision = download_latest_revision(article_title, language_code)
        print("Latest Revision Data:", latest_revision)

    # Deletion example
    if task == "del":
        deletion_success = delete_article(article_title, language_code, db_config=db_config)
        print(f"Deletion of article '{article_title}' successful: {deletion_success}")

    if task == "replace":
        # First delete the article
        deletion_success = delete_article(article_title, language_code, db_config=db_config)
        print(f"Deletion of article '{article_title}' successful: {deletion_success}")

        # Then get the updated article
        article_data, history_data = get_or_update_article(article_title, language_code, db_config=db_config)

        print("Article Data:", article_data)
        print("History Data:", history_data.head(5))

