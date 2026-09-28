"""Unit tests for the lakehouse ETL: the transforms and the SQL `upsert_rows`
builds. No Postgres and no lakehouse — everything is monkeypatched.
"""

import asyncio
from decimal import Decimal

import polars as pl
import pytest

from lakehouse_etl import load, pipeline, transforms
from utils import utils_db

# `run` stands in for an async pytest plugin, which the project does not carry
# — same convention as tests/test_search_routes.py.
run = asyncio.run


@pytest.fixture(autouse=True)
def no_db(monkeypatch):
    """A stray real-pool call fails loudly instead of hanging."""

    async def _fail():
        raise AssertionError("test reached the real database")

    monkeypatch.setattr(utils_db, "get_pool", _fail)


# --- transforms --------------------------------------------------------------


def _lfa1(**overrides) -> pl.DataFrame:
    row = {
        "LIFNR": "0100000001",
        "NAME1": "Acme",
        "NAME2": "",
        "NAME3": "",
        "NAME4": "",
        "STCEG": "PT123456789",
        "STCD1": "",
        "LAND1": "PT",
    }
    row.update(overrides)
    return pl.DataFrame([row])


def _but000(partner: str = "0100000001", langu: str = "P") -> pl.DataFrame:
    return pl.DataFrame([{"PARTNER": partner, "BU_LANGU": langu}])


@pytest.mark.parametrize(
    "names,expected",
    [
        (("Acme", "", "", ""), "Acme"),
        (("Acme", "Lda", "", ""), "Acme Lda"),
        # A dot-only line is a placeholder, not part of the name.
        (("Acme", "", ".", "."), "Acme"),
        (("  Acme  ", "  Lda  ", "", ""), "Acme Lda"),
        (("", "", "", ""), ""),
    ],
)
def test_full_name(names, expected):
    df = _lfa1(NAME1=names[0], NAME2=names[1], NAME3=names[2], NAME4=names[3])
    assert df.select(transforms.full_name()).item() == expected


def test_build_suppliers_columns_exclude_generated():
    """The four GENERATED ALWAYS columns must never reach the upsert."""
    rows = transforms.build_suppliers(_lfa1(), _but000())
    assert tuple(rows.columns) == transforms.SUPPLIER_COLUMNS
    assert not {"id_norm", "vat_norm", "vat_core", "name_norm"} & set(rows.columns)


def test_build_suppliers_keeps_supplier_without_partner_row():
    rows = transforms.build_suppliers(_lfa1(), _but000(partner="9999999999"))
    assert rows.height == 1
    assert rows["preferred_language"].item() is None


def test_build_suppliers_blank_language_becomes_null():
    rows = transforms.build_suppliers(_lfa1(), _but000(langu=""))
    assert rows["preferred_language"].item() is None


def test_build_suppliers_vat_falls_back_to_stcd1():
    rows = transforms.build_suppliers(_lfa1(STCEG=None, STCD1="509225918"), _but000())
    assert rows["vat"].item() == "509225918"


def test_build_suppliers_collapses_duplicate_lifnr():
    df = pl.concat([_lfa1(), _lfa1(NAME1="Acme II")])
    assert transforms.build_suppliers(df, _but000()).height == 1


def test_classify_is_financial():
    financial = transforms.FINANCIAL_SUPPLIERS[0]
    both = transforms.BOTH_SUPPLIERS[0]
    df = pl.DataFrame({"name": [financial, both, "Some Logistics Lda"]})
    assert df.select(transforms.classify_is_financial())["is_financial"].to_list() == [1, 2, 0]


def test_unmatched_financial_names_reports_drift():
    rows = pl.DataFrame({"name": ["Nothing In The List"]})
    unmatched = transforms.unmatched_financial_names(rows)
    assert transforms.FINANCIAL_SUPPLIERS[0] in unmatched


def _t001(bu_id: str = "1000", **overrides) -> dict:
    row = {"BUKRS": bu_id, "BUTXT": "GS Lines", "STCEG": "PT511011911", "LAND1": "PT"}
    row.update(overrides)
    return row


def test_build_business_units_columns():
    rows = transforms.build_business_units(pl.DataFrame([_t001()]))
    assert tuple(rows.columns) == transforms.BUSINESS_UNIT_COLUMNS


def test_build_business_units_raises_on_duplicate_bu_id():
    """A duplicate means the client filter stopped working — do not collapse it."""
    df = pl.DataFrame([_t001(), _t001(BUTXT="SAP SE")])
    with pytest.raises(ValueError, match="Duplicate bu_id"):
        transforms.build_business_units(df)


def _ekko(code: str = "6400136458", loekz: str = "", memory: str = "", changed: str = "20260911000002.6") -> dict:
    return {
        "EBELN": code,
        "LIFNR": "0100000001",
        "BUKRS": "1000",
        "BEDAT": "20260901",
        "RLWRT": Decimal("100.00"),
        "WAERS": "EUR",
        "LASTCHANGEDATETIME": Decimal(changed),
        "LOEKZ": loekz,
        "MEMORY": memory,
    }


def test_build_purchase_orders_columns_and_types():
    rows, _ = transforms.build_purchase_orders(pl.DataFrame([_ekko()]))
    assert tuple(rows.columns) == transforms.PURCHASE_ORDER_COLUMNS
    assert rows["date"].dtype == pl.Date
    # Exact Decimal, never a float round-trip.
    assert rows["source_changed_at"].item() == Decimal("20260911000002.6")


@pytest.mark.parametrize("flags", [{"loekz": "C"}, {"memory": "X"}, {"loekz": "C", "memory": "X"}])
def test_build_purchase_orders_removes_cancelled_and_held(flags):
    rows, deletes = transforms.build_purchase_orders(pl.DataFrame([_ekko(**flags)]))
    assert rows.height == 0
    assert deletes == ["6400136458"]


def test_build_purchase_orders_sorted_ascending():
    """The crash-safety invariant: MAX over committed rows must be a safe resume."""
    df = pl.DataFrame(
        [
            _ekko("6400000003", changed="20260911000009.0"),
            _ekko("6400000001", changed="20260911000001.0"),
            _ekko("6400000002", changed="20260911000005.0"),
        ]
    )
    rows, _ = transforms.build_purchase_orders(df)
    assert rows["source_changed_at"].is_sorted()


# --- clients -----------------------------------------------------------------
# `sap_queries` hands the transforms readable column names; the helpers build
# them from the same mapping, so a renamed description cannot drift silently.

_PARTNER_NAME_COLUMNS = (
    "NAME_ORG1",
    "NAME_ORG2",
    "NAME_ORG3",
    "NAME_ORG4",
    "NAME_FIRST",
    "NAME_LAST",
    "NAME_GRP1",
    "NAME_GRP2",
    "BU_SORT1",
)


def _partner(partner: str = "0100000001", **names) -> dict:
    row = {"PARTNER": partner, **{c: "" for c in _PARTNER_NAME_COLUMNS}, **names}
    return {transforms._BUT000[k]: v for k, v in row.items()}


def _kna1(kunnr: str = "0100000001", **overrides) -> dict:
    row = {
        "KUNNR": kunnr,
        "NAME1": "Acme Kna1",
        "NAME2": "",
        "NAME3": "",
        "NAME4": "",
        "STCEG": "PT123456789",
        "STCD1": "",
    }
    row.update(overrides)
    return row


def _clients(customers, partners) -> pl.DataFrame:
    partner_schema = {transforms._BUT000[c]: pl.String for c in ("PARTNER", *_PARTNER_NAME_COLUMNS)}
    return transforms.build_clients(pl.DataFrame(customers), pl.DataFrame(partners, schema=partner_schema))


def test_build_clients_columns_exclude_generated():
    rows = _clients([_kna1()], [_partner(NAME_ORG1="Acme")])
    assert tuple(rows.columns) == transforms.CLIENT_COLUMNS
    assert not {"id_norm", "vat_norm", "vat_core", "name_norm"} & set(rows.columns)


@pytest.mark.parametrize(
    "names,expected",
    [
        ({"NAME_ORG1": "Acme", "NAME_ORG2": "Lda"}, "Acme Lda"),
        ({"NAME_FIRST": "Ana", "NAME_LAST": "Silva"}, "Ana Silva"),
        ({"NAME_GRP1": "Grupo X"}, "Grupo X"),
        ({"BU_SORT1": "ACME"}, "ACME"),
        # An organization name wins over the search term.
        ({"NAME_ORG1": " Acme ", "BU_SORT1": "ACME"}, "Acme"),
    ],
)
def test_build_clients_name_fallback(names, expected):
    rows = _clients([_kna1()], [_partner(**names)])
    assert rows["name"].item() == expected


def test_build_clients_keeps_every_customer():
    """Every KNA1 customer is a client, posted to or not; a BUT000 partner that
    is not a customer (a supplier) is not.
    """
    customers = [_kna1("0100000001"), _kna1("0100000002")]
    partners = [_partner("0100000001", NAME_ORG1="A"), _partner("0200000002", NAME_ORG1="Supplier")]
    rows = _clients(customers, partners)
    assert rows["client_id"].to_list() == ["0100000001", "0100000002"]


def test_build_clients_name_falls_back_to_kna1():
    """BUT000 holds the whole name; KNA1's 35-char lines only when it has none."""
    rows = _clients([_kna1(NAME1="Acme Distribuição Alimentar,", NAME2=" Lda.")], [])
    assert rows["name"].item() == "Acme Distribuição Alimentar, Lda."


def test_build_clients_drops_customer_without_name():
    rows = _clients([_kna1(NAME1="", NAME2="")], [_partner()])
    assert rows.height == 0


@pytest.mark.parametrize(
    "vats,expected",
    [
        ({"STCEG": "PT123456789", "STCD1": "509225918"}, "PT123456789"),
        ({"STCEG": "  ", "STCD1": "509225918"}, "509225918"),
        ({"STCEG": None, "STCD1": ""}, None),
    ],
)
def test_build_clients_vat(vats, expected):
    rows = _clients([_kna1(**vats)], [_partner(NAME_ORG1="A")])
    assert rows.row(0, named=True) == {"client_id": "0100000001", "name": "A", "vat": expected}


@pytest.mark.parametrize(
    "customers,partners,source",
    [
        ([_kna1(), _kna1(NAME1="B")], [], "KNA1"),
        ([_kna1()], [_partner(NAME_ORG1="A"), _partner(NAME_ORG1="B")], "BUT000"),
    ],
)
def test_build_clients_raises_on_duplicate_client_id(customers, partners, source):
    with pytest.raises(ValueError, match=f"Duplicate client_id in {source}"):
        _clients(customers, partners)


# --- invoices ----------------------------------------------------------------


def _item(**overrides) -> dict:
    row = {
        "BUKRS": "1000",
        "BELNR": "1400000001",
        "GJAHR": "2026",
        "BUZEI": "001",
        "KUNNR": "0100000001",
        "BSCHL": "01",
        "UMSKZ": "",
        "SHKZG": "S",
        "WRBTR": Decimal("100.00"),
        "H_WAERS": "EUR",
        "H_BLDAT": "20260110",
        "H_BLART": "RV",
        "ZUONR": "",
        "VBELN": "6071717686",
        "ZFBDT": "20260115",
        "ZBD1T": Decimal("30"),
        "ZBD2T": Decimal("0"),
        "ZBD3T": Decimal("0"),
        "REBZG": "",
        "REBZJ": "",
        "REBZZ": "",
        "REBZT": "",
    }
    row.update(overrides)
    return {transforms._BSEG[k]: v for k, v in row.items()}


def _invoices(*items: dict) -> pl.DataFrame:
    return transforms.build_open_invoices(pl.DataFrame(list(items)))


def _payment(amount: str, belnr: str = "1500000001") -> dict:
    return _item(
        BELNR=belnr,
        BSCHL="15",
        SHKZG="H",
        WRBTR=Decimal(amount),
        VBELN="",
        REBZT="Z",
        REBZG="1400000001",
        REBZJ="2026",
        REBZZ="001",
    )


def test_build_open_invoices_columns_and_types():
    rows = _invoices(_item())
    assert tuple(rows.columns) == transforms.INVOICE_COLUMNS
    row = rows.row(0, named=True)
    assert row["invoice_id"] == "1000/2026/1400000001/001"
    assert row["billing_document"] == "6071717686"
    assert row["issue_date"].isoformat() == "2026-01-10"
    # Exact Decimal, never a float round-trip.
    assert row["total_amount"] == Decimal("100.00")
    assert row["amount_paid"] == Decimal("0.00")
    assert row["open_amount"] == Decimal("100.00")


def test_build_open_invoices_sums_partial_payments():
    rows = _invoices(_item(), _payment("30.00"), _payment("20.50", belnr="1500000002"))
    assert rows.height == 1
    assert rows["amount_paid"].item() == Decimal("50.50")
    assert rows["open_amount"].item() == Decimal("49.50")


def test_build_open_invoices_ignores_unlinked_credits():
    """A credit memo or payment on account is not an invoice, nor paid against one."""
    rows = _invoices(
        _item(),
        _item(BELNR="1600000001", BSCHL="11", SHKZG="H"),
        _item(BELNR="1600000002", BSCHL="15", SHKZG="H"),
    )
    assert rows["invoice_id"].to_list() == ["1000/2026/1400000001/001"]
    assert rows["amount_paid"].item() == Decimal("0.00")


@pytest.mark.parametrize(
    "bschl,umskz,is_invoice",
    [
        ("01", "", True),
        # A receivable SAPF103 re-posted to special G/L 'E' is still owed.
        ("09", "E", True),
        # A down-payment request is a debit, not an invoice.
        ("09", "A", False),
        ("05", "", False),
        ("07", "", False),
    ],
)
def test_build_open_invoices_selects_invoice_lines(bschl, umskz, is_invoice):
    rows = _invoices(_item(BSCHL=bschl, UMSKZ=umskz))
    assert rows.height == (1 if is_invoice else 0)


def test_build_open_invoices_blank_billing_document_is_null():
    """A non-SD invoice has no billing document."""
    assert _invoices(_item(H_BLART="DR", VBELN=""))["billing_document"].item() is None


@pytest.mark.parametrize(
    "zuonr,expected",
    [("14000000010012025", "1400000001"), ("", None), ("FT 2025/123", None), ("1400000001001202", None)],
)
def test_build_open_invoices_original_document(zuonr, expected):
    assert _invoices(_item(ZUONR=zuonr))["original_document_nr"].item() == expected


@pytest.mark.parametrize(
    "terms,expected",
    [
        ({"ZBD1T": Decimal("30")}, "2026-02-14"),
        ({"ZBD1T": Decimal("10"), "ZBD2T": Decimal("60")}, "2026-03-16"),
        ({"ZBD1T": Decimal("10"), "ZBD2T": Decimal("20"), "ZBD3T": Decimal("90")}, "2026-04-15"),
        ({"ZBD1T": Decimal("0")}, "2026-01-15"),
    ],
)
def test_build_open_invoices_net_due_date(terms, expected):
    assert _invoices(_item(**terms))["due_date"].item().isoformat() == expected


def test_build_open_invoices_raises_on_duplicate_invoice_id():
    with pytest.raises(ValueError, match="Duplicate invoice_id"):
        _invoices(_item(), _item())


@pytest.fixture
def stub_invoice_db(monkeypatch):
    calls: dict = {"known": set(), "upserted": None, "deleted": None}

    async def _existing(table, id_column):
        return set(calls["known"])

    async def _upsert(table, rows, **kwargs):
        calls["upserted"] = [r["invoice_id"] for r in rows]
        return len(rows)

    async def _delete(table, key_column, keys, **kwargs):
        calls["deleted"] = keys
        return len(keys)

    monkeypatch.setattr(load, "existing_ids", _existing)
    monkeypatch.setattr(load, "upsert_rows", _upsert)
    monkeypatch.setattr(load, "delete_rows", _delete)
    return calls


def test_sync_open_invoices_deletes_cleared(stub_invoice_db):
    stub_invoice_db["known"] = {"1000/2026/1400000001/001", "1000/2026/1400000009/001"}
    counts = run(load.sync_open_invoices(_invoices(_item())))
    assert stub_invoice_db["upserted"] == ["1000/2026/1400000001/001"]
    assert stub_invoice_db["deleted"] == ["1000/2026/1400000009/001"]
    assert (counts.upserted, counts.deleted) == (1, 1)


def test_sync_open_invoices_refuses_empty_extract(stub_invoice_db):
    """An empty read must not wipe the table."""
    stub_invoice_db["known"] = {"1000/2026/1400000001/001"}
    with pytest.raises(ValueError, match="refusing to delete"):
        run(load.sync_open_invoices(_invoices(_item()).clear()))
    assert stub_invoice_db["deleted"] is None


def test_sync_open_invoices_dry_run_writes_nothing(stub_invoice_db):
    stub_invoice_db["known"] = {"1000/2026/1400000009/001"}
    run(load.sync_open_invoices(_invoices(_item()), dry_run=True))
    assert stub_invoice_db["upserted"] is None
    assert stub_invoice_db["deleted"] is None


# --- upsert_rows SQL ---------------------------------------------------------
# `upsert_rows` deliberately does NOT filter generated columns; the guarantee
# lives in the transforms' column-set assertions above. Do not add filtering
# here — it would hide a real bug instead of surfacing it.


class _FakePool:
    def __init__(self):
        self.calls: list[tuple[str, list]] = []

    def acquire(self):
        return _FakeAcquire(self)

    async def execute(self, query, *params):
        self.calls.append((query, list(params)))
        return "DELETE 2"


class _FakeAcquire:
    def __init__(self, pool):
        self.pool = pool

    async def __aenter__(self):
        return _FakeConn(self.pool)

    async def __aexit__(self, *exc):
        return False


class _FakeConn:
    def __init__(self, pool):
        self.pool = pool

    def transaction(self):
        return _FakeAcquire(self.pool)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def executemany(self, query, params):
        self.pool.calls.append((query, list(params)))


@pytest.fixture
def fake_pool(monkeypatch):
    pool = _FakePool()

    async def _get_pool():
        return pool

    monkeypatch.setattr(utils_db, "get_pool", _get_pool)
    return pool


def test_upsert_rows_builds_conflict_clause(fake_pool):
    run(utils_db.upsert_rows("t", [{"id": 1, "name": "a"}], conflict_columns=["id"]))
    query = fake_pool.calls[0][0]
    assert "ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name" in query
    # The conflict column is not in the SET list.
    assert "id = EXCLUDED.id" not in query


def test_upsert_rows_composite_conflict_columns(fake_pool):
    run(utils_db.upsert_rows("t", [{"a": 1, "b": 2, "c": 3}], conflict_columns=["a", "b"]))
    assert "ON CONFLICT (a, b) DO UPDATE SET c = EXCLUDED.c" in fake_pool.calls[0][0]


def test_upsert_rows_empty_update_columns_is_do_nothing(fake_pool):
    run(utils_db.upsert_rows("t", [{"id": 1}], conflict_columns=["id"], update_columns=[]))
    assert "DO NOTHING" in fake_pool.calls[0][0]


def test_upsert_rows_chunks(fake_pool):
    rows = [{"id": n} for n in range(2500)]
    sent = run(utils_db.upsert_rows("t", rows, conflict_columns=["id"], chunk_size=1000))
    assert sent == 2500
    assert len(fake_pool.calls) == 3


def test_upsert_rows_empty_writes_nothing(fake_pool):
    assert run(utils_db.upsert_rows("t", [], conflict_columns=["id"])) == 0
    assert fake_pool.calls == []


def test_delete_rows_empty_writes_nothing(fake_pool):
    assert run(utils_db.delete_rows("t", "id", [])) == 0
    assert fake_pool.calls == []


def test_delete_rows_parses_command_tag(fake_pool):
    assert run(utils_db.delete_rows("t", "po_code", ["a", "b"])) == 2


# --- orchestration -----------------------------------------------------------


@pytest.fixture
def stub_sync(monkeypatch):
    """Record which tables synced, in order, and the watermark POs got."""
    calls: dict = {"order": [], "since": "unset"}

    async def _bu(dry_run):
        calls["order"].append("business_units")
        return load.SyncCounts(table="dim_business_units")

    async def _sup(dry_run):
        calls["order"].append("suppliers")
        return load.SyncCounts(table="dim_suppliers"), []

    async def _cl(dry_run):
        calls["order"].append("clients")
        return load.SyncCounts(table="dim_clients")

    async def _po(full, dry_run):
        calls["order"].append("purchase_orders")
        calls["since"] = None if full else Decimal("1")
        return load.SyncCounts(table="fct_purchase_orders")

    async def _inv(dry_run):
        calls["order"].append("invoices")
        return load.SyncCounts(table="fct_invoices")

    monkeypatch.setattr(pipeline, "_sync_business_units", _bu)
    monkeypatch.setattr(pipeline, "_sync_suppliers", _sup)
    monkeypatch.setattr(pipeline, "_sync_clients", _cl)
    monkeypatch.setattr(pipeline, "_sync_purchase_orders", _po)
    monkeypatch.setattr(pipeline, "_sync_invoices", _inv)
    return calls


def test_run_sync_syncs_dims_before_facts(stub_sync):
    run(pipeline.run_sync())
    assert stub_sync["order"] == ["business_units", "suppliers", "clients", "purchase_orders", "invoices"]


def test_run_sync_full_ignores_watermark(stub_sync):
    run(pipeline.run_sync(full=True))
    assert stub_sync["since"] is None


def test_run_sync_incremental_uses_watermark(stub_sync):
    run(pipeline.run_sync())
    assert stub_sync["since"] == Decimal("1")


def test_run_sync_subset(stub_sync):
    run(pipeline.run_sync(tables=("suppliers",)))
    assert stub_sync["order"] == ["suppliers"]


def test_run_sync_continues_after_a_table_fails(monkeypatch, stub_sync):
    async def _boom(dry_run):
        raise RuntimeError("lakehouse down")

    monkeypatch.setattr(pipeline, "_sync_suppliers", _boom)
    results, _ = run(pipeline.run_sync())

    assert "purchase_orders" in stub_sync["order"]
    assert [c.failed for c in results] == [False, True, False, False, False]
