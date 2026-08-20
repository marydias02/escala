import asyncio
import json
from pathlib import Path
from typing import Optional

from api.exceptions import NotFoundError
from api.repositories.extraction_repository import DocumentsRepository, ExtractionBigNumbers
from invoice_extraction.config import PROCESSED_EMAILS_DIR #temporary, while there is no access to blob storage


class ExtractionService:
    def __init__(self):
        self.big_numbers = ExtractionBigNumbers()
        self.documents = DocumentsRepository()

    async def list_priority_documents(self, limit: int = 100) -> list[dict]:
        df = await self.documents.list_priority_documents(limit=limit)
        return df.to_dicts()

    async def get_next_priority_document(self, document_id: str) -> dict:
        result = await self.documents.get_next_priority_document(document_id)
        if not result:
            raise NotFoundError(f"Document with ID {document_id} not found")
        return result

    async def list_all_documents(self, limit: int = 100) -> list[dict]:
        df = await self.documents.list_all_documents(limit=limit)
        return df.to_dicts()
    
    async def list_pending_documents(self, limit: int = 100) -> list[dict]:
        df = await self.documents.list_pending_documents(limit=limit)
        return df.to_dicts()

    async def get_document(self, document_id: str) -> dict:
        row = await self.documents.get_document(document_id)
        if not row:
            raise NotFoundError(f"Document with ID {document_id} not found")

        content_value = row["document_content"]
        if isinstance(content_value, str):
            content = json.loads(content_value) if content_value else {}
        else:
            content = content_value or {}
        po_list = content.pop("po_list", None) or []

        return {
            "document_id": row["document_id"],
            "alerts": row["alerts_list"] or [],
            "fields": content,
            "po_list": po_list,
            "action": row.get("action"),
            "status": row.get("status"),
        }
#TODO: This method is temporary, while there is no access to blob storage.
# When blob storage is available, it only needs to retrun the path (no need for Processed Emails dir) and the PDF will be retrieved from blob storage.
#
# async def get_document_pdf_stream(self, document_id: str):
#     blob_key = await self.documents.get_file_path(document_id)
#     if not blob_key:
#         raise NotFoundError(f"No PDF available for document {document_id}")
#     try:
#         return await blob_client.download_blob(blob_key)  # returns bytes or an async iterator
#     except BlobNotFoundError:
#         raise NotFoundError(f"PDF file missing in blob storage for document {document_id}")

    async def get_document_pdf_path(self, document_id: str) -> Path:
        relative_path = await self.documents.get_file_path(document_id)
        if not relative_path:
            raise NotFoundError(f"No PDF available for document {document_id}")
        full_path = PROCESSED_EMAILS_DIR / relative_path
        if not full_path.is_file():
            raise NotFoundError(f"PDF file missing on disk for document {document_id}")
        return full_path

    async def get_document_email(self, document_id: str) -> dict:
        row = await self.documents.get_document_email(document_id)
        if not row:
            raise NotFoundError(f"Document with ID {document_id} not found")
        return row
    
    async def alter_document_details(
        self,
        document_id: str,
        alerts_list: list[str],
        document_content: dict,
        action: Optional[str] = None,
        status: Optional[str] = None,
        last_modified_by: Optional[str] = None,
    ) -> dict:
        row = await self.documents.get_document(document_id)
        if not row:
            raise NotFoundError(f"Document with ID {document_id} not found")

        content = document_content
        if not isinstance(content, str):
            content = json.dumps(content)

        action = action or row.get("action")
        status = status or "Sob Revisão"
        last_modified_by = last_modified_by

        data = {
            "document_id": document_id,
            "alerts_list": alerts_list,
            "document_content": content,
            "action": action,
            "status": status,
            "last_modified_by": last_modified_by,
        }

        updated_row = await self.documents.alter(data)
        updated_content_value = updated_row.get("document_content")
        if isinstance(updated_content_value, str):
            updated_content = json.loads(updated_content_value) if updated_content_value else {}
        else:
            updated_content = updated_content_value or {}

        po_list = updated_content.pop("po_list", None) or []

        return {
            "document_id": updated_row["document_id"],
            "alerts": updated_row.get("alerts_list") or [],
            "fields": updated_content,
            "po_list": po_list,
            "action": updated_row.get("action"),
            "status": updated_row.get("status"),
        }

    async def get_extraction_big_numbers(self) -> dict:
        (
            pending_manual_validation,
            first_manual_by_week,
            auto_ingested_by_week,
            returned_by_week,
        ) = await asyncio.gather(
            self.big_numbers.count_pending_manual_validation(),
            self.big_numbers.count_first_manual_by_week(),
            self.big_numbers.count_auto_ingested_by_week(),
            self.big_numbers.count_returned_to_supplier_by_week(),
        )

        return {
            "pending_manual_validation": {
                "value": pending_manual_validation,
                "delta_pp": _count_wow_delta(first_manual_by_week),
            },
            "auto_ingested": _pct_with_wow_delta(auto_ingested_by_week),
            "returned_to_supplier": _pct_with_wow_delta(returned_by_week),
        }


def _percentage(matched: int, total: int) -> float:
    return round(matched / total * 100, 2) if total else 0.0


def _pct_with_wow_delta(by_week: dict[str, tuple[int, int]]) -> dict:
    current_pct = _percentage(*by_week["current"])
    previous_pct = _percentage(*by_week["previous"])
    return {
        "pct": current_pct,
        "delta_pp": round(current_pct - previous_pct, 2),
    }


def _count_wow_delta(by_week: dict[str, tuple[int, int]]) -> float:
    """Percent change in the MATCHED count, current week vs previous week.

    `by_week` values are (matched, total); only `matched` (documents whose
    first_action was MANUAL) matters here — there is no ratio to take, unlike
    `_pct_with_wow_delta`.
    """
    current_count, _ = by_week["current"]
    previous_count, _ = by_week["previous"]
    if not previous_count:
        return 0.0
    return round((current_count - previous_count) / previous_count * 100, 2)
