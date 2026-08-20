from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from api.dependencies.security import verify_api_key
from api.dependencies.services import ExtractionServiceDep
from api.messages.store import (
    DocumentDetailRead,
    DocumentEmailRead,
    DocumentRead,
    DocumentUpdate,
    ExtractionBigNumbersDict,
    NextPriorityDocumentRead,
)

router = APIRouter(prefix="/extraction", tags=["extraction"], dependencies=[Depends(verify_api_key)])


@router.get("/big-numbers", summary="Get extraction dashboard indicators")
async def get_extraction_big_numbers(service: ExtractionServiceDep) -> ExtractionBigNumbersDict:
    """
    Top indicator tiles for the extraction dashboard.

    - **pending_manual_validation**: documents currently awaiting manual validation,
      with the week-over-week % change in documents first sent to manual validation
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


@router.get(
    "/next-priority-document/{document_id}",
    summary="Get the next priority document",
)
async def get_next_priority_document(
    service: ExtractionServiceDep, document_id: str
) -> NextPriorityDocumentRead:
    """Return whether the current document is eligible for manual validation and
    the next document in the priority queue, if one exists.
    """
    result = await service.get_next_priority_document(document_id)
    return NextPriorityDocumentRead.model_validate(result)


@router.get("/documents", summary="Get all documents")
async def get_all_documents(service: ExtractionServiceDep, limit: int = 100) -> list[DocumentRead]:
    """
    All documents, most recently received first.

    - **limit**: Maximum number of documents to return (default: 100)
    """
    rows = await service.list_all_documents(limit=limit)
    return [DocumentRead.model_validate(r) for r in rows]


@router.get("/pending-documents", summary="Get pending documents")
async def get_pending_documents(service: ExtractionServiceDep, limit: int = 100) -> list[DocumentRead]:
    """
    Documents awaiting a response, most recently received first.

    - **limit**: Maximum number of documents to return (default: 100)
    """
    rows = await service.list_pending_documents(limit=limit)
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

#TODO: This method is temporary, while there is no access to blob storage.
# With acess to blob storage, would need a file response from the blob
#Implementation for blob storage would be like:
#
# @router.get("/documents/{document_id}/pdf", summary="Get the source PDF for a document")
# async def get_document_pdf(service: ExtractionServiceDep, document_id: str) -> StreamingResponse:
#     """
#     The invoice PDF for one document, streamed from blob storage.
#
#     - **document_id**: Document ID
#     """
#     stream = await service.get_document_pdf_stream(document_id)  # blob client .download_blob() -> bytes/iterator
#     return StreamingResponse(stream, media_type="application/pdf")


@router.get("/documents/{document_id}/pdf", summary="Get the source PDF for a document")
async def get_document_pdf(service: ExtractionServiceDep, document_id: str) -> FileResponse:
    """
    The invoice PDF for one document, as stored on disk (local emulation of blob storage).

    - **document_id**: Document ID
    """
    path = await service.get_document_pdf_path(document_id)
    return FileResponse(path, media_type="application/pdf")


@router.patch("", status_code=201, summary="Alter the details of a document")
async def alter_document_details(
    service: ExtractionServiceDep, payload: DocumentUpdate
) -> DocumentDetailRead:
    """
    Alter the details of a document.

    - **document_id**: Document ID
    - **alerts_list**: List of alerts
    - **document_content**: Document content
    - **action**: Optional action value
    - **status**: Optional status value
    - **last_modified_by**: Optional modifier name
    """
    result = await service.alter_document_details(
        payload.document_id,
        payload.alerts_list,
        payload.document_content,
        action=payload.action,
        status=payload.status,
        last_modified_by=payload.last_modified_by,
    )
    return DocumentDetailRead.model_validate(result)
