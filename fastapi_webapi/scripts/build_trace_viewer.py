"""Build a self-contained HTML viewer for the invoice-extraction traces.

Reads the MLflow SQLite backend plus the source PDFs on disk and writes ONE
`.html` file with everything embedded. No server, no CORS, no dependencies —
open it by double-clicking, email it, put it on a USB stick.

    python scripts/build_trace_viewer.py --out trace_viewer.html

Why this exists
---------------
`tracing.py` is explicit that traces are development instrumentation and that
"nothing here is meant to be shown to a customer". This script is the boundary
that makes them presentable: it re-labels the pipeline stages in business
language and drops confidence scores, token costs, evidence strings and raw LLM
prompts. Redaction happens *here*, on the way out — the excluded fields never
reach the HTML, so they cannot be recovered with devtools. `--include-internals`
re-enables them for internal review.

Where the data lives
--------------------
Not in `mlruns/1/traces/` — that holds only PDF blobs, the same document
duplicated once per LLM call, extension-less and UUID-named. The real trace data
is in `mlflow.db`, and the usable PDFs are found through the `extract:` span's
`spanInputs.path`, which is an absolute path to the split document on disk.
"""

from __future__ import annotations

import argparse
import base64
import json
import sqlite3
import sys
from html import escape
from pathlib import Path
from typing import Any, Optional

# --------------------------------------------------------------------------- #
# Stage presentation
# --------------------------------------------------------------------------- #
#
# Maps the pipeline's internal span names onto the language a client speaks.
# `scope` decides whether a stage belongs to the whole email or to one document:
# document stages are the per-PDF pipeline, email stages apply across all of
# them and are badged accordingly in the UI.

STAGES: list[dict[str, Any]] = [
    {"span": "email-intent", "label": "Email Triage", "scope": "email"},
    {"span": "1-chunking", "label": "Document Splitting", "scope": "email"},
    {"span": "2-classification", "label": "Document Classification", "scope": "document"},
    {"span": "3-parsing", "label": "Text Extraction", "scope": "document"},
    {"span": "4-extraction", "label": "Data Extraction", "scope": "document"},
    {"span": "5-validation", "label": "Validation & Verification", "scope": "document"},
    {"span": "6-decision", "label": "Routing Decision", "scope": "email"},
]

# `email-intent` runs only on the no-PDF branch, so listing it for every email
# would imply a step that is usually absent. Shown only where it actually ran.
CONDITIONAL_STAGES = {"email-intent"}

# Field labels. Anything not named here still renders, with the raw key
# prettified — a new pipeline field shows up as readable text rather than
# vanishing silently.
FIELD_LABELS = {
    "filename": "Document",
    "total_pages": "Pages",
    "document_type": "Document Type",
    "document_state": "Document State",
    "document_exception": "Exception",
    "supplier_name": "Supplier",
    "supplier_vat": "Supplier VAT",
    "supplier_id": "Supplier ID",
    "client_name": "Client",
    "client_vat": "Client VAT",
    "bu_name": "Business Unit",
    "bu_vat": "Business Unit VAT",
    "bu_id": "Business Unit ID",
    "issue_date": "Issue Date",
    "base_amount": "Net Amount",
    "vat_amount": "VAT",
    "total_amount": "Total",
    "currency": "Currency",
    "po_list": "Purchase Orders",
    "notes": "Notes",
    "count": "Documents Found",
    "documents": "Documents",
    "problems": "Problems",
    "action": "Action",
    "reason": "Reason",
    "subject": "Subject",
    "body_chars": "Body Length",
    "is_invoice_related": "Invoice Related",
    "has_invoice_link": "Contains Invoice Link",
    "chars": "Characters Extracted",
    "ok": "Succeeded",
    "status": "Status",
}

# Internal-only keys. Dropped unless --include-internals.
REDACTED_KEYS = {
    "confidence",
    "evidence",
    "min_confidence",
    "has_parsed_text",
    "start_page",
    "end_page",
    "reply_lines",
    "should_reply",
    "reply_text",
    "intent",
}

# Amount fields, formatted with the document's currency.
AMOUNT_KEYS = {"base_amount", "vat_amount", "total_amount"}


# --------------------------------------------------------------------------- #
# Reading the trace store
# --------------------------------------------------------------------------- #


def _span_io(content: str) -> tuple[dict, dict]:
    """Pull a span's inputs and outputs out of its OTel content blob.

    MLflow stores these double-encoded: `content` is JSON, and the
    `mlflow.spanInputs` / `mlflow.spanOutputs` attributes inside it are
    themselves JSON *strings*. Hence the second parse.
    """
    try:
        attrs = json.loads(content).get("attributes", {})
    except (json.JSONDecodeError, TypeError):
        return {}, {}

    def parse(key: str) -> dict:
        raw = attrs.get(key)
        if not raw:
            return {}
        try:
            value = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {"value": value}

    return parse("mlflow.spanInputs"), parse("mlflow.spanOutputs")


def load_traces(db: Path) -> list[dict]:
    """Read every trace out of the MLflow SQLite backend."""
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    traces = []
    rows = conn.execute(
        "SELECT request_id, timestamp_ms, execution_time_ms, status "
        "FROM trace_info ORDER BY timestamp_ms"
    ).fetchall()

    for row in rows:
        trace_id = row["request_id"]
        tags = {
            t["key"]: t["value"]
            for t in conn.execute(
                "SELECT key, value FROM trace_tags WHERE request_id = ?", (trace_id,)
            )
        }
        spans = conn.execute(
            "SELECT span_id, parent_span_id, name, content "
            "FROM spans WHERE trace_id = ? ORDER BY start_time_unix_nano",
            (trace_id,),
        ).fetchall()

        traces.append(
            {
                "trace_id": trace_id,
                "timestamp_ms": row["timestamp_ms"],
                "duration_ms": row["execution_time_ms"],
                "tags": tags,
                # Note: span_id/parent_span_id come from the DB *columns* (hex).
                # The ids inside `content` are base64-encoded bytes and do not
                # match these — building the tree from those would find no
                # parents at all.
                "spans": [dict(s) for s in spans],
            }
        )

    conn.close()
    return traces


# --------------------------------------------------------------------------- #
# Redaction and value shaping
# --------------------------------------------------------------------------- #


def _unwrap(value: Any, keep_internals: bool) -> Any:
    """Reduce a pipeline value to what should be displayed.

    Extraction and validation emit uniform `{"value": ..., "confidence": ...}`
    dicts. For a client-facing view only `value` survives.
    """
    if isinstance(value, dict):
        if "value" in value and not keep_internals:
            return value["value"]
        return {
            k: _unwrap(v, keep_internals)
            for k, v in value.items()
            if keep_internals or k not in REDACTED_KEYS
        }
    if isinstance(value, list):
        return [_unwrap(v, keep_internals) for v in value]
    return value


def _format(key: str, value: Any, currency: Optional[str]) -> Optional[str]:
    """Render one value as display text, or None to omit the row entirely."""
    if value is None or value == "" or value == [] or value == {}:
        return None
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if key in AMOUNT_KEYS and isinstance(value, (int, float)):
        symbol = {"EUR": "€", "USD": "$", "GBP": "£"}.get(currency or "", "")
        return f"{symbol}{value:,.2f}".strip()
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def build_rows(payload: dict, keep_internals: bool) -> list[dict]:
    """Turn a span's input/output dict into ordered, labelled display rows."""
    if not payload:
        return []

    currency = payload.get("currency")
    if isinstance(currency, dict):
        currency = currency.get("value")

    rows = []
    for key, raw in payload.items():
        if not keep_internals and key in REDACTED_KEYS:
            continue
        # An absolute filesystem path is noise on screen and leaks the machine's
        # directory layout to whoever is watching.
        if key == "path":
            continue
        text = _format(key, _unwrap(raw, keep_internals), currency)
        if text is None:
            continue
        label = FIELD_LABELS.get(key) or key.replace("_", " ").title()
        rows.append({"label": label, "value": text, "block": "\n" in text})
    return rows


# --------------------------------------------------------------------------- #
# Assembling the view model
# --------------------------------------------------------------------------- #


def _stage_entry(
    spec: dict, span: Optional[dict], keep_internals: bool, missing_reason: str
) -> dict:
    """Build one stage, whether or not the pipeline actually reached it."""
    if span is None:
        return {
            "label": spec["label"],
            "scope": spec["scope"],
            "reached": False,
            "reason": missing_reason,
            "inputs": [],
            "outputs": [],
        }
    inputs, outputs = _span_io(span["content"])
    return {
        "label": spec["label"],
        "scope": spec["scope"],
        "reached": True,
        "reason": "",
        "inputs": build_rows(inputs, keep_internals),
        "outputs": build_rows(outputs, keep_internals),
    }


def build_view_model(traces: list[dict], keep_internals: bool) -> list[dict]:
    emails = []

    for trace in traces:
        spans = trace["spans"]
        by_name: dict[str, dict] = {}
        for span in spans:
            by_name.setdefault(span["name"], span)

        children: dict[str, list[dict]] = {}
        for span in spans:
            children.setdefault(span["parent_span_id"], []).append(span)

        tags = trace["tags"]
        action = tags.get("action", "")
        # Explains a short-circuit in the client's terms rather than leaving a
        # blank panel that reads as a failure.
        missing_reason = (
            f"Not reached — routed to {action.replace('Forward to ', '')} "
            "after classification."
            if action and "Ingest" not in action
            else "Not reached for this document."
        )

        documents = []
        for span in spans:
            if not span["name"].startswith("extract:"):
                continue

            inputs, _ = _span_io(span["content"])
            pdf_path = inputs.get("path")
            filename = inputs.get("filename") or span["name"][len("extract:") :]

            pdf_b64, pdf_error = None, None
            if pdf_path:
                path = Path(pdf_path)
                if path.is_file():
                    pdf_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
                else:
                    pdf_error = "The source PDF is no longer on disk."
            else:
                pdf_error = "No file path was recorded for this document."

            # Restrict to this document's own subtree, so a stage from a sibling
            # document in the same email cannot leak into this one's panel.
            subtree = {c["name"]: c for c in children.get(span["span_id"], [])}
            stages = [
                _stage_entry(
                    spec, subtree.get(spec["span"]), keep_internals, missing_reason
                )
                for spec in STAGES
                if spec["scope"] == "document"
            ]

            documents.append(
                {
                    "filename": filename,
                    "pdf": pdf_b64,
                    "pdf_error": pdf_error,
                    "stages": stages,
                }
            )

        email_stages = [
            _stage_entry(spec, by_name.get(spec["span"]), keep_internals, missing_reason)
            for spec in STAGES
            if spec["scope"] == "email"
            and (spec["span"] in by_name or spec["span"] not in CONDITIONAL_STAGES)
        ]

        subject = tags.get("email", trace["trace_id"])
        emails.append(
            {
                "subject": subject.removesuffix(".msg").lstrip("_"),
                "action": action,
                "documents": documents,
                "email_stages": email_stages,
            }
        )

    return emails


# --------------------------------------------------------------------------- #
# HTML
# --------------------------------------------------------------------------- #

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>__TITLE__</title>
<style>
  /* LTPlabs brand tokens — see .claude/skills/ltp-html/DESIGN.md.
     Bw Modelica is not bundled with this repo, so the stack falls back to a
     neutral geometric sans. Drop the .otf files beside this build and add the
     @font-face block if the deliverable needs to be fully on-brand. */
  :root {
    color-scheme: light;

    --ltp-navy: #19105f;
    --ltp-teal: #007474;
    --ltp-mint: #00a590;
    --ltp-orange: #ff6b00;
    --ltp-white: #ffffff;
    --ltp-off-white: #f4f7f9;
    --ltp-gray-100: #eaecf0;
    --ltp-gray-500: #666666;
    --ltp-charcoal: #1c1f27;

    --color-bg: var(--ltp-off-white);
    --color-surface: var(--ltp-white);
    --color-text: #000000;
    --color-text-muted: var(--ltp-gray-500);
    --color-heading: var(--ltp-navy);
    --color-accent: var(--ltp-orange);
    --color-interactive: var(--ltp-teal);
    --color-border: var(--ltp-gray-100);

    --font-sans: "Bw Modelica", "Futura", "Century Gothic", "Avenir Next",
                 "Segoe UI", sans-serif;

    --radius-md: 8px;
    --radius-lg: 12px;
    --radius-card: 24px;
    --radius-pill: 9999px;
    --shadow-soft: 0 8px 24px rgb(25 16 95 / 8%);
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--color-bg); color: var(--color-text);
    font: 16px/1.6 var(--font-sans); -webkit-font-smoothing: antialiased;
  }
  header {
    background: var(--color-surface); border-bottom: 1px solid var(--color-border);
    padding: 16px 24px; display: flex; gap: 24px; align-items: center;
    flex-wrap: wrap; position: sticky; top: 0; z-index: 5;
  }
  .logo { display: flex; align-items: center; }
  .logo svg { display: block; height: 30px; width: auto; }
  h1 {
    font-size: 18px; margin: 0 8px 0 0; font-weight: 500; line-height: 1.4;
    color: var(--color-heading);
  }
  .field { display: flex; align-items: center; gap: 8px; }
  .field > span {
    font-size: 12px; color: var(--color-text-muted); text-transform: uppercase;
    letter-spacing: .04em; font-weight: 500;
  }
  select {
    font: 400 14px/1.2 var(--font-sans); padding: 11px 12px;
    border: 1px solid var(--color-border); border-radius: var(--radius-md);
    background: var(--color-surface); color: var(--color-text);
    max-width: 460px; min-height: 44px; cursor: pointer;
    transition: border-color 160ms ease;
  }
  select:hover { border-color: var(--color-interactive); }
  select:focus-visible {
    outline: 2px solid var(--color-interactive); outline-offset: 1px;
  }
  .tag {
    margin-left: auto; font-size: 14px; font-weight: 500; color: #fff;
    background: var(--color-accent); padding: 8px 16px;
    border-radius: var(--radius-pill);
  }
  main {
    display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr);
    gap: 24px; padding: 24px; align-items: start;
  }
  .card {
    background: var(--color-surface); border: 1px solid var(--color-border);
    border-radius: var(--radius-lg); overflow: hidden;
    box-shadow: var(--shadow-soft);
  }
  .pdf { height: calc(100vh - 142px); }
  .pdf iframe { width: 100%; height: 100%; border: 0; display: block; }
  .stage-head {
    padding: 16px; border-bottom: 1px solid var(--color-border);
    display: flex; gap: 10px; align-items: center;
  }
  .stage-head strong {
    font-size: 18px; font-weight: 500; color: var(--color-heading);
  }
  .body { padding: 24px; max-height: calc(100vh - 210px); overflow-y: auto; }
  h2 {
    font-size: 12px; text-transform: uppercase; letter-spacing: .04em;
    font-weight: 500; color: var(--color-interactive); margin: 0 0 12px;
  }
  h2:not(:first-child) { margin-top: 32px; }
  table { width: 100%; border-collapse: collapse; }
  td { padding: 10px 0; border-bottom: 1px solid var(--color-border); vertical-align: top; }
  tr:last-child td { border-bottom: 0; }
  td.k { color: var(--color-text-muted); font-size: 14px; width: 38%; padding-right: 16px; }
  td.v { font-weight: 500; font-size: 14px; word-break: break-word; }
  td.v pre {
    margin: 0; font: 13px/1.5 ui-monospace, Consolas, monospace;
    background: var(--ltp-off-white); padding: 12px;
    border-radius: var(--radius-md);
    white-space: pre-wrap; word-break: break-word;
  }
  .badge {
    font-size: 12px; text-transform: uppercase; letter-spacing: .04em;
    background: var(--color-interactive); color: #fff; padding: 4px 10px;
    border-radius: var(--radius-pill); font-weight: 500;
  }
  .empty {
    display: flex; align-items: center; justify-content: center; height: 100%;
    min-height: 260px; padding: 48px; text-align: center;
    color: var(--color-text-muted); font-size: 14px; line-height: 1.6;
  }
  /* Flat tinted callout — no left-border accent stripe (DESIGN.md §6). */
  .note {
    background: var(--ltp-off-white); padding: 16px;
    border-radius: var(--radius-md); color: var(--color-text-muted);
    font-size: 14px;
  }
  option:disabled { color: var(--color-border); }
  @media (max-width: 900px) {
    main { grid-template-columns: 1fr; }
    .pdf { height: 65vh; }
    .body { max-height: none; }
  }
  @media print {
    header { position: static; }
    main { grid-template-columns: 1fr 1fr; }
    .card { box-shadow: none; }
    .body { max-height: none; overflow: visible; }
  }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: .01ms !important; transition-duration: .01ms !important;
    }
  }
</style>
</head>
<body>
<header>
  <span class="logo">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 685.48 251.1" aria-label="LTP logo">
      <path fill="#ff6b00" d="M685.48,96.88h-230.22V0s133.34,0,133.34,0c53.5,0,96.88,43.37,96.88,96.88h0Z"/>
      <polygon fill="#19105f" points="96.88 154.22 96.88 0 0 0 0 251.1 195.4 251.1 195.4 154.22 96.88 154.22"/>
      <path fill="#00a590" d="M552.15,96.88v96.88h36.46c53.5,0,96.88-43.37,96.88-96.88h-133.34Z"/>
      <path fill="#19105f" d="M244.23,0h-78.65v96.88h83.99v154.22h96.88V96.88h-5.33C287.6,96.88,244.23,53.51,244.23,0Z"/>
      <path fill="#ff6b00" d="M286.74-42.51h96.88V42.51c0,53.47-43.41,96.88-96.88,96.88h0V-42.51h0Z" transform="translate(383.62 -286.74) rotate(90)"/>
      <path fill="#007474" d="M552.15,96.88v154.22s-96.88,0-96.88,0v-57.34c0-53.5,43.37-96.88,96.88-96.88h0Z"/>
    </svg>
  </span>
  <h1>__TITLE__</h1>
  <label class="field"><span>Email</span><select id="email"></select></label>
  <label class="field"><span>Document</span><select id="doc"></select></label>
  <label class="field"><span>Stage</span><select id="stage"></select></label>
  <div class="tag" id="action"></div>
</header>
<main>
  <section class="card pdf" id="pdf"></section>
  <section class="card">
    <div class="stage-head"><strong id="stage-name"></strong><span id="scope"></span></div>
    <div class="body" id="detail"></div>
  </section>
</main>
<script>
const DATA = __DATA__;
const $ = (id) => document.getElementById(id);

/* Document stages come first: they are the per-PDF pipeline and the reason
   someone opened this page. Email-level stages bracket them as context. */
function stagesFor(email, doc) {
  const lead = email.email_stages.filter((s) => s.label === "Email Triage"
                                             || s.label === "Document Splitting");
  const tail = email.email_stages.filter((s) => !lead.includes(s));
  return [...lead, ...(doc ? doc.stages : []), ...tail];
}

function fill(select, items, label, enabled) {
  select.innerHTML = "";
  items.forEach((item, i) => {
    const o = document.createElement("option");
    o.value = i;
    o.textContent = label(item);
    if (enabled && !enabled(item)) o.disabled = true;
    select.appendChild(o);
  });
  select.disabled = items.length <= 1;
  const first = items.findIndex((it) => !enabled || enabled(it));
  select.selectedIndex = first === -1 ? 0 : first;
}

function table(rows) {
  return `<table>${rows.map((r) => `<tr><td class="k">${r.label}</td>` +
    `<td class="v">${r.block ? `<pre>${r.value}</pre>` : r.value}</td></tr>`
  ).join("")}</table>`;
}

function renderEmails() {
  fill($("email"), DATA, (e) => e.subject);
  renderDocs();
}

function renderDocs() {
  const email = DATA[$("email").value];
  $("action").textContent = email.action;
  if (email.documents.length) {
    fill($("doc"), email.documents, (d) => d.filename);
  } else {
    $("doc").innerHTML = "<option>No document attached</option>";
    $("doc").disabled = true;
  }
  renderStages();
}

function renderStages() {
  const email = DATA[$("email").value];
  const doc = email.documents[$("doc").value];
  fill($("stage"), stagesFor(email, doc), (s) => s.label, (s) => s.reached);
  render();
}

function render() {
  const email = DATA[$("email").value];
  const doc = email.documents[$("doc").value];
  const stage = stagesFor(email, doc)[$("stage").value];

  $("pdf").innerHTML = doc && doc.pdf
    ? `<iframe title="${doc.filename}" src="data:application/pdf;base64,${doc.pdf}"></iframe>`
    : `<div class="empty">${doc
        ? doc.pdf_error
        : "No document attached to this email.<br>It was routed on its content alone."}</div>`;

  if (!stage) { $("stage-name").textContent = ""; $("detail").innerHTML = ""; return; }

  $("stage-name").textContent = stage.label;
  $("scope").innerHTML = stage.scope === "email"
    ? '<span class="badge">Whole email</span>' : "";

  if (!stage.reached) {
    $("detail").innerHTML = `<div class="note">${stage.reason}</div>`;
    return;
  }
  const parts = [];
  if (stage.inputs.length) parts.push("<h2>Input</h2>" + table(stage.inputs));
  if (stage.outputs.length) parts.push("<h2>Output</h2>" + table(stage.outputs));
  $("detail").innerHTML = parts.join("")
    || '<div class="note">This stage completed without recorded detail.</div>';
}

$("email").addEventListener("change", renderDocs);
$("doc").addEventListener("change", renderStages);
$("stage").addEventListener("change", render);
renderEmails();
</script>
</body>
</html>
"""


def render_html(emails: list[dict], title: str) -> str:
    # `</script>` inside the payload would close the tag early; `<` is enough to
    # prevent it and stays valid JSON.
    payload = json.dumps(emails, ensure_ascii=False).replace("<", "\\u003c")
    return TEMPLATE.replace("__DATA__", payload).replace("__TITLE__", escape(title))


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main() -> int:
    root = Path(__file__).resolve().parent.parent

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=root / "mlflow.db")
    parser.add_argument("--out", type=Path, default=root / "trace_viewer.html")
    parser.add_argument("--title", default="Invoice Processing — Pipeline Walkthrough")
    parser.add_argument(
        "--include-internals",
        action="store_true",
        help="Keep confidence scores and evidence (internal review only).",
    )
    args = parser.parse_args()

    if not args.db.is_file():
        print(f"error: no trace database at {args.db}", file=sys.stderr)
        return 1

    emails = build_view_model(load_traces(args.db), args.include_internals)
    if not emails:
        print(f"error: {args.db} contains no traces", file=sys.stderr)
        return 1

    args.out.write_text(render_html(emails, args.title), encoding="utf-8")

    docs = sum(len(e["documents"]) for e in emails)
    missing = sum(1 for e in emails for d in e["documents"] if not d["pdf"])
    size = args.out.stat().st_size / 1_048_576

    print(f"{args.out}  ({size:.1f} MB)")
    print(f"  {len(emails)} emails, {docs} documents")
    if missing:
        print(f"  warning: {missing} document(s) had no readable PDF")
    if args.include_internals:
        print("  warning: built WITH internals — not for client viewing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
