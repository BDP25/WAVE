# visualisation.py

import re
import psycopg2
from psycopg2.extras import RealDictCursor
from bs4 import BeautifulSoup, NavigableString, Comment
import colorsys
import logging
import redis
import json
import hashlib
import time

logger = logging.getLogger(__name__)

# Must double‐brace any { } in CSS so Python .format() only sees {body}
HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <meta charset='utf-8'>
  <title>Wikipedia Article Changes</title>
  <style>
    body {{ font-family: Arial, sans-serif; line-height: 1.6; background-color: #fff; }}
    .revision-info {{ font-size: 12px; color: #666; margin-bottom: 4px; }}
  </style>
</head>
<body>
{body}
</body>
</html>"""

# Patterns for cleaning unwrapped or stray NewPP comments
_CLEAN_PATTERNS = [
    re.compile(r'NewPP', re.IGNORECASE),
    re.compile(r'Cache expiry', re.IGNORECASE),
    re.compile(r'CPU time usage', re.IGNORECASE),
    re.compile(r'Real time usage', re.IGNORECASE),
    re.compile(r'Preprocessor visited node count', re.IGNORECASE),
    re.compile(r'Post-expand', re.IGNORECASE),
    re.compile(r'Unstrip', re.IGNORECASE),
    re.compile(r'RevisionOutputCache', re.IGNORECASE),
    re.compile(r'Transclusion expansion time report', re.IGNORECASE),
    re.compile(r'Saved in parser cache', re.IGNORECASE)
]

def generate_color_for_user(user_name: str) -> str:
    """Map a username to a distinct hex color via HSL hashing."""
    hue = hash(user_name) % 360
    r, g, b = colorsys.hls_to_rgb(hue/360, 0.55, 0.65)
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

def inline_merge_spans(base_html: str, diff_html: str):
    """
    Take base_html (the final revision HTML) and a diff fragment,
    find each <span user-add> or <span user-del> in the diff, and
    splice it into its first matching location in base_html.
    """
    base_soup = BeautifulSoup(base_html, "html.parser")
    diff_soup = BeautifulSoup(diff_html, "html.parser")

    # Only look at the special span tags
    for span in diff_soup.find_all("span", attrs={"user-add": True}) + \
                diff_soup.find_all("span", attrs={"user-del": True}):

        token = span.get_text()
        user_attr = "user-add" if span.has_attr("user-add") else "user-del"

        # Walk text nodes in base until we find the token
        for text_node in base_soup.find_all(string=True):
            if token in text_node:
                parent = text_node.parent
                before, after = text_node.split(token, 1)
                # Build new sequence: before text, span, after text
                new_nodes = []
                if before:
                    new_nodes.append(NavigableString(before))
                # Apply the span itself
                new_span = BeautifulSoup(str(span), "html.parser").span
                new_nodes.append(new_span)
                if after:
                    new_nodes.append(NavigableString(after))
                # Replace original text_node with our sequence
                text_node.replace_with(new_nodes[0])
                for node in new_nodes[1:]:
                    new_nodes[0].insert_after(node)
                    new_nodes[0] = node
                break

    return str(base_soup)

def get_cache_key(article_id, start_revid, end_revid, word_level, show_revision_info):
    """Generate a unique cache key for the visualization parameters."""
    params = f"{article_id}:{start_revid}:{end_revid}:{word_level}:{show_revision_info}"
    return f"wiki_vis:{hashlib.md5(params.encode()).hexdigest()}"

def visualize_wiki_versions_with_deletions(article_id, start_revid, end_revid,
                                           word_level, verbose, db_config,
                                           redis_config, show_revision_info):
    """
    Fetch all revisions between start_revid and end_revid,
    then inline-merge their spans into the final HTML.
    Uses Redis cache if available to avoid regenerating the same visualization.
    """
    # Generate a cache key for these parameters
    cache_key = get_cache_key(article_id, start_revid, end_revid, word_level, show_revision_info)

    # Try to get from cache first
    try:
        if redis_config:
            r = redis.Redis(
                host=redis_config.get('host', 'localhost'),
                port=redis_config.get('port', 6379),
                db=redis_config.get('db', 0),
                password=redis_config.get('password'),
                decode_responses=True  # Auto-decode bytes to strings
            )

            # Check if visualization exists in cache
            cached_html = r.get(cache_key)
            if cached_html:
                if verbose:
                    logger.info(f"Cache hit for {cache_key}")
                return cached_html

            if verbose:
                logger.info(f"Cache miss for {cache_key}")
    except Exception as e:
        # Log the error but continue without caching
        logger.warning(f"Redis cache error (will continue without caching): {e}")

    # If not in cache, generate the visualization
    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # 1) Normalize to ints
        start_revid = int(start_revid)
        end_revid   = int(end_revid)

        # 2) Look up their actual timestamps
        cur.execute(
            "SELECT timestamp FROM history WHERE article_id=%s AND revid=%s",
            (article_id, start_revid)
        )
        row = cur.fetchone()
        if not row:
            return HTML_TEMPLATE.format(body="<p>No such start revision</p>")
        ts_start = row["timestamp"]

        cur.execute(
            "SELECT timestamp FROM history WHERE article_id=%s AND revid=%s",
            (article_id, end_revid)
        )
        row = cur.fetchone()
        if not row:
            return HTML_TEMPLATE.format(body="<p>No such end revision</p>")
        ts_end = row["timestamp"]

        # 3) Swap so start_ts ≤ end_ts
        ts1, ts2 = (ts_start, ts_end) if ts_start <= ts_end else (ts_end, ts_start)

        # 4) Fetch every revision in that time window
        cur.execute("""
            SELECT revid, user_name, timestamp, comment, content, diff_content
              FROM history
             WHERE article_id = %s
               AND timestamp BETWEEN %s AND %s
             ORDER BY timestamp ASC
        """, (article_id, ts1, ts2))
        revisions = cur.fetchall()
        cur.close()
        conn.close()

        if not revisions:
            return HTML_TEMPLATE.format(body="<p>No revisions found</p>")

        # Start from the very last revision's full HTML
        final = revisions[-1]["content"]

        # Apply each diff inline, oldest first
        for rev in revisions:
            diff_html = rev.get("diff_content") or ""
            final = inline_merge_spans(final, diff_html)

        # Parse the merged HTML and strip out *all* HTML comments
        soup = BeautifulSoup(final, "html.parser")
        for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
            comment.extract()
        # Remove stray NewPP-like text nodes
        for text_node in soup.find_all(string=True):
            if any(pat.match(text_node) for pat in _CLEAN_PATTERNS):
                text_node.extract()

        # Re-color all spans by their user
        for span in soup.find_all("span"):
            user = span.get("user-add") or span.get("user-del")
            color = generate_color_for_user(user)
            if span.has_attr("user-add"):
                span["style"] = f"background-color: {color};"
            else:
                existing = span.get("style", "")
                span["style"] = f"{existing} text-decoration: line-through; text-decoration-color: {color};"

        # Optional header with revision info
        body = []
        if show_revision_info:
            for rev in revisions:
                body.append(
                    f"<div class='revision-info'>"
                    f"{rev['timestamp']} - rev {rev['revid']} by {rev['user_name']}: {rev['comment']}"
                    f"</div>"
                )
        body.append(str(soup))
        html_result = HTML_TEMPLATE.format(body="\n".join(body))

        # Save to cache for future requests
        try:
            if redis_config:
                # Cache for 1 hour (3600 seconds)
                cache_ttl = 3600
                r.setex(cache_key, cache_ttl, html_result)
                if verbose:
                    logger.info(f"Cached visualization for {cache_key} (expires in {cache_ttl}s)")
        except Exception as e:
            logger.warning(f"Failed to cache result: {e}")

        return html_result

    except Exception as e:
        logger.error("Error generating visualization", exc_info=True)
        return HTML_TEMPLATE.format(body=f"<p>Error: {e}</p>")

