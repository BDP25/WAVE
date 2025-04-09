import datetime
from get_news_data import fetch_swissdox_data

from clean_data import clean_and_process_data

# Calculate the date range for the last week
end_date = datetime.date.today()
start_date = end_date - datetime.timedelta(days=2)


# Format the dates in the desired format (YYYY-MM-DD)
start_date_str = start_date.strftime("%Y-%m-%d")
end_date_str = end_date.strftime("%Y-%m-%d")

fetch_swissdox_data(start_date_str, end_date_str)
clean_and_process_data()
