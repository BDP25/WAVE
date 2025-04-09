import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.cluster import DBSCAN
from sklearn.manifold import TSNE
import plotly.express as px
from collections import Counter
import nltk
import os
import json
import re
import groq
from dotenv import load_dotenv



# Umgebungsvariablen laden
load_dotenv(dotenv_path='../../WAVE/.env')
groq_key = os.getenv("GROQ_API_KEY")
client = groq.Groq(api_key=groq_key)


os.environ["TOKENIZERS_PARALLELISM"] = "true"  # or "true"


# Sicherstellen, dass der Punkt-Tokenizer von NLTK heruntergeladen ist
nltk.download('punkt')




def load_data():
    """Lädt die bereinigte Daten aus einer Parquet-Datei."""
    return pd.read_parquet("cleaned_data/cleaned_data.parquet", engine="pyarrow")



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



import json
import hashlib
from datetime import datetime

def generate_cluster_id(cluster_number):
    """
    Erstelle eine gehashte Cluster-ID aus der Clusterzahl und der aktuellen Zeit.
    :param cluster_number: Die Clusterzahl
    :return: Gehashte Cluster-ID als String
    """
    current_time = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')  # Aktuelle Zeit im gewünschten Format
    raw_id = f"{cluster_number}-{current_time}"
    # Hashen der ID mit SHA256
    hashed_id = hashlib.sha256(raw_id.encode()).hexdigest()
    return hashed_id

def generate_cluster_json(filtered_df):
    """
    Diese Funktion nimmt einen gefilterten DataFrame und gibt die Cluster-Daten im neuen JSON-Format zurück.
    :param filtered_df: DataFrame mit Clusterdaten
    :return: JSON-String der Cluster-Daten im neuen Format
    """
    cluster_data = {}
    artikel_data = []

    for cluster_id in sorted(filtered_df["dbscan_cluster"].unique()):
        # Gehashte Cluster-ID erstellen
        hashed_cluster_id = generate_cluster_id(cluster_id)

        cluster_entries = filtered_df[filtered_df['dbscan_cluster'] == cluster_id]
        # TODO replace with ARTICLE Names
        wikipedia_article_names = ['test', 'test2']

        # Cluster-Daten für die Cluster-Tabelle erstellen
        cluster_data[hashed_cluster_id] = {
            "cluster_id": hashed_cluster_id,
            "wikipedia_article_names": wikipedia_article_names,
            "date": filtered_df["pubtime"].iloc[0].strftime('%Y-%m-%d')
        }

        # Artikel-Daten für die Artikel-Tabelle erstellen
        for _, row in cluster_entries.iterrows():
            article_entry = {
                "article_id": str(row["id"]),
                "cluster_id": hashed_cluster_id,
                "pubtime": row["pubtime"].strftime('%Y-%m-%dT%H:%M:%S'),
                "medium_name": row["medium_name"],
                "head": row["head"],
                "article_link": row.get("article_link", "")
            }
            artikel_data.append(article_entry)

    # Das final formatierte JSON
    json_data = {
        "artikel": artikel_data,
        "cluster": list(cluster_data.values())
    }

    # Ausgabe als JSON-String ohne Unicode-Escape-Sequenzen
    return json.dumps(json_data, indent=4, ensure_ascii=False)




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

    # Ausgabe des JSON-Strings
    print("\nCluster JSON Output:")
    print(type(cluster_json_data))




    # Optional: Rückgabe des JSON-Strings
    return cluster_json_data



# Beispielaufruf
df = load_data()
df_plot_dbscan_with_json_output(df, target_clusters=(4, 6))

