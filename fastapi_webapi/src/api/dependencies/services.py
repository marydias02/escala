from fastapi import Depends
from typing_extensions import Annotated

from api.services.air_example import AirExampleService
from api.services.service_example import ItemService


async def get_item_service() -> ItemService:
    return ItemService()


ItemServiceDep = Annotated[ItemService, Depends(get_item_service)]


async def get_air_service() -> AirExampleService:
    return AirExampleService(app_id=123)


AirExampleServiceDependency = Annotated[AirExampleService, Depends(get_air_service)]


# These dependencies might seem redundant now, but it's here to allow easy extension in the future
# e.g., caching, configuring parameters, or switching implementations dynamically.

# If the service requires async initialization (not possible with __init__), this allows us to handle that cleanly as well.
# For now, it simply provides a new instance of each service.
