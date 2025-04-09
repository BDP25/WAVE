from sentence_transformers import SentenceTransformer
from sklearn.cluster import DBSCAN
from sklearn.manifold import TSNE
from collections import Counter
from dotenv import load_dotenv
from cluster_data_to_db_json import generate_cluster_json
import nltk
import os
import re
import groq
import json



# Umgebungsvariablen laden
load_dotenv(dotenv_path='../../WAVE/.env')
groq_key = os.getenv("GROQ_API_KEY")
client = groq.Groq(api_key=groq_key)


os.environ["TOKENIZERS_PARALLELISM"] = "true"

# TODO
# Download NLTK resources if needed (uncomment first time)
# nltk.download('punkt')
# nltk.download('punkt_tab')



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
    """Analyze multiple texts to find common Wikipedia articles"""
    all_articles = []

    for text in cluster_texts:
        articles = get_wikipedia_suggestions(text)
        if articles:
            all_articles.extend(articles)

    if not all_articles:
        return "Keine relevanten Artikel gefunden"

    # Count and filter articles
    counter = Counter(all_articles)
    min_occurrences = max(2, len(cluster_texts) // 3)
    common_articles = [
        f"{art} ({cnt}x)"
        for art, cnt in counter.most_common()
        if cnt >= min_occurrences
    ]

    return "\n".join(common_articles[:5]) if common_articles else "Keine konsistenten Artikel"




def df_plot_dbscan_with_json_output(df, target_clusters=(4, 6)):
    if len(df) <= 400:
        eps = 0.05
        min_samples = 4
    else:
        eps = 0.04
        min_samples = 6

    df.loc[:, "combined_text"] = df["head"] + " " + df["content"]

    model = SentenceTransformer('all-MiniLM-L12-v2')
    embeddings = model.encode(df['combined_text'].tolist())

    dbscan = DBSCAN(eps=eps, min_samples=min_samples)
    df.loc[:, 'dbscan_cluster'] = dbscan.fit_predict(embeddings)

    num_clusters = len(df['dbscan_cluster'].unique()) - (1 if -1 in df['dbscan_cluster'].unique() else 0)

    while num_clusters < target_clusters[0] or num_clusters > target_clusters[1]:
        if num_clusters < target_clusters[0]:
            eps += 0.025
        elif num_clusters > target_clusters[1]:
            eps -= 0.025

        dbscan = DBSCAN(eps=eps, min_samples=min_samples)
        df.loc[:, 'dbscan_cluster'] = dbscan.fit_predict(embeddings)
        num_clusters = len(df['dbscan_cluster'].unique()) - (1 if -1 in df['dbscan_cluster'].unique() else 0)

    tsne = TSNE(n_components=2, random_state=42)
    tsne_results = tsne.fit_transform(embeddings)
    df.loc[:, 'tsne_x'] = tsne_results[:, 0]
    df.loc[:, 'tsne_y'] = tsne_results[:, 1]

    filtered_df = df[df["dbscan_cluster"] >= 0]

    # JSON-Daten für jedes Cluster sammeln
    cluster_json_data = generate_cluster_json(filtered_df)

    return cluster_json_data




