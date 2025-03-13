import requests
import datetime
import os
import random
import time
from dotenv import load_dotenv

# .env-Datei laden
load_dotenv()

# API-Zugangsdaten aus Umgebungsvariablen
headers = {
    "X-API-Key": os.getenv("SWISSDOX_KEY"),
    "X-API-Secret": os.getenv("SWISSDOX_SECRET")
}

API_BASE_URL = "https://swissdox.linguistik.uzh.ch/api"
API_URL_QUERY = f"{API_BASE_URL}/query"
API_URL_STATUS = f"{API_BASE_URL}/status"
API_URL_DOWNLOAD = f"{API_BASE_URL}/download"

# Berechnung des Zeitraums der letzten Woche
end_date = datetime.date.today()
start_date = end_date - datetime.timedelta(days=7)

# Formatieren der Daten im gewünschten Format (YYYY-MM-DD)
start_date_str = start_date.strftime("%Y-%m-%d")
end_date_str = end_date.strftime("%Y-%m-%d")

# Erstellen der YAML-Abfrage mit den formatierten Start- und Enddaten
query_yaml = f"""
query:
  dates:
    - from: {start_date_str}
      to: {end_date_str}
  languages:
    - de
result:
  format: TSV
  maxResults: 10000000
  columns:
    - id
    - pubtime
    - medium_code
    - medium_name
    - rubric
    - regional
    - doctype
    - doctype_description
    - language
    - char_count
    - dateline
    - head
    - subhead
    - article_link
    - content_id
    - content
version: 1.2
"""

# Generiere einen einzigartigen Namen für die Query
query_name = f"LastWeekNews_{int(time.time())}_{random.randint(1000, 9999)}"

data = {
    "query": query_yaml,
    "name": query_name,
    "comment": "Alle Nachrichten aus der letzten Woche",
    "expirationDate": str(end_date + datetime.timedelta(days=30))
}

# Senden der Anfrage an die API
r = requests.post(
    API_URL_QUERY,
    headers=headers,
    data=data
)


import requests
import time

# Assuming you already have the status check logic in place
if r.status_code == 200:
    query_id = r.json().get("queryId")

    # Check the status of the query
    while True:
        status_response = requests.get(f"{API_URL_STATUS}/{query_id}", headers=headers)
        status = status_response.json()[0]

        if status.get('status') == 'finished':
            download_url = status.get('downloadUrl')

            if download_url:
                print(f"Download URL: {download_url}")  # Print the URL to verify

                # Directly download the file from the download URL
                download_response = requests.get(download_url, headers=headers)

                # Check if the download was successful
                if download_response.status_code == 200:
                    # Save the file in the current directory
                    file_name = download_url.split("/")[-1]  # Get the file name from the URL
                    with open(file_name, "wb") as file:
                        file.write(download_response.content)
                    print(f"Download complete. File saved as {file_name}")
                else:
                    print(f"Error downloading the file. Status code: {download_response.status_code}")
            else:
                print("Download URL not found.")
            break
        else:
            print("Job still running...")
            time.sleep(5)
else:
    print(f"Failed to submit query. Status code: {r.status_code}")
