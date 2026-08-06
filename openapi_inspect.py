import requests, json
url = 'http://localhost:8000/openapi.json'
r = requests.get(url, timeout=10)
print('status', r.status_code)
if r.status_code == 200:
    data = r.json()
    for path in ['/extraction', '/extraction/documents/{document_id}', '/extraction/documents', '/extraction/priority-documents', '/extraction/pending-documents']:
        print(path, 'in schema' if path in data.get('paths', {}) else 'NOT in schema')
    print('PATCH /extraction methods:', list(data['paths'].get('/extraction', {}).keys()))
    if '/extraction' in data['paths']:
        print(json.dumps(data['paths']['/extraction'], indent=2)[:1000])
else:
    print(r.text)
