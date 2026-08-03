import asyncio
import json

from api.exceptions import NotFoundError
from api.repositories.extraction_repository import DocumentsRepository, ExtractionBigNumbers


class ExtractionService:
    def __init__(self):
        self.big_numbers = ExtractionBigNumbers()
        self.documents = DocumentsRepository()

    async def list_priority_documents(self, limit: int = 100) -> list[dict]:
        df = await self.documents.list_priority_documents(limit=limit)
        return df.to_dicts()

    async def list_all_documents(self, limit: int = 100) -> list[dict]:
        df = await self.documents.list_all_documents(limit=limit)
        return df.to_dicts()

    async def get_document(self, document_id: str) -> dict:
        row = await self.documents.get_document(document_id)
        if not row:
            raise NotFoundError(f"Document with ID {document_id} not found")

        content = json.loads(row["document_content"]) if row["document_content"] else {}
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
