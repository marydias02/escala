from fastapi import APIRouter, HTTPException
from loguru import logger

from api.sql import get_database_pool

router = APIRouter(prefix="/health", tags=["health"])


async def _database_reachable() -> bool:
    pool = get_database_pool()
    if pool is None or pool.is_closing():
        return False
    try:
        await pool.fetchval("SELECT 1")
    except Exception as exc:  # noqa: BLE001 - any failure to reach the database is "not ready"
        logger.warning(f"Deep health check failed: {exc}")
        return False
    return True


@router.get("", summary="Liveness and readiness")
async def health(deep: bool = False) -> dict[str, str]:
    """Liveness by default; `?deep=true` also checks database connectivity.

    The endpoint is public, so a failure reports a status and nothing else — a driver
    error would name the database host and schema to the internet.
    """
    if deep and not await _database_reachable():
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ok"}
