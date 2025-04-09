import datetime
import time
import argparse
import os

from get_news_data import fetch_swissdox_data
from clean_data import clean_and_process_data
from load_db import load_data as db_load
from clustering import df_plot_dbscan_with_json_output, load_data


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
parser.add_argument('--date', type=str, default='latest', help='Date in YYYY-MM-DD format or "latest" for the latest data. Witch is two days ago')
args = parser.parse_args()

# Handle the date parameter
if args.date.lower() == "latest":
    date_of_interest = datetime.date.today() - datetime.timedelta(days=2)
else:
    try:
        date_of_interest = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError:
        print(f"Error: Invalid date format '{args.date}'. Please use YYYY-MM-DD or 'today'. Using today's date.")
        date_of_interest = datetime.date.today()

end_date = datetime.date.today()
start_date = end_date - datetime.timedelta(days=2)


# Format the dates in the desired format (YYYY-MM-DD)
start_date_str = start_date.strftime("%Y-%m-%d")
end_date_str = end_date.strftime("%Y-%m-%d")
raw_data_folder = './raw_data'
os.makedirs(raw_data_folder, exist_ok=True)
fetch_swissdox_data(date_of_interest, date_of_interest)
cleaned_data_folder = './cleaned_data'
os.makedirs(cleaned_data_folder, exist_ok=True)
clean_and_process_data()

time.sleep(2)
df = load_data()
json_data = df_plot_dbscan_with_json_output(df, target_clusters=(4, 6))
db_load(json_data, db_params)


