import nest_asyncio
nest_asyncio.apply()

import pandas as pd
from psycopg2.extras import execute_batch
from datetime import datetime
import difflib
import re
from bs4 import BeautifulSoup, NavigableString
import hashlib  # added for user color generation

# Import from new db_utils module instead of defining locally
from db_utils import create_db_connection, db_params

def initialize_tables(conn):
    """
    Create database tables if they don't exist.

    Args:
        conn: Database connection object

    Returns:
        bool: True if tables were created successfully, False otherwise

    Tables created:
        - WP_article: Stores article metadata
        - history: Stores article revision history data
    """
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
                diff_content TEXT,
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

def clean_internal_links(html):
    """
    Remove internal same-page links (<a> tags with href starting with '/wiki/' or '/w/')
    but keep image links and external links.

    Args:
        html (str): HTML content to process

    Returns:
        str: Processed HTML with internal links replaced by their text content

    Raises:
        Exception: If there's an error during HTML processing
    """
    try:
        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.find_all('a', href=True):
            # Skip altering if the link contains an image
            if a.find('img'):
                continue
            if (a['href'].startswith("/wiki/") and not a['href'].startswith("/wiki/File:")) \
               or (a['href'].startswith("/w/") and "File:" not in a['href']):
                a.replace_with(a.get_text())
        return str(soup)
    except Exception as e:
        print(f"Error cleaning internal links: {e}")
        return html

def get_user_color(user):
    """
    Assign a consistent hex color based on a user name.

    Args:
        user (str): Username to generate color for

    Returns:
        str: Hex color code (e.g., '#a1b2c3') derived from user's name
    """
    # Use first six characters of md5 hash for color code.
    return f"#{hashlib.md5(user.encode()).hexdigest()[:6]}"

def diff_text(old_text, new_text, user):
    """
    Compute a word-level diff between two text strings.
    Merges consecutive additions or deletions by the same user into single spans.

    Args:
        old_text (str): Original text
        new_text (str): New text to compare against
        user (str): Username to associate with the changes

    Returns:
        str: HTML string with added/deleted content wrapped in styled spans
    """
    # Tokenize words, punctuation, and whitespace
    tokens_old = re.findall(r'\w+|[^\w\s]|\s+', old_text, flags=re.UNICODE)
    tokens_new = re.findall(r'\w+|[^\w\s]|\s+', new_text, flags=re.UNICODE)

    # Use ndiff to get detailed character-level differences
    diff = difflib.ndiff(tokens_old, tokens_new)

    # Initialize variables for tracking and combining consecutive changes
    result = []
    current_operation = None  # '+', '-', or None for unchanged
    current_user = None
    buffer = []

    def flush_buffer():
        """Helper to wrap and append buffered content when operation changes"""
        nonlocal buffer, current_operation, current_user, result
        if not buffer:
            return

        combined_text = ''.join(buffer)
        if current_operation == '+':
            result.append(
                f'<span style="background-color: orange;" user-add="{current_user}">{combined_text}</span>'
            )
        elif current_operation == '-':
            result.append(
                f'<span style="text-decoration: line-through; text-decoration-color: orange;"'
                f' user-del="{current_user}">{combined_text}</span>'
            )
        else:
            result.append(combined_text)

        buffer = []

    # Process each token from the diff
    for op in diff:
        code, tok = op[0], op[2:]

        # Skip the '?' hint lines from ndiff
        if code == '?':
            continue

        # Determine operation type
        operation = None
        if code == ' ':
            operation = None  # unchanged
        elif code == '-':
            operation = '-'  # deletion
        elif code == '+':
            operation = '+'  # addition

        # If operation or user changed, flush the buffer
        if operation != current_operation or (operation in ['+', '-'] and current_user != user):
            flush_buffer()
            current_operation = operation
            current_user = user if operation in ['+', '-'] else None

        # Add current token to buffer
        buffer.append(tok)

    # Flush any remaining content
    flush_buffer()

    return ''.join(result)


def compute_diff(old_html, new_html, user):
    """
    Compute an HTML diff that preserves the overall structure.

    For each target tag (title, h1, p, th), compute a diff on its text content,
    then replace its inner HTML with the diff result wrapping inserted/deleted words.

    Args:
        old_html (str): Original HTML content
        new_html (str): New HTML content to compare against
        user (str): Username to associate with the changes

    Returns:
        str: HTML with differences highlighted in spans
    """
    old_soup = BeautifulSoup(old_html, 'html.parser')
    new_soup = BeautifulSoup(new_html, 'html.parser')
    target_tags = ['title', 'h1', 'p',  'th']

    # Process target tags (title, h1, p)
    for tag_name in target_tags:
        old_tags = old_soup.find_all(tag_name)
        new_tags = new_soup.find_all(tag_name)

        # Process each tag by index
        for i, new_tag in enumerate(new_tags):
            if i < len(old_tags):  # Only process if there's a corresponding old tag
                old_tag = old_tags[i]

                # Get complete text including any nested content
                old_text = old_tag.get_text(" ", strip=False)
                new_text = new_tag.get_text(" ", strip=False)

                # Skip if texts are identical (optimization)
                if old_text == new_text:
                    continue

                # Compute diff between old and new text
                diff_result = diff_text(old_text, new_text, user)

                # Replace the content of the tag with the diff result
                new_tag.clear()
                new_fragment = BeautifulSoup(diff_result, 'html.parser')
                for content in list(new_fragment.contents):
                    new_tag.append(content)

    # Return the modified HTML as a string
    return str(new_soup)

def save_article_to_db(conn, article_title, language_code, page_id):
    """
    Save article metadata to the WP_article table.

    Args:
        conn: Database connection object
        article_title (str): Title of the Wikipedia article
        language_code (str): Language code (e.g., 'en', 'de')
        page_id (int): Wikipedia's page ID for the article

    Returns:
        int or None: The article_id if saved successfully, None otherwise

    Notes:
        - Updates last_updated timestamp if article already exists
        - Creates a new record if article doesn't exist
    """
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
    """
    Save article revision history to the database.

    Args:
        conn: Database connection object
        article_id (int): ID of the article in the database
        history_df (pandas.DataFrame): DataFrame containing revision history data
            with columns: revid, time, user, comment, raw_html

    Returns:
        bool: True if history was saved successfully, False otherwise
    """
    if history_df.empty:
        print("No history data to save")
        return False

    try:
        cursor = conn.cursor()

        # Prepare data for batch insert
        history_data = []
        for _, row in history_df.iterrows():
            # Convert timestamp string to datetime if needed
            timestamp = row.get('time')
            if isinstance(timestamp, str):
                try:
                    timestamp = pd.to_datetime(timestamp)
                except:
                    timestamp = None

            history_data.append((
                article_id,
                row.get('revid'),
                timestamp,
                row.get('user'),
                row.get('comment'),
                row.get('raw_html')  # Changed: use raw_html column instead of text
            ))

        # Batch insert with content field
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

    Downloads article history from Wikipedia, saves it to the database,
    and computes incremental diffs between revisions.

    Args:
        article_title (str): Title of the Wikipedia article
        language_code (str): Language code for Wikipedia domain (e.g., 'en', 'de')
        db_config (dict, optional): Dictionary with database connection parameters.
            If None, default parameters are used.

    Returns:
        bool: True if update was successful, False otherwise
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
        if not success:
            conn.close()
            return False

        # --- New diff calculation: Compute incremental diffs ---
        cursor = conn.cursor()
        cursor.execute("""
            SELECT revid, content, user_name, timestamp FROM history
            WHERE article_id = %s
            ORDER BY timestamp ASC
        """, (article_id,))
        revisions = cursor.fetchall()  # (revid, content, user_name, timestamp)

        if revisions:
            # Set diff_content for the oldest revision equal to its content.
            first_revid, first_content, first_user, _ = revisions[0]
            cursor.execute("""
                UPDATE history SET diff_content = %s
                WHERE article_id = %s AND revid = %s
            """, (first_content, article_id, first_revid))

            # Use immediate predecessor for incremental diff.
            prev_content = first_content
            for rev in revisions[1:]:
                current_revid, current_content, current_user, _ = rev
                # Compute diff between previous revision content and the current one.
                diff_result = compute_diff(prev_content, current_content, current_user)
                cursor.execute("""
                    UPDATE history SET diff_content = %s
                    WHERE article_id = %s AND revid = %s
                """, (diff_result, article_id, current_revid))
                prev_content = current_content

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error in update_article_history: {e}")
        if conn:
            conn.close()
        return False

def update_article_history_in_batches(article_title, language_code, db_config=None, batch_size=50):
    """
    Update article history in the database using batch processing for diff calculation.

    Similar to update_article_history() but processes revisions in batches to improve
    performance for articles with large history.

    Args:
        article_title (str): Title of the Wikipedia article
        language_code (str): Language code for Wikipedia domain (e.g., 'en', 'de')
        db_config (dict, optional): Dictionary with database connection parameters.
            If None, default parameters are used.
        batch_size (int, optional): Number of revisions to process in each batch. Default is 50.

    Returns:
        bool: True if update was successful, False otherwise
    """
    if db_config is None:
        db_config = db_params

    from get_or_update_articel import download_wiki_history

    history_df, page_id = download_wiki_history(article_title, language_code)

    if history_df.empty or page_id is None:
        print(f"Failed to retrieve history or page ID for {article_title}")
        return False

    conn = create_db_connection(**db_config)
    if not conn:
        return False

    try:
        initialize_tables(conn)
        article_id = save_article_to_db(conn, article_title, language_code, page_id)
        if not article_id:
            conn.close()
            return False

        save_article_history_to_db(conn, article_id, history_df)

        cursor = conn.cursor()

        # Get the total number of revisions
        cursor.execute("""
                       SELECT COUNT(*)
                       FROM history
                       WHERE article_id = %s
                       """, (article_id,))
        total_revisions = cursor.fetchone()[0]

        prev_content = None
        prev_revid = None

        for offset in range(0, total_revisions, batch_size):
            print(f"Processing batch starting at offset {offset}...")

            cursor.execute("""
                           SELECT revid, content, user_name, timestamp
                           FROM history
                           WHERE article_id = %s
                           ORDER BY timestamp ASC
                               LIMIT %s
                           OFFSET %s
                           """, (article_id, batch_size, offset))
            revisions = cursor.fetchall()

            if not revisions:
                break

            for i, (current_revid, current_content, current_user, _) in enumerate(revisions):
                if offset == 0 and i == 0:
                    # For the very first revision, set diff_content = content
                    cursor.execute("""
                                   UPDATE history
                                   SET diff_content = %s
                                   WHERE article_id = %s
                                     AND revid = %s
                                   """, (current_content, article_id, current_revid))
                elif prev_content is not None:
                    # Compute diff between previous content and current content
                    diff_result = compute_diff(prev_content, current_content, current_user)
                    cursor.execute("""
                                   UPDATE history
                                   SET diff_content = %s
                                   WHERE article_id = %s
                                     AND revid = %s
                                   """, (diff_result, article_id, current_revid))

                # Update the previous content and revid for the next iteration
                prev_content = current_content
                prev_revid = current_revid

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error in update_article_history_in_batches: {e}")
        if conn:
            conn.close()
        return False
