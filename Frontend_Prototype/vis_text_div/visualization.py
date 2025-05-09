"""
Core function to visualize wiki diffs with inline deletions.
"""
import difflib
import hashlib
import colorsys
import html as _html
import pandas as pd
from typing import Dict, List, Optional, Union
from IPython.display import HTML

from logger_utils import setup_logger
from extractor import extract_revision_texts
from cache_utils import get_revision_text
from redis_utils import get_redis_connection, cache_set, cache_get
from html_utils import clean_html_output
from db_history import get_revisions_by_article_id, get_revisions_between

logger = setup_logger("visualization")

def get_cache_key_for_visualization(article_id: int, start_revid: int, end_revid: int, word_level: bool,
                                     show_revision_info: bool, clean_html: bool) -> str:
    """Generate a cache key for visualization results based on input parameters"""
    parts = [f"article:{article_id}", f"start:{start_revid}", f"end:{end_revid}",
             f"word:{word_level}", f"info:{show_revision_info}", f"clean:{clean_html}"]
    return "visualization:" + ":".join(parts)


def get_color_for_revision(rev_id: int) -> str:
    """Generate a consistent color for a given revision ID"""
    hash_value = int(hashlib.md5(str(rev_id).encode()).hexdigest(), 16) % (2**24)
    # Convert to HSL and ensure good contrast with light background
    h = hash_value / (2**24)
    s = 0.7  # Fairly saturated colors
    l = 0.4  # Darker colors for better visibility
    # Convert HSL to RGB
    r, g, b = [int(x * 255) for x in colorsys.hls_to_rgb(h, l, s)]
    return f"rgb({r}, {g}, {b})"


def format_user_info(row: pd.Series) -> str:
    """Format user info with timestamp for display"""
    rev_id = row['revid']
    timestamp = row['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(row['timestamp'], 'strftime') else row['timestamp']
    user = row['userid']
    comment = row['comment'] if pd.notna(row['comment']) else ""

    return f"<span class='rev-info' style='font-size:0.8em; color:gray;'>[Rev {rev_id} | {timestamp} | User: {user}]</span> {comment}<br>"


def visualize_wiki_versions_with_deletions(
        article_id: Optional[int] = None,
        revision_indices: Optional[List[int]] = None,
        start_revid: Optional[int] = None,
        end_revid: Optional[int] = None,
        word_level: bool = True,
        show_revision_info: bool = True,
        clean_html: bool = True,
        db_config: Optional[Dict] = None,
        redis_config: Optional[Dict] = None,
        use_mock_data: bool = False,
        verbose: bool = False
) -> str:
    """
    Visualize Wikipedia versioning with each revision's contributions colored by revision ID,
    including inline strikethrough for deleted text.
    """
    # Set default Redis config
    if redis_config is None:
        redis_config = {'host': 'localhost', 'port': 6379, 'db': 0, 'password': None}
    
    # Check for cached result in Redis
    if article_id is not None and start_revid is not None and end_revid is not None:
        cache_key = get_cache_key_for_visualization(article_id, start_revid, end_revid, word_level, show_revision_info, clean_html)
        
        r = get_redis_connection(**redis_config)
        if r:
            cached_result = cache_get(r, cache_key)
            if cached_result:
                logger.info(f"Using cached visualization for article {article_id} from {start_revid} to {end_revid}")
                return cached_result

    # Load article history
    if article_id is not None:
        if use_mock_data:
            # Create mock data for testing
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
            history_table = pd.DataFrame(mock_data)

            # If specific revids were requested, filter the mock data
            if start_revid is not None and end_revid is not None:
                revision_indices = list(range(len(history_table)))
        else:
            # Get revision history from database
            history_table = get_revisions_by_article_id(article_id, db_config)

            if history_table.empty:
                logger.error(f"Could not retrieve revision history for article ID {article_id}")
                return None

            # Get revisions between start_revid and end_revid
            if start_revid is not None and end_revid is not None:
                revision_ids = get_revisions_between(article_id, start_revid, end_revid, db_config)
                if not revision_ids:
                    logger.error("No revisions found between the specified revision IDs")
                    return None
                
                # Map revision IDs to indices in the history_table
                rev_to_idx = {row['revid']: idx for idx, row in history_table.iterrows()}
                revision_indices = [rev_to_idx[rev_id] for rev_id in revision_ids if rev_id in rev_to_idx]
            else:
                logger.info("No specific revision IDs provided. Using first and last available revisions.")
                revision_indices = [0, len(history_table) - 1]

        # Extract revision texts
        revision_texts_dict = extract_revision_texts(history_table, redis_config)
    
    # Ensure we have valid revision indices
    if revision_indices is None or len(revision_indices) < 2:
        logger.error("Need at least two revisions to compare")
        return None

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
            
            # Cache in Redis if possible
            r = get_redis_connection(**redis_config)
            if r:
                cache_set(r, f"revision:{rev_id}:text", text, expire=86400)

        texts.append(text)
        user_infos.append(format_user_info(history_table.iloc[idx]))

    if verbose:
        logger.info(f"Comparing {len(texts)} revisions")
        for i, rev_id in enumerate(rev_ids):
            logger.info(f"Revision {i+1}: {rev_id}, length: {len(texts[i])}")

    # Prepare the visualized output
    html_output = "<div style='font-family: monospace; white-space: pre-wrap;'>\n"
    # Add CSS to fix spacing issues
    html_output += "<style>\n"
    html_output += "  span { display: inline; }\n"
    html_output += "  .word-span { margin-right: 0; }\n"
    html_output += "  .deleted-word { margin-right: 0; }\n"
    html_output += "</style>\n"
    html_output += "<h3>Wikipedia Article Diff Visualization</h3>\n"

    # Display revision info at the top (only if show_revision_info is True)
    if show_revision_info:
        for i, info in enumerate(user_infos):
            html_output += f"<div style='margin-bottom: 5px;'><b>Revision {i+1}:</b> {info}</div>\n"

    html_output += "<hr>\n<div style='padding: 20px; border: 1px solid #ccc; background-color: #f9f9f9;'>\n"

    # Process all revisions sequentially to show cumulative changes
    # Start with the first revision text as our base
    current_text = texts[0]
    result = []

    # Add the first revision text (unmarked as it's the base)
    if word_level:
        tokens = current_text.split()
        for i, token in enumerate(tokens):
            # Don't add space through CSS margin
            is_last = i == len(tokens) - 1
            result.append(f"<span class='word-span'>{_html.escape(token)}</span>")
            # Add a real space between words (not before punctuation)
            if not is_last:
                if tokens[i+1] not in [',', '.', ':', ';', '?', '!', ')', ']', '}'] and token not in ['(', '[', '{', '-']:
                    result.append(" ")
    else:
        lines = current_text.splitlines()
        for line in lines:
            result.append(f"<span>{_html.escape(line)}</span><br>")

    # Process each subsequent revision and apply changes
    for i in range(1, len(texts)):
        prev_text = current_text
        current_text = texts[i]
        current_rev_id = rev_ids[i]

        # Get color for this revision
        color = get_color_for_revision(current_rev_id)

        # Calculate diff between previous text and current text
        if word_level:
            prev_tokens = prev_text.split()
            curr_tokens = current_text.split()
            diff = difflib.SequenceMatcher(None, prev_tokens, curr_tokens)

            # Create a new result with changes applied
            new_result = []
            current_pos = 0

            # Process each diff operation
            for op, i1, i2, j1, j2 in diff.get_opcodes():
                if op == 'equal':
                    # Copy unchanged tokens
                    for k in range(i1, i2):
                        token_idx = current_pos
                        current_pos += 1
                        if token_idx < len(result):
                            new_result.append(result[token_idx])
                elif op == 'delete':
                    # Mark deleted tokens with strikethrough and add class with revision ID
                    for k in range(i1, i2):
                        token = prev_tokens[k]
                        # Use classes to control spacing
                        new_result.append(f"<span class='rev-{current_rev_id} deleted-word' style='text-decoration:line-through; color:{color};'>{_html.escape(token)}</span>")
                        current_pos += 1
                        # Add appropriate space after deleted text unless it's the last token or before punctuation
                        if k < i2-1 and prev_tokens[k+1] not in [',', '.', ':', ';', '?', '!', ')', ']', '}'] and token not in ['(', '[', '{', '-']:
                            new_result.append(" ")
                elif op == 'insert':
                    # Add new tokens with highlight and add class with revision ID
                    for k in range(j1, j2):
                        token = curr_tokens[k]
                        new_result.append(f"<span class='rev-{current_rev_id} word-span' style='background-color:rgba({color[4:-1]},0.2); color:{color};'>{_html.escape(token)}</span>")
                        # Add space only if needed - not before punctuation and not at the end
                        if k < j2-1 and curr_tokens[k+1] not in [',', '.', ':', ';', '?', '!', ')', ']', '}'] and token not in ['(', '[', '{', '-']:
                            new_result.append(" ")
                elif op == 'replace':
                    # Mark deleted tokens with strikethrough
                    for k in range(i1, i2):
                        token = prev_tokens[k]
                        new_result.append(f"<span class='rev-{current_rev_id} deleted-word' style='text-decoration:line-through; color:{color};'>{_html.escape(token)}</span>")
                        current_pos += 1
                        # Only add space between deleted words, not after the last one
                        if k < i2-1 and prev_tokens[k+1] not in [',', '.', ':', ';', '?', '!', ')', ']', '}'] and token not in ['(', '[', '{', '-']:
                            new_result.append(" ")

                    # Add new tokens with highlight
                    for k in range(j1, j2):
                        token = curr_tokens[k]
                        new_result.append(f"<span class='rev-{current_rev_id} word-span' style='background-color:rgba({color[4:-1]},0.2); color:{color};'>{_html.escape(token)}</span>")
                        # Add space only when needed
                        if k < j2-1 and curr_tokens[k+1] not in [',', '.', ':', ';', '?', '!', ')', ']', '}'] and token not in ['(', '[', '{', '-']:
                            new_result.append(" ")

            result = new_result
        else:
            # Line-level diff
            prev_lines = prev_text.splitlines()
            curr_lines = current_text.splitlines()
            diff = difflib.SequenceMatcher(None, prev_lines, curr_lines)

            # Create a new result with changes applied
            new_result = []
            current_pos = 0

            # Process each diff operation
            for op, i1, i2, j1, j2 in diff.get_opcodes():
                if op == 'equal':
                    # Copy unchanged lines
                    for k in range(i1, i2):
                        line_idx = current_pos
                        current_pos += 1
                        if line_idx < len(result):
                            new_result.append(result[line_idx])
                elif op == 'delete':
                    # Mark deleted lines with strikethrough and add class with revision ID
                    for k in range(i1, i2):
                        line = prev_lines[k]
                        new_result.append(f"<span class='rev-{current_rev_id}' style='text-decoration:line-through; color:{color};'>{_html.escape(line)}</span><br>")
                        current_pos += 1
                elif op == 'insert':
                    # Add new lines with highlight and add class with revision ID
                    for k in range(j1, j2):
                        line = curr_lines[k]
                        new_result.append(f"<span class='rev-{current_rev_id}' style='background-color:rgba({color[4:-1]},0.2); color:{color};'>{_html.escape(line)}</span><br>")
                elif op == 'replace':
                    # Mark deleted lines with strikethrough and add class with revision ID
                    for k in range(i1, i2):
                        line = prev_lines[k]
                        new_result.append(f"<span class='rev-{current_rev_id}' style='text-decoration:line-through; color:{color};'>{_html.escape(line)}</span><br>")
                        current_pos += 1

                    # Add new lines with highlight and add class with revision ID
                    for k in range(j1, j2):
                        line = curr_lines[k]
                        new_result.append(f"<span class='rev-{current_rev_id}' style='background-color:rgba({color[4:-1]},0.2); color:{color};'>{_html.escape(line)}</span><br>")

            result = new_result

    # Add the result to the HTML output
    html_output += "".join(result)
    html_output += "\n</div>\n</div>"

    # Clean up the HTML if requested
    if clean_html:
        html_output = clean_html_output(html_output)

    # Cache the result in Redis before returning
    if article_id is not None and start_revid is not None and end_revid is not None:
        cache_key = get_cache_key_for_visualization(article_id, start_revid, end_revid, word_level, show_revision_info, clean_html)
        r = get_redis_connection(**redis_config)
        if r and html_output:
            # Store the result with a TTL of 1 day (86400 seconds)
            cache_set(r, cache_key, html_output, expire=86400)
            logger.info(f"Cached visualization result for article {article_id} from {start_revid} to {end_revid}")
            
            # Also add to a set of cached visualizations for this article
            article_cache_key = f"article:{article_id}:visualizations"
            r.sadd(article_cache_key, cache_key)
            r.expire(article_cache_key, 86400)

    return html_output
