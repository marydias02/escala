"""Validation dashboard endpoints: the big-numbers tiles and the document list
backing the manual-validation screen."""

from fastapi import APIRouter

from api.dependencies.security import has_authorization_for
from api.dependencies.services import ValidationServiceDep
from api.messages.store import SapMessageRead, ValidationBigNumbersDict

router = APIRouter(prefix="/validation", tags=["validation"])

READ_DOCUMENTS = has_authorization_for("read", "documents")


@router.get("/big-numbers", summary="Get validation dashboard indicators", dependencies=[READ_DOCUMENTS])
async def get_validation_big_numbers(service: ValidationServiceDep) -> ValidationBigNumbersDict:
    """
    Top indicator tiles for the validation dashboard. Each value is bucketed by
    the week the process was created in SAP (`added_in_sap_timestamp`), with the
    standard week-over-week % change: (current - previous) / previous * 100.

    - **non_conforming_received**: non-conforming processes received this week,
      excluding those fully auto-processed (status = "Processamento automático")
    - **needs_manual_validation**: processes currently at status = "Necessita de
      validação manual"
    - **processed_by_agent**: processes currently at status = "Processado pelo agente"
    - **with_buyer**: processes currently being resolved by the buyer
      (status = "Em resolução pelo buyer")
    """
    return await service.get_validation_big_numbers()  # type: ignore


@router.get("/documents", summary="Get all documents", dependencies=[READ_DOCUMENTS])
async def get_all_documents(service: ValidationServiceDep, limit: int = 100) -> list[dict]:
    """
    All documents, most recently received first.

    - **limit**: Maximum number of documents to return (default: 100)
    """
    rows = await service.list_all_documents(limit=limit)
    return rows


@router.get(
    "/{process_ref_no}/messages",
    summary="Get the message log of a SAP process",
    dependencies=[has_authorization_for("read", "processes")],
)
async def get_process_messages(process_ref_no: str, service: ValidationServiceDep) -> list[SapMessageRead]:
    """
    Messages exchanged during a SAP process, oldest first.

    - **process_ref_no**: the `sap_processes.reference_no` the messages belong to

    Returns an empty list when the process has no messages or does not exist.
    """
    rows = await service.list_process_messages(process_ref_no)
    return [SapMessageRead(**row) for row in rows]
