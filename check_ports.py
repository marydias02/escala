import requests
urls = [
    'http://localhost:8000/openapi.json',
    'http://localhost:8080/openapi.json',
    'http://localhost:8000/extraction',
    'http://localhost:8080/extraction'
]
for url in urls:
    try:
        r = requests.get(url, timeout=5)
        print(url, r.status_code)
        print(r.text[:200])
    except Exception as e:
        print(url, 'ERROR', e)
