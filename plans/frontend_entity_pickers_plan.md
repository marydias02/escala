# ESCALA — Frontend entity pickers (supplier / business unit / PO)

## Why

`plotly_webapp/pages/email_detail.py` lets a reviewer edit **supplier name**, **supplier VAT**
and **business-unit name** as free text. It never sets `supplier_id` / `bu_id` — and
`invoice_extraction.decisions.ingestion_blockers` refuses to ingest a document whose ids are
null (`"supplier_id not found in registry"`). So a reviewer can "fix" an invoice by hand and it
still will not ingest.

Three backend search endpoints now exist to close that. This plan covers wiring them into the
page. **The backend is done and merged; nothing here requires backend work** except one
optional item flagged in §6.

---

## What the backend gives you

All three: bearer auth, `q` and `limit` (1..20, default 10) query params, `200 []` when nothing
matches, ranked best-first. A single result is still a list of one — **never auto-select it**;
a VAT is shared across branches and vessels, so "exactly one result" does not mean "the right
one".

| Endpoint | min `q` | Returns per row |
|---|---|---|
| `GET /suppliers/search` | 3 | `supplier_id, name, vat, country, is_financial` |
| `GET /business-units/search` | 2 | `bu_id, name, vat, country` |
| `GET /purchase-orders/search` | 3 | `po_code, supplier_id, bu_id, date, value, currency,`<br>`supplier_name, supplier_vat, bu_name, bu_vat` |

Matching is generous on purpose: id with or without zero-padding, VAT with or without country
prefix, name regardless of accents/punctuation, plus fuzzy fallback for typos. **You do not need
to pre-clean what the user typed** — send it as-is.

Error shapes worth handling:
- **422** — `q` shorter than the minimum, or `limit` out of range. Guard client-side so this
  never fires.
- **400** — `q` that is long enough raw but empty after normalization (`"..."`, `"PT "`). Rare
  but reachable; must not surface as a stack trace.
- The API helper `_request()` in `assets/api_calls/extraction_api.py` calls `raise_for_status()`,
  so **both raise `RequestException`**. Catch and show no options.

---

## 1. Fields to add to the page

Today the page shows `bu_name`, `supplier_name`, `supplier_vat` (three `dcc.Input`s at roughly
`email_detail.py:300-331`) and no PO at all. Target state:

| Field | Today | Target |
|---|---|---|
| `supplier_name` | free text | **picker** (searches id, VAT or name) |
| `supplier_vat` | free text | read-only, filled from the selection |
| `supplier_id` | absent | **new** — the field that actually unblocks ingestion |
| `bu_name` | free text | **picker** |
| `bu_vat` | absent (commented out at `:154`) | read-only, filled from the selection |
| `bu_id` | absent | **new** |
| `po_list` | absent from the UI entirely | **new** — picker + list of chosen POs |

Open question for you: **how visible should the ids be?** They are what matters technically but
mean little to a reviewer. Options: show them small/muted under the name, show them only inside
the dropdown option label, or keep them in a `dcc.Store` and never render them. Worth a quick
opinion from whoever owns the review UX — this decides how much layout changes.

`po_list` is genuinely new UI: `GET /extraction/documents/{id}` already returns it and
`email_detail.py` ignores it. A document can carry several POs, so this is a list the reviewer
adds to and removes from, not a single field.

---

## 2. Debounce

**Nothing to implement server-side** — debounce is a client-side timer. The endpoints' minimum
lengths already stop the pathological queries.

Dash specifics:
- `dcc.Input(debounce=True)` waits for blur/Enter — **wrong for a picker**, you need results
  while typing.
- `dcc.Dropdown` fires its `search_value` prop **on every keystroke**. That is the thing to damp.

Target ~250–350ms. Two routes:

1. **Ship without debounce first.** Gate the callback on `len(search_value.strip()) >= min` and
   measure. Few reviewers, indexed queries, small tables — per-keystroke may simply be fine, and
   this is the cheapest thing that could work.
2. **If it is not fine**, add a clientside debounce in `assets/`. Dash has no `debounce` prop on
   `search_value`, so this is a small JS clientside callback. Check whether the design system
   already has a pattern for this before writing one.

Start with (1). Do not build (2) on speculation.

---

## 3. Supplier and BU pickers

Same shape for both; build **supplier first as the pilot** — it exercises every hard part
(shared VAT, the name/VAT merge, the confidence write). Only generalise to BU once supplier
feels right in the hand.

Use the design system's `Select` (`components/select/select.py`), not a raw `dcc.Dropdown` — it
wraps `dcc.Dropdown`, passes `**kwargs` straight through (so `search_value` works), and gives
you `label`, `has_error`/`error_message` and `additional_message` for free.

Pieces:

**a. API client functions** — add to `assets/api_calls/` following the existing `_request`
pattern. Either extend `extraction_api.py` or start `search_api.py`; your call, but note
`extraction_api.py` also holds dashboard caching that has nothing to do with search.

**b. Search callback** — `Input(picker, "search_value")` → `Output(picker, "options")`. Guard
the minimum length, catch `RequestException` → `[]`.

**c. Option labels** must disambiguate, because shared VATs mean two rows can look identical:
`f"{name} — {vat or 'sem NIF'} ({supplier_id})"`. `value` is always the canonical id.

**d. A `dcc.Store` of the full rows.** On selection the dropdown hands back only the id, but the
save needs `name` and `vat` too. Stash results keyed by id; look up on select. The page already
uses this pattern (`document_fields_store`), so follow it.

**e. Selection callback** fills the sibling fields — name, VAT, and the hidden id.

**f. Seed the initial options.** On load a document may already have a `supplier_id`.
`dcc.Dropdown` renders **nothing** for a value absent from `options`, so the current selection
must be seeded in or the field looks empty on a document that is in fact filled.

**Known Dash friction:** `search_value` resets on blur. Tab away mid-search and the typed text
vanishes. Workarounds exist (persist `search_value` into a Store) but it is fiddly — build one
picker end to end and *try it* before committing to three.

---

## 4. PO picker with party auto-fill

The PO endpoint was widened specifically for this: each row carries `supplier_name`,
`supplier_vat`, `bu_name`, `bu_vat` alongside the ids, so **selecting a PO can fill both parties
in one step**.

Flow: reviewer types a PO code → picks one → supplier and BU fields populate from that row →
the PO is appended to `po_list`.

Three cases that are not the happy path:

**Party fields can be null.** `fct_purchase_orders` has no FKs (the SAP feeds land out of order
and the dim tables are truncate-and-reloaded), so the backend uses LEFT JOINs. A PO whose
supplier has not landed in the current snapshot returns with `supplier_id` set but
`supplier_name` null. Auto-fill must cope: fill the id, leave the name blank, do not crash and
do not blank out a name the reviewer already had.

**Conflict with what is already there.** If the document already names supplier X and the picked
PO belongs to supplier Y, silently overwriting is wrong — that disagreement is a signal, and
`decisions.py` has a whole `PartyMismatch` concept for it. Decide with the UX owner: warn and
let the reviewer choose, or overwrite and show what changed. **Do not silently overwrite.**

**Pre-2026 POs do not exist.** `fct_purchase_orders` only holds `BEDAT >= 2026-01-01`. An older
PO returns `[]` — indistinguishable from a typo unless you say so. Worth an explicit "not in the
PO set" hint rather than an empty dropdown.

---

## 5. Saving

The save callback is `update_document_details` at roughly `email_detail.py:507-600`.

Two changes:

**a. Write the ids.** `supplier_id` / `bu_id` are the fields `ingestion_blockers` checks. Writing
name and VAT alone changes nothing about whether the document ingests — this is the whole point
of the work.

**b. Confidence.** `update_field()` (`:560-562`) preserves whatever confidence was there, which
is right for a text edit and **wrong for a picker selection**: a human choice would inherit the
LLM's low confidence and potentially stay blocked. A human selection should write `1.0`. Needs a
variant of `update_field` that sets confidence rather than preserving it.

Also check `missing_field_alert_map` (`:583-593`) — it drives the "Campo em falta" alerts and
currently lists the three text fields by their Portuguese labels. New required fields likely
belong there; confirm which are genuinely required.

`po_list` entries are `{"value", "confidence"}` like every other field, and the backend
`PATCH /extraction` replaces the whole `document_content` blob — no API change needed for any
of this.

---

## 6. Possible backend follow-up

Not needed to start, listed so it is not rediscovered later:

- **Supplier/BU lookup by id**, for seeding initial options (§3f) when a document already has an
  id. You can currently fake it by searching the id as `q` — it matches at tier 100 — so try
  that before asking for an endpoint.
- `/extraction/business-units/exists` still matches raw `WHERE vat = $1`, so formatting
  differences miss. Unrelated to the pickers but adjacent.

---

## Suggested order

1. API client functions + supplier picker end to end, including save with `confidence: 1.0`.
   **Verify a document actually ingests afterwards** — that is the acceptance test for the whole
   feature, and everything else is a repeat of it.
2. Decide on debounce from what you observe in (1).
3. BU picker (mechanical repeat).
4. PO picker + `po_list` UI + the auto-fill conflict rule from §4.

---

## Before you start

- Run the backend locally (`uv run uvicorn api.main:app`) and poke the endpoints in Swagger
  **before** writing any Dash code — you will learn the response shapes faster than from this
  document.
