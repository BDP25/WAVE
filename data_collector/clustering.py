from sentence_transformers import SentenceTransformer
from sklearn.cluster import DBSCAN
from sklearn.manifold import TSNE


# just get relevant articles
def dbscan_clustering_get_relevant_articles(df, target_clusters=(4, 6)):
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

    df_relevant_articles = df[df["dbscan_cluster"] >= 0]



    return df_relevant_articles




