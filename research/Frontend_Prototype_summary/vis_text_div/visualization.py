if __name__ == "__main__" and __package__ is None:
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    __package__ = "vis_text_div"

"""
Visualization functions for wiki revision histories with inline deletions.
"""
import pandas as pd
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import difflib
import re
import time

from .db_history import get_revisions_by_article_id, get_revisions_between
from .extractor import extract_revision_texts
from .html_utils import clean_html_output
from .logger_utils import setup_logger

logger = setup_logger("visualization")

def visualize_wiki_versions_with_deletions(
    article_id: int,
    start_revid: int,
    end_revid: int,
    word_level: bool = True,
    show_revision_info: bool = True,
    clean_html: bool = True,
    verbose: bool = False,
    db_config: dict = None,
    redis_config: dict = None,
    use_precalc_diffs: bool = False
) -> str:
    """
    Visualize differences between wiki article revisions with inline deletions.
    
    Args:
        article_id: Wikipedia article ID
        start_revid: Starting revision ID
        end_revid: Ending revision ID
        word_level: Use word-level diff if True, line-level otherwise
        show_revision_info: Include revision metadata in output
        clean_html: Clean and optimize the generated HTML
        verbose: Enable verbose logging
        db_config: Database connection parameters
        redis_config: Redis connection parameters
        use_precalc_diffs: Use precalculated diffs from database
        
    Returns:
        HTML string showing differences with inline deletions
    """
    start_time = time.time()
    
    if verbose:
        logger.setLevel("DEBUG")
        logger.debug(f"Visualizing article {article_id} from rev {start_revid} to {end_revid}")
    
    # Get all revision IDs between start and end (inclusive)
    rev_ids = get_revisions_between(article_id, start_revid, end_revid, db_config)
    if not rev_ids:
        error_msg = f"<div class='alert alert-danger'><strong>Error:</strong> No revisions found between {start_revid} and {end_revid} for article {article_id}.<br>The revision IDs may not exist in our database or may belong to different articles.</div>"
        logger.error(f"No revisions found between {start_revid} and {end_revid} for article {article_id}")
        return error_msg
    
    # Get revision data from DB
    history_df = get_revisions_by_article_id(article_id, db_config)
    if history_df.empty:
        error_msg = f"<div class='alert alert-danger'><strong>Error:</strong> No history data found for article {article_id}.</div>"
        logger.error(f"No history data found for article {article_id}")
        return error_msg
    
    # Filter to just the revisions we need
    history_df = history_df[history_df['revid'].isin(rev_ids)].reset_index(drop=True)
    history_df = history_df.sort_values(by='timestamp')
    
    if history_df.empty:
        error_msg = f"<div class='alert alert-danger'><strong>Error:</strong> After filtering, no valid revision data found between {start_revid} and {end_revid}.</div>"
        logger.error(f"After filtering, no valid revision data found between {start_revid} and {end_revid}")
        return error_msg

    # Check if we have at least two revisions to compare
    if len(history_df) < 2:
        error_msg = f"<div class='alert alert-warning'><strong>Warning:</strong> Need at least two revisions to compare. Only found {len(history_df)} revision(s).</div>"
        logger.warning(f"Need at least two revisions to compare. Only found {len(history_df)} revision(s)")
        return error_msg

    if use_precalc_diffs and 'diff_content' in history_df.columns:
        # Use the precalculated diffs approach
        html_result = _generate_from_precalc_diffs(
            history_df, 
            start_revid, 
            end_revid, 
            show_revision_info,
            verbose
        )
    else:
        # Fall back to calculating diffs on the fly
        revision_texts = extract_revision_texts(history_df, redis_config)
        html_result = _generate_from_text_diff(
            history_df,
            revision_texts,
            start_revid,
            end_revid,
            word_level,
            show_revision_info,
            verbose
        )
    
    # Clean the HTML if requested
    if clean_html:
        html_result = clean_html_output(html_result)
    
    if verbose:
        elapsed = time.time() - start_time
        logger.debug(f"Visualization completed in {elapsed:.2f} seconds")
    
    return html_result

def get_user_color(user_name: str) -> str:
    # Simple mapping: picks a color from a preset list based on hash of username.
    colors = ["#a2d5f2", "#ffb3ba", "#baffc9", "#ffffba", "#ffdfba", "#d3b3ff"]
    return colors[hash(user_name) % len(colors)]

def _generate_from_precalc_diffs(
    history_df: pd.DataFrame,
    start_revid: int,
    end_revid: int,
    show_revision_info: bool,
    verbose: bool
) -> str:
    """Generate visualization using precalculated diffs from the database."""
    logger.info("Using precalculated diffs for visualization")
    
    # Ensure revisions are in correct order
    if start_revid > end_revid:
        start_revid, end_revid = end_revid, start_revid
    
    # Get the base content from the first revision
    first_rev = history_df[history_df['revid'] == start_revid].iloc[0]
    base_content = first_rev['content']
    
    # Prepare the result container
    combined_content = BeautifulSoup(base_content, 'html.parser')
    
    # Get all revisions between start and end (excluding the start revision)
    relevant_revs = history_df[
        (history_df['revid'] > start_revid) & 
        (history_df['revid'] <= end_revid)
    ].sort_values(by='timestamp')
    
    # Track metadata for revision info
    rev_metadata = []
    if show_revision_info:
        rev_metadata.append({
            'revid': first_rev['revid'],
            'timestamp': first_rev['timestamp'],
            'user_name': first_rev['user_name'],
            'comment': first_rev['comment']
        })
    
    # Combine all diff_content sequentially
    for _, rev in relevant_revs.iterrows():
        if show_revision_info:
            rev_metadata.append({
                'revid': rev['revid'],
                'timestamp': rev['timestamp'],
                'user_name': rev['user_name'],
                'comment': rev['comment']
            })
            
        if not pd.isna(rev['diff_content']) and rev['diff_content']:
            diff_soup = BeautifulSoup(rev['diff_content'], 'html.parser')
            
            # Merge changes into the combined content; update styles by user
            for tag in diff_soup.find_all(['ins', 'del']):
                if tag.name == 'ins':
                    tag['style'] = f"background-color: {get_user_color(rev['user_name'])};"
                elif tag.name == 'del':
                    tag['style'] = f"text-decoration: line-through; text-decoration-color: {get_user_color(rev['user_name'])};"
                combined_content.append(tag)
    
    # Build the final HTML
    html_parts = []
    
    # Add header with revision info if requested
    if show_revision_info:
        revision_info = "<div style='margin-bottom: 15px;'>"
        for rev in rev_metadata:
            revision_info += (
                f"<p>Revision {rev['revid']} | {rev['timestamp']} | "
                f"User: {rev['user_name']} | Comment: {rev['comment']}</p>"
            )
        revision_info += "</div>"
        html_parts.append(revision_info)
    
    # Add content with diffs
    html_parts.append("<div style='padding: 20px; border: 1px solid #ccc; background-color: #f9f9f9;'>")
    html_parts.append(str(combined_content))
    html_parts.append("</div>")
    
    return "\n".join(html_parts)

def _generate_from_text_diff(
    history_df: pd.DataFrame,
    revision_texts: Dict[int, str],
    start_revid: int,
    end_revid: int,
    word_level: bool,
    show_revision_info: bool,
    verbose: bool
) -> str:
    logger.info("Calculating diffs from revision texts")
    
    if start_revid not in revision_texts or end_revid not in revision_texts:
        logger.error(f"Missing revision texts for {start_revid} or {end_revid}")
        return "<p>Error: Could not retrieve revision texts</p>"
    
    old_text = revision_texts[start_revid]
    new_text = revision_texts[end_revid]
    
    # Always retrieve revision metadata for diff creator
    old_rev = history_df[history_df['revid'] == start_revid].iloc[0]
    new_rev = history_df[history_df['revid'] == end_revid].iloc[0]
    
    html_diff = _create_diff_html(
        old_text, new_text, word_level,
        old_rev['user_name'], new_rev['user_name']
    )
    
    # Build the final HTML
    html_parts = []
    
    if show_revision_info:
        revision_info = (
            f"<div style='margin-bottom: 15px;'>"
            f"<p>From: Revision {old_rev['revid']} | {old_rev['timestamp']} | "
            f"User: {old_rev['user_name']} | Comment: {old_rev['comment']}</p>"
            f"<p>To: Revision {new_rev['revid']} | {new_rev['timestamp']} | "
            f"User: {new_rev['user_name']} | Comment: {new_rev['comment']}</p>"
            f"</div>"
        )
        html_parts.append(revision_info)
    
    html_parts.append("<div style='padding: 20px; border: 1px solid #ccc; background-color: #f9f9f9;'>")
    html_parts.append(html_diff)
    html_parts.append("</div>")
    
    return "\n".join(html_parts)

def _create_diff_html(old_text: str, new_text: str, word_level: bool, old_user: str, new_user: str) -> str:
    """Create HTML diff between two texts at word or line level, coloring changes by editor."""
    if word_level:
        # Split text into words for word-level diff
        old_words = re.findall(r'\S+|\s+', old_text)
        new_words = re.findall(r'\S+|\s+', new_text)
        
        # Generate diff
        diff = difflib.ndiff(old_words, new_words)
        
        # Process diff into HTML
        html_parts = []
        for line in diff:
            if line.startswith('- '):
                html_parts.append(f"<span style='text-decoration: line-through; text-decoration-color: {get_user_color(old_user)};'>{line[2:]}</span>")
            elif line.startswith('+ '):
                html_parts.append(f"<span style='background-color: {get_user_color(new_user)};'>{line[2:]}</span>")
            elif line.startswith('  '):
                html_parts.append(line[2:])
        
        return "".join(html_parts)
    else:
        # Line-level diff
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()
        
        # Generate diff
        diff = difflib.ndiff(old_lines, new_lines)
        
        # Process diff into HTML
        html_parts = []
        for line in diff:
            if line.startswith('- '):
                html_parts.append(f"<p style='text-decoration: line-through; text-decoration-color: {get_user_color(old_user)};'>{line[2:]}</p>")
            elif line.startswith('+ '):
                html_parts.append(f"<p style='background-color: {get_user_color(new_user)};'>{line[2:]}</p>")
            elif line.startswith('  '):
                html_parts.append(f"<p>{line[2:]}</p>")
        
        return "\n".join(html_parts)

if __name__ == "__main__":
    # Minimal test harness for local execution.
    # Use dummy configurations; adjust as needed.
    import os

    dummy_db_config = {
        "dbname": os.getenv("DB_NAME", "your_database"),
        "user": os.getenv("DB_USER", "your_username"),
        "password": os.getenv("DB_PASSWORD", "your_password"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432")
    }
    dummy_redis_config = {}
    article_id = 1118968
    start_revid = 11775085
    end_revid = 126704837
    # Call the main visualization function and print output.
    html_output = visualize_wiki_versions_with_deletions(
        article_id=article_id,
        start_revid=start_revid,
        end_revid=end_revid,
        word_level=True,
        show_revision_info=False,
        clean_html=False,
        verbose=True,
        db_config=dummy_db_config,
        redis_config=dummy_redis_config,
        use_precalc_diffs=False
    )
    print(html_output)

