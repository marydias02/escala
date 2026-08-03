from api.repositories.process_repository import ProcessRepository


class ProcessService:
    def __init__(self):
        self.process_repository = ProcessRepository()

    async def list_processes(self, limit: int = 100) -> list[dict]:
        df = await self.process_repository.list_processes(limit=limit)
        return df.to_dicts()
