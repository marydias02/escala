import os
from dotenv import load_dotenv
import requests
import json

if __name__ == "__main__":
    load_dotenv("./plotly_webapp/.env")
    url = "http://localhost:8000/openapi.json"
    headers = {"X-API-KEY": os.environ.get("API_KEY")}
    res = requests.get(url, headers=headers, timeout=10)
    print(res.status_code)
    if res.status_code == 200:
        data = res.json()
        path = data["paths"].get("/extraction", {})
        patch = path.get("patch")
        print(json.dumps(patch, indent=2, ensure_ascii=False))
    else:
        print(res.text)
