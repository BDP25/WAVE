# Extract the text content for each revision from history_table
import difflib
import pickle
import os
import html
from tqdm import tqdm
import pandas as pd

# Add installation commands for required packages
# Uncomment and run these lines if you're getting IProgress errors
# !pip install --upgrade jupyter
# !pip install --upgrade ipywidgets
# !jupyter nbextension enable --py widgetsnbextension

def extract_revision_texts(history_df, cache_path="revision_texts_cache.pkl"):
    """
    Extract text content for each revision from a history DataFrame
    
    Parameters:
    history_df (DataFrame): DataFrame containing revision history with 'revid' and 'text' columns
    cache_path (str): Path to save the extracted texts
    
    Returns:
    dict: Dictionary mapping revision IDs to their text content
    """
    # Create a dictionary to store revision texts
    revision_texts = {}

    print("Extracting text content for each revision...")
    # Loop through the revision IDs and get text from the dataframe
    for index, row in tqdm(history_df.iterrows(), total=len(history_df)):
        rev_id = row['revid']
        try:
            # Get the text content from the 'text' column
            if 'text' in row and pd.notna(row['text']):
                revision_texts[rev_id] = row['text']
            else:
                print(f"No text available for revision {rev_id}")
                revision_texts[rev_id] = ""  # Store empty string for missing text
        except Exception as e:
            print(f"Error extracting text for revision {rev_id}: {e}")
            revision_texts[rev_id] = ""  # Store empty string for failed extractions

    print(f"Successfully extracted text for {len(revision_texts)} revisions")

    # Save the revision texts to avoid re-processing
    with open(cache_path, "wb") as f:
        pickle.dump(revision_texts, f)

    print(f"Saved revision texts to {cache_path}")
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
    
    # First test the connection to provide better error messages
    if not test_db_connection(db_config):
        print("Database connection test failed. Please check your database configuration.")
        return pd.DataFrame()
    
    try:
        # Create database connection
        conn = create_db_connection(db_config=db_config)
        
        if not conn:
            print("Failed to establish database connection.")
            return pd.DataFrame()
        
        # Updated SQL query to use the correct tables based on actual schema
        query = """
        SELECT h.revid, h.timestamp, h.user_name as userid, h.comment, h.content as text 
        FROM history h
        WHERE h.article_id = %s
        ORDER BY h.timestamp
        """
        
        # Execute query and return results as DataFrame
        article_history = pd.read_sql(query, conn, params=[article_id])
        
        # Add 'minor' column (which doesn't exist in the schema) with default value
        article_history['minor'] = False
        
        # Close the connection
        conn.close()
        
        print(f"Retrieved {len(article_history)} revisions for article ID {article_id}")
        return article_history
        
    except Exception as e:
        print(f"Error retrieving revisions for article ID {article_id}: {e}")
        return pd.DataFrame()  # Return empty DataFrame on error

# Initialize a global variable to store revision texts
revision_texts = {}

def visualize_wiki_versions_with_deletions(revision_indices=None, article_id=None, start_revid=None, end_revid=None, word_level=True, verbose=False, db_config=None, use_mock_data=False):
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

    Returns:
    str: HTML content for visualization
    """
    from db_utils import db_params
    global history_table, revision_texts
    
    # Set default db_config if not provided
    if db_config is None:
        db_config = db_params
    
    # Check if we're using article_id and revids
    if article_id is not None:
        if use_mock_data:
            # Create mock data for testing when database is unavailable
            print("Using mock data instead of database")
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
                print(f"Could not retrieve revision history for article ID {article_id}")
                return None
                
        # Set the global history_table variable
        history_table = article_history
        
        # Extract revision texts if not already loaded
        if not revision_texts:
            revision_texts = extract_revision_texts(history_table)
        
        # Find indices for the specified revision IDs
        if start_revid is not None and end_revid is not None and not use_mock_data:
            # Check if the specified revisions exist
            start_exists = start_revid in article_history['revid'].values
            end_exists = end_revid in article_history['revid'].values

            if not start_exists or not end_exists:
                print(f"Warning: Specified revision IDs not found.")
                if not start_exists:
                    print(f"Start revision ID {start_revid} not found")
                if not end_exists:
                    print(f"End revision ID {end_revid} not found")
                
                # Fallback: Use first and last revisions instead
                print("Using first and last available revisions instead.")
                revision_indices = [0, len(article_history) - 1]
            else:
                # Get the indices of the specified revisions
                start_idx = article_history[article_history['revid'] == start_revid].index
                end_idx = article_history[article_history['revid'] == end_revid].index
                
                # Get all revisions between start and end (inclusive)
                revision_indices = list(range(start_idx[0], end_idx[0] + 1))
        else:
            if not use_mock_data:
                print("No specific revision IDs provided. Using first and last available revisions.")
                revision_indices = [0, len(article_history) - 1]
    
    # Make sure history_table is defined before continuing
    if 'history_table' not in globals():
        print("Error: history_table not defined. Please provide article_id or define history_table before calling this function.")
        return None
        
    # Ensure we have valid revision indices
    if revision_indices is None or len(revision_indices) < 2:
        print("Need at least two revisions to compare")
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
        
        if rev_id in revision_texts:
            text = revision_texts[rev_id]
        else:
            text = history_table.iloc[idx]['text'] if 'text' in history_table.columns else ""
        
        texts.append(text)
        user_infos.append(format_user_info(idx))
    
    if verbose:
        print(f"Comparing {len(texts)} revisions")
        for i, rev_id in enumerate(rev_ids):
            print(f"Revision {i+1}: {rev_id}, length: {len(texts[i])}")
    
    # Prepare the visualized output
    html_output = "<div style='font-family: monospace; white-space: pre-wrap;'>\n"
    html_output += "<h3>Wikipedia Article Diff Visualization</h3>\n"
    
    # Display revision info at the top
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
    from db_utils import create_db_connection, db_params, test_db_connection

    db_config = db_params  # Fixed: use db_params as a dict, not calling it as a function

    # Test database connection before trying to use it
    connection_ok = test_db_connection(db_config)
    
    # Example usage - compare two revisions with inline deletions
    article_id = "13436958"  # This article ID is valid
    
    # Option 1: Specify revision IDs that don't exist (will use fallback)
    # start_revid = 123456789  # This ID doesn't exist
    # end_revid = 987654321    # This ID doesn't exist
    
    # Option 2: Don't specify revision IDs at all (will use first and last)
    start_revid = None
    end_revid = None
    
    # Use mock data if connection fails
    use_mock = not connection_ok
    if use_mock:
        print("Using mock data since database connection failed")
    
    html = visualize_wiki_versions_with_deletions(article_id=article_id,
                                                  start_revid=start_revid,
                                                  end_revid=end_revid,
                                                  word_level=True,
                                                  verbose=True,
                                                  db_config=db_config,
                                                  use_mock_data=use_mock
                                                 )

    print(html)

