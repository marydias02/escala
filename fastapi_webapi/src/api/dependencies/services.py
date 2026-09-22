from typing import Annotated

from fastapi import Depends

from api.services.air_example import AirExampleService
from api.services.extraction_service import ExtractionService
from api.services.search_service import SearchService
from api.services.validation_service import ValidationService


async def get_air_service() -> AirExampleService:
    return AirExampleService(app_id=123)


AirExampleServiceDependency = Annotated[AirExampleService, Depends(get_air_service)]


async def get_extraction_service() -> ExtractionService:
    return ExtractionService()


ExtractionServiceDep = Annotated[ExtractionService, Depends(get_extraction_service)]


async def get_validation_service() -> ValidationService:
    return ValidationService()


ValidationServiceDep = Annotated[ValidationService, Depends(get_validation_service)]


async def get_search_service() -> SearchService:
    return SearchService()


SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]


# These dependencies might seem redundant now, but it's here to allow easy extension in the future
# e.g., caching, configuring parameters, or switching implementations dynamically.

# If the service requires async initialization (not possible with __init__), this allows us to handle that cleanly as well.
# For now, it simply provides a new instance of each service.
