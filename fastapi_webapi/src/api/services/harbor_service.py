from api.exceptions import NotFoundError
from api.repositories.harbor_repository import HarborRepository


class HarborService:
    def __init__(self):
        self.repository = HarborRepository()

    async def list_accounts(self) -> list[str]:
        return await self.repository.list_accounts()

    async def list_payments(self, account: str | None = None, limit: int = 500) -> list[dict]:
        return await self.repository.list_payments(account=account, limit=limit)

    async def get_dashboard(self, account: str | None = None) -> dict:
        return await self.repository.get_dashboard_indicators(account=account)

    async def list_ingestion_messages(self, limit: int = 500) -> list[dict]:
        return await self.repository.list_email_messages(limit=limit)

    async def get_reconciliation(self, payment_id: str) -> dict:
        result = await self.repository.get_payment_reconciliation(payment_id)
        if result is None:
            raise NotFoundError(f"Payment with ID {payment_id} not found")
        return result
