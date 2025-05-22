import concurrent.futures
import json
import os
import random
import re
import groq
import nltk
from dotenv import load_dotenv

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

# Environment setup
load_dotenv(dotenv_path='../../WAVE/.env')
API_KEYS = os.getenv("GROQ_API_KEY").split(", ")

def show_api_keys():
    """Display the API keys."""
    print("API Keys:")
    for i, key in enumerate(API_KEYS):
        print(f"Key {i + 1}: {key}")

os.environ["TOKENIZERS_PARALLELISM"] = "true"



def split_text_sentencewise(text, max_length=CHUNK_SIZE):
    """Split text into sentence-wise chunks within word count limit."""
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


# --- NEW: Create a requests.Session per API key, each using a different Tor SOCKS proxy ---
def get_tor_session_for_key_index(key_index):
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

# --- NEW: Patch Groq client to use our session ---
class PatchedGroqClient(groq.Groq):
    def __init__(self, api_key, session):
        super().__init__(api_key=api_key)
        self._session = session

    def _request(self, method, url, **kwargs):
        # Use our session for all HTTP requests
        kwargs.setdefault('timeout', 60)
        return self._session.request(method, url, **kwargs)


def call_groq_api(prompt, system_content, temperature=0.4, max_tokens=300, json_format=True):
    api_key_index = 0
    rate_limit_errors = [0] * len(API_KEYS)

    max_total_attempts = len(API_KEYS) * 3  # Jeder Key darf 3x versagen
    attempts = 0

    while attempts < max_total_attempts:
        try:
            # --- NEW: Use a Tor session per API key ---
            session = get_tor_session_for_key_index(api_key_index)
            client = PatchedGroqClient(api_key=API_KEYS[api_key_index], session=session)

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

            # reset rate limit error count for the current API key
            rate_limit_errors[api_key_index] = 0
            return completion.choices[0].message.content

        except Exception as e:
            error_msg = str(e)
            print(f"Fehler bei API-Key {api_key_index + 1}: {error_msg}")

            # rate limit or organization restriction error handling
            if (
                "rate limit" in error_msg.lower() or
                "429" in error_msg or
                "organization has been restricted" in error_msg.lower() or
                "organization_restricted" in error_msg.lower()
            ):
                rate_limit_errors[api_key_index] += 1
                print(f"Rate-Limit/Org-Restrict-Fehler: Zähler für Key {api_key_index + 1} = {rate_limit_errors[api_key_index]}")

                # change API key if error occurs
                if rate_limit_errors[api_key_index] >= 3:
                    print(f"Wechsle API-Key von {api_key_index + 1} auf {(api_key_index + 1) % len(API_KEYS) + 1}")
                    rate_limit_errors[api_key_index] = 0
                    api_key_index = (api_key_index + 1) % len(API_KEYS)
            else:
                print("Kein Rate-Limit- oder Org-Restrict-Fehler – versuche erneut mit gleichem Key...")

        attempts += 1

    print("Alle API-Keys ausgeschöpft oder mehrfach fehlgeschlagen.")
    return ""


def parse_json_response(response):
    """Extract JSON data from API response string."""
    try:
        json_str = re.search(r'\{.*\}', response, re.DOTALL)
        return json.loads(json_str.group()) if json_str else {}
    except json.JSONDecodeError:
        return {}


def create_prompt(chunk, title_focus=False):
    """Create analysis prompt based on focus type."""
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
    """Process text chunk to extract summary and Wikipedia titles."""
    system_content = "Du bist ein präziser Analyst, der Texte zusammenfasst und relevante Wikipedia-Artikel findet."
    prompt = create_prompt(chunk, title_focus)

    response = call_groq_api(prompt, system_content)
    result = parse_json_response(response)

    return ("", result.get('titles', [])) if title_focus else (result.get('summary', ''), result.get('titles', []))


def process_text_chunks_batch(chunks, max_workers=MAX_WORKERS, title_focus=False):
    """Process multiple text chunks in parallel."""
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
    """Extract titles with shorter text snippets when initial attempt fails."""
    all_titles = []

    for attempt in range(max_attempts):
        print(f"Versuch {attempt + 1} für Wikipedia-Titel...")
        chunks = [text[:min(len(text), RETRY_TEXT_LENGTH)] for text in texts]
        if chunks:
            _, titles = process_text_chunks_batch(chunks, title_focus=True)
            all_titles.extend(titles)


    return all_titles



def deduplicate_titles(titles):
    """Remove similar titles while keeping at least the first 3 entries."""

    # Always keep the first 3 titles (most frequent ones)
    result = []

    # Process remaining titles, avoiding duplicates
    for title in titles:

        result.append(title)

    return result


def generate_final_summary(summaries):
    """Create final summary from multiple chunk summaries."""
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
    """First generate a summary, then use it to extract Wikipedia titles."""
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
    """Process all clusters to extract Wikipedia titles and summaries using summary-based approach."""
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