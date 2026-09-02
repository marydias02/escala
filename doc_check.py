import requests
import json
from dotenv import load_dotenv
import os

if __name__ == "__main__":
    load_dotenv("./plotly_webapp/.env")
    headers = {"X-API-KEY": os.environ.get("API_KEY")}
    doc_id = "03072d38-c155-434b-883e-5806563f4bf5"
    for url in [
        f"http://localhost:8000/extraction/documents/{doc_id}",
        f"http://localhost:8000/extraction/documents/{doc_id}/email",
    ]:
        print(url)
        r = requests.get(url, headers=headers, timeout=10)
        print(r.status_code)
        try:
            print(json.dumps(r.json(), indent=2, ensure_ascii=False))
        except Exception:
            print(r.text)
