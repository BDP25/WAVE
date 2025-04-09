import json
import hashlib
from datetime import datetime


def generate_cluster_id(cluster_number: int, date) -> str:
    """
    Generates a hashed cluster ID based on the cluster number and the current timestamp.

    :param cluster_number: The cluster number
    :return: A hashed cluster ID as a string
    """
    raw_id = f"{cluster_number}-{date}"

    # Hashing the ID with SHA256
    return hashlib.sha256(raw_id.encode()).hexdigest()


def generate_cluster_json(filtered_df) -> str:
    """
    Transforms the filtered DataFrame into a structured JSON format for clustering data.

    :param filtered_df: A DataFrame containing cluster data
    :return: A JSON-formatted string representing the cluster data
    """
    cluster_data = {}
    artikel_data = []
    publication_date = filtered_df["pubtime"].iloc[0].strftime('%Y-%m-%d')


    # Process each unique cluster
    for cluster_id in sorted(filtered_df["dbscan_cluster"].unique()):
        hashed_cluster_id = generate_cluster_id(cluster_id, publication_date)

        # Filter DataFrame for current cluster
        cluster_entries = filtered_df[filtered_df['dbscan_cluster'] == cluster_id]

        # Placeholder for actual article names (to be replaced later)
        wikipedia_article_names = ['test', 'test2']

        # Create cluster data entries
        cluster_data[hashed_cluster_id] = {
            "cluster_id": hashed_cluster_id,
            "wikipedia_article_names": wikipedia_article_names,
            "date": publication_date,
        }

        # Create article data entries for each row in the cluster
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

    # Final JSON structure
    json_data = {
        "artikel": artikel_data,
        "cluster": list(cluster_data.values())
    }

    # Return the formatted JSON string without Unicode escapes
    return json.dumps(json_data, indent=4, ensure_ascii=False)
