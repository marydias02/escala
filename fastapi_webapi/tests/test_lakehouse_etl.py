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
        "MANDT": "100",
        "LIFNR": "0100000001",
        "NAME1": "Acme",
        "NAME2": "",
        "NAME3": "",
        "NAME4": "",
        "STCEG": "PT123456789",
        "STCD1": "",
        "LAND1": "PT",
        "SPERR": "",
        "SPERM": "",
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
    rows, _ = transforms.build_suppliers(_lfa1(), _but000())
    assert tuple(rows.columns) == transforms.SUPPLIER_COLUMNS
    assert not {"id_norm", "vat_norm", "vat_core", "name_norm"} & set(rows.columns)


def test_build_suppliers_keeps_supplier_without_partner_row():
    rows, _ = transforms.build_suppliers(_lfa1(), _but000(partner="9999999999"))
    assert rows.height == 1
    assert rows["preferred_language"].item() is None


def test_build_suppliers_blank_language_becomes_null():
    rows, _ = transforms.build_suppliers(_lfa1(), _but000(langu=""))
    assert rows["preferred_language"].item() is None


def test_build_suppliers_vat_falls_back_to_stcd1():
    rows, _ = transforms.build_suppliers(_lfa1(STCEG=None, STCD1="509225918"), _but000())
    assert rows["vat"].item() == "509225918"


def test_build_suppliers_collapses_duplicate_lifnr():
    df = pl.concat([_lfa1(), _lfa1(NAME1="Acme II")])
    rows, _ = transforms.build_suppliers(df, _but000())
    assert rows.height == 1


@pytest.mark.parametrize("flags", [{"SPERR": "X"}, {"SPERM": "X"}, {"SPERR": "X", "SPERM": "X"}])
def test_build_suppliers_deletes_blocked(flags):
    df = pl.concat([_lfa1(), _lfa1(LIFNR="0000001270", **flags)])
    rows, deletes = transforms.build_suppliers(df, _but000())
    assert rows["supplier_id"].to_list() == ["0100000001"]
    assert deletes == ["0000001270"]


def test_build_suppliers_null_flags_are_active():
    rows, deletes = transforms.build_suppliers(_lfa1(SPERR=None, SPERM=None), _but000())
    assert rows.height == 1
    assert deletes == []


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
    row = {"MANDT": "100", "BUKRS": bu_id, "BUTXT": "GS Lines", "STCEG": "PT511011911", "LAND1": "PT", "F_OBSOLETE": ""}
    row.update(overrides)
    return row


def test_build_business_units_columns():
    rows, _ = transforms.build_business_units(pl.DataFrame([_t001()]))
    assert tuple(rows.columns) == transforms.BUSINESS_UNIT_COLUMNS


def test_build_business_units_deletes_obsolete():
    """PT511030746 is OPM (1060) and Bitrans (1100, obsolete): only OPM stays."""
    df = pl.DataFrame(
        [
            _t001("1060", BUTXT="OPM", STCEG="PT511030746"),
            _t001("1100", BUTXT="Bitrans", STCEG="PT511030746", F_OBSOLETE="X"),
        ]
    )
    rows, deletes = transforms.build_business_units(df)
    assert rows["bu_id"].to_list() == ["1060"]
    assert deletes == ["1100"]


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


def test_sync_dimension_deletes_inactive_and_excludes_them_from_absent(monkeypatch):
    deleted: list = []

    async def _existing(table, id_column):
        return {"1060", "1100", "9999"}

    async def _upsert(table, rows, **kwargs):
        return len(rows)

    async def _delete(table, key_column, keys, **kwargs):
        deleted.extend(keys)
        return len(keys)

    monkeypatch.setattr(load, "existing_ids", _existing)
    monkeypatch.setattr(load, "upsert_rows", _upsert)
    monkeypatch.setattr(load, "delete_rows", _delete)

    rows = pl.DataFrame([{"bu_id": "1060", "name": "OPM", "vat": "PT511030746", "country": "PT"}])
    counts = run(load.sync_business_units(rows, ["1100"]))

    assert deleted == ["1100"]
    assert (counts.upserted, counts.deleted, counts.absent_from_source) == (1, 1, 1)


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

    async def _po(full, dry_run):
        calls["order"].append("purchase_orders")
        calls["since"] = None if full else Decimal("1")
        return load.SyncCounts(table="fct_purchase_orders")

    monkeypatch.setattr(pipeline, "_sync_business_units", _bu)
    monkeypatch.setattr(pipeline, "_sync_suppliers", _sup)
    monkeypatch.setattr(pipeline, "_sync_purchase_orders", _po)
    return calls


def test_run_sync_syncs_dims_before_facts(stub_sync):
    run(pipeline.run_sync())
    assert stub_sync["order"] == ["business_units", "suppliers", "purchase_orders"]


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
    assert [c.failed for c in results] == [False, True, False]
