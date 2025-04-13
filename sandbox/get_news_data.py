import requests
import datetime
import os
import random
import time
from dotenv import load_dotenv

# https://liri.linguistik.uzh.ch/wiki/langtech/swissdox/api
# https://swissdox.linguistik.uzh.ch/queries

# Load the .env file
load_dotenv(dotenv_path='../.env')

# API credentials from environment variables
headers = {
    "X-API-Key": os.getenv("SWISSDOX_KEY"),
    "X-API-Secret": os.getenv("SWISSDOX_SECRET")
}

# Define the base URL for the API
API_BASE_URL = "https://swissdox.linguistik.uzh.ch/api"
API_URL_QUERY = f"{API_BASE_URL}/query"
API_URL_STATUS = f"{API_BASE_URL}/status"
API_URL_DOWNLOAD = f"{API_BASE_URL}/download"

# Calculate the date range for the last week
end_date = datetime.date.today()
start_date = end_date - datetime.timedelta(days=5)


# Format the dates in the desired format (YYYY-MM-DD)
start_date_str = start_date.strftime("%Y-%m-%d")
end_date_str = end_date.strftime("%Y-%m-%d")

sources_list = [
    "ZWSO", "AZM", "APPZ", "BLZ", "BAZ", "BEOL", "BZ", "BLI", "BU", "LB",
    "WEW", "WOZ", "DOMO", "FUW", "SHZ", "LTZ", "LUZ", "NZZS", "NLZ", "NZZ",
    "NIW", "OBW", "OLT", "SAW", "SCHB", "SWO", "SIS", "SPOM", "SGT", "THT",
    "TZ", "TBT", "ZHUL", "ZSZ", "NZZB", "NNBE", "SIO", "SRF", "NNTA", "ZSZO"
]



abbreviations = [
    "ZWAF", "ZWA", "ZWAO", "ZWAS", "ZWSO", "HEU", "HEUL", "APO", "AZ", "APPZ",
    "BT", "BLZ", "BAZ", "BEOL", "BZ", "BLI", "BBLI", "BLIA", "BOLF", "CVAL",
    "WEW", "WOZ", "DOMO", "GTB", "LPNV", "TLMD", "LTZ", "LUZ", "MLZ", "CAMP",
    "NZZG", "TICK", "NZZS", "NZZM", "NLZ", "NZZ", "NNTZ", "NIW", "OBW", "OAS",
    "LRVI", "PME", "SAS", "SAW", "SI", "NMZ", "HEUN", "TAE", "SHZ", "LM",
    "LAT", "TA", "THT", "TZ", "TBT", "NLZS", "ZHUL", "BLIAO", "BLIO", "SRF",
    "SGTO", "NNTA", "SFTV", "ZSZO", "ZHUO"
]

used_sources = [
    "ZWA", "ZWAF", "ZWAO", "ZWAS", "ZWSO", "HEU", "HEUL", "HEUC", "HEUN", "HEUR", "NNHEU",
    "APO", "TAB", "AT", "AZ", "AZM", "APPZ", "BT", "BLZ", "BZM", "BAZA", "BAZM", "BEOL",
    "BRS", "BZ", "BBLI", "BLIA", "BU", "LB", "WEW", "WOZ", "TAE", "SHZ", "LAT", "ESV",
    "LPNV", "LPRC", "LTB", "LTZ", "MLZ", "CAMP", "NEWS", "NZZS", "NLZ", "NZZ", "NN",
    "NNTZ", "NIW", "OBW", "OLT", "PHRC", "SWO", "NMZ", "SOZ", "SOZM", "SGT", "TA", "THT",
    "TZ", "TBT", "WZ", "URZ", "ZOF", "ZN", "ZUGZ", "ZHUL", "ZUGB", "AZO", "BTO", "NZZB",
    "BLIO", "BLIAO", "SHZO", "LTZO", "NZZO", "OLTO", "SGTO", "NNTA", "ZSZO", "TAZT"
]



# Create the YAML query with the formatted start and end dates
query_yaml = f"""
query:
  sources: {used_sources}
  dates:
    - from: {start_date_str}
      to: {end_date_str}
  languages:
    - de
result:
  format: TSV
  maxResults: 50000  # Adjust this number based on the server's limit
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

# Generate a unique name for the query
query_name = f"LastWeekNews_{int(time.time())}_{random.randint(1000, 9999)}"

data = {
    "query": query_yaml,
    "name": query_name,
    "comment": "Alle Nachrichten aus der letzten Woche",
    "expirationDate": str(end_date + datetime.timedelta(days=5))
}

# Send the request to the API
r = requests.post(
    API_URL_QUERY,
    headers=headers,
    data=data
)

if r.status_code == 200:
    query_id = r.json().get("queryId")

    # Check the status of the query
    while True:
        status_response = requests.get(f"{API_URL_STATUS}/{query_id}", headers=headers)
        status = status_response.json()[0]

        if status.get('status') == 'finished':
            download_url = status.get('downloadUrl')
            print(f"Downloading from: {download_url}")
            filename = download_url.split("/")[-1]

            d = requests.get(
                download_url,
                headers=headers)

            if d.status_code == 200:
                print("Size of file: %.2f KB" % (len(d.content) / 1024))

                # Define the raw_data folder path
                raw_data_folder = './raw_data'
                # Ensure the folder exists
                os.makedirs(raw_data_folder, exist_ok=True)
                file_path = os.path.join(raw_data_folder, filename)

                fp = open(f"./{file_path}", "wb")
                fp.write(d.content)
                fp.close()
            else:
                print(d.text)

            break

        else:
            print("Job still running...")
            time.sleep(5)
else:
    print(f"Failed to submit query. Status code: {r.status_code}")