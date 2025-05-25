import argparse
import sys
from safe_wiki_to_db import update_article_history, update_article_history_in_batches
from db_utils import db_params

def main():
    """
    Main entry point for the Wikipedia Article History Collector.

    Processes command-line arguments to collect and store history for either
    a single Wikipedia article or multiple articles specified in a text file.
    Each article is processed and saved to the database.

    Command-line arguments:
        --title, -t: Wikipedia article title (required unless --articles is provided)
        --lang, -l: Language code (default: en)
        --articles, -a: Path to text file with list of articles

    Returns:
        None. Exits with status code 1 on error.
    """
    parser = argparse.ArgumentParser(description='Wikipedia Article History Collector')
    parser.add_argument('--title', '-t', required=True, help='Wikipedia article title')
    parser.add_argument('--lang', '-l', default='en', help='Language code (default: en)')
    parser.add_argument('--articles', '-a', help='Path to text file with list of articles (one per line)')
    
    args = parser.parse_args()
    
    articles_to_process = []
    
    # Process single article
    if args.title:
        articles_to_process.append((args.title, args.lang))
    
    # Process articles from file if provided
    if args.articles:
        try:
            with open(args.articles, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split(',')
                        if len(parts) == 1:
                            articles_to_process.append((parts[0], args.lang))
                        elif len(parts) >= 2:
                            articles_to_process.append((parts[0], parts[1]))
        except Exception as e:
            print(f"Error reading articles file: {e}")
            sys.exit(1)
    
    if not articles_to_process:
        print("No articles to process. Use --title or --articles arguments.")
        sys.exit(1)
    
    # Process all articles
    success_count = 0
    for title, lang in articles_to_process:
        print(f"Processing article: {title} ({lang})")
        if update_article_history_in_batches(title, lang, db_params, batch_size=50):
            success_count += 1
            print(f"Successfully processed article: {title}")
        else:
            print(f"Failed to process article: {title}")
    
    print(f"Completed processing {success_count}/{len(articles_to_process)} articles")

if __name__ == "__main__":
    main()
