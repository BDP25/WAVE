import concurrent.futures
import json
import os
import random
import re
import groq
import nltk
from dotenv import load_dotenv
import logging

# --- NEW: Tor/proxy imports ---
import requests
import socks
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Constants
MAX_WORKERS = 3
CHUNK_SIZE = 1000
MAX_TEXTS_PER_CLUSTER = 30
MAX_TITLES = 4
MODEL_NAME = "llama3-8b-8192"
RETRY_TEXT_LENGTH = 1500

# --- NEW: Tor SOCKS proxy base port ---
TOR_BASE_PORT = 9050  # First Tor instance on 9050, next on 9052, etc.
TOR_PORT_STEP = 2     # Each Tor instance uses a separate port (9050, 9052, 9054, ...)

# Setup logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Environment setup
load_dotenv()

# Parse API keys from comma-separated string
raw_api_keys = os.getenv("GROQ_API_KEY", "")
API_KEYS = [key.strip() for key in raw_api_keys.split(",") if key.strip()]

# Track permanently failed keys
BLACKLISTED_KEYS = set()
CURRENT_KEY_INDEX = 0

def show_api_keys():
    """
    Display the number of valid API keys available for use.
    Logs the count of valid keys (total keys minus blacklisted keys).
    """
    valid_keys = len(API_KEYS) - len(BLACKLISTED_KEYS)
    logger.info(f"Using {valid_keys} of {len(API_KEYS)} available Groq API keys")

os.environ["TOKENIZERS_PARALLELISM"] = "true"

def get_next_valid_key_index():
    """
    Get the next valid API key index, skipping any blacklisted keys.

    Returns:
        int or None: The index of the next valid API key, or None if no valid keys are available.
    """
    global CURRENT_KEY_INDEX

    if len(BLACKLISTED_KEYS) >= len(API_KEYS):
        logger.error("All API keys are blacklisted! Unable to proceed.")
        return None

    # Start from the next key after the current one
    start_index = CURRENT_KEY_INDEX
    while True:
        # Move to next key
        CURRENT_KEY_INDEX = (CURRENT_KEY_INDEX + 1) % len(API_KEYS)

        # If we've cycled through all keys and back to where we started, no valid keys
        if CURRENT_KEY_INDEX == start_index and CURRENT_KEY_INDEX in BLACKLISTED_KEYS:
            return None

        # If key is not blacklisted, use it
        if CURRENT_KEY_INDEX not in BLACKLISTED_KEYS:
            return CURRENT_KEY_INDEX

def split_text_sentencewise(text, max_length=CHUNK_SIZE):
    """
    Split text into sentence-wise chunks within word count limit.

    Args:
        text (str): The text to split into chunks.
        max_length (int): Maximum number of words per chunk. Defaults to CHUNK_SIZE.

    Returns:
        list: A list of text chunks, each containing complete sentences and not exceeding max_length.
    """
    sentences = nltk.sent_tokenize(text)
    chunks, current_chunk, current_length = [], [], 0

    for sentence in sentences:
        sentence_length = len(sentence.split())
        if current_length + sentence_length > max_length:
            if current_chunk:
                chunks.append(' '.join(current_chunk))
            current_chunk = [sentence]
            current_length = sentence_length
        else:
            current_chunk.append(sentence)
            current_length += sentence_length

    if current_chunk:
        chunks.append(' '.join(current_chunk))
    return chunks


def get_tor_session_for_key_index(key_index):
    """
    Create a requests Session that routes through a Tor SOCKS proxy for the given key index.

    Args:
        key_index (int): Index of the API key, used to determine which Tor port to use.

    Returns:
        requests.Session: A configured Session object that routes through the appropriate Tor proxy.
    """
    session = requests.Session()
    tor_port = TOR_BASE_PORT + key_index * TOR_PORT_STEP
    session.proxies = {
        'http': f'socks5h://127.0.0.1:{tor_port}',
        'https': f'socks5h://127.0.0.1:{tor_port}',
    }
    # Optional: Add retries for robustness
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    session.mount('http://', HTTPAdapter(max_retries=retries))
    return session

class PatchedGroqClient(groq.Groq):
    """
    A patched version of the Groq client that uses a custom session for HTTP requests.

    This allows routing requests through Tor or other proxies.
    """
    def __init__(self, api_key, session):
        """
        Initialize the patched Groq client.

        Args:
            api_key (str): The Groq API key.
            session (requests.Session): The session to use for HTTP requests.
        """
        super().__init__(api_key=api_key)
        self._session = session

    def _request(self, method, url, **kwargs):
        """
        Override the _request method to use our custom session.

        Args:
            method (str): HTTP method.
            url (str): URL to request.
            **kwargs: Additional keyword arguments for the request.

        Returns:
            Response: The HTTP response.
        """
        # Use our session for all HTTP requests
        kwargs.setdefault('timeout', 60)
        return self._session.request(method, url, **kwargs)


def call_groq_api(prompt, system_content, temperature=0.4, max_tokens=300, json_format=True):
    """
    Call the Groq API with automatic key rotation and error handling.

    Args:
        prompt (str): The user prompt to send to the API.
        system_content (str): The system message content.
        temperature (float): The sampling temperature. Defaults to 0.4.
        max_tokens (int): Maximum number of tokens to generate. Defaults to 300.
        json_format (bool): Whether to request JSON formatted output. Defaults to True.

    Returns:
        str: The generated content from the API, or an empty string if all attempts fail.
    """
    global CURRENT_KEY_INDEX

    if len(API_KEYS) == 0:
        logger.error("No API keys available. Check your GROQ_API_KEY environment variable.")
        return ""

    # Track error counts for temporary rate-limiting
    rate_limit_errors = {}
    max_errors_per_key = 3
    max_total_attempts = 30  # Avoid infinite loops
    attempts = 0

    while attempts < max_total_attempts:
        # If all keys are blacklisted, return empty result
        if len(BLACKLISTED_KEYS) >= len(API_KEYS):
            logger.error("All API keys are blacklisted! Unable to proceed.")
            return ""

        current_key = API_KEYS[CURRENT_KEY_INDEX]

        try:
            # --- Use a Tor session per API key ---
            session = get_tor_session_for_key_index(CURRENT_KEY_INDEX)
            client = PatchedGroqClient(api_key=current_key, session=session)

            # request completion
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"} if json_format else None
            )

            # Reset rate limit error count on success
            if CURRENT_KEY_INDEX in rate_limit_errors:
                rate_limit_errors[CURRENT_KEY_INDEX] = 0

            return completion.choices[0].message.content

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error with API key {CURRENT_KEY_INDEX + 1} of {len(API_KEYS)}: {error_msg}")

            # Permanently blacklist keys with organization_restricted errors
            if "organization_restricted" in error_msg.lower() or "organization has been restricted" in error_msg.lower():
                logger.warning(f"API key {CURRENT_KEY_INDEX + 1} has been permanently blacklisted due to organization restriction")
                BLACKLISTED_KEYS.add(CURRENT_KEY_INDEX)
                next_key = get_next_valid_key_index()
                if next_key is None:
                    break
                logger.info(f"Switching from API key {CURRENT_KEY_INDEX + 1} to key {next_key + 1} (of {len(API_KEYS)} available keys)")
                CURRENT_KEY_INDEX = next_key
                continue

            # Handle rate limiting
            if "rate limit" in error_msg.lower() or "429" in error_msg:
                # Initialize error count for this key if not present
                if CURRENT_KEY_INDEX not in rate_limit_errors:
                    rate_limit_errors[CURRENT_KEY_INDEX] = 0

                # Increment error count
                rate_limit_errors[CURRENT_KEY_INDEX] = rate_limit_errors.get(CURRENT_KEY_INDEX, 0) + 1
                logger.warning(f"Rate-limit error: API key {CURRENT_KEY_INDEX + 1} - Error count = {rate_limit_errors[CURRENT_KEY_INDEX]} (will switch after {max_errors_per_key} errors)")

                # Switch key if too many rate-limit errors
                if rate_limit_errors[CURRENT_KEY_INDEX] >= max_errors_per_key:
                    next_key = get_next_valid_key_index()
                    if next_key is None:
                        break
                    logger.info(f"Switching from API key {CURRENT_KEY_INDEX + 1} to key {next_key + 1} (of {len(API_KEYS)} available keys)")
                    CURRENT_KEY_INDEX = next_key
                else:
                    # Exponential backoff for rate limits
                    backoff = 3 * (2 ** rate_limit_errors[CURRENT_KEY_INDEX])
                    logger.info(f"Waiting {backoff} seconds before retrying with same key...")
                    import time
                    time.sleep(backoff)
            else:
                # For other errors, try a different key
                next_key = get_next_valid_key_index()
                if next_key is None:
                    break
                logger.info(f"Switching from API key {CURRENT_KEY_INDEX + 1} to key {next_key + 1} (of {len(API_KEYS)} available keys)")
                CURRENT_KEY_INDEX = next_key

        attempts += 1

    logger.error("Failed to get a successful response after multiple attempts.")
    return ""


def parse_json_response(response):
    """
    Extract JSON data from API response string.

    Args:
        response (str): The API response string.

    Returns:
        dict: Extracted JSON data as a dictionary, or empty dict if parsing fails.
    """
    try:
        json_str = re.search(r'\{.*\}', response, re.DOTALL)
        return json.loads(json_str.group()) if json_str else {}
    except json.JSONDecodeError:
        return {}


def create_prompt(chunk, title_focus=False):
    """
    Create analysis prompt based on focus type.

    Args:
        chunk (str): Text chunk to analyze.
        title_focus (bool): If True, focus only on extracting Wikipedia titles.
                           If False, extract both summary and titles. Defaults to False.

    Returns:
        str: The prompt to send to the language model.
    """
    if title_focus:
        return (
            "Analysiere diesen Text und finde exakt passende Wikipedia-Artikeltitel.\n\n"
            "Wichtig: Die Titel MÜSSEN existierenden Wikipedia-Artikeln entsprechen. "
            "Verwende nur Eigennamen, Konzepte oder Ereignisse, die mit hoher Wahrscheinlichkeit als Wikipedia-Artikel existieren.\n\n"
            "Formatiere deine Antwort als JSON: {'titles': ['Titel1', 'Titel2', 'Titel3', 'Titel4', 'Titel5']}\n\n"
            f"{chunk}"
        )
    else:
        return (
            "Führe zwei Aufgaben für diesen Textabschnitt durch:\n\n"
            "1. Erstelle eine prägnante Zusammenfassung der Hauptpunkte in 1-2 Sätzen.\n"
            "2. Identifiziere 2-3 relevante Wikipedia-Artikeltitel, die genau zu diesem Inhalt passen.\n\n"
            "Formatiere deine Antwort als JSON: {'summary': 'Deine Zusammenfassung hier', 'titles': ['Titel1', 'Titel2']}\n\n"
            f"{chunk}"
        )


def process_text_chunk(chunk, title_focus=False):
    """
    Process text chunk to extract summary and Wikipedia titles.

    Args:
        chunk (str): Text chunk to analyze.
        title_focus (bool): If True, focus only on extracting titles. Defaults to False.

    Returns:
        tuple: (summary, titles) where summary is a string and titles is a list of strings.
              If title_focus is True, summary will be an empty string.
    """
    system_content = "Du bist ein präziser Analyst, der Texte zusammenfasst und relevante Wikipedia-Artikel findet."
    prompt = create_prompt(chunk, title_focus)

    response = call_groq_api(prompt, system_content)
    result = parse_json_response(response)

    return ("", result.get('titles', [])) if title_focus else (result.get('summary', ''), result.get('titles', []))


def process_text_chunks_batch(chunks, max_workers=MAX_WORKERS, title_focus=False):
    """
    Process multiple text chunks in parallel.

    Args:
        chunks (list): List of text chunks to analyze.
        max_workers (int): Maximum number of concurrent workers. Defaults to MAX_WORKERS.
        title_focus (bool): If True, focus only on extracting titles. Defaults to False.

    Returns:
        tuple: (summaries, titles) where summaries is a list of strings and titles is a list of strings.
    """
    summaries, titles = [], []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_chunk = {executor.submit(process_text_chunk, chunk, title_focus): chunk for chunk in chunks}

        for future in concurrent.futures.as_completed(future_to_chunk):
            try:
                summary, chunk_titles = future.result()
                if summary:
                    summaries.append(summary)
                if chunk_titles:
                    titles.extend(chunk_titles)
            except Exception as e:
                print(f"Fehler bei der Verarbeitung eines Chunks: {e}")

    return summaries, titles


def retry_title_extraction(texts, max_attempts=1):
    """
    Extract titles with shorter text snippets when initial attempt fails.

    Args:
        texts (list): List of texts to analyze.
        max_attempts (int): Maximum number of retry attempts. Defaults to 1.

    Returns:
        list: List of extracted Wikipedia article titles.
    """
    all_titles = []

    for attempt in range(max_attempts):
        print(f"Versuch {attempt + 1} für Wikipedia-Titel...")
        chunks = [text[:min(len(text), RETRY_TEXT_LENGTH)] for text in texts]
        if chunks:
            _, titles = process_text_chunks_batch(chunks, title_focus=True)
            all_titles.extend(titles)


    return all_titles



def deduplicate_titles(titles):
    """
    Remove similar titles while keeping at least the first entries.

    Args:
        titles (list): List of Wikipedia article titles.

    Returns:
        list: Deduplicated list of Wikipedia article titles.
    """
    # Always keep the first 3 titles (most frequent ones)
    result = []

    # Process remaining titles, avoiding duplicates
    for title in titles:

        result.append(title)

    return result


def generate_final_summary(summaries):
    """
    Create final summary from multiple chunk summaries.

    Args:
        summaries (list): List of summary texts from different chunks.

    Returns:
        str: A consolidated summary of approximately 4 sentences.
    """
    if not summaries:
        return "Keine Zusammenfassung verfügbar."

    selected_summaries = random.sample(summaries, min(80, len(summaries)))
    combined_input = "\n".join(selected_summaries)

    system_content = "Du bist ein erfahrener Analyst, der aus mehreren kurzen Abschnitten ein stimmiges Gesamtbild erstellt."
    prompt = (
        "Hier sind mehrere Zusammenfassungen von Nachrichtenartikeln zum gleichen Thema. "
        "Fasse NUR das Hauptthema zusammen, ignoriere Nebenthemen. "
        "Erstelle eine präzise Gesamtzusammenfassung in genau 4 Sätzen, die alle wichtigen Aspekte des Hauptthemas abdeckt. "
        "Beginne die Zusammenfassung direkt mit dem Inhalt, ohne eine Einleitung oder Floskel wie 'Hier ist eine präzise Gesamtzusammenfassung...' zu verwenden. "
        "Die Zusammenfassung muss vollständig auf Deutsch verfasst sein.\n\n"
        f"{combined_input}"
    )

    response = call_groq_api(prompt, system_content, temperature=0.3, json_format=False)
    return response.strip()



def process_cluster_texts(texts, chunk_size=CHUNK_SIZE, max_texts=MAX_TEXTS_PER_CLUSTER):
    """
    First generate a summary, then use it to extract Wikipedia titles.

    Args:
        texts (list): List of article texts to process.
        chunk_size (int): Maximum size of each text chunk. Defaults to CHUNK_SIZE.
        max_texts (int): Maximum number of texts to process. Defaults to MAX_TEXTS_PER_CLUSTER.

    Returns:
        tuple: (final_summary, wiki_titles) where final_summary is a string and
               wiki_titles is a list of Wikipedia article titles.
    """
    sampled_texts = random.sample(texts, min(len(texts), max_texts))

    # Use only the first 7 chunks per article
    all_chunks = []
    for text in sampled_texts:
        chunks = split_text_sentencewise(text, max_length=chunk_size)
        all_chunks.extend(chunks[:5])

    chunk_summaries, _ = process_text_chunks_batch(all_chunks)
    final_summary = generate_final_summary(chunk_summaries)

    # Use only the summary to extract Wikipedia titles
    system_content = "Du bist ein präziser Analyst, der aus einer Zusammenfassung relevante Wikipedia-Artikel findet."
    prompt = (
        "Analysiere diese Zusammenfassung und finde exakt passende Wikipedia-Artikeltitel.\n\n"
        "Wichtig: Die Titel MÜSSEN existierenden Wikipedia-Artikeln entsprechen. "
        "Verwende nur Eigennamen, Konzepte oder Ereignisse, die mit hoher Wahrscheinlichkeit als Wikipedia-Artikel existieren.\n\n"
        "Formatiere deine Antwort als JSON: {'titles': ['Titel1', 'Titel2', 'Titel3', 'Titel4', 'Titel5']}\n\n"
        f"{final_summary}"
    )
    response = call_groq_api(prompt, system_content)
    result = parse_json_response(response)
    wiki_titles = result.get('titles', [])

    # If not enough titles, fallback to retry
    if not wiki_titles:
        print("Zu wenige Wikipedia-Titel gefunden, starte letzten Versuch...")
        extra_titles = retry_title_extraction([final_summary])
        wiki_titles.extend(extra_titles)

    return final_summary, wiki_titles

def collect_wikipedia_candidates_per_cluster(filtered_df):
    """
    Process all clusters to extract Wikipedia titles and summaries using summary-based approach.

    Args:
        filtered_df (pd.DataFrame): DataFrame containing cluster data with a 'cluster_id'
                                   column and 'combined_text' column.

    Returns:
        tuple: (cluster_candidates, cluster_summaries) where cluster_candidates is a dict
               mapping cluster IDs to lists of Wikipedia titles, and cluster_summaries
               is a dict mapping cluster IDs to summary texts.
    """
    cluster_candidates, cluster_summaries = {}, {}

    for cluster_id in sorted(filtered_df["cluster_id"].unique()):
        cluster_data = filtered_df[filtered_df["cluster_id"] == cluster_id]
        print(f"\nCluster {cluster_id} (Size: {len(cluster_data)})")

        cluster_texts = cluster_data["combined_text"].tolist()
        final_summary, wiki_titles = process_cluster_texts(cluster_texts)
        cluster_summaries[cluster_id] = final_summary

        print("\nCluster Summary:")
        print(final_summary)

        common_titles = deduplicate_titles(wiki_titles)

        if not common_titles:
            print("Keine Wikipedia-Titel nach Filterung gefunden, letzter Versuch...")
            focused_titles = retry_title_extraction([final_summary])
            common_titles = focused_titles[:5]

        if common_titles:
            cluster_candidates[cluster_id] = common_titles
            print(f"\nSuggested Wikipedia titles: {common_titles}")
        else:
            print("\nKeine Wikipedia-Titel für diesen Cluster gefunden.")

    return cluster_candidates, cluster_summaries



def filter_wikipedia_articles_with_groq(summary_dict, wiki_articles_dict):
    """
    Filter Wikipedia articles to keep only those relevant to the cluster summaries.

    Args:
        summary_dict (dict): Dictionary mapping cluster IDs to summary texts.
        wiki_articles_dict (dict): Dictionary mapping cluster IDs to lists of Wikipedia article titles.

    Returns:
        dict: Filtered dictionary mapping cluster IDs to lists of relevant Wikipedia article titles.
    """
    filtered = {}
    for cluster_id, articles in wiki_articles_dict.items():
        summary = summary_dict.get(cluster_id, "")
        if not summary or not articles:
            filtered[cluster_id] = articles
            continue

        system_content = "Du bist ein präziser Analyst, der Wikipedia-Artikel anhand einer Zusammenfassung filtert."
        prompt = (
            "Hier ist eine Zusammenfassung und eine Liste von Wikipedia-Artikeln. "
            "Entferne alle Artikel aus der Liste, die nicht zur Zusammenfassung passen. "
            "Füge KEINE neuen Artikel hinzu. "
            "Gib die gefilterte Liste als JSON zurück: {'titles': ['Titel1', ...]}\n\n"
            f"Zusammenfassung:\n{summary}\n\n"
            f"Wikipedia-Artikel:\n{json.dumps(articles, ensure_ascii=False)}"
        )
        response = call_groq_api(prompt, system_content)
        try:
            result = json.loads(response)
            filtered[cluster_id] = result.get('titles', articles)
        except Exception:
            filtered[cluster_id] = articles  # fallback

    return filtered