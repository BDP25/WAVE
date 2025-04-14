# Extract the text content for each revision from history_table
import pandas as pd
import redis
import logging

# Setup logging
def setup_logger(level=logging.INFO):
    """Configure and return a logger for the application"""
    logger = logging.getLogger("wiki_diff")
    logger.setLevel(level)
    
    # Create console handler if not already added
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

# Initialize logger
logger = setup_logger()

# Add installation commands for required packages
# Uncomment and run these lines if you're getting IProgress errors
# !pip install --upgrade jupyter
# !pip install --upgrade ipywidgets
# !jupyter nbextension enable --py widgetsnbextension
# !pip install redis

def get_redis_connection(host='localhost', port=6379, db=0, password=None):
    """
    Get a connection to Redis
    
    Parameters:
    host (str): Redis host
    port (int): Redis port
    db (int): Redis database number
    password (str): Redis password if needed
    
    Returns:
    redis.Redis: Redis connection object or None if connection fails
    """
    try:
        conn = redis.Redis(host=host, port=port, db=db, password=password, decode_responses=True)
        # Test connection
        conn.ping()
        return conn
    except redis.ConnectionError as e:
        logger.error(f"Redis connection error: {e}")
        return None

def extract_revision_texts(history_df, redis_config=None):
    """
    Extract text content for each revision from a history DataFrame
    and store it in Redis
    
    Parameters:
    history_df (DataFrame): DataFrame containing revision history with 'revid' and 'text' columns
    redis_config (dict): Redis connection parameters
    
    Returns:
    dict: Dictionary mapping revision IDs to their text content
    """
    # Create a dictionary to store revision texts
    revision_texts = {}
    
    # Set default Redis config if not provided
    if redis_config is None:
        redis_config = {
            'host': 'localhost',
            'port': 6379,
            'db': 0,
            'password': None
        }
    
    # Try to connect to Redis
    r = get_redis_connection(**redis_config)
    using_redis = r is not None
    
    if not using_redis:
        logger.warning("Redis connection failed, using in-memory cache only")

    logger.info("Extracting text content for each revision...")
    # Loop through the revision IDs and get text from the dataframe
    for index, row in history_df.iterrows():
        rev_id = row['revid']
        cache_key = f"revision:{rev_id}:text"
        
        # Try to get from Redis first if connected
        if using_redis:
            cached_text = r.get(cache_key)
            if cached_text:
                revision_texts[rev_id] = cached_text
                continue
        
        try:
            # Get the text content from the 'text' column
            if 'text' in row and pd.notna(row['text']):
                revision_texts[rev_id] = row['text']
                # Store in Redis if connected
                if using_redis:
                    r.set(cache_key, row['text'])
                    # Add to the set of cached revisions
                    r.sadd("cached_revisions", rev_id)
            else:
                logger.warning(f"No text available for revision {rev_id}")
                revision_texts[rev_id] = ""  # Store empty string for missing text
                if using_redis:
                    r.set(cache_key, "")
        except Exception as e:
            logger.error(f"Error extracting text for revision {rev_id}: {e}")
            revision_texts[rev_id] = ""  # Store empty string for failed extractions
            if using_redis:
                r.set(cache_key, "")

    if using_redis:
        # Set expiration on all keys (optional, 1 day = 86400 seconds)
        for rev_id in revision_texts:
            r.expire(f"revision:{rev_id}:text", 86400)
        logger.info(f"Successfully cached {len(revision_texts)} revisions in Redis")
    else:
        logger.info(f"Successfully extracted text for {len(revision_texts)} revisions (in-memory only)")

    return revision_texts

# Initialize a global variable to store revision texts
revision_texts = {}

# Enhanced function to visualize Wikipedia versioning with inline deletion display
from IPython.display import HTML
import re
import hashlib
import colorsys
import html
import difflib  # Make sure difflib is imported

def get_revisions_by_article_id(article_id, db_config):
    """
    Retrieve revision history for an article from the database
    
    Parameters:
    article_id (int): The ID of the article to retrieve revisions for
    db_config (dict): Database connection parameters
    
    Returns:
    DataFrame: DataFrame containing revision history with columns including 'revid' and 'text'
    """
    from db_utils import create_db_connection, test_db_connection
    import sqlalchemy

    # First test the connection to provide better error messages
    if not test_db_connection(db_config):
        logger.error("Database connection test failed. Please check your database configuration.")
        return pd.DataFrame()
    
    try:
        # Create database connection
        conn = create_db_connection(db_config=db_config)
        
        if not conn:
            logger.error("Failed to establish database connection.")
            return pd.DataFrame()
        
        # Create SQLAlchemy engine from connection parameters
        # This approach avoids modifying the db_utils module
        try:
            # If using PostgreSQL
            db_type = db_config.get('type', 'postgresql')
            user = db_config.get('user', '')
            password = db_config.get('password', '')
            host = db_config.get('host', 'localhost')
            port = db_config.get('port', '5432')
            database = db_config.get('database', '')

            connection_string = f"{db_type}://{user}:{password}@{host}:{port}/{database}"
            engine = sqlalchemy.create_engine(connection_string)

            # Updated SQL query to use the correct tables based on actual schema
            query = """
            SELECT h.revid, h.timestamp, h.user_name as userid, h.comment, h.content as text 
            FROM history h
            WHERE h.article_id = %s
            ORDER BY h.timestamp
            """

            # Execute query using SQLAlchemy engine instead of direct connection
            article_history = pd.read_sql(query, engine, params=[article_id])

            # Add 'minor' column (which doesn't exist in the schema) with default value
            article_history['minor'] = False

            logger.info(f"Retrieved {len(article_history)} revisions for article ID {article_id}")
            return article_history

        except Exception as sqlalchemy_error:
            # Fallback to original method with warning suppression if SQLAlchemy approach fails
            logger.warning(f"SQLAlchemy connection failed ({sqlalchemy_error}), falling back to direct connection")

            import warnings
            # Temporarily suppress the specific pandas warning
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=UserWarning,
                                       message="pandas only supports SQLAlchemy connectable.*")

                # Use the original connection directly with warning suppressed
                query = """
                SELECT h.revid, h.timestamp, h.user_name as userid, h.comment, h.content as text 
                FROM history h
                WHERE h.article_id = %s
                ORDER BY h.timestamp
                """

                article_history = pd.read_sql(query, conn, params=[article_id])
                article_history['minor'] = False

                # Close the connection
                if hasattr(conn, 'close'):
                    conn.close()

                logger.info(f"Retrieved {len(article_history)} revisions for article ID {article_id}")
                return article_history

    except Exception as e:
        logger.error(f"Error retrieving revisions for article ID {article_id}: {e}")
        return pd.DataFrame()  # Return empty DataFrame on error

# Initialize a global variable to store revision texts
revision_texts = {}

def get_revision_text(rev_id, redis_config=None):
    """
    Get revision text from Redis cache or return from in-memory cache
    
    Parameters:
    rev_id: Revision ID
    redis_config (dict): Redis connection parameters
    
    Returns:
    str: Text content of the revision
    """
    global revision_texts
    
    # If already in memory, return it
    if rev_id in revision_texts:
        return revision_texts[rev_id]
    
    # Set default Redis config if not provided
    if redis_config is None:
        redis_config = {
            'host': 'localhost',
            'port': 6379,
            'db': 0,
            'password': None
        }
    
    # Try to get from Redis
    r = get_redis_connection(**redis_config)
    if r:
        cache_key = f"revision:{rev_id}:text"
        text = r.get(cache_key)
        if text:
            # Store in memory cache too
            revision_texts[rev_id] = text
            return text
    
    # Not found in any cache
    return None

def visualize_wiki_versions_with_deletions(revision_indices=None, article_id=None, start_revid=None, end_revid=None, word_level=True, verbose=False, db_config=None, use_mock_data=False, redis_config=None, show_revision_info=True):
    """
    Visualize Wikipedia versioning with each revision's contributions colored by revision ID,
    including inline strikethrough for deleted text.

    Parameters:
    revision_indices (list): List of indices in history_table to compare sequentially
    article_id (int): The ID of the article to visualize (alternative to revision_indices)
    start_revid (int): The starting revision ID (used with article_id)
    end_revid (int): The ending revision ID (used with article_id)
    word_level (bool): If True, perform word-level diff instead of line-level
    verbose (bool): If True, print additional information about each revision
    db_config (dict): Database connection parameters
    use_mock_data (bool): If True, use mock data instead of database (for development/testing)
    redis_config (dict): Redis connection parameters
    show_revision_info (bool): If True, show revision info lines at the top of the visualization

    Returns:
    str: HTML content for visualization
    """
    from db_utils import db_params
    global history_table, revision_texts

    # Set default db_config if not provided
    if db_config is None:
        db_config = db_params

    # Set default Redis config if not provided
    if redis_config is None:
        redis_config = {
            'host': 'localhost',
            'port': 6379,
            'db': 0,
            'password': None
        }

    # Check if we're using article_id and revids
    if article_id is not None:
        if use_mock_data:
            # Create mock data for testing when database is unavailable
            logger.info("Using mock data instead of database")
            mock_data = {
                'revid': [100001, 100002, 100003],
                'timestamp': ['2023-01-01', '2023-01-02', '2023-01-03'],
                'userid': [1, 2, 1],
                'minor': [False, False, True],
                'comment': ['Initial version', 'Added introduction', 'Fixed typo'],
                'text': [
                    'This is a sample article.',
                    'This is a sample article with an introduction.',
                    'This is a sample article with an introduction. Fixed a typo.'
                ]
            }
            article_history = pd.DataFrame(mock_data)

            # If specific revids were requested, filter the mock data
            if start_revid is not None and end_revid is not None:
                # For mock data, just use all available revisions
                revision_indices = list(range(len(article_history)))

        else:
            # Get revision history from database
            article_history = get_revisions_by_article_id(article_id, db_config)

            if article_history.empty:
                logger.error(f"Could not retrieve revision history for article ID {article_id}")
                return None

        # Set the global history_table variable
        history_table = article_history

        # Extract revision texts if not already loaded
        if not revision_texts:
            revision_texts = extract_revision_texts(history_table, redis_config)

        # Find indices for the specified revision IDs
        if start_revid is not None and end_revid is not None and not use_mock_data:
            # Check if the specified revisions exist
            start_exists = start_revid in article_history['revid'].values
            end_exists = end_revid in article_history['revid'].values

            if not start_exists or not end_exists:
                logger.warning(f"Specified revision IDs not found.")
                if not start_exists:
                    logger.warning(f"Start revision ID {start_revid} not found")
                if not end_exists:
                    logger.warning(f"End revision ID {end_revid} not found")

                # Fallback: Use first and last revisions instead
                logger.info("Using first and last available revisions instead.")
                revision_indices = [0, len(article_history) - 1]
            else:
                # Get the indices of the specified revisions
                start_idx = article_history[article_history['revid'] == start_revid].index
                end_idx = article_history[article_history['revid'] == end_revid].index

                # Get all revisions between start and end (inclusive)
                revision_indices = list(range(start_idx[0], end_idx[0] + 1))
        else:
            if not use_mock_data:
                logger.info("No specific revision IDs provided. Using first and last available revisions.")
                revision_indices = [0, len(article_history) - 1]

    # Make sure history_table is defined before continuing
    if 'history_table' not in globals():
        logger.error("history_table not defined. Please provide article_id or define history_table before calling this function.")
        return None

    # Ensure we have valid revision indices
    if revision_indices is None or len(revision_indices) < 2:
        logger.error("Need at least two revisions to compare")
        return None

    # Generate color mapping based on revision IDs
    def get_color_for_revision(revision_id):
        """Generate a consistent color for a given revision ID"""
        hash_value = int(hashlib.md5(str(revision_id).encode()).hexdigest(), 16) % (2**24)
        # Convert to HSL and ensure good contrast with light background
        h = hash_value / (2**24)
        s = 0.7  # Fairly saturated colors
        l = 0.4  # Darker colors for better visibility
        # Convert HSL to RGB
        r, g, b = [int(x * 255) for x in colorsys.hls_to_rgb(h, l, s)]
        return f"rgb({r}, {g}, {b})"

    # Function to format user info with timestamp
    def format_user_info(revision_idx):
        """Format user info with timestamp for display"""
        row = history_table.iloc[revision_idx]
        rev_id = row['revid']
        timestamp = row['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(row['timestamp'], 'strftime') else row['timestamp']
        user = row['userid']
        comment = row['comment'] if pd.notna(row['comment']) else ""

        return f"<span class='rev-info' style='font-size:0.8em; color:gray;'>[Rev {rev_id} | {timestamp} | User: {user}]</span> {comment}<br>"

    # Get text for all revisions we need to compare
    texts = []
    rev_ids = []
    user_infos = []

    for idx in revision_indices:
        rev_id = history_table.iloc[idx]['revid']
        rev_ids.append(rev_id)

        # Try to get from Redis first, then fallback to in-memory cache
        text = get_revision_text(rev_id, redis_config)

        if text is None:
            text = history_table.iloc[idx]['text'] if 'text' in history_table.columns else ""
            # Store for future use
            revision_texts[rev_id] = text

            # Cache in Redis if possible
            r = get_redis_connection(**redis_config)
            if r:
                r.set(f"revision:{rev_id}:text", text)
                r.sadd("cached_revisions", rev_id)

        texts.append(text)
        user_infos.append(format_user_info(idx))

    if verbose:
        logger.info(f"Comparing {len(texts)} revisions")
        for i, rev_id in enumerate(rev_ids):
            logger.info(f"Revision {i+1}: {rev_id}, length: {len(texts[i])}")

    # Prepare the visualized output
    html_output = "<div style='font-family: monospace; white-space: pre-wrap;'>\n"
    html_output += "<h3>Wikipedia Article Diff Visualization</h3>\n"

    # Display revision info at the top (only if show_revision_info is True)
    if show_revision_info:
        for i, info in enumerate(user_infos):
            html_output += f"<div style='margin-bottom: 5px;'><b>Revision {i+1}:</b> {info}</div>\n"

    html_output += "<hr>\n<div style='padding: 20px; border: 1px solid #ccc; background-color: #f9f9f9;'>\n"

    # Perform diff between first and last revision
    first_text = texts[0]
    last_text = texts[-1]

    # Split text by words or lines based on the word_level parameter
    if word_level:
        first_tokens = first_text.split()
        last_tokens = last_text.split()
    else:
        first_tokens = first_text.splitlines()
        last_tokens = last_text.splitlines()

    # Generate the diff
    diff = difflib.SequenceMatcher(None, first_tokens, last_tokens)

    # Process the diff operations
    result = []

    for op, i1, i2, j1, j2 in diff.get_opcodes():
        if op == 'equal':
            # Text present in both versions
            for token in first_tokens[i1:i2]:
                result.append(f"<span>{html.escape(token)}</span>")
                if word_level:
                    result.append(" ")
                else:
                    result.append("<br>")
        elif op == 'delete':
            # Text deleted in the newer version
            color = get_color_for_revision(rev_ids[0])
            for token in first_tokens[i1:i2]:
                result.append(f"<span style='text-decoration:line-through; color:{color};'>{html.escape(token)}</span>")
                if word_level:
                    result.append(" ")
                else:
                    result.append("<br>")
        elif op == 'insert':
            # Text added in the newer version
            color = get_color_for_revision(rev_ids[-1])
            for token in last_tokens[j1:j2]:
                result.append(f"<span style='background-color:rgba({color[4:-1]},0.2); color:{color};'>{html.escape(token)}</span>")
                if word_level:
                    result.append(" ")
                else:
                    result.append("<br>")
        elif op == 'replace':
            # Text replaced (combination of delete and insert)
            # First show the deleted text
            delete_color = get_color_for_revision(rev_ids[0])
            for token in first_tokens[i1:i2]:
                result.append(f"<span style='text-decoration:line-through; color:{delete_color};'>{html.escape(token)}</span>")
                if word_level:
                    result.append(" ")
                else:
                    result.append("<br>")

            # Then show the inserted text
            insert_color = get_color_for_revision(rev_ids[-1])
            for token in last_tokens[j1:j2]:
                result.append(f"<span style='background-color:rgba({insert_color[4:-1]},0.2); color:{insert_color};'>{html.escape(token)}</span>")
                if word_level:
                    result.append(" ")
                else:
                    result.append("<br>")

    # Add the result to the HTML output
    html_output += "".join(result)
    html_output += "\n</div>\n</div>"

    return html_output

if __name__ == "__main__":
    from db_utils import create_db_connection, db_params, redis_params, test_db_connection

    # Set logging level to DEBUG for detailed output
    logger.setLevel(logging.ERROR)

    # Use Redis and Postgress configuration from environment variables
    db_config = db_params
    redis_config = redis_params

    # Example usage - compare two revisions with inline deletions
    article_id = "13436958"  # This article ID is valid

    # Specify revision IDs
    start_revid = 254642216
    end_revid = 255135586


    html = visualize_wiki_versions_with_deletions(article_id=article_id,
                                                  start_revid=start_revid,
                                                  end_revid=end_revid,
                                                  word_level=True,
                                                  verbose=True,
                                                  db_config=db_config,
                                                  redis_config=redis_config,
                                                  show_revision_info=False
                                                 )

    print(f"\nHTML:\n-------------------------------------------------------\n{html}\n-------------------------------------------------------")

