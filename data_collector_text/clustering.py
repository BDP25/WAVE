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
    df.loc[:, 'cluster_id'] = dbscan.fit_predict(embeddings)

    num_clusters = len(df['cluster_id'].unique()) - (1 if -1 in df['cluster_id'].unique() else 0)

    while num_clusters < target_clusters[0] or num_clusters > target_clusters[1]:
        if num_clusters < target_clusters[0]:
            eps += 0.025
        elif num_clusters > target_clusters[1]:
            eps -= 0.025

        dbscan = DBSCAN(eps=eps, min_samples=min_samples)
        df.loc[:, 'cluster_id'] = dbscan.fit_predict(embeddings)
        num_clusters = len(df['cluster_id'].unique()) - (1 if -1 in df['cluster_id'].unique() else 0)

    tsne = TSNE(n_components=2, random_state=42)
    tsne_results = tsne.fit_transform(embeddings)
    df.loc[:, 'tsne_x'] = tsne_results[:, 0]
    df.loc[:, 'tsne_y'] = tsne_results[:, 1]

    df_relevant_articles = df[df["cluster_id"] >= 0]
    # plot
    plot_and_save_silhouette(df, embeddings)



    return df_relevant_articles




import os
import datetime
import matplotlib.pyplot as plt
from sklearn.metrics import silhouette_samples, silhouette_score
import pandas as pd
import numpy as np

def plot_and_save_silhouette(df, embeddings):
    # Use the earliest pubtime date in the DataFrame

    if "pubtime" in df.columns:
            # Extract date part from pubtime (assume it's datetime or string)
            pub_dates = pd.to_datetime(df["pubtime"])
            date = pub_dates.min().strftime("%Y-%m-%d")
    else:
            date = (datetime.date.today() - datetime.timedelta(days=2)).strftime("%Y-%m-%d")
    labels = df['cluster_id'].values
    if len(set(labels)) < 2 or (labels == -1).all():
        print("Not enough clusters for silhouette plot.")
        return

    sil_score = silhouette_score(embeddings, labels)
    sil_samples = silhouette_samples(embeddings, labels)

    fig, ax = plt.subplots(figsize=(8, 5))
    y_lower = 10
    for i in sorted(set(labels)):
        if i == -1:
            continue
        ith_cluster_silhouette_values = sil_samples[labels == i]
        ith_cluster_silhouette_values.sort()
        size_cluster_i = ith_cluster_silhouette_values.shape[0]
        y_upper = y_lower + size_cluster_i
        ax.fill_betweenx(
            np.arange(y_lower, y_upper),
            0, ith_cluster_silhouette_values
        )
        ax.text(-0.05, y_lower + 0.5 * size_cluster_i, str(i))
        y_lower = y_upper + 10

    ax.set_title(f"Silhouette plot for clusters (score={sil_score:.2f})")
    ax.set_xlabel("Silhouette coefficient values")
    ax.set_ylabel("Cluster label")
    ax.axvline(x=sil_score, color="red", linestyle="--")
    ax.set_yticks([])

    os.makedirs("plots", exist_ok=True)
    plot_path = f"plots/silhouette_{date}.png"
    plt.tight_layout()
    plt.savefig(plot_path)
    plt.close()
    print(f"Silhouette plot saved to {plot_path}")



