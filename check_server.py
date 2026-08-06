import requests
url='http://localhost:8000/extraction/big-numbers'
headers={'X-API-KEY':'4TOaTIKu64Dea4Kj0YmEH3bOF3K1ip9005NmXweWyes'}
try:
    r=requests.get(url, headers=headers)
    print('status', r.status_code)
    print(r.text)
except Exception as e:
    print('error', e)
