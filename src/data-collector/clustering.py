import pandas as pd
import spacy
import sys
import subprocess
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def setup_spacy_model(model_name="de_core_news_md"):
    """
    Load a spaCy language model, downloading it if not already available.

    Args:
        model_name (str): Name of the spaCy model to load. Defaults to "de_core_news_md".

    Returns:
        spacy.language.Language: The loaded spaCy language model.
    """
    try:
        nlp = spacy.load(model_name)
    except OSError:
        subprocess.check_call([sys.executable, "-m", "spacy", "download", model_name])
        nlp = spacy.load(model_name)
    return nlp

nlp = setup_spacy_model("de_core_news_md")
german_stop_words = list(nlp.Defaults.stop_words)

def identify_and_save_daily_events_to_df(
    df, max_events=7, similarity_threshold=0.35, min_entity_importance=3, min_articles=2
):
    """
    Identifies daily events from a dataframe of news articles by clustering similar articles
    and extracting important entities.

    Args:
        df (pd.DataFrame): Dataframe containing news articles with 'head', 'content', 'id',
                          'pubtime', 'medium_name', and optionally 'article_link' columns.
        max_events (int): Maximum number of events/clusters to identify. Defaults to 7.
        similarity_threshold (float): Minimum cosine similarity for articles to be considered
                                     in the same cluster. Defaults to 0.35.
        min_entity_importance (int): Minimum importance score for entities to consider a
                                    cluster valid. Defaults to 3.
        min_articles (int): Minimum number of articles required to form a valid cluster.
                          Defaults to 2.

    Returns:
        pd.DataFrame: A dataframe with articles grouped by clusters, containing columns:
                     'id', 'cluster_id', 'pubtime', 'medium_name', 'article_link',
                     'head', 'content', and 'combined_text'.
    """
    article_entities = []
    headline_texts = []
    content_texts = []

    for _, row in df.iterrows():
        headline = row['head']
        content_brief = row['content']
        headline_texts.append(headline)
        content_texts.append(content_brief)
        entities = {}
        headline_doc = nlp(headline)
        for ent in headline_doc.ents:
            if len(ent.text) > 2:
                entities[ent.text] = entities.get(ent.text, 0) + 3
        content_doc = nlp(content_brief)
        for ent in content_doc.ents:
            if len(ent.text) > 2:
                entities[ent.text] = entities.get(ent.text, 0) + 1
        article_entities.append({
            'headline': headline,
            'content': content_brief,
            'entities': entities
        })

    combined_texts = [f"{h} {c}" for h, c in zip(headline_texts, content_texts)]
    vectorizer = TfidfVectorizer(max_features=5000, stop_words=german_stop_words)
    tfidf_matrix = vectorizer.fit_transform(combined_texts)
    similarity_matrix = cosine_similarity(tfidf_matrix)

    event_groups = []
    used_indices = set()
    article_importance = [(i, len(article['entities'])) for i, article in enumerate(article_entities)]
    article_importance.sort(key=lambda x: x[1], reverse=True)

    for idx, _ in article_importance:
        if idx in used_indices:
            continue
        similar_indices = [idx]
        used_indices.add(idx)
        for other_idx in range(len(article_entities)):
            if other_idx != idx and other_idx not in used_indices:
                if similarity_matrix[idx, other_idx] > similarity_threshold:
                    similar_indices.append(other_idx)
                    used_indices.add(other_idx)
        if len(similar_indices) >= min_articles:
            group_entities = Counter()
            group_articles = []
            for i in similar_indices:
                article = article_entities[i]
                group_articles.append(f"{article['headline']} {article['content']}")
                for entity, count in article['entities'].items():
                    group_entities[entity] += count
            if not group_entities:
                for idx in similar_indices[1:]:
                    used_indices.remove(idx)
                continue
            most_important_entity_count = group_entities.most_common(1)[0][1] if group_entities else 0
            if most_important_entity_count < min_entity_importance:
                for idx in similar_indices[1:]:
                    used_indices.remove(idx)
                continue
            main_entities = [entity for entity, _ in group_entities.most_common(5)]
            event_groups.append({
                'main_entities': main_entities,
                'articles': group_articles,
                'article_indices': similar_indices,
                'article_count': len(similar_indices),
                'entity_counts': dict(group_entities.most_common(10)),
                'importance_score': most_important_entity_count * len(similar_indices)
            })

    event_groups.sort(key=lambda x: x['importance_score'], reverse=True)

    # Build outputs: one row per article, including 'id' and 'combined_text'
    cluster_rows = []
    for cluster_id, event in enumerate(event_groups[:max_events]):
        for i in event['article_indices']:
            row = df.iloc[i]
            cluster_rows.append({
                'id': row['id'],
                'cluster_id': cluster_id,
                'pubtime': row['pubtime'],
                'medium_name': row['medium_name'],
                'article_link': row.get('article_link', ''),
                'head': row['head'],
                'content': row['content'],
                'combined_text': f"{row['head']} {row['content']}"
            })

    cluster_df = pd.DataFrame(cluster_rows)
    return cluster_df
