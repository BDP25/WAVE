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

# Create a dictionary to store revision texts
revision_texts = {}

print("Extracting text content for each revision...")
# Loop through the revision IDs and get text from the dataframe
for index, row in tqdm(history_table.iterrows(), total=len(history_table)):
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
cache_path = "revision_texts_cache.pkl"
with open(cache_path, "wb") as f:
    pickle.dump(revision_texts, f)

print(f"Saved revision texts to {cache_path}")

# Enhanced function to visualize Wikipedia versioning with inline deletion display
from IPython.display import HTML
import re
import hashlib
import colorsys
import html
import difflib  # Make sure difflib is imported


def get_history_from_db(article_id, db_params):
    """
    Fetch the article history from the database.

    Parameters:
    article_id (int): The ID of the article to fetch history for.
    db_params (dict): Database connection parameters.

    Returns:
    DataFrame: A DataFrame containing the article history.
    """
    # Placeholder function - implement your database fetching logic here
    pass


def get_article_id_by_name(article_title, language_code='en', db_config=None):
    """
    Get the article ID for a given article title and language code.
    
    Parameters:
    article_title (str): The title of the Wikipedia article
    language_code (str): Language code (default: 'en')
    db_config (dict): Database connection parameters
    
    Returns:
    int: The article ID if found, None otherwise
    """
    # Import at runtime to avoid circular dependency
    from db_utils import create_db_connection, db_params
    
    # Set default db_config if not provided
    if db_config is None:
        db_config = db_params
        
    # Connect to database
    conn = create_db_connection(**db_config)
    if not conn:
        print(f"Failed to connect to the database")
        return None
        
    try:
        cursor = conn.cursor()
        
        # Query the database for the article
        cursor.execute("""
            SELECT article_id FROM WP_article 
            WHERE article_title = %s AND language_code = %s
        """, (article_title, language_code))
        
        result = cursor.fetchone()
        
        if result:
            return result[0]
        else:
            print(f"No article found with title '{article_title}' and language '{language_code}'")
            return None
            
    except Exception as e:
        print(f"Error retrieving article ID: {e}")
        return None
        
    finally:
        if conn:
            conn.close()

def get_revisions_by_article_id(article_id, db_config=None):
    """
    Get all revisions with their timestamps for a given article ID.
    
    Parameters:
    article_id (int): The ID of the Wikipedia article
    db_config (dict): Database connection parameters
    
    Returns:
    DataFrame: A DataFrame containing revid, timestamp, and user for each revision
    """
    from db_utils import create_db_connection, db_params
    
    # Set default db_config if not provided
    if db_config is None:
        db_config = db_params
        
    # Connect to database
    conn = create_db_connection(**db_config)
    if not conn:
        print(f"Failed to connect to the database")
        return pd.DataFrame()
        
    try:
        cursor = conn.cursor()
        
        # Query the database for the revisions
        cursor.execute("""
            SELECT revid, timestamp, user_name, comment 
            FROM history 
            WHERE article_id = %s
            ORDER BY timestamp ASC
        """, (article_id,))
        
        results = cursor.fetchall()
        
        if results:
            # Convert to DataFrame
            df = pd.DataFrame(results, columns=['revid', 'time', 'user', 'comment'])
            return df
        else:
            print(f"No revisions found for article ID {article_id}")
            return pd.DataFrame()
            
    except Exception as e:
        print(f"Error retrieving revisions: {e}")
        return pd.DataFrame()
        
    finally:
        if conn:
            conn.close()

def get_revision_text(article_id, revid, language_code='en'):
    """
    Get the text content for a specific revision ID.
    
    Parameters:
    article_id (int): The article ID
    revid (int): The revision ID
    language_code (str): Language code (default: 'en')
    
    Returns:
    str: The text content of the revision
    """
    from wikipedia_histories import get_revision_content
    
    try:
        # Get article title from article_id (would need another DB lookup in practice)
        cursor = conn.cursor()
        cursor.execute("SELECT article_title FROM WP_article WHERE article_id = %s", (article_id,))
        result = cursor.fetchone()
        
        if not result:
            print(f"No article found with ID {article_id}")
            return ""
            
        article_title = result[0]
        
        # Use the Wikipedia API to get the revision content
        text = get_revision_content(article_title, revid, domain=f"{language_code}.wikipedia.org")
        return text
    except Exception as e:
        print(f"Error retrieving revision text: {e}")
        return ""

def visualize_wiki_versions_with_deletions(revision_indices=None, article_id=None, start_revid=None, end_revid=None, word_level=True, verbose=False, db_config=None):
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

    Returns:
    str: HTML content for visualization
    """
    from db_utils import db_params
    global history_table
    
    # Set default db_config if not provided
    if db_config is None:
        db_config = db_params
    
    # Check if we're using article_id and revids
    if article_id is not None:
        # Get revision history from database
        article_history = get_revisions_by_article_id(article_id, db_config)
        
        if article_history.empty:
            print(f"Could not retrieve revision history for article ID {article_id}")
            return None
            
        # Set the global history_table variable
        history_table = article_history
        
        # Find indices for the specified revision IDs
        if start_revid is not None and end_revid is not None:
            # Get the indices of the specified revisions
            start_idx = article_history[article_history['revid'] == start_revid].index
            end_idx = article_history[article_history['revid'] == end_revid].index
            
            if len(start_idx) == 0:
                print(f"Start revision ID {start_revid} not found")
                return None
                
            if len(end_idx) == 0:
                print(f"End revision ID {end_revid} not found")
                return None
                
            # Get all revisions between start and end (inclusive)
            revision_indices = list(range(start_idx[0], end_idx[0] + 1))
        else:
            print("Both start_revid and end_revid must be specified when using article_id")
            return None
    
    # Ensure we have valid revision indices
    if revision_indices is None or len(revision_indices) < 2:
        print("Need at least two revisions to compare")
        return None

    # Validate indices and get revision IDs
    rev_ids = []
    users = []
    timestamps = []

    # Make indices unique to avoid duplication issues
    revision_indices = list(dict.fromkeys(revision_indices))

    for idx in revision_indices:
        if 0 <= idx < len(history_table):
            rev_ids.append(history_table['revid'].iloc[idx])
            users.append(history_table['user'].iloc[idx])
            timestamps.append(history_table['time'].iloc[idx] if 'time' in history_table.columns else 'Unknown')
        else:
            print(f"Invalid index: {idx}")
            return

    # Define baseline_rev_id as the first revision and final_rev_id as the last revision
    baseline_rev_id = rev_ids[0]
    final_rev_id = rev_ids[-1]

    if verbose:
        for i, (rev_id, user, timestamp) in enumerate(zip(rev_ids, users, timestamps)):
            print(f"V{i + 1}: Rev {rev_id} by {user} at {timestamp}")

    # Function to generate maximally distinct colors
    def generate_distinct_colors(n_colors):
        """Generate n distinct colors that are maximally separated in hue space."""
        colors = []
        for i in range(n_colors):
            # Use golden ratio conjugate for better distribution
            hue = (i * 0.618033988749895) % 1
            saturation = 0.7 + (i % 3) * 0.1  # Vary saturation slightly
            value = 0.85 + (i % 2) * 0.1  # Vary brightness slightly

            r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
            hex_color = "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))
            colors.append(hex_color)
        return colors

    # Generate distinct colors based on number of revisions
    distinct_colors = generate_distinct_colors(len(rev_ids))

    # Create a mapping from revision IDs to colors
    rev_colors = {rev_id: color for rev_id, color in zip(rev_ids, distinct_colors)}

    # Get the revision texts
    revision_texts_dict = {}
    for i, rev_id in enumerate(rev_ids):
        try:
            # Try to get text from the dataframe first
            idx = revision_indices[i]
            if 'text' in history_table.columns and pd.notna(history_table['text'].iloc[idx]):
                revision_texts_dict[rev_id] = history_table['text'].iloc[idx]
            # Fall back to the revision_texts dictionary if available
            elif rev_id in revision_texts and revision_texts[rev_id]:
                revision_texts_dict[rev_id] = revision_texts[rev_id]
            else:
                print(f"Warning: No text available for revision {rev_id}")
                revision_texts_dict[rev_id] = ""
        except Exception as e:
            print(f"Error retrieving text for revision {rev_id}: {e}")
            revision_texts_dict[rev_id] = revision_texts[rev_id]

    # Collect deletions and their replacements for each revision pair
    all_replacements = []

    for i in range(1, len(rev_ids)):
        prev_rev_id = rev_ids[i - 1]
        current_rev_id = rev_ids[i]

        prev_text = revision_texts_dict[prev_rev_id]
        current_text = revision_texts_dict[current_rev_id]

        # Use SequenceMatcher for more accurate diff
        if word_level:
            # Split into words for word-level diff
            prev_words = re.findall(r'\w+|\s+|[^\w\s]', prev_text)
            current_words = re.findall(r'\w+|\s+|[^\w\s]', current_text)

            # Find word-level differences
            matcher = difflib.SequenceMatcher(None, prev_words, current_words)

            for op, i1, i2, j1, j2 in matcher.get_opcodes():
                if op == 'replace':
                    # Text was replaced
                    deleted_content = ''.join(prev_words[i1:i2])
                    added_content = ''.join(current_words[j1:j2])

                    all_replacements.append({
                        'deleted': deleted_content,
                        'added': added_content,
                        'prev_rev_id': prev_rev_id,
                        'current_rev_id': current_rev_id,
                        'position': j2  # Position after the added content
                    })
                elif op == 'delete':
                    # Text was deleted without replacement
                    deleted_content = ''.join(prev_words[i1:i2])

                    all_replacements.append({
                        'deleted': deleted_content,
                        'added': '',
                        'prev_rev_id': prev_rev_id,
                        'current_rev_id': current_rev_id,
                        'position': j1  # Position where deletion occurred
                    })
        else:
            # Line-level diff
            prev_lines = prev_text.splitlines()
            current_lines = current_text.splitlines()

            differ = difflib.Differ()
            diff = list(differ.compare(prev_lines, current_lines))

            # Process line diffs to detect replacements
            i = 0
            while i < len(diff):
                line = diff[i]
                if line.startswith('- '):
                    deleted_content = line[2:]

                    # Look ahead for potential replacement
                    if i + 1 < len(diff) and diff[i + 1].startswith('+ '):
                        added_content = diff[i + 1][2:]
                        all_replacements.append({
                            'deleted': deleted_content,
                            'added': added_content,
                            'prev_rev_id': prev_rev_id,
                            'current_rev_id': current_rev_id,
                            'position': i  # Approximate position
                        })
                        i += 2  # Skip the next line as we've processed it
                    else:
                        # No replacement found
                        all_replacements.append({
                            'deleted': deleted_content,
                            'added': '',
                            'prev_rev_id': prev_rev_id,
                            'current_rev_id': current_rev_id,
                            'position': i  # Approximate position
                        })
                        i += 1
                else:
                    i += 1

    # Create token mappings for each revision
    token_attributions = []

    # Process first revision
    first_text = revision_texts_dict[baseline_rev_id]
    token_pattern = r'\w+|\s+|[^\w\s]' if word_level else r'.'
    first_tokens = re.findall(token_pattern, first_text)

    # Initialize with first revision - all tokens attributed to baseline
    token_attributions.append({
        'tokens': first_tokens,
        'attributions': [baseline_rev_id] * len(first_tokens)
    })

    # Process subsequent revisions
    for i in range(1, len(rev_ids)):
        prev_rev_id = rev_ids[i - 1]
        current_rev_id = rev_ids[i]

        prev_tokens = token_attributions[-1]['tokens']
        prev_attributions = token_attributions[-1]['attributions']

        new_text = revision_texts_dict[current_rev_id]
        new_tokens = re.findall(token_pattern, new_text)

        # Use difflib's SequenceMatcher to find differences
        matcher = difflib.SequenceMatcher(None, prev_tokens, new_tokens)

        # Create new attribution information
        new_attributions = []

        # Process each diff operation
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == 'equal':
                # Tokens unchanged - preserve attributions
                for k in range(j1, j2):
                    idx = k - j1 + i1
                    new_attributions.append(prev_attributions[idx])
            elif op == 'replace' or op == 'insert':
                # New tokens inserted by current revision
                for _ in range(j1, j2):
                    new_attributions.append(current_rev_id)
            # 'delete' operations are not reflected in new_tokens

        # Store this revision's information
        token_attributions.append({
            'tokens': new_tokens,
            'attributions': new_attributions
        })

    # Use the final revision's tokens and attributions
    final_attribution = token_attributions[-1]
    final_tokens = final_attribution['tokens']
    final_token_attributions = final_attribution['attributions']

    # Generate HTML for visualization
    html_content = """
    <style>
    .wiki-version {
        font-family: monospace;
        white-space: pre-wrap;
        line-height: 1.5;
        font-size: 14px;
        padding: 10px;
        border: 1px solid #ddd;
        border-radius: 5px;
        background-color: #fff;
    }
    .wiki-version span.text {
        border-radius: 2px;
        color: #000000;
    }
    .wiki-version span.text:hover {
        outline: 1px dotted #888;
    }
    .wiki-version span.deletion {
        text-decoration: line-through;
        border-radius: 2px;
        margin-right: 2px;
        color: #000000;
    }
    .revision-legend {
        margin-top: 15px;
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
    }
    .revision-legend .item {
        display: flex;
        align-items: center;
        gap: 5px;
        border: 1px solid #ddd;
        padding: 3px 8px;
        border-radius: 3px;
    }
    .revision-legend .color {
        width: 15px;
        height: 15px;
        border-radius: 3px;
    }
    </style>
    <div class="wiki-version">
    """

    # Track positions for inserting deletions
    insertion_points = {}

    # Process by token to create spans for the visualization
    current_rev = None
    current_segment = ""
    result_html = ""
    html_position = 0
    text_position = 0

    # Map to track text positions to HTML positions
    position_mapping = {}

    # First, construct the basic text with attribution spans
    for token, attribution in zip(final_tokens, final_token_attributions):
        if attribution != current_rev:
            # Output any accumulated segment
            if current_segment:
                bg_color = "transparent"
                if current_rev != baseline_rev_id:  # Don't highlight the oldest revision
                    rev_color = rev_colors.get(current_rev, "#cccccc")
                    bg_color = f"rgba({int(rev_color[1:3], 16)}, {int(rev_color[3:5], 16)}, {int(rev_color[5:7], 16)}, 0.2)"

                span_html = f'<span class="text" style="color: #000000; background-color: {bg_color};" title="Added by Rev {current_rev}">{html.escape(current_segment)}</span>'

                # Record the position before adding the span
                position_mapping[text_position] = html_position

                result_html += span_html
                html_position += len(span_html)
                text_position += len(current_segment)

            current_rev = attribution
            current_segment = token
        else:
            current_segment += token

    # Add any remaining segment
    if current_segment:
        bg_color = "transparent"
        if current_rev != baseline_rev_id:  # Don't highlight the oldest revision
            rev_color = rev_colors.get(current_rev, "#cccccc")
            bg_color = f"rgba({int(rev_color[1:3], 16)}, {int(rev_color[3:5], 16)}, {int(rev_color[5:7], 16)}, 0.2)"

        span_html = f'<span class="text" style="color: #000000; background-color: {bg_color};" title="Added by Rev {current_rev}">{html.escape(current_segment)}</span>'

        # Record the position before adding the span
        position_mapping[text_position] = html_position

        result_html += span_html
        html_position += len(span_html)
        text_position += len(current_segment)

    # Final position mapping for the end of the text
    position_mapping[text_position] = html_position

    # Parse HTML to find insertion points for deletions
    final_html = result_html
    final_text = ''.join(final_tokens)

    # Add deletions after relevant content
    replacement_insertions = []

    for replacement in all_replacements:
        deleted_text = replacement['deleted']
        added_text = replacement['added']
        prev_rev = replacement['prev_rev_id']
        del_rev = replacement['current_rev_id']

        # Find position in the text where this added content is
        if added_text:
            pos = final_text.find(added_text)
            if pos >= 0:
                insertion_pos = pos + len(added_text)  # Position after the added content
            else:
                # If we can't find the exact added text, use an approximate position
                insertion_pos = min(replacement['position'], len(final_text))
        else:
            # For pure deletions, use the position directly
            insertion_pos = min(replacement['position'], len(final_text))

        # Find closest mapping point
        closest_pos = min(position_mapping.keys(), key=lambda x: abs(x - insertion_pos))
        html_insert_pos = position_mapping[closest_pos]

        # Prepare the deletion HTML with the color of the replacing revision
        del_color = rev_colors.get(del_rev, "#cccccc")
        deletion_html = f'<span class="deletion" style="text-decoration-color: {del_color};" title="Deleted by Rev {del_rev}">{html.escape(deleted_text)}</span>'

        replacement_insertions.append((html_insert_pos, deletion_html))

    # Sort insertions by position in reverse order so we don't affect earlier positions
    replacement_insertions.sort(key=lambda x: x[0], reverse=True)

    # Apply all insertions
    for pos, html_snippet in replacement_insertions:
        final_html = final_html[:pos] + html_snippet + final_html[pos:]

    html_content += final_html + '</div>'

    # Add a legend with unique entries
    html_content += '<div class="revision-legend">'

    # Create the legend entries
    for i, rev_id in enumerate(rev_ids):
        user = users[i]
        timestamp = timestamps[i]
        rev_color = rev_colors[rev_id]

        # Special styling for baseline
        if rev_id == baseline_rev_id:
            label = f"Rev {rev_id} ({user}) - {timestamp} - BASELINE"
            style = f"border: 2px solid {rev_color}"
        else:
            label = f"Rev {rev_id} ({user}) - {timestamp}"
            style = f"background-color: rgba({int(rev_color[1:3], 16)}, {int(rev_color[3:5], 16)}, {int(rev_color[5:7], 16)}, 0.2); border: 1px solid {rev_color}"

        html_content += f'''
        <div class="item">
            <div class="color" style="{style}"></div>
            <div>{label}</div>
        </div>
        '''

    html_content += '</div>'


    if verbose:
        print(html_content)
        print("\nColor coding:")
        print("- Background color shows which revision added the text")
        print("- Strikethrough color shows which revision deleted the text")
        print("- Baseline text has no background color")
        print("- All text is black for better readability")
        print(f"\nFound {len(all_replacements)} deletions/replacements between revisions")

    return html_content


if __name__ == "__main__":
    # Example usage - compare two revisions with inline deletions
    visualize_wiki_versions_with_deletions([20, 21], word_level=True, verbose=True)

    # Example usage - compare two revisions with inline deletions
    visualize_wiki_versions_with_deletions([27, 28], word_level=False, verbose=True)

