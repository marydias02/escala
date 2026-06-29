from fastapi import FastAPI

from api.routers.airpy_example import router as air_router
from api.routers.business_example import router as business_router


def include_all_routers(app: FastAPI):
    """Include all routers in the FastAPI app."""
    app.include_router(business_router)
    app.include_router(air_router)


__all__ = ["include_all_routers"]
