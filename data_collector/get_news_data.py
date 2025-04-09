import requests
import datetime
import os
import random
import time
from dotenv import load_dotenv


def fetch_swissdox_data(start_date=None, end_date=None, save_folder='./raw_data'):
    # Load environment variables
    load_dotenv(dotenv_path='../../WAVE/.env')

    headers = {
        "X-API-Key": os.getenv("SWISSDOX_KEY"),
        "X-API-Secret": os.getenv("SWISSDOX_SECRET")
    }

    API_BASE_URL = "https://swissdox.linguistik.uzh.ch/api"
    API_URL_QUERY = f"{API_BASE_URL}/query"
    API_URL_STATUS = f"{API_BASE_URL}/status"



    used_sources = [
        "ZWA", "ZWAF", "ZWAO", "ZWAS", "ZWSO", "HEU", "HEUL", "HEUC", "HEUN", "HEUR", "NNHEU",
        "APO", "TAB", "AT", "AZ", "AZM", "APPZ", "BT", "BLZ", "BZM", "BAZA", "BAZM", "BEOL",
        "BRS", "BZ", "BBLI", "BLIA", "BU", "LB", "WEW", "WOZ", "TAE", "SHZ", "LAT", "ESV",
        "LPNV", "LPRC", "LTB", "LTZ", "MLZ", "CAMP", "NEWS", "NZZS", "NLZ", "NZZ", "NN",
        "NNTZ", "NIW", "OBW", "OLT", "PHRC", "SWO", "NMZ", "SOZ", "SOZM", "SGT", "TA", "THT",
        "TZ", "TBT", "WZ", "URZ", "ZOF", "ZN", "ZUGZ", "ZHUL", "ZUGB", "AZO", "BTO", "NZZB",
        "BLIO", "BLIAO", "SHZO", "LTZO", "NZZO", "OLTO", "SGTO", "NNTA", "ZSZO", "TAZT"
    ]

    query_yaml = f"""
query:
  sources: {used_sources}
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

    query_name = f"LastWeekNews_{int(time.time())}_{random.randint(1000, 9999)}"

    data = {
        "query": query_yaml,
        "name": query_name,
        "comment": "Alle Nachrichten aus dem angegebenen Zeitraum"
    }

    response = requests.post(API_URL_QUERY, headers=headers, data=data)

    if response.status_code != 200:
        print(f"Fehler beim Senden der Anfrage: {response.status_code}")
        return None

    query_id = response.json().get("queryId")
    print(f"Query ID: {query_id}")

    while True:
        status_response = requests.get(f"{API_URL_STATUS}/{query_id}", headers=headers)
        status_data = status_response.json()[0]

        if status_data.get('status') == 'finished':
            download_url = status_data.get('downloadUrl')
            print(f"Download-Link: {download_url}")
            filename = download_url.split("/")[-1]

            file_response = requests.get(download_url, headers=headers)
            if file_response.status_code == 200:
                os.makedirs(save_folder, exist_ok=True)



                file_path = os.path.join(save_folder, filename)
                with open(file_path, "wb") as f:
                    f.write(file_response.content)
                print(f"Datei erfolgreich gespeichert unter: {file_path}")
                print("Dateigröße: %.2f KB" % (len(file_response.content) / 1024))
                return file_path
            else:
                print(f"Fehler beim Herunterladen: {file_response.status_code}")
                print(file_response.text)
                return None
        else:
            print("Abfrage läuft noch...")
            time.sleep(5)



