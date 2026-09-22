import sys
sys.path.insert(0, 'src')
import asyncio
from api.sql import init_database_pool
from api.services.extraction_service import ExtractionService

async def main():
    await init_database_pool()
    service = ExtractionService()
    docs = await service.list_priority_documents()
    print('OK', len(docs))
    print(docs[:1])

asyncio.run(main())
