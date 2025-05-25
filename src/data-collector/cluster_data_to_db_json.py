import json
import hashlib


def generate_cluster_id(cluster_number: str, date: str) -> str:
    """
    Generates a hashed cluster ID based on the cluster number and the current timestamp.

    :param cluster_number: The cluster number
    :param date: The publication date to include in the hash
    :return: A hashed cluster ID as a string
    """
    raw_id = f"{cluster_number}{date}"

    # Hashing the ID with SHA256
    return hashlib.sha256(raw_id.encode()).hexdigest()


def generate_cluster_json(filtered_df, cluster_topics, cluster_summaries) -> str:
    """
    Transforms the filtered DataFrame into a structured JSON format for clustering data.

    :param filtered_df: A DataFrame containing cluster data with article information
    :param cluster_topics: A dictionary mapping cluster IDs to lists of relevant Wikipedia article names
    :param cluster_summaries: A dictionary mapping cluster IDs to summary texts
    :return: A JSON-formatted string representing the cluster data
    """
    cluster_data = {}
    artikel_data = []
    publication_date = filtered_df["pubtime"].iloc[0].strftime('%Y-%m-%d')



    for cluster_id in sorted(filtered_df["cluster_id"].unique()):
        hashed_cluster_id = generate_cluster_id(str(cluster_id), str(publication_date))
        cluster_entries = filtered_df[filtered_df['cluster_id'] == cluster_id]
        wikipedia_article_names = cluster_topics.get(cluster_id, [])
        summary_text = cluster_summaries.get(cluster_id, None)  # Get summary for this cluster

        cluster_data[hashed_cluster_id] = {
            "cluster_id": hashed_cluster_id,
            "wikipedia_article_names": wikipedia_article_names,
            "date": publication_date,
            "summary_text": summary_text
        }

        for _, row in cluster_entries.iterrows():
            artikel_data.append({
                "article_id": str(row["id"]),
                "cluster_id": hashed_cluster_id,
                "pubtime": row["pubtime"].strftime('%Y-%m-%dT%H:%M:%S'),
                "medium_name": row["medium_name"],
                "head": row["head"],
                "article_link": row.get("article_link", ""),
                "content": row.get("content", "")
            })

    json_data = {
        "artikel": artikel_data,
        "cluster": list(cluster_data.values())
    }
    return json.dumps(json_data, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    print(generate_cluster_id("1", "2023-10-01"))
