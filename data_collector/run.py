import datetime
import os
from get_news_data import fetch_swissdox_data
from clean_data import clean_and_process_data
from load_db import load_data as db_load
from clustering import df_plot_dbscan_with_json_output



db_params = {
        "dbname": os.getenv("DB_NAME", "your_database"),
        "user": os.getenv("DB_USER", "your_username"),
        "password": os.getenv("DB_PASSWORD", "your_password"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432")
    }

# Calculate the date range for the last week
end_date = datetime.date.today()
start_date = end_date - datetime.timedelta(days=2)


# Format the dates in the desired format (YYYY-MM-DD)
start_date_str = start_date.strftime("%Y-%m-%d")
end_date_str = end_date.strftime("%Y-%m-%d")

# download data
fetch_swissdox_data(start_date_str, end_date_str)

# clean data
cleaned_data = clean_and_process_data()


#
json_data = df_plot_dbscan_with_json_output(cleaned_data, target_clusters=(4, 6))

# load data to database
db_load(json_data, db_params)


