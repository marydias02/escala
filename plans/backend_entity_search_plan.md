# ESCALA — Backend entity search (suppliers / business units / purchase orders)

## Context

The invoice review page (`plotly_webapp/pages/email_detail.py`) lets a reviewer edit supplier name, supplier VAT and business-unit name as free text. It never sets `supplier_id` / `bu_id`, yet `invoice_extraction.decisions.ingestion_blockers` blocks ingestion when either id is null. The frontend needs pickers that resolve a typed query to a canonical `dim_suppliers` / `dim_business_units` / `fct_purchase_orders` row. This plan adds three ranked, server-side search endpoints on the FastAPI backend. Frontend pickers are out of scope. **Nothing is implemented yet; this is the plan.**

Decisions already confirmed with the user:
- Source: Postgres `dim_*` / `fct_purchase_orders` tables (not the lakehouse).
- `pg_trgm` and `unaccent` extensions may be created by a migration.
- Authorization: new `suppliers` / `business_units` / `purchase_orders` resources with `read` in the RBAC policy.

---

## A. Current-state findings

**Architecture** (all under `fastapi_webapi/`, imports rooted at `src/`):
- Router → service → repository → `api.sql.BaseRepository` over a module-global asyncpg pool. Raw SQL with `$n` params, lists returned via `query_df` → polars → `df.to_dicts()`. No ORM; Alembic migrations are hand-written (`migrations/env.py` has `target_metadata = None`).
- Routers: `src/api/routers/{extraction,validation,health,airpy_example}.py`, each with its own prefix, registered in `src/api/routers/__init__.py::include_all_routers`. Response type is the return annotation. Query params are bare defaults (`limit: int = 100`); `fastapi.Query` is not used anywhere yet.
- Schemas: all in `src/api/messages/store.py`, snake_case, `<Entity>Read` naming.
- DI: `src/api/dependencies/services.py` (`get_extraction_service` + `ExtractionServiceDep`), overridden in tests.
- Auth: `src/api/dependencies/security.py` — OIDC bearer + `policy` dict keyed `"Admin"`/`"User"`; `has_authorization_for(action, resource)`. No per-entity (ABAC) scoping exists. Precedent for a dim-table lookup: `GET /extraction/business-units/exists?vat=` (any valid token, raw `WHERE vat = $1`).
- Errors: `src/api/exceptions.py` (400/404/409 `HTTPException` subclasses); no custom handlers; empty lists return `200 []`.
- Tests: `tests/conftest.py` — sync `TestClient`, no DB, `override_claims`, `mint_token(roles=...)`, service stubs via `dependency_overrides`. No DB-backed tests exist.

**Schema** (`migrations/versions/20260821_01_add_supplier_bu_po_tables copy.py`, widened by `20260915_01`):
- `dim_suppliers(supplier_id varchar(10) PK, name varchar(255) NOT NULL, vat varchar(20) NULL, country varchar(2), preferred_language varchar(2), is_financial int)`. Only the PK index.
- `dim_business_units(bu_id varchar(4) PK, name varchar(255) NOT NULL, vat varchar(20) NULL, country varchar(2))`. Only the PK index.
- `fct_purchase_orders(po_code varchar(10) PK, supplier_id varchar(10), bu_id varchar(4), date, value numeric(18,2), currency)`. Btree on `supplier_id`, `bu_id`. No FKs by design (SAP feeds land out of order). Loaded only for `BEDAT >= 2026-01-01`.
- No extensions installed; no trigram/GIN/functional indexes anywhere.
- Alembic HEAD: `20260918_01` (`20260918_01_create_email_sync_tables.py`). Naming: `YYYYMMDD_NN_<slug>.py`, revision id = filename prefix.

**Data formats** (from `scripts/seed_sap_real_data.py`, `scripts/test_sap_ingestion.py`, `tools/po_confirmation.py`):
- `supplier_id` = SAP `LFA1.LIFNR`, zero-padded 10 digits (`0100003539`); dummy seed uses 9 digits (`100000001`).
- `bu_id` = `T001.BUKRS`, 4 chars (`1130`, `0001`).
- `po_code` = `EKKO.EBELN`, 10 digits, ranges `45…`, `47…`, `50…`.
- `vat` = `STCEG` else `STCD1`: mostly `PT500697370`; also `NL800822274B01`, `LU19578473`, bare `286861798`. **Not unique** (branches/vessels share one VAT).
- `name` = `NAME1..NAME4` joined, often truncated mid-word, Portuguese accents (`Município`, `Comercializ. Energia,`).
- Load path: `TRUNCATE` + `utils.utils_db.insert_rows` with explicit column lists (verified), so stored generated columns are safe.

**Existing normalization to reuse**:
- `utils.utils_db.normalize_key(value)` (strip non-alnum, upper) and `normalize_sql(column)` = `upper(regexp_replace(col, '[^A-Za-z0-9]', '', 'g'))`.
- `tools/po_confirmation._same_party` compares ids with `lstrip("0")`.
- `utils_lakehouse.strip_country_prefix_str` (do not import into API; pulls lakehouse deps).
- `nodes/validate._normalize_name` (NFKD accent strip, lower, punctuation drop) — the SQL function below mirrors it.

**Invoice workflow**: `fct_documents.document_content` JSONB holds `supplier_id/supplier_name/supplier_vat/bu_id/bu_name/bu_vat` as `{"value","confidence"}` and `po_list` as a list of the same. No FK columns. `PATCH /extraction` replaces the whole blob (`DocumentsRepository.alter`). The Dash page merges edits with `update_field(name, value)` preserving confidence.

**Known pre-existing issue**: `policy` keys are `"Admin"`/`"User"` but `tests/test_authorization.py` and `conftest.mint_token` use lowercase `"user"`/`"admin"`. Run pytest before starting; write new tests with the exact policy keys.

---

## B. Recommended architecture

Shared infrastructure, separate domain semantics:
- **Shared**: `Query` param validation helpers (min/max length, `limit` 1..20), `SearchService` parameter preparation (`normalize_key`, id-digit and VAT-core helpers), `BaseRepository`, RBAC pattern, response-model conventions, one router module.
- **Domain-specific**: one SQL statement + one repository class per domain; supplier and BU share the same SQL template (different table/id column), PO has its own numeric-oriented SQL.
- Normalization is **stored** in generated columns (`id_norm`, `vat_norm`, `vat_core`, `name_norm`) computed once per row at write time, so every match tier compares plain columns, each of which can carry its own index. No normalization expression is repeated inside the queries.
- Trigram fuzziness uses an explicit threshold constant set per query (`SET LOCAL`), never the server default silently.
- The response is always zero to `limit` distinct candidates ordered by relevance. The backend never auto-selects, and the frontend must not auto-select a lone result either.
- Frontend guidance (out of scope, for the follow-up): debounce picker input by roughly 250–350 ms before calling any of the three endpoints, and only call once the trimmed query reaches the endpoint's minimum length.

---

## C. Supplier search design

Endpoint `GET /suppliers/search?q=<str>&limit=<1..20>` (min `q` length 3, max 64).

**Query validation in the service** (after FastAPI's `min_length`): trim `q`, compute `key = normalize_key(q)` and `name_q` (Python mirror of `f_search_norm`, i.e. `nodes/validate._normalize_name`). If both are `None` or the longer of them is shorter than the endpoint's minimum (suppliers 3, business units 2, purchase orders 3; one `MIN_QUERY_LENGTH` constant per domain shared by the router's `Query(min_length=...)` and the service check), raise `BadRequestError("query too short after normalization")` (400, `api.exceptions`). So `"PT "`, `"   "`, `"..."` are rejected, not silently searched.

Parameters: `$1` raw trimmed `q`; `$2` `key`; `$3` `id_q` = `key.lstrip("0") or "0"` when `key.isdigit()` else NULL (the `or "0"` keeps an all-zero query from collapsing to an empty prefix that matches every row); `$4` `vat_core_q` = `key` with a leading `^[A-Z]{2}(?=[0-9])` removed; `$5` limit. Normalized per-row values are **stored generated columns** (section F): `id_norm`, `vat_norm`, `vat_core`, `name_norm`. Nothing is recomputed per row in the query.

Ranking tiers (higher wins), one `CASE` per row so no duplicates:

| Tier | Match |
|---|---|
| 100 | `id_norm = $3` (zero-pad-insensitive exact id) |
| 95 | `vat_norm = $2` (exact normalized VAT) |
| 90 | `vat_core = $4` (country prefix stripped on both sides) |
| 80 | `id_norm LIKE $3 || '%'` |
| 75 | `vat_norm` or `vat_core` prefix |
| 70 | `name_norm = f_search_norm($1)` |
| 60 | name prefix |
| 50 | name substring |
| 40 | `name_norm % f_search_norm($1)` (pg_trgm, threshold set explicitly, see below) |

Order: `tier DESC, similarity(name_norm, name_q) DESC, length(name) ASC, supplier_id ASC`. Response: `supplier_id, name, vat, country, is_financial`.

SQL (in `search_repository.py`; `{table}`, `{id}` and `{select}` filled from class constants):

```sql
WITH q AS (
    SELECT $2::text AS key, $3::text AS id_q, $4::text AS vat_core_q, public.f_search_norm($1::text) AS name_q
),
scored AS (
    SELECT s.supplier_id, s.name, s.vat, s.country, s.is_financial,
           CASE
             WHEN s.id_norm = q.id_q                                                   THEN 100
             WHEN s.vat_norm = q.key                                                   THEN 95
             WHEN s.vat_core = q.vat_core_q                                            THEN 90
             WHEN s.id_norm LIKE q.id_q || '%'                                         THEN 80
             WHEN s.vat_norm LIKE q.key || '%' OR s.vat_core LIKE q.vat_core_q || '%'  THEN 75
             WHEN s.name_norm = q.name_q                                               THEN 70
             WHEN s.name_norm LIKE q.name_q || '%'                                     THEN 60
             WHEN s.name_norm LIKE '%' || q.name_q || '%'                              THEN 50
             WHEN s.name_norm % q.name_q                                               THEN 40
           END AS tier,
           similarity(s.name_norm, q.name_q) AS sim
    FROM dim_suppliers s CROSS JOIN q
    WHERE s.id_norm LIKE q.id_q || '%'
       OR s.vat_norm LIKE q.key || '%'
       OR s.vat_core LIKE q.vat_core_q || '%'
       OR s.name_norm LIKE '%' || q.name_q || '%'
       OR s.name_norm % q.name_q
)
SELECT supplier_id, name, vat, country, is_financial
FROM scored WHERE tier IS NOT NULL
ORDER BY tier DESC, sim DESC, length(name) ASC, supplier_id ASC
LIMIT $5
```
A NULL parameter disables its branch (`LIKE NULL` and `= NULL` are NULL, i.e. false), so no `IS NOT NULL` guards are needed.

**Trigram threshold**: `%` reads `pg_trgm.similarity_threshold` from the session. The repository sets it explicitly per call: `TRIGRAM_SIMILARITY_THRESHOLD = 0.3` module constant; each search runs inside `async with self.pool.acquire() as conn, conn.transaction():` with `SELECT set_config('pg_trgm.similarity_threshold', $1, true)` before the `fetch`. `set_config(..., is_local=true)` scopes it to that transaction, so nothing leaks to other pool users. This needs a small `query_df_with_threshold` helper on the search repositories (not on `BaseRepository`, which has no transaction helper). Document in the repository docstring that `%` is index-accelerated only through the GUC, which is why `similarity() >= x` is not used in `WHERE`.

LIKE metacharacters need no escaping: every value reaching LIKE has been reduced to `[A-Za-z0-9 ]` by `normalize_key` / `f_search_norm` (document this invariant in the service).

Indexes (suppliers): GIN `gin_trgm_ops` on `name_norm` (serves prefix, substring and `%`); btree `text_pattern_ops` on `id_norm`, `vat_norm` and `vat_core` (each `=` and prefix `LIKE` hits its own column's index; no expression indexes needed).

---

## D. Business-unit search design

Endpoint `GET /business-units/search?q=<str>&limit=` — **min `q` length 2**, applied both to the raw `q` (`Query(min_length=2)`) and to the normalized query in the service (`bu_id` is 4 chars and codes are grouped by their first two digits, e.g. `11xx`; the table has tens of rows). A one-character query is therefore always rejected: 422 when raw, 400 when it only becomes one character after normalization (e.g. `"1."`). Same SQL template as suppliers with `dim_business_units b`, `b.bu_id`, select `bu_id, name, vat, country`. No `is_financial`, no active/inactive flag exists in the schema, so nothing to filter. No indexes needed at this size (generated columns are still added so the SQL template is shared). Existing `/extraction/business-units/exists` stays untouched.

---

## E. Purchase-order search design

Endpoint `GET /purchase-orders/search?q=<str>&limit=` (min 3, max 64). PO search is by `po_code` only.

Representation: `po_code varchar(10)`, in practice 10 digits, three live ranges (`45`, `47`, `50` = SAP document type).

Service validation: strip all whitespace; if the result is shorter than 3 characters raise `BadRequestError` (400); if it contains a non-digit or is longer than 10 characters (EBELN is CHAR(10), nothing longer can match) return `[]` without querying. So `$1` is always `^[0-9]{3,10}$`, which fits `bigint` and keeps every cast on the parameter safe.

Definition of "close":
1. **Exact** (tier 100) and **prefix** (tier 80): `po_code LIKE $1 || '%'` on the PK btree.
2. **Fuzzy** (tier 60): `po_code % $1` via GIN trigram, only when `length($1) >= 8` (one wrong or transposed digit in a near-complete code; at threshold 0.3 that is roughly one wrong digit). Same explicit `set_config` threshold as suppliers.
3. **Numeric neighbours** (tier 40): only for a complete 10-digit query, the `limit` nearest codes above and below via two ordered PK walks. Each walk filters `po_code ~ '^[0-9]{10}$'` **before** its inner `ORDER BY ... LIMIT`, so only fixed-width numeric codes are walked (they sort identically as text and as numbers, so no cast in `WHERE`) and a non-numeric or shorter code can never consume a neighbour slot. Neighbours may cross the 45/47/50 ranges; that is intended (no range clause). Ordered by numeric distance.

Distance is type-safe: `q.code_num` is computed once in the `q` CTE as `bigint` (safe, see validation above); every neighbour row has already passed the ten-digit filter, so `n.po_code::bigint` cannot fail, and all `distance` columns are declared `bigint` in every branch of the `UNION ALL`.

A code appearing in both fuzzy and neighbours is de-duplicated with `DISTINCT ON (po_code)` keeping the best tier. Final order: `tier DESC, sim DESC, distance ASC NULLS LAST, date DESC NULLS LAST, po_code ASC`. Response: `po_code, supplier_id, bu_id, date, value, currency` (supplier/BU ids are already in the row and are useful to warn about party mismatches; no joins).

```sql
WITH q AS (
    SELECT $1::text AS code, $1::bigint AS code_num
),
exact_prefix AS (
    SELECT p.po_code, p.supplier_id, p.bu_id, p.date, p.value, p.currency,
           CASE WHEN p.po_code = q.code THEN 100 ELSE 80 END AS tier,
           1.0::real AS sim, 0::bigint AS distance
    FROM fct_purchase_orders p CROSS JOIN q
    WHERE p.po_code LIKE q.code || '%'
),
fuzzy AS (
    SELECT p.po_code, p.supplier_id, p.bu_id, p.date, p.value, p.currency,
           60 AS tier, similarity(p.po_code, q.code) AS sim, NULL::bigint AS distance
    FROM fct_purchase_orders p CROSS JOIN q
    WHERE length(q.code) >= 8 AND p.po_code % q.code
),
neighbours AS (
    (SELECT p.po_code, p.supplier_id, p.bu_id, p.date, p.value, p.currency
     FROM fct_purchase_orders p CROSS JOIN q
     WHERE length(q.code) = 10 AND p.po_code ~ '^[0-9]{10}$' AND p.po_code > q.code
     ORDER BY p.po_code ASC LIMIT $2)
    UNION ALL
    (SELECT p.po_code, p.supplier_id, p.bu_id, p.date, p.value, p.currency
     FROM fct_purchase_orders p CROSS JOIN q
     WHERE length(q.code) = 10 AND p.po_code ~ '^[0-9]{10}$' AND p.po_code < q.code
     ORDER BY p.po_code DESC LIMIT $2)
),
candidates AS (
    SELECT * FROM exact_prefix
    UNION ALL SELECT * FROM fuzzy
    UNION ALL
    SELECT n.po_code, n.supplier_id, n.bu_id, n.date, n.value, n.currency,
           40 AS tier, 0::real AS sim,
           abs(n.po_code::bigint - q.code_num)::bigint AS distance
    FROM neighbours n CROSS JOIN q
),
best AS (SELECT DISTINCT ON (po_code) * FROM candidates ORDER BY po_code, tier DESC)
SELECT po_code, supplier_id, bu_id, date, value, currency
FROM best
ORDER BY tier DESC, sim DESC, distance ASC NULLS LAST, date DESC NULLS LAST, po_code ASC
LIMIT $3
```

Index: GIN `gin_trgm_ops` on `po_code` (fuzzy tier only; PK serves the rest).

---

## F. Database changes

New migration `fastapi_webapi/migrations/versions/20260918_02_search_normalization_and_indexes.py` — `revision = "20260918_02"`, `down_revision = "20260918_01"`. Use `[0-9]` not `\d` in non-raw strings.

`upgrade()`:
1. `CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;`
2. `public.f_unaccent(text)` — `LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS $$ SELECT public.unaccent('public.unaccent', $1) $$` (unaccent itself is STABLE; generated columns/indexes need IMMUTABLE; docstring must state the caveat).
3. `public.f_search_norm(text)` — `LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS $$ SELECT nullif(btrim(regexp_replace(public.f_unaccent(lower($1)), '[^a-z0-9]+', ' ', 'g')), '') $$`, mirroring `nodes/validate._normalize_name`. Both functions are created, referenced (in the generated columns and in the query CTEs) and dropped with the explicit `public.` schema so they do not depend on `search_path`.
4. For `dim_suppliers` (id column `supplier_id`) and `dim_business_units` (id column `bu_id`), four `GENERATED ALWAYS AS (...) STORED` text columns. Postgres forbids a generated column from referencing another generated column, so `vat_core` is derived from `vat` directly, not from `vat_norm`:
   - `id_norm` = `coalesce(nullif(ltrim(<id>, '0'), ''), '0')` (zero-pad-insensitive; an all-zero id becomes `'0'`, never empty)
   - `vat_norm` = `upper(regexp_replace(vat, '[^A-Za-z0-9]', '', 'g'))` (same expression as `utils_db.normalize_sql`)
   - `vat_core` = `nullif(regexp_replace(upper(regexp_replace(vat, '[^A-Za-z0-9]', '', 'g')), '^[A-Z]{2}(?=[0-9])', ''), '')` (Postgres ARE supports the lookahead)
   - `name_norm` = `public.f_search_norm(name)`
5. Indexes: `ix_dim_suppliers_name_norm_trgm` (GIN gin_trgm_ops), `ix_dim_suppliers_id_norm`, `ix_dim_suppliers_vat_norm`, `ix_dim_suppliers_vat_core` (btree text_pattern_ops each), `ix_fct_purchase_orders_po_code_trgm` (GIN gin_trgm_ops). None on `dim_business_units` (tens of rows; the columns exist only so the SQL template is shared).

`downgrade()`: drop the five indexes, drop the eight generated columns, drop the two functions. Leave extensions installed (harmless; dropping can fail if anything else depends on them).

Follow-up (separate change, note in PR): switch `BusinessUnitRepository.exists_by_vat` to `WHERE vat_norm = $1` with `normalize_key(vat)` so it matches `po_confirmation`'s behaviour.

---

## G. API contracts

All three: bearer auth, `has_authorization_for("read", <resource>)`, `q: str` (`Query(..., min_length=N, max_length=64)`), `limit: int` (`Query(10, ge=1, le=20)`), `200 []` on no match, `422` on invalid params (FastAPI default), `401`/`403` as today.

| Endpoint | min `q` | Resource | Response item |
|---|---|---|---|
| `GET /suppliers/search` | 3 | `suppliers` | `{supplier_id, name, vat, country, is_financial}` |
| `GET /business-units/search` | 2 | `business_units` | `{bu_id, name, vat, country}` |
| `GET /purchase-orders/search` | 3 | `purchase_orders` | `{po_code, supplier_id, bu_id, date, value, currency}` |

Post-normalization rule (all three): a query that is empty or shorter than the endpoint minimum (3 / 2 / 3, the same numbers as the `min q` column) after trimming and normalization (e.g. `"   "`, `"PT "`, `"..."`, BU `"1."`) is rejected with `400` via `api.exceptions.BadRequestError`; FastAPI's `422` only covers the raw-length check. A PO query that is well-formed but cannot match (non-digits, more than 10 digits) returns `200 []`.

The response is always zero to `limit` distinct candidates ordered by relevance. A single result is still a list of one; neither backend nor frontend auto-selects it.

---

## H. Workflow / data-model integration

- No schema change to `fct_documents`: the canonical ids already have slots in `document_content` (`supplier_id`, `bu_id`, `po_list[].value`). The frontend picker must write the returned `supplier_id`/`name`/`vat` (resp. `bu_id`, `po_code`) into those `{value, confidence}` entries via the existing `PATCH /extraction`; recommend `confidence: 1.0` for a human selection. That unblocks `decisions.ingestion_blockers` for manually resolved documents.
- FK columns on `fct_documents` are intentionally **not** proposed: `fct_purchase_orders` / `dim_*` are truncate-and-reloaded snapshots without FKs by design, so an FK would break the reload. If a relational link is wanted later, add nullable `supplier_id`/`bu_id` columns without FK constraints in a separate migration.
- `sap_processes.supplier_id`/`bu_id` (validation dashboard) are unaffected.

---

## I. File-by-file implementation plan

1. **Database/migrations** — new `fastapi_webapi/migrations/versions/20260918_02_search_normalization_and_indexes.py` (section F).
2. **Models/entities** — none (no ORM). Generated columns live in the migration only.
3. **Repository** — new `fastapi_webapi/src/api/repositories/search_repository.py`: constants `TRIGRAM_SIMILARITY_THRESHOLD = 0.3`, `PARTY_SEARCH_SQL` (template with `{table}`, `{id}`, `{select}`), `PO_SEARCH_SQL`; a small mixin/helper `_fetch_df_with_threshold(query, params)` that acquires a connection, opens a transaction, runs `set_config('pg_trgm.similarity_threshold', $1, true)`, fetches, and builds the polars frame the same way `BaseRepository.query_df` does; classes `SupplierSearchRepository(BaseRepository)` (`__table_name__ = "dim_suppliers"`), `BusinessUnitSearchRepository` (`"dim_business_units"`), `PurchaseOrderSearchRepository` (`"fct_purchase_orders"`), each with `async def search(...) -> pl.DataFrame`. Keep the `pool=` constructor passthrough for DB tests.
4. **Service** — new `fastapi_webapi/src/api/services/search_service.py`: `SearchService.__init__` instantiates the three repos (pattern of `ExtractionService`); `search_suppliers(q, limit)`, `search_business_units(q, limit)`, `search_purchase_orders(q, limit)` return `df.to_dicts()`. Private helpers `_id_query(key)` (`key.lstrip("0") or "0"` for digit keys), `_vat_core(key)` (3-line regex, do not import `utils_lakehouse`), `_name_query(q)` (Python mirror of `f_search_norm`), `_po_code(q)`, and `_require_min_length(...)` raising `BadRequestError`; import `normalize_key` from `utils.utils_db`.
5. **DI** — `fastapi_webapi/src/api/dependencies/services.py`: add `get_search_service()` and `SearchServiceDep`.
6. **Routes** — new `fastapi_webapi/src/api/routers/search.py` with three `APIRouter`s (`prefix="/suppliers"`, `"/business-units"`, `"/purchase-orders"`, `tags=["search"]`), shared `LimitParam = Annotated[int, Query(10, ge=1, le=20)]` and `_query_param(min_length)`; register all three in `fastapi_webapi/src/api/routers/__init__.py::include_all_routers`.
7. **Schemas** — `fastapi_webapi/src/api/messages/store.py`: add `SupplierSearchRead`, `BusinessUnitSearchRead`, `PurchaseOrderSearchRead` (`value: float | None` coerces asyncpg `Decimal`, as `DocumentRead.total_amount` does).
8. **Authorization** — `fastapi_webapi/src/api/dependencies/security.py`: add `"suppliers": {"read"}, "business_units": {"read"}, "purchase_orders": {"read"}` to both `"Admin"` and `"User"`.
9. **Workflow integration** — no backend change; document the `document_content` write contract (section H) in the router docstrings / PR.
10. **Tests** — section J.

---

## J. Testing plan

**(a) Router tests, no DB** — new `fastapi_webapi/tests/test_search_routes.py`; add `_StubSearchService` (records `(q, limit)`, returns a configurable list) and `stub_search_service` fixture to `tests/conftest.py` overriding `get_search_service`. For each route:
- `q` below min length (`"ab"` / BU `"a"`), missing `q`, 65-char `q` → 422.
- Service-level (unit test on `SearchService` with stubbed repositories): `"   "`, `"PT "`, `"..."` → `BadRequestError` (400) on suppliers/POs; BU `"1."` → 400 while BU `"11"` and `"1 1"` (normalizes to `"11"`) → accepted; `"000"` → `id_q == "0"`; `"pt 500 697 370"` → `key == "PT500697370"`, `vat_core_q == "500697370"`; PO `"ABC123"` and an 11-digit code → `[]` with no repository call; PO `" 5000 363827 "` → `"5000363827"`.
- `limit=0`, `limit=21`, `limit=abc` → 422; omitted → stub sees 10; `limit=5` → stub sees 5.
- Stub `[]` → `200 []`; stub one row → response echoes canonical fields unchanged.
- `override_claims(roles=["User"])` → 200; `roles=["Guest"]` → 403; `mint_token(roles=None)` → 403; no header → 401.

**(b) Repository tests, opt-in DB** — new `fastapi_webapi/tests/test_search_repositories.py`: skip the module unless `ESCALA_TEST_DATABASE_URI` is set (DB migrated to head, dedicated to tests). Session fixture creates its own event loop + asyncpg pool (no pytest-asyncio in dev deps) and injects `pool=` into the repositories. Fixture truncates the three tables, inserts rows with explicit column lists (never `name_norm`/`vat_norm`), truncates at teardown. Fixture rows: suppliers `0100003539 "Município de Lisboa" PT500697370`, `0100003540 "Município de Lisboa - Serviços Urbanos" PT500697370` (shared VAT), `0100004000 "EDP Comercializ. Energia," PT503504564`, `0100004001 "Van Dijk B.V." NL800822274B01`, `0100004002 "Lux Holding Sarl" LU19578473`, `0100004003 "Bare Vat Lda" 286861798`, `100000001 "Dummy Nine Digits" NULL`; BUs `1130 "EDP Distribuição" PT500697370`, `1100 "EDP Comercial"`, `0001 "Holding"`; POs `5000363827, 5000363828, 5000363830, 5000463827, 5000000001, 4500026805, 4700000001`.

Supplier cases: exact id; zero-pad variants `100003539` / `00100003539`; `000` → `[]` (matches nothing, never every row); 9-digit dummy id; id prefix `01000035` ranks both branches first; VAT `pt 500 697 370` → both shared-VAT rows (tier 95, "Município de Lisboa" first by length); VAT without prefix `500697370` (tier 90); VAT prefixes `PT5006` / `5006`; `NL800822274B01` and `800822274B01`; bare `286861798`; exact name unaccented `municipio de lisboa`; accented input `Município`; prefix `edp`; substring `energia`; punctuation-insensitive `comercializ energia`; fuzzy typo `municpio lisboa` (tier 40); ranking: VAT-core match outranks a supplier named "500697370 Lda"; `zzzzzz` → `[]`; `limit=1`; no duplicate ids.

BU cases: `1130`; `0001` / `1` / `01`; `11` prefix → 1130 and 1100 only; VAT exact and core; `edp` prefix → two rows; `distribuicao` accent-insensitive; `zz` → `[]`; limit.

PO cases: exact `5000363827` first and alone in tier 100; prefix `500036` → 27/28/30 only; `ABC123` → `[]` with no query; one-digit typo `5000463827` → exact first, then `5000363827` via fuzzy; missing complete code `5000363829` → 28 and 30 first (distance 1), 27 next; `4799999999` → neighbours include `5000000001` (ranges may cross); a fixture row with a non-numeric `po_code` (e.g. `"PO-TEST-01"`) never raises and never appears among neighbours (it can still be an exact/prefix hit); `5000000` prefix → `5000000001`; dedupe across fuzzy/neighbours; limit; `999` → `[]`; threshold: with `TRIGRAM_SIMILARITY_THRESHOLD` monkeypatched to `0.9`, the typo case no longer returns the fuzzy hit.

Also: run existing `pytest fastapi_webapi/tests` first to surface the role-casing mismatch; `ruff check` / `ruff format` on new files.

---

## K. Risks and trade-offs

- **IMMUTABLE wrapper**: `f_unaccent` declares immutability the unaccent dictionary cannot guarantee. If the rules file changes, `name_norm` and its index drift; fix by reload (seed already truncates) or drop/re-add the column. State this in the migration docstring.
- **Extension availability**: `CREATE EXTENSION pg_trgm` / `unaccent` needs the contrib modules present on the server and a role allowed to create extensions (both are trusted extensions since PG13, so `CREATE` on the database suffices). Confirm on each environment's Postgres before running the migration; it fails loudly otherwise.
- **Generated columns vs loaders**: `insert_rows` and `upload_df` pass explicit column lists (verified), so `seed_sap_real_data.py` / `seed_sap_dummy_data.py` are unaffected. Any future `INSERT … SELECT *` or `COPY` without a column list would break. Generated columns cannot reference each other, hence `vat_core` is derived from `vat`, duplicating the `vat_norm` expression inside the migration only.
- **Per-call `set_config` transaction**: each search acquires a connection and opens a short transaction to pin the trigram threshold. Cost is negligible at this volume, but it is the one place the API deviates from `BaseRepository`'s pool-level helpers; keep it confined to the search repositories.
- **Prepared-statement plans**: `LIKE $n || '%'` cannot use the btree prefix optimisation under a generic plan; the GIN trigram index has no such limit and the tables are small. Footnote, not a blocker.
- **VAT non-unique**: all branches sharing a VAT return in one tier; the picker must show names and let the reviewer choose. Do not auto-select unless exactly one row returns.
- **Pre-2026 PO gap**: `fct_purchase_orders` only holds `BEDAT >= 2026-01-01`; older POs search to `[]`, while the pipeline's `po_exists()` checks lakehouse EKKO. Either widen the seed window or show a "not in PO set" hint in the UI.
- **Role-casing mismatch** between `policy` and existing tests is pre-existing; new tests must use `"User"`/`"Admin"`.
- **Frontend not yet consuming**: endpoints are additive; `PATCH /extraction` is unchanged. Dash pickers (`dcc.Dropdown` with `search_value` callbacks) are a follow-up; none exist today.
- **Unrelated but noted**: `non_conformities_resolution/sap/sap_queries.py` builds SQL with f-strings of caller values. New repositories use only `$n` parameters and class-constant table names.

---

## Verification

1. `cd fastapi_webapi && uv run alembic upgrade head` against a dev DB; confirm `\df f_search_norm`, `\d dim_suppliers` shows `id_norm`/`vat_norm`/`vat_core`/`name_norm`, and the five indexes exist. Spot-check: `SELECT supplier_id, id_norm, vat, vat_norm, vat_core, name, name_norm FROM dim_suppliers LIMIT 20` looks right for accented and unprefixed rows. Run `uv run alembic downgrade -1` then `upgrade head` to prove reversibility.
2. Re-run `scripts/seed_sap_real_data.py` (or the dummy seed) to prove the truncate-and-reload still works with generated columns.
3. `uv run pytest tests/` — new router tests pass without a DB; set `ESCALA_TEST_DATABASE_URI` and run `tests/test_search_repositories.py` for the ranking matrix.
4. Start the API (`uv run uvicorn api.main:app` per existing run instructions) and exercise via Swagger with a real token: `/suppliers/search?q=munic`, `/suppliers/search?q=PT 500 697 370`, `/business-units/search?q=11`, `/purchase-orders/search?q=5000363829`; check `EXPLAIN ANALYZE` on the supplier query shows the GIN index for the name branch.
