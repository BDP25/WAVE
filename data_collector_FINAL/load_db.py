import psycopg2
import json
from psycopg2 import sql
from dotenv import load_dotenv
import os

load_dotenv()


def create_schema(db_params=None):
    """
    Connects to the PostgreSQL database and creates the 'Cluster' and 'Artikel' tables.

    Parameters:
    db_params (dict): Dictionary containing database connection parameters.
                      Keys should include: 'dbname', 'user', 'password', 'host', 'port'
    """
    # Use default parameters if db_params is None
    if db_params is None:
        db_params = {
            "dbname": "your_database",
            "user": "your_username",
            "password": "your_password",
            "host": "localhost",
            "port": "5432"
        }

    # Define the SQL commands for creating tables
    commands = [
        """
        CREATE TABLE IF NOT EXISTS Cluster (
            cluster_id VARCHAR(255) PRIMARY KEY,
            wikipedia_article_names TEXT,
            date DATE,
            summary_text TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS Artikel (
            article_id VARCHAR(255) PRIMARY KEY,
            cluster_id VARCHAR(255),
            pubtime TIMESTAMP,
            medium_name VARCHAR(255),
            head TEXT,
            content TEXT,
            article_link TEXT,
            CONSTRAINT fk_cluster
                FOREIGN KEY(cluster_id) 
                REFERENCES Cluster(cluster_id)
                ON DELETE SET NULL
        )
        """
    ]

    conn = None
    try:
        # Connect to the PostgreSQL server using db_params
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor()

        # Execute each SQL command
        for command in commands:
            cur.execute(command)

        # Commit the changes
        conn.commit()

        # Close communication with the database
        cur.close()

        print("Tables created successfully.")
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error creating tables: {error}")
        if conn is not None:
            conn.rollback()
    finally:
        if conn is not None:
            conn.close()


def load_data(json_input, db_params):
    # Check if json_input is a file path, a JSON string, or a dictionary
    if isinstance(json_input, (str, bytes, os.PathLike)):
        try:
            # Try to parse it as a JSON string
            data = json.loads(json_input)
        except json.JSONDecodeError:
            # If it fails, assume it's a file path and read JSON data from the file
            with open(json_input, "r") as f:
                data = json.load(f)
    else:
        # Assume json_input is already a dictionary
        data = json_input

    # Establish a connection to PostgreSQL
    conn = psycopg2.connect(**db_params)
    cur = conn.cursor()

    try:
        # Insert records into the Cluster table first (since articles reference clusters)
        cluster_records = data.get("cluster", [])
        for cluster in cluster_records:
            cur.execute(
                """
                INSERT INTO Cluster (cluster_id, wikipedia_article_names, date, summary_text)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (cluster_id) DO NOTHING;
                """,
                (
                    cluster["cluster_id"],
                    cluster["wikipedia_article_names"],
                    cluster["date"],
                    cluster.get("summary_text", None)  # Use .get in case the key is missing
                )
            )
            print(f"Inserted Cluster with cluster_id: {cluster['cluster_id']}")

        # Insert records into the Artikel table
        artikel_records = data.get("artikel", [])
        for artikel in artikel_records:
            cur.execute(
                """
                INSERT INTO Artikel (article_id, cluster_id, pubtime, medium_name, head, article_link)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (article_id) DO NOTHING;
                """,
                (
                    artikel["article_id"],
                    artikel["cluster_id"],
                    artikel["pubtime"],
                    artikel["medium_name"],
                    artikel["head"],
                    artikel["article_link"]
                )
            )
            print(f"Inserted Artikel with article_id: {artikel['article_id']}")

        # Commit the transactions
        conn.commit()

    except Exception as e:
        conn.rollback()
        print("Error inserting data:", e)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    # Define your PostgreSQL connection

    db_params = {
        "dbname": os.getenv("DB_NAME", "your_database"),
        "user": os.getenv("DB_USER", "your_username"),
        "password": os.getenv("DB_PASSWORD", "your_password"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432")
    }

    # Create schema using db_params
    create_schema(db_params)

    json_data = {
        "artikel": [
            {
                "article_id": "art001",
                "cluster_id": "2025-04-09T08:30:00",
                "pubtime": "2025-04-09T08:30:00",
                "medium_name": "Example News",
                "head": "Breaking News: Example Event",
                "article_link": "https://www.example.com/news/example-event"
            },
            {
                "article_id": "art002",
                "cluster_id": "2025-04-09T08:30:00",
                "pubtime": "2025-04-09T09:00:00",
                "medium_name": "Daily Times",
                "head": "Local Update: Community Event",
                "article_link": "https://www.dailytimes.com/news/community-event"
            },
            {
                "article_id": "art003",
                "cluster_id": "2025-04-09T09:15:00",
                "pubtime": "2025-04-09T09:15:00",
                "medium_name": "Tech Daily",
                "head": "Innovative Tech Unveiled",
                "article_link": "https://www.techdaily.com/innovative-tech"
            },
            {
                "article_id": "art004",
                "cluster_id": "2025-04-10T10:00:00",
                "pubtime": "2025-04-10T10:00:00",
                "medium_name": "World News",
                "head": "International Summit Begins",
                "article_link": "https://www.worldnews.com/summit-begins"
            },
            {
                "article_id": "art005",
                "cluster_id": "2025-04-11T12:30:00",
                "pubtime": "2025-04-11T12:30:00",
                "medium_name": "Health Weekly",
                "head": "Health Alert: New Guidelines Released",
                "article_link": "https://www.healthweekly.com/guidelines-released"
            },
            {
                "article_id": "art006",
                "cluster_id": "2025-04-10T10:00:00",
                "pubtime": "2025-04-10T10:30:00",
                "medium_name": "Global Times",
                "head": "Summit Highlights: Global Leaders Agree",
                "article_link": "https://www.globaltimes.com/summit-highlights"
            }
        ],
        "cluster": [
            {
                "cluster_id": "2025-04-09T08:30:00",
                "wikipedia_article_names": "Example_Event,Community_Event",
                "date": "2025-04-09",
                "summary_text": "This is a summary for the first cluster."
            },
            {
                "cluster_id": "2025-04-09T09:15:00",
                "wikipedia_article_names": "Innovative_Tech,Startups",
                "date": "2025-04-09",
                "summary_text": "This is a summary for the second cluster."
            },
            {
                "cluster_id": "2025-04-10T10:00:00",
                "wikipedia_article_names": "International_Summit,Diplomacy",
                "date": "2025-04-10",
                "summary_text": "This is a summary for the third cluster."
            },
            {
                "cluster_id": "2025-04-11T12:30:00",
                "wikipedia_article_names": "Health_Alert,Medical_Guidelines",
                "date": "2025-04-11",
                "summary_text": "This is a summary for the fourth cluster."
            }
        ]
    }



    # Pass the JSON data directly
    load_data(json_data, db_params)
