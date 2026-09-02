import requests
import json
from dotenv import load_dotenv
import os

if __name__ == "__main__":
    load_dotenv("./plotly_webapp/.env")
    url = "http://localhost:8000/extraction"
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": os.environ.get("API_KEY"),
    }
    payload = {
        "document_id": "03072d38-c155-434b-883e-5806563f4bf5",
        "alerts_list": [
            "Campo em falta: NIF do cliente",
            "Confian\\u00e7a baixa: Data de emiss\\u00e3o (0.60)",
            "Confian\\u00e7a baixa: Moeda (0.60)",
            "Nota de encomenda n\\u00e3o encontrada: 4700037142",
        ],
        "document_content": {
            "bu_id": None,
            "bu_vat": None,
            "bu_name": {
                "value": "MARMOD CABO VERDE - AGÊNCIA E TRÂNSITO LDA",
                "confidence": 0.7,
            },
            "currency": {"value": "CVE", "confidence": 0.6},
            "issue_date": {"value": "23-06-2026", "confidence": 0.6},
            "vat_amount": {"value": 72.0, "confidence": 0.8},
            "base_amount": {"value": 478.0, "confidence": 0.8},
            "supplier_id": None,
            "supplier_vat": {"value": "PT268786102", "confidence": 0.9},
            "total_amount": {"value": 550.0, "confidence": 0.9},
            "supplier_name": {
                "value": "NILO - SOC. PROD. E COM. DE REFRIG E BEBIDAS, SA",
                "confidence": 0.85,
            },
            "document_number": {"value": "FRN 2026/1690", "confidence": 0.8},
        },
    }
    res = requests.patch(url, headers=headers, json=payload)
    print("status", res.status_code)
    try:
        print(json.dumps(res.json(), indent=2, ensure_ascii=False))
    except Exception:
        print(res.text)
