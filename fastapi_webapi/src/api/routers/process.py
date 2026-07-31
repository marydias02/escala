from fastapi import APIRouter, Depends

from api.dependencies.security import verify_api_key
from api.dependencies.services import ProcessServiceDep
from api.messages.store import ProcessRead

router = APIRouter(prefix="/processes", tags=["processes"], dependencies=[Depends(verify_api_key)])


@router.get("", summary="List processes")
async def list_processes(service: ProcessServiceDep, limit: int = 100) -> list[ProcessRead]:
    """
    List ingested processes, most recently received first.

    - **limit**: Maximum number of processes to return (default: 100)
    """
    rows = await service.list_processes(limit=limit)
    return [ProcessRead.model_validate(r) for r in rows]
