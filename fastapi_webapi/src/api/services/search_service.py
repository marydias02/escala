"""Ranked lookup of the canonical supplier / business unit / purchase order a
reviewer means, so the invoice review page can write a real `supplier_id` /
`bu_id` / `po_code` into `fct_documents.document_content` instead of free text.

The service never auto-selects: it returns zero to `limit` ranked candidates
and the caller chooses. A single result is still a list of one.
"""

import re

from api.exceptions import BadRequestError
from api.repositories.search_repository import (
    BusinessUnitSearchRepository,
    PurchaseOrderSearchRepository,
    SupplierSearchRepository,
)
from utils.utils_db import normalize_key

SUPPLIER_MIN_QUERY_LENGTH = 3
BUSINESS_UNIT_MIN_QUERY_LENGTH = 2
PURCHASE_ORDER_MIN_QUERY_LENGTH = 3

# EBELN is CHAR(10); nothing longer can match a stored code.
PO_CODE_MAX_LENGTH = 10

_VAT_COUNTRY_PREFIX = re.compile(r"^[A-Z]{2}(?=[A-Z0-9])")
_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


class SearchService:
    def __init__(self):
        self.suppliers = SupplierSearchRepository()
        self.business_units = BusinessUnitSearchRepository()
        self.purchase_orders = PurchaseOrderSearchRepository()

    async def search_suppliers(self, q: str, limit: int = 10) -> list[dict]:
        raw, key = self._party_query(q, SUPPLIER_MIN_QUERY_LENGTH)
        df = await self.suppliers.search(raw, key, _id_query(key), _vat_core(key), limit)
        return df.to_dicts()

    async def search_business_units(self, q: str, limit: int = 10) -> list[dict]:
        raw, key = self._party_query(q, BUSINESS_UNIT_MIN_QUERY_LENGTH)
        df = await self.business_units.search(raw, key, _id_query(key), _vat_core(key), limit)
        return df.to_dicts()

    async def search_purchase_orders(self, q: str, limit: int = 10) -> list[dict]:
        code = _po_code(q)
        if len(code) < PURCHASE_ORDER_MIN_QUERY_LENGTH:
            raise _too_short(PURCHASE_ORDER_MIN_QUERY_LENGTH)
        # Well-formed but unmatchable: an empty result, not an error.
        if not code.isdigit() or len(code) > PO_CODE_MAX_LENGTH:
            return []
        df = await self.purchase_orders.search(code, limit)
        return df.to_dicts()

    @staticmethod
    def _party_query(q: str, minimum: int) -> tuple[str, str]:
        """The trimmed query and its alphanumeric key, rejecting a query that
        carries too little signal to search on (`"   "`, `"PT "`, `"..."`).

        The name side is normalized in SQL by the same `f_search_norm` that
        built `name_norm`, so only the length is checked here.
        """
        raw = q.strip()
        key = normalize_key(raw) or ""
        if max(len(key), len(_name_length_probe(raw))) < minimum:
            raise _too_short(minimum)
        return raw, key


def _too_short(minimum: int) -> BadRequestError:
    return BadRequestError(f"query too short after normalization (minimum {minimum} characters)")


def _name_length_probe(raw: str) -> str:
    """How much of the query survives name normalization, for the length check
    only — the value compared in SQL is `f_search_norm`'s own output.
    """
    return _NON_ALPHANUMERIC.sub(" ", raw.lower()).strip()


def _id_query(key: str) -> str | None:
    """A digit query as a zero-pad-insensitive id, else None (disabling the tier).

    `or "0"` keeps an all-zero query from collapsing to an empty prefix, which
    would match every row.
    """
    if not key.isdigit():
        return None
    return key.lstrip("0") or "0"


def _vat_core(key: str) -> str | None:
    """The VAT without its country prefix, so `PT500697370` and `500697370` meet."""
    return _VAT_COUNTRY_PREFIX.sub("", key) or None


def _po_code(q: str) -> str:
    """A PO query with all whitespace removed; `5000 363827` is one code."""
    return "".join(q.split())
