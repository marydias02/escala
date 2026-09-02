import requests
import json
from dotenv import load_dotenv
import os

if __name__ == "__main__":
    load_dotenv("./plotly_webapp/.env")
    url = "http://localhost:8000/extraction/priority-documents"
    headers = {"X-API-KEY": os.environ.get("API_KEY")}
    r = requests.get(url, headers=headers, timeout=10)
    print("status", r.status_code)
    print(r.text)
    try:
        print(json.dumps(r.json(), indent=2, ensure_ascii=False))
    except Exception:
        pass
