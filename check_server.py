import requests
from dotenv import load_dotenv
import os

if __name__ == "__main__":
    load_dotenv("./plotly_webapp/.env")
    url = "http://localhost:8000/extraction/big-numbers"
    headers = {"X-API-KEY": os.environ.get("API_KEY")}
    try:
        r = requests.get(url, headers=headers)
        print("status", r.status_code)
        print(r.text)
    except Exception as e:
        print("error", e)
