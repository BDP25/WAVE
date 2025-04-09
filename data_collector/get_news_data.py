import os
import random
import time
import requests
from dotenv import load_dotenv
from typing import Optional

# https://liri.linguistik.uzh.ch/wiki/langtech/swissdox/api
# https://swissdox.linguistik.uzh.ch/queries

# Load environment variables from .env file
load_dotenv(dotenv_path='../../WAVE/.env')

# Constants
SAVE_FOLDER = './raw_data'
API_BASE_URL = "https://swissdox.linguistik.uzh.ch/api"
API_URL_QUERY = f"{API_BASE_URL}/query"
API_URL_STATUS = f"{API_BASE_URL}/status"

# API headers with authentication
HEADERS = {
    "X-API-Key": os.getenv("SWISSDOX_KEY"),
    "X-API-Secret": os.getenv("SWISSDOX_SECRET")
}

# List of sources used for querying news articles
USED_SOURCES = [
    "ZWA", "ZWAF", "ZWAO", "ZWAS", "ZWSO", "HEU", "HEUL", "HEUC", "HEUN", "HEUR", "NNHEU",
    "APO", "TAB", "AT", "AZ", "AZM", "APPZ", "BT", "BLZ", "BZM", "BAZA", "BAZM", "BEOL",
    "BRS", "BZ", "BBLI", "BLIA", "BU", "LB", "WEW", "WOZ", "TAE", "SHZ", "LAT", "ESV",
    "LPNV", "LPRC", "LTB", "LTZ", "MLZ", "CAMP", "NEWS", "NZZS", "NLZ", "NZZ", "NN",
    "NNTZ", "NIW", "OBW", "OLT", "PHRC", "SWO", "NMZ", "SOZ", "SOZM", "SGT", "TA", "THT",
    "TZ", "TBT", "WZ", "URZ", "ZOF", "ZN", "ZUGZ", "ZHUL", "ZUGB", "AZO", "BTO", "NZZB",
    "BLIO", "BLIAO", "SHZO", "LTZO", "NZZO", "OLTO", "SGTO", "NNTA", "ZSZO", "TAZT"
]


def build_query_yaml(start_date: str, end_date: str) -> str:
    """Builds the YAML query string to send to the Swissdox API."""
    return f"""
query:
  sources: {USED_SOURCES}
  dates:
    - from: {start_date}
      to: {end_date}
  languages:
    - de
result:
  format: TSV
  maxResults: 50000
  columns:
    - id
    - pubtime
    - medium_code
    - medium_name
    - char_count
    - head
    - article_link
    - content_id
    - content
version: 1.2
"""


def fetch_swissdox_data(start_date: str, end_date: str) -> Optional[str]:
    """Sends a query to the Swissdox API and initiates the download process if successful."""
    query_yaml = build_query_yaml(start_date, end_date)
    query_name = f"LastWeekNews_{int(time.time())}_{random.randint(1000, 9999)}"

    response = requests.post(API_URL_QUERY, headers=HEADERS, data={
        "query": query_yaml,
        "name": query_name,
        "comment": "All news articles from the specified time period"
    })

    if response.status_code != 200:
        print(f"Error sending query: {response.status_code}")
        return None

    query_id = response.json().get("queryId")
    print(f"Query sent successfully. Query ID: {query_id}")

    return download_news_data(query_id)


def download_news_data(query_id: int) -> Optional[str]:
    """Polls the API until the query is finished and downloads the result file."""
    while True:
        response = requests.get(f"{API_URL_STATUS}/{query_id}", headers=HEADERS)
        status_data = response.json()[0]

        if status_data.get('status') == 'finished':
            download_url = status_data.get('downloadUrl')
            if not download_url:
                print("No download URL found.")
                return None

            print(f"Download URL received: {download_url}")
            return save_downloaded_file(download_url)

        print("Query still processing...")
        time.sleep(5)


def save_downloaded_file(download_url: str) -> Optional[str]:
    """Downloads the file from the given URL and saves it locally."""
    filename = os.path.basename(download_url)
    response = requests.get(download_url, headers=HEADERS)

    if response.status_code != 200:
        print(f"Error downloading file: {response.status_code}")
        print(response.text)
        return None

    os.makedirs(SAVE_FOLDER, exist_ok=True)
    file_path = os.path.join(SAVE_FOLDER, filename)

    with open(file_path, "wb") as file:
        file.write(response.content)

    print(f"✅ File saved successfully: {file_path}")
    print("File size: %.2f KB" % (len(response.content) / 1024))
    return file_path
