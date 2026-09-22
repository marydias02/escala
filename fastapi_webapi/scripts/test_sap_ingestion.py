"""Probe the SAP VIM document-registration endpoint with deliberately shaped payloads.

Mirrors the "Document registration IS" request in IS_LPTLabs_Insomnia.yaml: an
OAuth2 client_credentials token, then a multipart POST carrying three parts —
`register_document_request` (XML), `document` (the PDF) and `metadata` (the
extfield/extvalue table).

The point is to find out what SAP actually enforces, so each scenario omits or
varies one thing:

    mandatory_only  every mandatory field, nothing else -> baseline
    with_tax        mandatory + TOT_TAX_AMOUNT          -> optional field accepted?
    no_po           EBELN dropped                       -> is EBELN really mandatory?
    multi_po        two EBELN entries                   -> are several POs accepted?
    no_supplier     LIFNR dropped                       -> is the supplier id enforced?
    no_fields       empty <metadata>, real PDF          -> are fields enforced at all?
    empty_pdf       full metadata, zero-byte attachment -> is the file checked?
    garbage_pdf     full metadata, non-PDF bytes        -> is the file type checked?

Credentials come from the environment (see SAP_* below). Dry run by default;
nothing leaves the machine until you pass --send.

    python scripts/test_sap_ingestion.py                       # print payloads only
    python scripts/test_sap_ingestion.py --send                # run every scenario
    python scripts/test_sap_ingestion.py --send --case no_po   # run one scenario
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import httpx
from dotenv import find_dotenv, load_dotenv

if f := find_dotenv():
    load_dotenv(f)

# -- Credentials ---------------------------------------------------------------

SAP_INGEST_URL = os.getenv("SAP_INGEST_URL", "")
SAP_TOKEN_URL = os.getenv("SAP_TOKEN_URL", "")
SAP_CLIENT_ID = os.getenv("SAP_CLIENT_ID", "")
SAP_CLIENT_SECRET = os.getenv("SAP_CLIENT_SECRET", "")
SAP_TIMEOUT = float(os.getenv("SAP_TIMEOUT", "60"))

# -- Baseline field values (from the Insomnia example) -------------------------

COMPANY_CODE = "1130"
SUPPLIER_ID = "0100003004"
PURCHASE_ORDER = "5000363827"
PURCHASE_ORDER_2 = "5000363828"
CURRENCY = "EUR"
GROSS_AMOUNT = "200.00"
TOTAL_TAX_AMOUNT = "0.00"

# Labels SAP shows for each extfield. Values are informational, but the example
# sends them, so send them too rather than discovering they matter the hard way.
FIELD_LABELS = {
    "BLDAT": "Document Date",
    "BUKRS": "Company Code",
    "EBELN": "Purchase Order",
    "GROSS_AMOUNT": "Gross Amount",
    "LIFNR": "Vendor Number",
    "TOT_TAX_AMOUNT": "Total Tax Amount",
    "WAERS": "Currency",
    "XBLNR": "Reference Number",
}

MANDATORY_FIELDS = ["BLDAT", "BUKRS", "EBELN", "GROSS_AMOUNT", "LIFNR", "WAERS", "XBLNR"]


def _reference_number(case_name: str) -> str:
    """A reference unique per run, so repeat runs are not rejected as duplicates."""
    return f"TEST-{case_name.upper()}-{datetime.now():%Y%m%d%H%M%S}"


def base_fields(case_name: str) -> list[tuple[str, str]]:
    """The mandatory set, as ordered (extfield, extvalue) pairs."""
    return [
        ("BLDAT", date.today().strftime("%Y%m%d")),
        ("BUKRS", COMPANY_CODE),
        ("EBELN", PURCHASE_ORDER),
        ("GROSS_AMOUNT", GROSS_AMOUNT),
        ("LIFNR", SUPPLIER_ID),
        ("WAERS", CURRENCY),
        ("XBLNR", _reference_number(case_name)),
    ]


# -- Scenarios -----------------------------------------------------------------


@dataclass
class Case:
    name: str
    question: str
    drop: list[str] = field(default_factory=list)
    add: list[tuple[str, str]] = field(default_factory=list)
    no_fields: bool = False
    pdf: Literal["valid", "empty", "garbage"] = "valid"

    def fields(self) -> list[tuple[str, str]]:
        if self.no_fields:
            return []
        kept = [(k, v) for k, v in base_fields(self.name) if k not in self.drop]
        return kept + self.add


CASES = [
    Case("mandatory_only", "Does the mandatory set alone succeed?"),
    Case(
        "with_tax",
        "Is TOT_TAX_AMOUNT accepted alongside the mandatory set?",
        add=[("TOT_TAX_AMOUNT", TOTAL_TAX_AMOUNT)],
    ),
    Case("no_po", "Is EBELN really mandatory?", drop=["EBELN"]),
    Case(
        "multi_po",
        "Are several EBELN entries accepted, and how are they indexed?",
        add=[("EBELN", PURCHASE_ORDER_2)],
    ),
    Case("no_supplier", "Is LIFNR enforced?", drop=["LIFNR"]),
    Case(
        "no_fields",
        "Are the mandatory fields enforced at the API, or deferred to OCR/manual keying?",
        no_fields=True,
    ),
    Case("empty_pdf", "Is a zero-byte attachment rejected?", pdf="empty"),
    Case("garbage_pdf", "Is the attachment validated as a PDF at all?", pdf="garbage"),
]

CASES_BY_NAME = {case.name: case for case in CASES}


# -- Payload construction ------------------------------------------------------


def build_metadata_xml(fields: list[tuple[str, str]]) -> str:
    """The <metadata> part: one <Table> block per field.

    Repeated extfields (multi_po) get a 1-based extindex; single ones are left
    blank, matching the example. If SAP wants a different multi-value convention,
    the multi_po response is what tells us.
    """
    if not fields:
        return '<?xml version="1.0" encoding="UTF-8"?>\n<metadata>\n</metadata>'

    counts: dict[str, int] = {}
    for name, _ in fields:
        counts[name] = counts.get(name, 0) + 1

    seen: dict[str, int] = {}
    blocks = []
    for name, value in fields:
        if counts[name] > 1:
            seen[name] = seen.get(name, 0) + 1
            extindex = str(seen[name])
        else:
            extindex = ""
        blocks.append(
            "\t<Table>\n"
            f"\t\t<extindex>{extindex}</extindex>\n"
            f"\t\t<fieldinfo>{FIELD_LABELS.get(name, name)}</fieldinfo>\n"
            f"\t\t<extfield>{name}</extfield>\n"
            f"\t\t<extvalue>{value}</extvalue>\n"
            "\t</Table>"
        )
    return '<?xml version="1.0" encoding="UTF-8"?>\n<metadata>\n' + "\n".join(blocks) + "\n</metadata>"


def build_register_request_xml() -> str:
    """The <register_document_request> part: scan metadata for this submission."""
    now = datetime.now()
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<register_document_request>\n"
        f"\t<scan_date>{now:%Y-%m-%d}</scan_date>\n"
        f"\t<scan_time>{now:%H:%M:%S}</scan_time>\n"
        "\t<scan_user>LTPLabs</scan_user>\n"
        "\t<doc_type>PDF</doc_type>\n"
        "\t<version>000000001</version>\n"
        "</register_document_request>"
    )


def placeholder_pdf() -> bytes:
    """A minimal one-page PDF. The content is irrelevant — SAP only needs a file."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"

    xref_at = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1)
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref_at,
    )
    return bytes(out)


def case_pdf(case: Case, valid: bytes) -> bytes:
    """The attachment for one case — a real PDF unless the case corrupts it."""
    if case.pdf == "empty":
        return b""
    if case.pdf == "garbage":
        return b"this is not a pdf"
    return valid


# -- Sending -------------------------------------------------------------------


def missing_credentials() -> list[str]:
    """Which SAP_* variables are unset — checked before any scenario runs."""
    required = {
        "SAP_INGEST_URL": SAP_INGEST_URL,
        "SAP_TOKEN_URL": SAP_TOKEN_URL,
        "SAP_CLIENT_ID": SAP_CLIENT_ID,
        "SAP_CLIENT_SECRET": SAP_CLIENT_SECRET,
    }
    return [name for name, value in required.items() if not value]


def fetch_token(client: httpx.Client) -> str:
    """OAuth2 client_credentials token for the Integration Suite endpoint."""
    response = client.post(
        SAP_TOKEN_URL,
        data={"grant_type": "client_credentials"},
        auth=(SAP_CLIENT_ID, SAP_CLIENT_SECRET),
    )
    response.raise_for_status()
    return response.json()["access_token"]


def send_case(client: httpx.Client, token: str, case: Case, pdf: bytes) -> httpx.Response:
    """POST one scenario's multipart payload to the ingestion endpoint."""
    return client.post(
        SAP_INGEST_URL,
        headers={"Authorization": f"Bearer {token}"},
        files={
            "register_document_request": (None, build_register_request_xml(), "application/xml"),
            "document": ("test_invoice.pdf", case_pdf(case, pdf), "application/pdf"),
            "metadata": (None, build_metadata_xml(case.fields()), "application/xml"),
        },
    )


# -- Reporting -----------------------------------------------------------------


def print_case(case: Case, show_xml: bool) -> None:
    print("\n" + "=" * 70)
    print(f"  {case.name}  —  {case.question}")
    print("=" * 70)
    sent = [name for name, _ in case.fields()]
    print("  fields:  " + (", ".join(sent) if sent else "<none>"))
    absent = [name for name in MANDATORY_FIELDS if name not in sent]
    if absent:
        print("  omitted: " + ", ".join(absent))
    if case.pdf != "valid":
        print(f"  pdf:     {case.pdf}")
    if show_xml:
        print("\n" + build_metadata_xml(case.fields()))


def print_response(response: httpx.Response) -> None:
    marker = "✅" if response.is_success else "❌"
    print(f"  {marker} HTTP {response.status_code}")
    body = response.text.strip()
    print("  " + (body[:2000] if body else "<empty body>"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send", action="store_true", help="actually POST to SAP")
    parser.add_argument("--case", action="append", choices=list(CASES_BY_NAME), help="run only these scenarios")
    parser.add_argument("--xml", action="store_true", help="print the metadata XML for each scenario")
    parser.add_argument("--save-pdf", type=Path, help="write the placeholder PDF here and exit")
    args = parser.parse_args()

    if args.save_pdf:
        args.save_pdf.write_bytes(placeholder_pdf())
        print(f"wrote {args.save_pdf}")
        return 0

    cases = [CASES_BY_NAME[name] for name in args.case] if args.case else CASES

    if not args.send:
        for case in cases:
            print_case(case, show_xml=True)
        print("\nDry run — nothing sent. Re-run with --send to POST to SAP.")
        return 0

    if absent := missing_credentials():
        print("Missing environment variables: " + ", ".join(absent))
        return 1

    pdf = placeholder_pdf()
    with httpx.Client(timeout=SAP_TIMEOUT) as client:
        token = fetch_token(client)
        print(f"Authenticated against {SAP_TOKEN_URL}")

        for case in cases:
            print_case(case, show_xml=args.xml)
            try:
                print_response(send_case(client, token, case, pdf))
            except httpx.HTTPError as exc:
                print(f"  ❌ {type(exc).__name__}: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
