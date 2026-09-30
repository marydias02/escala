from typing import Annotated

from fastapi import APIRouter, Query

from api.dependencies.security import has_authorization_for
from api.dependencies.services import HarborServiceDep

router = APIRouter(prefix="/harbor", tags=["harbor"])

READ_HARBOR = has_authorization_for("read", "harbor")
LimitParam = Annotated[int, Query(ge=1, le=2000)]


@router.get("/accounts", summary="List Harbor accounts", dependencies=[READ_HARBOR])
async def list_accounts(service: HarborServiceDep) -> list[str]:
    return await service.list_accounts()


@router.get("/dashboard", summary="Get Harbor dashboard data", dependencies=[READ_HARBOR])
async def get_dashboard(
    service: HarborServiceDep, account: str | None = None, limit: LimitParam = 500
) -> dict:
    """Return account-filtered payment rows and dashboard indicators."""
    return {
        "account_ids": await service.list_accounts(),
        "indicators": await service.get_dashboard(account),
        "transactions": await service.list_payments(account, limit),
    }


@router.get("/payments", summary="List Harbor payments", dependencies=[READ_HARBOR])
async def list_payments(
    service: HarborServiceDep, account: str | None = None, limit: LimitParam = 500
) -> list[dict]:
    return await service.list_payments(account=account, limit=limit)


@router.get("/ingestion/messages", summary="List Harbor ingestion messages", dependencies=[READ_HARBOR])
async def list_ingestion_messages(service: HarborServiceDep, limit: LimitParam = 500) -> list[dict]:
    return await service.list_ingestion_messages(limit=limit)


@router.get("/payments/{payment_id}/reconciliation", summary="Get payment reconciliation", dependencies=[READ_HARBOR])
async def get_reconciliation(service: HarborServiceDep, payment_id: str) -> dict:
    return await service.get_reconciliation(payment_id)
