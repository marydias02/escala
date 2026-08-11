import requests

BASE_URL = "http://localhost:8000"

HEADERS = {
    "X-API-KEY": "4TOaTIKu64Dea4Kj0YmEH3bOF3K1ip9005NmXweWyes"
}

def get_big_numbers():
    response = requests.get(
        f"{BASE_URL}/extraction/big-numbers",
        headers=HEADERS,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()
  
  
def get_priority_documents():
    response = requests.get(
        f"{BASE_URL}/extraction/priority-documents",
        headers=HEADERS,
        timeout=10,
    )
    response.raise_for_status()
    rows = response.json()

    for row in rows:
        created_at = row.get("created_at")
        if created_at:
            row["created_at"] = created_at[:16].replace("T", " ")

    return rows

  
def get_all_documents():
    response = requests.get(
        f"{BASE_URL}/extraction/documents",
        headers=HEADERS,
        timeout=10,
    )
    response.raise_for_status()
    rows = response.json()
    
    for row in rows:
        created_at = row.get("created_at")
        if created_at:
            row["created_at"] = created_at[:16].replace("T", " ")

    return rows
  
  
def get_pending_documents():
    response = requests.get(
        f"{BASE_URL}/extraction/pending-documents",
        headers=HEADERS,
        timeout=10,
    )
    response.raise_for_status()
    rows = response.json()
    
    for row in rows:
        created_at = row.get("created_at")
        if created_at:
            row["created_at"] = created_at[:16].replace("T", " ")

    return rows
  
  
def get_document_details(doc_id: str):
    response = requests.get(
        f"{BASE_URL}/extraction/documents/{doc_id}",
        headers=HEADERS,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def alter_document_details(
    document_id: str,
    alerts_list: list[str],
    document_content: dict,
    action: str | None = None,
    status: str | None = None,
    last_modified_by: str | None = None,
):
    payload = {
        "document_id": document_id,
        "alerts_list": alerts_list,
        "document_content": document_content,
    }
    if action is not None:
        payload["action"] = action
    if status is not None:
        payload["status"] = status
    if last_modified_by is not None:
        payload["last_modified_by"] = last_modified_by

    response = requests.patch(
        f"{BASE_URL}/extraction",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def get_next_priority_document(document_id: str):
    response = requests.get(
        f"{BASE_URL}/extraction/next-priority-document/{document_id}",
        headers=HEADERS,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()