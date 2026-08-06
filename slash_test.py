import requests
for url in ['http://localhost:8000/extraction','http://localhost:8000/extraction/']:
    try:
        r=requests.get(url, timeout=5)
        print(url, r.status_code, r.text)
    except Exception as e:
        print(url, 'ERROR', e)
