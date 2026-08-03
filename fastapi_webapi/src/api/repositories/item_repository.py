from typing import Optional

import polars as pl
from typing_extensions import Any

from api.sql import BaseRepository


class ItemRepository(BaseRepository):
    __table_name__ = "item"

    # NOTE: kept as a reference example. Schema is now managed by Alembic — the
    # `item` table has no migration yet, so these endpoints will error until one
    # is added (out of scope). Previously a declare_table() here created it at
    # startup; that mechanism was removed when Alembic became the source of truth.

    async def get(self, _id: int | str) -> Optional[dict[str, Any]]:
        query = f"SELECT * FROM {self.table} WHERE id = $1"
        return await self.query_dict(query, parameters=[_id])

    async def create(self, data: dict) -> dict[str, Any]:
        query = f"""
        INSERT INTO {self.table} (code, description, category, status, score)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, code, description, category, status, score;
        """
        params = [data["code"], data["description"], data["category"], data["status"], data["score"]]

        return await self.query_dict(query, parameters=params)

    async def update(self, _id: int | str, data: dict) -> Optional[dict]:
        set_parts = []

        params = []
        param_index = 1
        for key, value in data.items():
            set_parts.append(f"{key} = ${param_index}")
            params.append(value)
            param_index += 1
        params.append(_id)
        set_clause = ", ".join(set_parts)

        query = f"""
        UPDATE {self.table} SET {set_clause} WHERE id = ${param_index}
        RETURNING id, code, description, category, status, score
        """

        return await self.query_dict(query, parameters=params)

    async def delete(self, _id: int | str) -> bool:
        return (
            await self.query_df(f"DELETE FROM {self.table} WHERE id = $1 RETURNING id", parameters=[_id])
        ).height > 0

    async def get_by_code(self, code: str) -> Optional[dict]:
        query = f"SELECT * FROM {self.table} WHERE code = $1"

        return await self.query_dict(query, parameters=[code])

    async def get_by_category(self, category: str) -> pl.DataFrame:
        query = f"SELECT * FROM {self.table} WHERE category = $1"

        return await self.query_df(query, parameters=[category])

    async def get_active_items(self) -> pl.DataFrame:
        return await self.query_df(f"SELECT * FROM {self.table} WHERE status = 'active' ORDER BY code")

    async def get_inactive_items(self) -> pl.DataFrame:
        return await self.query_df(f"SELECT * FROM {self.table} WHERE status = 'inactive' ORDER BY code")

    async def search_items(
        self, query_str: str, category: Optional[str] = None, status: Optional[str] = None
    ) -> pl.DataFrame:
        conditions = ["description ILIKE $1"]
        params = [f"%{query_str}%"]
        param_index = 2

        if category is not None:
            conditions.append(f"category = ${param_index}")
            params.append(category)
            param_index += 1

        if status is not None:
            conditions.append(f"status = ${param_index}")
            params.append(status)

        where_clause = " AND ".join(conditions)
        sql_query = f"SELECT * FROM {self.table} WHERE {where_clause} ORDER BY description"
        return await self.query_df(sql_query, parameters=params)

    async def get_high_score_items(self, limit: int = 10) -> pl.DataFrame:
        query = f"SELECT * FROM {self.table} ORDER BY score DESC LIMIT $1"
        return await self.query_df(query, parameters=[limit])

    async def count(self) -> int:
        query = f"SELECT COUNT(*) FROM {self.table}"
        return await self.query_scalar(query)

    async def avg_score(self) -> float:
        query = f"SELECT AVG(score) FROM {self.table}"
        result = await self.query_scalar(query)
        return result or 0.0

    async def count_by_status(self) -> dict[str, int]:
        query = f"SELECT status, COUNT(*) as count FROM {self.table} GROUP BY status"
        results = await self.query_df(query)
        return {row["status"]: row["count"] for row in results.iter_rows(named=True)}

    async def count_by_category(self) -> dict[str, int]:
        query = f"SELECT category, COUNT(*) as count FROM {self.table} GROUP BY category"
        results = await self.query_df(query)
        return {row["category"]: row["count"] for row in results.iter_rows(named=True)}

    async def bulk_update_status(self, status: str, category: Optional[str] = None) -> int:
        if category:
            query = f"UPDATE {self.table} SET status = $1 WHERE category = $2 RETURNING id"
            params = [status, category]
        else:
            query = f"UPDATE {self.table} SET status = $1 RETURNING id"
            params = [status]

        df = await self.query_df(query, parameters=params)

        return df.height

    async def filter_by_score_range(self, min_score: float, max_score: float) -> pl.DataFrame:
        query = f"SELECT * FROM {self.table} WHERE score >= $1 AND score <= $2 ORDER BY score"

        return await self.query_df(query, parameters=[min_score, max_score])
