from api.repositories.validation_repository import DocumentsRepository


class ValidationService:
    def __init__(self):
        self.documents = DocumentsRepository()

    async def list_all_documents(self, limit: int = 100) -> list[dict]:
        df = await self.documents.list_all_documents(limit=limit)
        return df.to_dicts()
