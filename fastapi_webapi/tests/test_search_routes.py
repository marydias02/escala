"""Parameter validation, auth and shape of the three entity-search routes.

No database: the service is stubbed, so what is under test is the contract the
frontend pickers will code against. Ranking is the repositories' concern.
"""

import asyncio

import pytest

from api.exceptions import BadRequestError
from api.services.search_service import SearchService

pytestmark = pytest.mark.usefixtures("fake_oidc")

SUPPLIERS = "/suppliers/search"
BUSINESS_UNITS = "/business-units/search"
PURCHASE_ORDERS = "/purchase-orders/search"

ALL_ROUTES = [SUPPLIERS, BUSINESS_UNITS, PURCHASE_ORDERS]

SUPPLIER_ROW = {
    "supplier_id": "0100003539",
    "name": "Município de Lisboa",
    "vat": "PT500697370",
    "country": "PT",
    "is_financial": 1,
}
BU_ROW = {"bu_id": "1130", "name": "EDP Distribuição", "vat": "PT500697370", "country": "PT"}
PO_ROW = {
    "po_code": "5000363827",
    "supplier_id": "0100003539",
    "bu_id": "1130",
    "date": "2026-03-04",
    "value": 1234.56,
    "currency": "EUR",
    "supplier_name": "Município de Lisboa",
    "supplier_vat": "PT500697370",
    "bu_name": "EDP Distribuição",
    "bu_vat": "PT500697370",
}


@pytest.fixture
def as_user(override_claims):
    override_claims({"sub": "u1", "name": "U", "roles": ["User"]})


# --- parameter validation -------------------------------------------------


@pytest.mark.parametrize(
    "route, too_short",
    [(SUPPLIERS, "ab"), (BUSINESS_UNITS, "a"), (PURCHASE_ORDERS, "ab")],
)
def test_query_below_minimum_length_is_422(client, as_user, stub_search_service, route, too_short):
    assert client.get(route, params={"q": too_short}).status_code == 422
    assert stub_search_service.calls == []


@pytest.mark.parametrize("route", ALL_ROUTES)
def test_missing_query_is_422(client, as_user, stub_search_service, route):
    assert client.get(route).status_code == 422


@pytest.mark.parametrize("route", ALL_ROUTES)
def test_query_over_max_length_is_422(client, as_user, stub_search_service, route):
    assert client.get(route, params={"q": "1" * 65}).status_code == 422


@pytest.mark.parametrize("route", ALL_ROUTES)
@pytest.mark.parametrize("limit", ["0", "21", "abc"])
def test_invalid_limit_is_422(client, as_user, stub_search_service, route, limit):
    assert client.get(route, params={"q": "5000363827", "limit": limit}).status_code == 422


@pytest.mark.parametrize("route", ALL_ROUTES)
def test_limit_defaults_to_ten(client, as_user, stub_search_service, route):
    client.get(route, params={"q": "5000363827"})
    assert stub_search_service.calls[0][2] == 10


@pytest.mark.parametrize("route", ALL_ROUTES)
def test_limit_is_passed_through(client, as_user, stub_search_service, route):
    client.get(route, params={"q": "5000363827", "limit": 5})
    assert stub_search_service.calls[0][2] == 5


# --- response shape -------------------------------------------------------


@pytest.mark.parametrize("route", ALL_ROUTES)
def test_no_match_is_an_empty_list(client, as_user, stub_search_service, route):
    resp = client.get(route, params={"q": "5000363827"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.parametrize(
    "route, row",
    [(SUPPLIERS, SUPPLIER_ROW), (BUSINESS_UNITS, BU_ROW), (PURCHASE_ORDERS, PO_ROW)],
)
def test_canonical_fields_are_echoed_unchanged(client, as_user, stub_search_service, route, row):
    stub_search_service.rows = [row]
    resp = client.get(route, params={"q": "5000363827"})
    assert resp.status_code == 200
    assert resp.json() == [row]


def test_purchase_order_party_fields_may_be_unresolved(client, as_user, stub_search_service):
    """A PO naming a supplier the dimension snapshot has not loaded still
    returns — with null name and VAT, not a dropped row.
    """
    stub_search_service.rows = [{**PO_ROW, "supplier_name": None, "supplier_vat": None}]
    resp = client.get(PURCHASE_ORDERS, params={"q": "5000363827"})
    assert resp.status_code == 200
    assert resp.json()[0]["supplier_id"] == "0100003539"
    assert resp.json()[0]["supplier_name"] is None


# --- authorization --------------------------------------------------------


@pytest.mark.parametrize("route", ALL_ROUTES)
def test_user_role_may_search(client, as_user, stub_search_service, route):
    assert client.get(route, params={"q": "5000363827"}).status_code == 200


@pytest.mark.parametrize("route", ALL_ROUTES)
def test_unknown_role_is_403(client, override_claims, stub_search_service, route):
    override_claims({"sub": "u1", "name": "U", "roles": ["Guest"]})
    assert client.get(route, params={"q": "5000363827"}).status_code == 403


@pytest.mark.parametrize("route", ALL_ROUTES)
def test_missing_roles_claim_is_403(client, auth, mint_token, stub_search_service, route):
    resp = client.get(route, params={"q": "5000363827"}, headers=auth(mint_token(roles=None)))
    assert resp.status_code == 403


@pytest.mark.parametrize("route", ALL_ROUTES)
def test_no_token_is_401(client, stub_search_service, route):
    assert client.get(route, params={"q": "5000363827"}).status_code == 401


# --- service-level query preparation --------------------------------------
#
# These drive SearchService directly with recording repositories: the 400 for a
# query that only falls short after normalization, and the parameters each
# search hands to SQL, are not visible through the stubbed-service routes above.
# `run` stands in for an async pytest plugin, which the project does not carry.


run = asyncio.run


class _RecordingPartyRepository:
    def __init__(self):
        self.calls: list[tuple] = []

    async def search(self, raw, key, id_q, vat_core_q, limit):
        self.calls.append((raw, key, id_q, vat_core_q, limit))
        return _EMPTY_FRAME


class _RecordingPoRepository:
    def __init__(self):
        self.calls: list[tuple] = []

    async def search(self, code, limit):
        self.calls.append((code, limit))
        return _EMPTY_FRAME


class _EmptyFrame:
    @staticmethod
    def to_dicts():
        return []


_EMPTY_FRAME = _EmptyFrame()


@pytest.fixture
def service():
    service = SearchService.__new__(SearchService)  # No DB pool: repositories are stubs.
    service.suppliers = _RecordingPartyRepository()
    service.business_units = _RecordingPartyRepository()
    service.purchase_orders = _RecordingPoRepository()
    return service


@pytest.mark.parametrize("q", ["   ", "PT ", "..."])
def test_supplier_query_empty_after_normalization_is_400(service, q):
    with pytest.raises(BadRequestError) as exc:
        run(service.search_suppliers(q))
    assert exc.value.status_code == 400
    assert service.suppliers.calls == []


def test_business_unit_query_too_short_after_normalization_is_400(service):
    with pytest.raises(BadRequestError):
        run(service.search_business_units("1."))


@pytest.mark.parametrize("q, expected_key", [("11", "11"), ("1 1", "11")])
def test_business_unit_two_character_query_is_accepted(service, q, expected_key):
    run(service.search_business_units(q))
    assert service.business_units.calls[0][1] == expected_key


def test_all_zero_id_query_does_not_become_an_empty_prefix(service):
    run(service.search_suppliers("000"))
    assert service.suppliers.calls[0][2] == "0"


def test_zero_padded_id_query_is_stripped(service):
    run(service.search_suppliers("0100003539"))
    assert service.suppliers.calls[0][2] == "100003539"


def test_spaced_vat_query_is_keyed_and_country_stripped(service):
    run(service.search_suppliers("pt 500 697 370"))
    _raw, key, _id_q, vat_core_q, _limit = service.suppliers.calls[0]
    assert key == "PT500697370"
    assert vat_core_q == "500697370"


@pytest.mark.parametrize(
    "q, expected_core",
    [
        ("PT500697370", "500697370"),
        ("ESA83398586", "A83398586"),  # Spanish CIF: the body itself starts with a letter.
        ("NL800822274B01", "800822274B01"),
        ("286861798", "286861798"),  # No prefix to strip.
    ],
)
def test_country_prefix_is_stripped_whatever_follows_it(service, q, expected_core):
    run(service.search_suppliers(q))
    assert service.suppliers.calls[0][3] == expected_core


def test_name_query_disables_the_id_tier(service):
    run(service.search_suppliers("Município"))
    assert service.suppliers.calls[0][2] is None


@pytest.mark.parametrize("q", ["ABC123", "50003638271"])
def test_unmatchable_po_query_returns_empty_without_querying(service, q):
    assert run(service.search_purchase_orders(q)) == []
    assert service.purchase_orders.calls == []


def test_po_query_whitespace_is_removed(service):
    run(service.search_purchase_orders(" 5000 363827 "))
    assert service.purchase_orders.calls[0][0] == "5000363827"


def test_po_query_too_short_after_stripping_is_400(service):
    with pytest.raises(BadRequestError):
        run(service.search_purchase_orders("  1  "))
