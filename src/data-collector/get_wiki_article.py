import wikipedia
from pprint import pprint


def validate_wikipedia_titles(cluster_topics: dict, language: str = 'de') -> dict:
    """
    Returns validated Wikipedia article titles for each cluster.

    Args:
        cluster_topics (dict): Dictionary mapping cluster IDs to lists of potential
                               Wikipedia article titles
        language (str): Wikipedia language edition to use (default: 'de' for German)

    Returns:
        dict: Dictionary mapping cluster IDs to lists of validated Wikipedia article titles
              Only clusters with at least one valid article are included
    """
    wikipedia.set_lang(language)
    results = {}

    for cluster_id, keywords in cluster_topics.items():
        if validated_articles := process_keywords(keywords):
            results[cluster_id] = validated_articles

    return results


def process_keywords(keywords: list) -> list:
    """
    Returns validated Wikipedia article titles from a list of keywords.

    Args:
        keywords (list): List of potential Wikipedia article titles or search terms

    Returns:
        list: List of validated Wikipedia article titles without duplicates
    """
    validated_articles = set()  # Use set instead of list to avoid duplicates

    for term in keywords:
        if article := get_wikipedia_article(term):
            validated_articles.add(article.title)  # Use add() for sets

    return list(validated_articles)  # Convert back to list for compatibility


def get_wikipedia_article(term: str):
    """
    Finds Wikipedia article for a term, handling disambiguation.

    First attempts an exact match, then handles disambiguation pages by taking
    the first option, and finally falls back to search suggestions if needed.

    Args:
        term (str): Search term or potential Wikipedia article title

    Returns:
        wikipedia.WikipediaPage or None: Wikipedia page object if found, None otherwise
    """
    # First try exact match
    try:
        return wikipedia.page(term, auto_suggest=False)
    except wikipedia.DisambiguationError as e:
        try:
            return wikipedia.page(e.options[0], auto_suggest=False)
        except:
            pass
    except wikipedia.PageError:
        pass

    # Try suggestions if direct lookup fails
    for suggestion in wikipedia.search(term):
        try:
            return wikipedia.page(suggestion, auto_suggest=False)
        except:
            continue

    return None


if __name__ == "__main__":
    topics = {
        0: ['Mobile phone use in schools'],
        1: ['Erdbeben Asien', 'Erdbeben Myanmar'],
        2: ['Kadetten Schaffhausen', 'Handball'],
        3: ['Winterthur', 'Pensionskasse', 'Finanzausgleich', 'Stadtpolizei Zürich']
    }

    pprint(validate_wikipedia_titles(topics), width=160)
