from fastapi import APIRouter, Depends

from api.dependencies.security import verify_api_key
from api.dependencies.services import ExtractionServiceDep
from api.messages.store import DocumentDetailRead, DocumentEmailRead, DocumentRead, ExtractionBigNumbersDict

router = APIRouter(prefix="/extraction", tags=["extraction"], dependencies=[Depends(verify_api_key)])


@router.get("/big-numbers", summary="Get extraction dashboard indicators")
async def get_extraction_big_numbers(service: ExtractionServiceDep) -> ExtractionBigNumbersDict:
    """
    Top indicator tiles for the extraction dashboard.

    - **pending_manual_validation**: documents currently awaiting manual validation
    - **auto_ingested**: % of this week's documents auto-ingested into SAP, with the
      week-over-week change in percentage points
    - **returned_to_supplier**: % of this week's documents sent back to the supplier,
      with the week-over-week change in percentage points
    """
    return await service.get_extraction_big_numbers()  # type: ignore


@router.get("/priority-documents", summary="Get priority documents")
async def get_priority_documents(service: ExtractionServiceDep, limit: int = 100) -> list[DocumentRead]:
    """
    Documents awaiting manual validation, most recently received first.

    - **limit**: Maximum number of documents to return (default: 100)
    """
    rows = await service.list_priority_documents(limit=limit)
    return [DocumentRead.model_validate(r) for r in rows]


@router.get("/documents", summary="Get all documents")
async def get_all_documents(service: ExtractionServiceDep, limit: int = 100) -> list[DocumentRead]:
    """
    All documents, most recently received first.

    - **limit**: Maximum number of documents to return (default: 100)
    """
    rows = await service.list_all_documents(limit=limit)
    return [DocumentRead.model_validate(r) for r in rows]


@router.get("/documents/{document_id}", summary="Get document details")
async def get_document(service: ExtractionServiceDep, document_id: str) -> DocumentDetailRead:
    """
    Alerts and extracted field values (with confidence) for one document.

    - **document_id**: Document ID
    """
    result = await service.get_document(document_id)
    return DocumentDetailRead.model_validate(result)


@router.get("/documents/{document_id}/email", summary="Get the source email for a document")
async def get_document_email(service: ExtractionServiceDep, document_id: str) -> DocumentEmailRead:
    """
    Sender, subject, content and reception date of the email that carried this document.

    - **document_id**: Document ID
    """
    result = await service.get_document_email(document_id)
    return DocumentEmailRead.model_validate(result)