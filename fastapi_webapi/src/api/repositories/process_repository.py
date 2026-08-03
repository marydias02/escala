import polars as pl

from api.sql import BaseRepository


class ProcessRepository(BaseRepository):
    __table_name__ = "fct_processes"

    # NOTE: no declare_table() here — the schema for fct_processes is owned by
    # Alembic (see migrations/versions/20260727_01_create_fct_processes.py).

    async def list_processes(self, limit: int = 100) -> pl.DataFrame:
        query = f"SELECT * FROM {self.table} ORDER BY reception_date DESC NULLS LAST LIMIT $1"
        return await self.query_df(query, parameters=[limit])