import asyncio
import json
import sys

sys.path.insert(0, "fastapi_webapi/src")
from api.sql import init_database_pool
from api.services.extraction_service import ExtractionService


async def main():
    await init_database_pool()
    service = ExtractionService()
    try:
        result = await service.alter_document_details(
            "03072d38-c155-434b-883e-5806563f4bf5",
            ["test"],
            {"bu_name": {"value": "X"}},
        )
        print("OK")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as exc:
        import traceback

        traceback.print_exc()
        print(type(exc).__name__, exc)


if __name__ == "__main__":
    asyncio.run(main())
