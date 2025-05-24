"""
Command-line entry point for wiki diff visualization.
"""
import argparse
import sys
import os
import logging

# Add parent directory to path to allow importing db_utils
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ../db_utils import db_params, redis_params
from .logger_utils import setup_logger
from .visualization import visualize_wiki_versions_with_deletions

logger = setup_logger(level=logging.ERROR)

def main():
    parser = argparse.ArgumentParser(description="Visualize wiki diffs between revisions.")
    parser.add_argument("--article-id", type=int, required=True)
    parser.add_argument("--start-revid", type=int, required=True)
    parser.add_argument("--end-revid", type=int, required=True)
    parser.add_argument("--word-level", action='store_true')
    parser.add_argument("--no-info", action='store_false', dest='show_revision_info')
    parser.add_argument("--no-clean", action='store_false', dest='clean_html')
    parser.add_argument("--verbose", action='store_true')
    parser.add_argument("--precalc-diffs", action='store_true', help="Use precalculated diffs visualization approach")
    args = parser.parse_args()

    html = visualize_wiki_versions_with_deletions(
        article_id=args.article_id,
        start_revid=args.start_revid,
        end_revid=args.end_revid,
        word_level=args.word_level,
        show_revision_info=args.show_revision_info,
        clean_html=args.clean_html,
        verbose=args.verbose,
        db_config=db_params,
        redis_config=redis_params,
        use_precalc_diffs=args.precalc_diffs  # new parameter passed here
    )
    print(html)

if __name__ == "__main__":
    from db_utils import create_db_connection, db_params, redis_params, test_db_connection

    # Set logging level to ERROR for detailed output
    logger.setLevel(logging.ERROR)

    # Use Redis and Postgres configuration from environment variables
    db_config = db_params
    redis_config = redis_params

    # Example usage - compare two revisions with inline deletions
    article_id = 13436958  # This article ID is valid

    # Specify revision IDs
    start_revid = 254642216
    end_revid = 255135586

    html = visualize_wiki_versions_with_deletions(
        article_id=article_id,
        start_revid=start_revid,
        end_revid=end_revid,
        word_level=True,
        verbose=True,
        db_config=db_config,
        redis_config=redis_config,
        show_revision_info=False,
        clean_html=True,  # Enable HTML cleanup
        use_precalc_diffs=False  # Example usage without precalculated diffs
    )

    print(f"\nHTML:\n-------------------------------------------------------\n{html}\n-------------------------------------------------------")

