from fastapi import APIRouter, Depends

from api.dependencies.security import verify_api_key
from api.dependencies.services import ValidationServiceDep

router = APIRouter(prefix="/validation", tags=["validation"], dependencies=[Depends(verify_api_key)])



@router.get("/documents", summary="Get all documents")
async def get_all_documents(service: ValidationServiceDep, limit: int = 100) -> list[dict]:
    """
    All documents, most recently received first.

    - **limit**: Maximum number of documents to return (default: 100)
    """
    rows = await service.list_all_documents(limit=limit)
    return rows

