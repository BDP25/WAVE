import os
import datetime
import json
import psycopg2
from psycopg2.extras import RealDictCursor
import csv
import io

def get_clusters_per_date(date: str):
    """
    Retrieve all news clusters for a specific date.

    Args:
        date (str): The date in 'YYYY-MM-DD' format

    Returns:
        dict: A dictionary containing lists of clusters, each with associated
              Wikipedia articles and news articles. Format:
              {
                "clusters": [
                  {
                    "cluster_id": id,
                    "wikipedia_articles": [article_names],
                    "news_articles": [article_objects]
                  }
                ]
              }

              If an error occurs, returns {"error": error_message}
    """
    date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
    
    db_params = {
        "dbname": os.getenv("DB_NAME", "your_database"),
        "user": os.getenv("DB_USER", "your_username"),
        "password": os.getenv("DB_PASSWORD", "your_password"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432")
    }
    
    result = {"clusters": []}
    
    try:
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get all clusters for the given date
        cursor.execute(
            "SELECT cluster_id, wikipedia_article_names FROM cluster WHERE date = %s",
            (date,)
        )
        clusters = cursor.fetchall()
        
        # For each cluster, get the associated articles
        for cluster in clusters:
            cluster_id = cluster['cluster_id']
            wiki_articles = cluster['wikipedia_article_names']
            
            # Clean and parse the wikipedia_articles field
            try:
                if wiki_articles and isinstance(wiki_articles, str):
                    # Remove curly braces at the beginning and end if they exist
                    if (wiki_articles.startswith('{') and wiki_articles.endswith('}')):
                        wiki_articles = wiki_articles[1:-1]
                    
                    # Use CSV reader to properly handle quoted values
                    csv_reader = csv.reader([wiki_articles], skipinitialspace=True)
                    wiki_articles = next(csv_reader)
                    
                    # Clean up each article name (remove extra quotes if present)
                    wiki_articles = [article.strip('"\'').strip() for article in wiki_articles if article.strip()]
            except Exception as e:
                print(f"Error cleaning wiki articles for cluster {cluster_id}: {e}")
                # If parsing fails, provide the raw value or an empty list as fallback
                wiki_articles = [wiki_articles] if wiki_articles else []

            # Get all articles for this cluster
            cursor.execute(
                """
                SELECT article_id, pubtime, medium_name, head, article_link 
                FROM artikel 
                WHERE cluster_id = %s
                ORDER BY pubtime DESC
                """,
                (cluster_id,)
            )
            articles = cursor.fetchall()
            
            # Format articles
            formatted_articles = []
            for article in articles:
                formatted_articles.append({
                    "head": article['head'],
                    "pubtime": article['pubtime'].isoformat() if isinstance(article['pubtime'], datetime.datetime) else article['pubtime'],
                    "medium_name": article['medium_name'],
                    "article_link": article['article_link']
                })
            
            # Add cluster to result
            result["clusters"].append({
                "cluster_id": cluster_id,
                "wikipedia_articles": wiki_articles,
                "news_articles": formatted_articles
            })
        
        cursor.close()
        conn.close()
        
        return result
        
    except Exception as e:
        print(f"Database error: {e}")
        return {"error": str(e)}

def get_article_info(article_id):
    """
    Retrieve detailed information about a specific article.

    Args:
        article_id: The unique identifier for the article

    Returns:
        dict: Article information including publication time, title, content, etc.
              If the article is not found, returns {"error": "Article not found"}
              If an error occurs, returns {"error": error_message}
    """
    db_params = {
        "dbname": os.getenv("DB_NAME", "your_database"),
        "user": os.getenv("DB_USER", "your_username"),
        "password": os.getenv("DB_PASSWORD", "your_password"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432")
    }
    
    try:
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute(
            "SELECT * FROM article WHERE article_id = %s",
            (article_id,)
        )
        article = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if article:
            article['pubtime'] = article['pubtime'].isoformat() if isinstance(article['pubtime'], datetime.datetime) else article['pubtime']
            return article
        else:
            return {"error": "Article not found"}
        
    except Exception as e:
        print(f"Database error: {e}")
        return {"error": str(e)}


def get_min_max_date():
    """
    Retrieve the minimum (oldest) and maximum (newest) dates from the cluster table.

    Returns:
        tuple: A tuple containing (min_date, max_date) as strings in ISO format,
               or empty strings if no dates are found or an error occurs
    """
    db_params = {
        "dbname": os.getenv("DB_NAME", "your_database"),
        "user": os.getenv("DB_USER", "your_username"),
        "password": os.getenv("DB_PASSWORD", "your_password"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432")
    }

    try:
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT MIN(date) AS oldest_date, MAX(date) AS newest_date FROM cluster"
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result and result['oldest_date'] and result['newest_date']:
            return result['oldest_date'].isoformat(), result['newest_date'].isoformat()
        else:
            # Return empty strings instead of a dictionary for consistent tuple unpacking
            return "", ""
    except Exception as e:
        print(f"Database error: {e}")
        # Return empty strings on exception
        return "", ""







if __name__ == "__main__":
    import dotenv
    dotenv.load_dotenv()

    # Call the function to get the oldest date
    min_date, max_date = get_min_max_date()

    # Print with ensure_ascii=False to properly display Unicode characters
    print(json.dumps(max_date, indent=4, ensure_ascii=False))
    print(json.dumps(min_date, indent=4, ensure_ascii=False))

    date = "2025-04-10"
    clusters_data = get_clusters_per_date(date)

    # Print with ensure_ascii=False to properly display Unicode characters like umlauts
    print(json.dumps(clusters_data, indent=4, ensure_ascii=False))




