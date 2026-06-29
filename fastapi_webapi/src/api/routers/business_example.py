from typing import Optional

from fastapi import APIRouter, Depends

from api.dependencies.security import verify_api_key
from api.dependencies.services import ItemServiceDep
from api.exceptions import NotFoundError
from api.messages.store import ItemCreate, ItemRead, ItemStatisticsDict, ItemUpdate

router = APIRouter(prefix="/example/item", tags=["example"], dependencies=[Depends(verify_api_key)])


@router.post("", status_code=201, summary="Create a new item")
async def create_item(item: ItemCreate, service: ItemServiceDep) -> ItemRead:
    """
    Create a new item.

    - **code**: Unique item identifier
    - **description**: Item description
    - **category**: Item category
    - **score**: Item score (0-100)
    """
    result = await service.create_item(
        code=item.code, description=item.description, category=item.category, score=item.score
    )

    return ItemRead.model_validate(result)


@router.get("", summary="List all items")
async def list_items(service: ItemServiceDep, active: bool = False) -> list[ItemRead]:
    """
    Get all items.

    - **active_only**: If True, return only active items (default: False)
    """

    items = await service.list_items(active=active)

    return [ItemRead.model_validate(r) for r in items.to_dicts()]


@router.get("/search", summary="Search items")
async def search_items(
    service: ItemServiceDep, q: str, category: Optional[str] = None, status: Optional[str] = None
) -> list[ItemRead]:
    """
    Search items by description with optional filters.

    - **q**: Search query (searches in description)
    - **category**: Optional category filter
    - **status**: Optional status filter (active/inactive)
    """
    items = await service.search_items(q, category=category, status=status)

    return [ItemRead.model_validate(r) for r in items.to_dicts()]


@router.get("/top", summary="Get top items by score")
async def get_top_items(service: ItemServiceDep, limit: int = 10) -> list[ItemRead]:
    """
    Get top items sorted by score.

    - **limit**: Number of items to return (default: 10)
    """
    items = await service.get_top_items(limit)

    return [ItemRead.model_validate(r) for r in items.to_dicts()]


@router.get("/statistics", summary="Get item statistics")
async def get_statistics(service: ItemServiceDep) -> ItemStatisticsDict:
    """
    Get statistics about items including counts and averages.
    """
    return await service.get_statistics()  # type: ignore


@router.get("/{item_id}", summary="Get a single item")
async def get_item(service: ItemServiceDep, item_id: int) -> ItemRead:
    """
    Get a single item by ID.

    - **item_id**: Item ID
    """
    result = await service.get_item(item_id)
    return ItemRead.model_validate(result)


@router.put("/{item_id}", summary="Update an item")
async def update_item(item_id: int, item: ItemUpdate, service: ItemServiceDep) -> ItemRead:
    """
    Update an item (only provided fields are updated).

    - **item_id**: Item ID
    - **description**: New description (optional)
    - **category**: New category (optional)
    - **score**: New score (optional, must be 0-100)
    - **status**: New status (optional)
    """
    result = await service.update_item(
        item_id, description=item.description, category=item.category, score=item.score, status=item.status
    )
    return ItemRead.model_validate(result)


@router.patch("/{item_id}/deactivate", summary="Deactivate an item")
async def deactivate_item(item_id: int, service: ItemServiceDep) -> ItemRead:
    """
    Deactivate an item (soft delete).

    - **item_id**: Item ID
    """
    result = await service.deactivate_item(item_id)
    return ItemRead.model_validate(result)


@router.delete("/{item_id}", status_code=204, summary="Delete an item")
async def delete_item(service: ItemServiceDep, item_id: int) -> None:
    """
    Delete an item by ID.

    - **item_id**: Item ID
    """
    deleted = await service.delete_item(item_id)
    if not deleted:
        raise NotFoundError(f"Item with ID {item_id} not found")
