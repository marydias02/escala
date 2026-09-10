import asyncio
import json

from azure.core.exceptions import ResourceNotFoundError
from loguru import logger

from api.exceptions import NotFoundError
from api.repositories.extraction_repository import (
    BusinessUnitRepository,
    DocumentsRepository,
    ExtractionBigNumbers,
    ProcessesRepository,
)
from invoice_extraction.decisions import INGEST, MANUAL, close_process_after_manual_send
from invoice_extraction.sap_pipeline import STATUS_BOOKED, book_document
from utils.blob_storage import download_document_bytes


class ExtractionService:
    def __init__(self):
        self.big_numbers = ExtractionBigNumbers()
        self.documents = DocumentsRepository()
        self.processes = ProcessesRepository()
        self.business_units = BusinessUnitRepository()
        self.processes = ProcessesRepository()

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

    async def get_document_pdf_bytes(self, document_id: str) -> bytes:
        blob_key = await self.documents.get_file_path(document_id)
        if not blob_key:
            raise NotFoundError(f"No PDF available for document {document_id}")
        try:
            return await asyncio.to_thread(download_document_bytes, blob_key)
        except ResourceNotFoundError:
            # Documents processed before the blob migration have a local-only path.
            raise NotFoundError(
                f"PDF not found in blob storage for document {document_id} (key {blob_key!r}). "
                "Documents processed before the blob migration are only on the pipeline host."
            )

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
        action: str | None = None,
        status: str | None = None,
        last_modified_by: str | None = None,
    ) -> dict:
        row = await self.documents.get_document(document_id)
        if not row:
            raise NotFoundError(f"Document with ID {document_id} not found")

        content = document_content
        if not isinstance(content, str):
            content = json.dumps(content)

        previous_action = row.get("action")
        action = action or previous_action
        status = status or "Sob Revisão"

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

        sap_booked = False
        process_closed = False
        if previous_action == MANUAL and action == INGEST:
            sap_booked, process_closed = await self._send_to_sap(document_id, row.get("document_type"), updated_content)

        po_list = updated_content.pop("po_list", None) or []

        return {
            "document_id": updated_row["document_id"],
            "alerts": updated_row.get("alerts_list") or [],
            "fields": updated_content,
            "po_list": po_list,
            "action": updated_row.get("action"),
            "status": STATUS_BOOKED if sap_booked else updated_row.get("status"),
            "sap_booked": sap_booked,
            "process_closed": process_closed,
        }

    async def _send_to_sap(
        self, document_id: str, document_type: str | None, document_content: dict
    ) -> tuple[bool, bool]:
        """Book a manually validated document, then close its process if nothing
        else is owed. Returns (booked, process_closed).

        Best-effort: the document is already saved, so a booking or closing
        failure must not fail the request. An unbooked document keeps
        `status = "Criado"` and stays eligible for the bulk `sap_pipeline` run.
        """
        booking_row = {
            "document_id": document_id,
            "document_type": document_type,
            "document_content": document_content,
        }

        try:
            outcome = await book_document(booking_row)
        except Exception as exc:  # noqa: BLE001 - the save stands regardless
            logger.error(f"SAP booking failed for document {document_id}: {exc}")
            return False, False

        if outcome.status != STATUS_BOOKED:
            logger.warning(f"SAP did not book document {document_id}")
            return False, False

        await self.documents.set_status(document_id, STATUS_BOOKED)

        try:
            return True, await self._close_process_if_settled(document_id)
        except Exception as exc:  # noqa: BLE001 - the booking stands regardless
            logger.error(f"Closing the process of document {document_id} failed: {exc}")
            return True, False

    async def _close_process_if_settled(self, document_id: str) -> bool:
        """Close the document's process once all of its documents are terminal."""
        process_id = await self.documents.get_process_id(document_id)
        if not process_id:
            return False

        documents = await self.documents.list_process_document_states(process_id)
        if not close_process_after_manual_send(documents):
            return False

        closed = await self.processes.close(process_id)
        if closed:
            logger.info(f"Process {process_id} closed after a manual send to SAP")
        return closed

    async def business_unit_exists(self, vat: str) -> bool:
        return await self.business_units.exists_by_vat(vat)

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
