import requests
import json
url = 'http://localhost:8000/extraction/priority-documents'
headers = {'X-API-KEY': '4TOaTIKu64Dea4Kj0YmEH3bOF3K1ip9005NmXweWyes'}
r = requests.get(url, headers=headers, timeout=10)
print('status', r.status_code)
print(r.text)
try:
    print(json.dumps(r.json(), indent=2, ensure_ascii=False))
except Exception:
    pass
