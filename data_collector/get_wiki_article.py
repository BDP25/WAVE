import wikipedia
from pprint import pprint

def validate_wikipedia_titles(cluster_topics: dict, language: str = 'de') -> dict:
    """
    Returns a list of Wikipedia articles for each cluster.
    If no exact article is found, the first suggestion is used.
    If no suggestion is found, the next term in the list is used.

    Args:
        cluster_topics (dict): Cluster ID as the key, list of terms as values.
        language (str): Wikipedia language (default: 'de').

    Returns:
        dict: Structured results with the titles of the validated articles.
    """
    wikipedia.set_lang(language)
    results = {}

    for cluster_id, keywords in cluster_topics.items():
        validated_articles = _process_keywords(keywords)
        if validated_articles:
            results[cluster_id] = validated_articles

    return results


def _process_keywords(keywords: list) -> list:
    """
    Processes a list of keywords and returns a list of validated Wikipedia articles.
    If no exact article is found, the first suggestion is used.

    Args:
        keywords (list): List of terms.

    Returns:
        list: A list of validated article titles.
    """
    validated_articles = []
    for term in keywords:
        article = _search_wikipedia_article(term)

        if article:
            validated_articles.append(article.title)
        else:
            suggestion = _get_first_suggestion(term)
            if suggestion:
                validated_articles.append(suggestion.title)
    return validated_articles


def _search_wikipedia_article(term: str):
    """
    Tries to find a matching Wikipedia article for the given term.

    Args:
        term (str): Term to search for.

    Returns:
        wikipedia.page: Wikipedia page of the article or None.
    """
    try:
        return wikipedia.page(term)
    except (wikipedia.DisambiguationError, wikipedia.PageError):
        return None


def _get_first_suggestion(term: str):
    """
    Returns the first Wikipedia search suggestion.

    Args:
        term (str): Term to search for.

    Returns:
        wikipedia.page: The first suggestion as a Wikipedia page or None.
    """
    suggestions = wikipedia.search(term)
    if suggestions:
        try:
            return wikipedia.page(suggestions[0])
        except:
            return None
    return None


if __name__ == "__main__":

    topics = {
        0: ['Donald Trump'],
        1: ['Erdbeben Asien', 'Erdbeben Myanmar'],
        2: ['Kadetten Schaffhausen', 'Handball'],
        3: ['Winterthur', 'Pensionskasse', 'Finanzausgleich', 'Zentrumslastenausgleich', 'Stadtpolizei Zürich']
    }

    cluster_topics = validate_wikipedia_titles(topics)

    pprint(cluster_topics, width=160)
