import asyncio
from typing import Optional

import polars as pl

from api.exceptions import BadRequestError, ConflictError, NotFoundError
from api.repositories.item_repository import ItemRepository


class ItemService:
    def __init__(self):
        self.item_repository = ItemRepository()

    async def create_item(self, code: str, description: str, category: str, score: float = 0.0) -> dict:
        if not 0 <= score <= 100:
            raise BadRequestError("Score must be between 0 and 100")

        existing = await self.item_repository.get_by_code(code)

        if existing:
            raise ConflictError(f"Item with code '{code}' already exists")

        item_data = {"code": code, "description": description, "category": category, "score": score, "status": "active"}

        return await self.item_repository.create(item_data)

    async def get_item(self, item_id: int) -> dict:
        item = await self.item_repository.get(item_id)
        if not item:
            raise NotFoundError(f"Item with ID {item_id} not found")
        return item

    async def list_items(self, active=False) -> pl.DataFrame:
        if active:
            return await self.item_repository.get_active_items()
        else:
            return await self.item_repository.get_inactive_items()

    async def search_items(
        self, query: str, category: Optional[str] = None, status: Optional[str] = None
    ) -> pl.DataFrame:
        return await self.item_repository.search_items(query, category=category, status=status)

    async def get_top_items(self, limit) -> pl.DataFrame:
        return await self.item_repository.get_high_score_items(limit)

    async def update_item(
        self,
        item_id: int,
        description: Optional[str] = None,
        category: Optional[str] = None,
        score: Optional[float] = None,
        status: Optional[str] = None,
    ) -> dict:
        item = await self.get_item(item_id)

        if score is not None and not 0 <= score <= 100:
            raise BadRequestError("Score must be between 0 and 100")

        update_data = dict(description=description, category=category, score=score, status=status)
        update_data = {k: v for k, v in update_data.items() if v is not None}
        if not update_data:
            return item
        return await self.item_repository.update(item_id, update_data)

    async def delete_item(self, item_id: int) -> bool:
        return await self.item_repository.delete(item_id)

    async def deactivate_item(self, item_id: int) -> dict:
        return await self.update_item(item_id, status="inactive")

    async def get_category_summary(self) -> dict[str, int]:
        return await self.item_repository.count_by_category()

    async def get_statistics(self) -> dict:
        result = await asyncio.gather(  # preforming them all concurrently
            self.item_repository.count(),
            self.item_repository.avg_score(),
            self.item_repository.count_by_status(),
            self.item_repository.count_by_category(),
        )
        return {"total_items": result[0], "average_score": result[1], "by_status": result[2], "by_category": result[3]}
