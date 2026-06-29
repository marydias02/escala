from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger
from starlette.middleware.cors import CORSMiddleware
from uvicorn import run

from api.dependencies.security import swagger_security_kwargs
from api.properties import BACKEND_BIND_HOST, BACKEND_CORS_ORIGINS, BACKEND_PORT, DEBUG_MODE
from api.routers import include_all_routers


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from api import setup_logger
    from api.repositories import declare_tables
    from api.sql import init_database_pool

    setup_logger(debug=DEBUG_MODE)

    db_pool = await init_database_pool()
    try:
        await declare_tables()
        yield
    finally:
        db_pool.terminate()


app = FastAPI(title="BACKEND API", lifespan=lifespan, **swagger_security_kwargs)

include_all_routers(app)

app.add_middleware(
    CORSMiddleware, allow_origins=BACKEND_CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)


if __name__ == "__main__":
    logger.warning("THIS IS A DEVELOPMENT STARTUP! DO NOT USE IN PRODUCTION!")

    run("main:app", host=BACKEND_BIND_HOST, port=BACKEND_PORT)
