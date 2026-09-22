import sys

sys.path.insert(0, "fastapi_webapi/src")
import asyncio
from api.sql import init_database_pool
from api.services.extraction_service import ExtractionService


async def main():
    await init_database_pool()
    service = ExtractionService()
    try:
        docs = await service.list_priority_documents()
        print("ok", docs[:2])
    except Exception as e:
        import traceback

        traceback.print_exc()
        print("EXC", type(e).__name__, e)


if __name__ == "__main__":
    asyncio.run(main())
