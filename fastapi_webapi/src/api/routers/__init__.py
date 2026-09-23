from fastapi import FastAPI

from api.routers.extraction import router as extraction_router
from api.routers.health import router as health_router
from api.routers.search import business_units_router, purchase_orders_router, suppliers_router
from api.routers.validation import router as validation_router


def include_all_routers(app: FastAPI):
    """Include all routers in the FastAPI app."""
    app.include_router(extraction_router)
    app.include_router(health_router)
    app.include_router(validation_router)
    app.include_router(suppliers_router)
    app.include_router(business_units_router)
    app.include_router(purchase_orders_router)


__all__ = ["include_all_routers"]
