import asyncio
import json
from typing import Optional

from api.exceptions import NotFoundError
from api.repositories.extraction_repository import DocumentsRepository, ExtractionBigNumbers


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
        }

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
        }

    async def get_extraction_big_numbers(self) -> dict:
        pending_manual_validation, auto_ingested_by_week, returned_by_week = await asyncio.gather(
            self.big_numbers.count_pending_manual_validation(),
            self.big_numbers.count_auto_ingested_by_week(),
            self.big_numbers.count_returned_to_supplier_by_week(),
        )

        return {
            "pending_manual_validation": pending_manual_validation,
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
