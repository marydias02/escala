"""Entity pickers for the invoice review page.

Each route resolves what a reviewer typed to canonical rows from the SAP
snapshots, ranked by how well they match. The caller writes the chosen row's
id into `fct_documents.document_content` via `PATCH /extraction` — as
`supplier_id` / `bu_id` / a `po_list` entry, each a `{"value", "confidence"}`
pair, with `confidence: 1.0` for a human selection. That is what unblocks
`decisions.ingestion_blockers`, which refuses to ingest a null id.

The response is always a list, never an auto-selection: a lone candidate is
still only a candidate, because a VAT is shared by branches and vessels.
"""

from typing import Annotated

from fastapi import APIRouter, Query

from api.dependencies.security import has_authorization_for
from api.dependencies.services import SearchServiceDep
from api.messages.store import BusinessUnitSearchRead, PurchaseOrderSearchRead, SupplierSearchRead
from api.services.search_service import (
    BUSINESS_UNIT_MIN_QUERY_LENGTH,
    PURCHASE_ORDER_MIN_QUERY_LENGTH,
    SUPPLIER_MIN_QUERY_LENGTH,
)

MAX_QUERY_LENGTH = 64

LimitParam = Annotated[int, Query(ge=1, le=20)]


def _query_param(min_length: int):
    """`q`, rejected with 422 below `min_length` raw. A query that only falls
    short after normalization is a 400 from the service.
    """
    return Annotated[str, Query(min_length=min_length, max_length=MAX_QUERY_LENGTH)]


SupplierQuery = _query_param(SUPPLIER_MIN_QUERY_LENGTH)
BusinessUnitQuery = _query_param(BUSINESS_UNIT_MIN_QUERY_LENGTH)
PurchaseOrderQuery = _query_param(PURCHASE_ORDER_MIN_QUERY_LENGTH)

suppliers_router = APIRouter(prefix="/suppliers", tags=["search"])
business_units_router = APIRouter(prefix="/business-units", tags=["search"])
purchase_orders_router = APIRouter(prefix="/purchase-orders", tags=["search"])


@suppliers_router.get(
    "/search",
    summary="Search suppliers",
    dependencies=[has_authorization_for("read", "suppliers")],
)
async def search_suppliers(
    service: SearchServiceDep, q: SupplierQuery, limit: LimitParam = 10
) -> list[SupplierSearchRead]:
    """
    Suppliers matching a supplier id, VAT or name, best match first.

    - **q**: id (zero-padding optional), VAT (with or without country prefix)
      or name (accents and punctuation optional; near-misses match)
    - **limit**: Maximum number of candidates to return (default: 10, max: 20)
    """
    rows = await service.search_suppliers(q, limit=limit)
    return [SupplierSearchRead.model_validate(r) for r in rows]


@business_units_router.get(
    "/search",
    summary="Search business units",
    dependencies=[has_authorization_for("read", "business_units")],
)
async def search_business_units(
    service: SearchServiceDep, q: BusinessUnitQuery, limit: LimitParam = 10
) -> list[BusinessUnitSearchRead]:
    """
    Business units matching a BU code, VAT or name, best match first.

    - **q**: code (`1130`, or `11` for the group), VAT or name
    - **limit**: Maximum number of candidates to return (default: 10, max: 20)
    """
    rows = await service.search_business_units(q, limit=limit)
    return [BusinessUnitSearchRead.model_validate(r) for r in rows]


@purchase_orders_router.get(
    "/search",
    summary="Search purchase orders",
    dependencies=[has_authorization_for("read", "purchase_orders")],
)
async def search_purchase_orders(
    service: SearchServiceDep, q: PurchaseOrderQuery, limit: LimitParam = 10
) -> list[PurchaseOrderSearchRead]:
    """
    Purchase orders whose code matches or is close to the query, best match first.

    A complete code also returns its numeric neighbours, so a single wrong or
    missing digit still surfaces the intended order.

    Each row carries its supplier and business unit — id, name and VAT — so
    selecting a PO can fill those fields in one step, and a party mismatch can
    be shown against what was extracted. The name and VAT are null when the PO
    names a party the current dimension snapshot has not loaded.

    Note that `fct_purchase_orders` only holds orders from 2026-01-01 onward.

    - **q**: full or partial PO code (digits; whitespace ignored)
    - **limit**: Maximum number of candidates to return (default: 10, max: 20)
    """
    rows = await service.search_purchase_orders(q, limit=limit)
    return [PurchaseOrderSearchRead.model_validate(r) for r in rows]
