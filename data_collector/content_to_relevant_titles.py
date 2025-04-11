import nltk
import os
import re
import groq
import json
from collections import Counter
from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv(dotenv_path='../../WAVE/.env')
groq_key = os.getenv("GROQ_API_KEY")
client = groq.Groq(api_key=groq_key)

os.environ["TOKENIZERS_PARALLELISM"] = "true"

# TODO
# Download NLTK resources if needed (uncomment first time)
nltk.download('punkt')
nltk.download('punkt_tab')


def split_text_sentencewise(text, max_length=1000):
    """Split the text into sentence-wise chunks that do not exceed max_length"""
    sentences = nltk.sent_tokenize(text)  # Tokenize into sentences
    chunks = []
    current_chunk = []
    current_length = 0

    for sentence in sentences:
        sentence_length = len(sentence.split())  # Count words (approximate tokens)

        # If adding this sentence exceeds the max length, start a new chunk
        if current_length + sentence_length > max_length:
            if current_chunk:
                chunks.append(' '.join(current_chunk))
            current_chunk = [sentence]
            current_length = sentence_length
        else:
            current_chunk.append(sentence)
            current_length += sentence_length

    # Add the last chunk if any
    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks

def parse_json_response(response):
    """Extract JSON from Groq response"""
    try:
        json_str = re.search(r'\{.*\}', response, re.DOTALL)
        if json_str:
            return json.loads(json_str.group())
        return {}
    except json.JSONDecodeError:
        return {}


def get_wikipedia_suggestions(text):
    """Get Wikipedia suggestions from Groq for a single text, ensuring the titles exist on Wikipedia"""

    # Split the text into chunks sentence-wise to avoid exceeding LLM input size limit
    chunks = split_text_sentencewise(text)

    all_titles = []

    for chunk in chunks:
        prompt = (
            "Gib 3-5 relevante Wikipedia-Artikel-Titel für diesen Text als JSON. "
            "Die Titel müssen echte Wikipedia-Artikel sein, d.h. sie müssen genau übereinstimmen. "
            "Format: {'titles': ['Artikel1', 'Artikel2']}. Nur exakte Artikelnamen, keine Vermutungen oder Platzhalter:\n\n"
            f"{chunk}"  # Each chunk of the text
        )

        try:
            completion = client.chat.completions.create(
                model="llama3-70b-8192",
                messages=[
                    {"role": "system", "content": "Du bist ein hilfreicher Assistent für Wikipedia-Recherche."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=200,
                response_format={"type": "json_object"}
            )
            response = completion.choices[0].message.content
            titles = parse_json_response(response).get('titles', [])
            all_titles.extend(titles)
        except Exception as e:
            print(f"API Fehler bei Chunk: {str(e)}")

    return all_titles


def get_common_suggestions(cluster_texts):
    """Analyze multiple texts to find common Wikipedia articles as a list"""
    all_articles = []

    for text in cluster_texts:
        articles = get_wikipedia_suggestions(text)
        if articles:
            all_articles.extend(articles)

    if not all_articles:
        return []

    # Count and filter articles
    counter = Counter(all_articles)
    min_occurrences = max(2, len(cluster_texts) // 3)

    # Only keep article titles that appear often enough
    common_articles = [
        art for art, cnt in counter.most_common()
        if cnt >= min_occurrences
    ]

    return common_articles[:5]  # return top 5 if available


def collect_wikipedia_candidates_per_cluster(filtered_df):
    """Collects potential Wikipedia article titles per cluster for later validation"""
    cluster_candidates = {}

    for cluster_id in sorted(filtered_df["dbscan_cluster"].unique()):
        cluster_data = filtered_df[filtered_df["dbscan_cluster"] == cluster_id]
        print(f"\nCluster {cluster_id} (Size: {len(cluster_data)})")

        suggestions = get_common_suggestions(
            cluster_data["combined_text"].str[:1000].tolist()
        )
        print("\nSuggested Wikipedia titles:")
        print(suggestions)

        cluster_candidates[cluster_id] = suggestions

    return cluster_candidates



