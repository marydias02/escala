"""Service layer for the validation dashboard: document listing and the
big-numbers tiles shown above it.
"""

import asyncio

from api.repositories.validation_repository import DocumentsRepository, ValidationBigNumbers


class ValidationService:
    def __init__(self):
        self.documents = DocumentsRepository()
        self.big_numbers = ValidationBigNumbers()

    async def list_all_documents(self, limit: int = 100) -> list[dict]:
        df = await self.documents.list_all_documents(limit=limit)
        return df.to_dicts()

    async def get_validation_big_numbers(self) -> dict:
        (
            received_by_week,
            needs_manual_by_week,
            processed_by_agent_by_week,
            with_buyer_by_week,
        ) = await asyncio.gather(
            self.big_numbers.count_non_conforming_received_by_week(),
            self.big_numbers.count_needs_manual_validation_by_week(),
            self.big_numbers.count_processed_by_agent_by_week(),
            self.big_numbers.count_with_buyer_by_week(),
        )

        return {
            "non_conforming_received": _value_with_wow_delta(received_by_week),
            "needs_manual_validation": _value_with_wow_delta(needs_manual_by_week),
            "processed_by_agent": _value_with_wow_delta(processed_by_agent_by_week),
            "with_buyer": _value_with_wow_delta(with_buyer_by_week),
        }


def _value_with_wow_delta(by_week: dict[str, tuple[int, int]]) -> dict:
    """Current week's matched count, with the standard % change vs. the
    previous week: (current - previous) / previous * 100.
    """
    current_count, _ = by_week["current"]
    previous_count, _ = by_week["previous"]
    delta_pp = round((current_count - previous_count) / previous_count * 100, 2) if previous_count else 0.0
    return {"value": current_count, "delta_pp": delta_pp}
