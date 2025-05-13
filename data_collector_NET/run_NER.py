import datetime
import argparse
import os
from get_news_data import fetch_swissdox_data
from clean_data import clean_and_process_data
from get_wiki_article import validate_wikipedia_titles
from NER_Ansatz import identify_and_save_daily_events_to_df_and_dict
from summary_NER import summarize_clusters, filter_wikipedia_articles_with_groq
from cluster_data_to_db_json import generate_cluster_json
from load_db import load_data



db_params = {
        "dbname": os.getenv("DB_NAME", "your_database"),
        "user": os.getenv("DB_USER", "your_username"),
        "password": os.getenv("DB_PASSWORD", "your_password"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432")
    }

# Calculate the date range for the last week
# Parse command-line arguments
parser = argparse.ArgumentParser(description='Process news data for a specific date.')
parser.add_argument('--date', type=str, default='latest', help='Date in YYYY-MM-DD format or "latest" for the latest data (which is two days ago)')
args = parser.parse_args()

# Handle the date parameter
if args.date.lower() == "latest":
    date_of_interest = datetime.date.today() - datetime.timedelta(days=2)
else:
    try:
        date_of_interest = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
        # Verify the date is valid for processing
        if date_of_interest > datetime.date.today():
            print(f"Error: Future date '{args.date}' not allowed. Using latest date (two days ago).")
            date_of_interest = datetime.date.today() - datetime.timedelta(days=2)
    except ValueError:
        print(f"Error: Invalid date format '{args.date}'. Please use YYYY-MM-DD or 'latest'. Using latest date (two days ago).")
        date_of_interest = datetime.date.today() - datetime.timedelta(days=2)

print(f"Processing data for date: {date_of_interest}")


# download data
fetch_swissdox_data(date_of_interest, date_of_interest)

# clean data
cleaned_data = clean_and_process_data()


wiki_titles_dict, cluster_df = identify_and_save_daily_events_to_df_and_dict(cleaned_data, max_events=6, min_entity_importance=3, min_articles=5)


wikipedia_articles_cluster = validate_wikipedia_titles(wiki_titles_dict)


summary = summarize_clusters(cluster_df)


wikipedia_articles_cluster = filter_wikipedia_articles_with_groq(wikipedia_articles_cluster, summary)

json_data = generate_cluster_json(cluster_df, wikipedia_articles_cluster, summary)




# load data to database
load_data(json_data, db_params)

