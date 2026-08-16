import requests, json
url='http://localhost:8000/openapi.json'
headers={'X-API-KEY':'4TOaTIKu64Dea4Kj0YmEH3bOF3K1ip9005NmXweWyes'}
res=requests.get(url, headers=headers, timeout=10)
print(res.status_code)
if res.status_code == 200:
    data = res.json()
    path = data['paths'].get('/extraction', {})
    patch = path.get('patch')
    print(json.dumps(patch, indent=2, ensure_ascii=False))
else:
    print(res.text)
