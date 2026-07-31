"""Email- and document-level routing decisions — THE place to change the rules.

Two layers, deliberately separated:

1. `decide_document(result)` — what to do with ONE document, from its
   classification alone. Pure, no I/O, no LLM.
2. `decide_email(...)` — rolls the per-document decisions up into the single
   reply the email may get, and SUPPRESSES replies the email does not warrant.

The suppression in step 2 is why step 1's answers are not final: a duplicate
invoice asks for a reply on its own, but if the same email also carried the
original there is nothing to ask for. Any document reaching "Ingest in SAP"
cancels every reply in that email.

The full case matrix lives in `DOCUMENT_RULES` and `decide_email` below so the
business rules can be read without reading the pipeline.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional

from invoice_extraction.config import MIN_CONFIDENCE
from invoice_extraction.extraction_pipeline import PipelineResult
from invoice_extraction.ingestion_pipeline import EmailIngestionResult
from invoice_extraction.models import DocumentClassification, EmailIntent, ValidationReport
from invoice_extraction.tools.po_confirmation import po_exists, supplier_requires_po

# The complete action vocabulary. Written to `fct_documents.action`, so a Literal
# rather than free-form strings — a typo cannot silently invent a sixth action.
Action = Literal[
    "Ingest in SAP",
    "Sent back to Supplier",
    "Forward to Treasury",
    "Left in Inbox",
    "Validate Manually",
]

INGEST: Action = "Ingest in SAP"
REPLY: Action = "Sent back to Supplier"
TREASURY: Action = "Forward to Treasury"
INBOX: Action = "Left in Inbox"
MANUAL: Action = "Validate Manually"

# Reply wording, in Portuguese, per reason. Only reasons that can produce a
# REPLY appear here.
REPLY_TEXT_NO_PDF = "Por favor enviar o documento em formato pdf"
REPLY_TEXT_PROFORMA = "Documento proforma, por favor enviar o original"
REPLY_TEXT_COPY = "Documento duplicado, por favor enviar o original"

# Document types routed by the B-cases below. Kept in sync with
# `extraction_pipeline.EXTRACTABLE_TYPES` by intent, not by import, because this
# module asks a different question (what to DO) than the gate (what to extract).
# The two are not identical: the gate also extracts exception receipts, which are
# routed by the C-cases here.
_INVOICE_LIKE = ("invoice", "credit_note", "debit_note")

# --------------------------------------------------------------------------- #
# Go / no-go on the extraction itself — THE place to tune ingestion strictness.
# --------------------------------------------------------------------------- #

# `status == "validated"` only means the three stages ran without raising. It says
# nothing about whether the numbers are trustworthy, so a second, deterministic
# gate decides whether a document is good enough for SAP. Deliberately not an LLM
# judgement: this rule is auditable and testable.

# Every field here must be present AND clear MIN_CONFIDENCE. `supplier_id` /
# `bu_id` are excluded by design — the schema says they are always null until a
# later registry lookup fills them.
REQUIRED_FIELDS = (
    "supplier_vat",
    "bu_vat",
    "issue_date",
    "base_amount",
    "vat_amount",
    "total_amount",
    "currency",
)

def _field_problems(
    validation: ValidationReport, field_labels: dict[str, str]
) -> list[tuple[str, str, Optional[float]]]:
    """(field_name, label, confidence) for every missing or low-confidence field.

    confidence is None for a missing field, so callers can tell the two cases
    apart without re-deriving which one they're in.
    """
    problems: list[tuple[str, str, Optional[float]]] = []
    for name, label in field_labels.items():
        checked = getattr(validation, name, None)
        if checked is None:
            problems.append((name, label, None))
        elif checked.confidence < MIN_CONFIDENCE:
            problems.append((name, label, checked.confidence))
    return problems


def ingestion_blockers(validation: Optional[ValidationReport]) -> list[str]:
    """Why this extraction is not safe to ingest. Empty list == good to go.

    Returns reasons rather than a bool so the blocking field(s) can be named in
    the document's reason and, later, shown to a reviewer.
    """
    if validation is None:
        return ["no validation report"]

    return [
        f"{name} missing" if confidence is None
        else f"{name} confidence {confidence:.2f} < {MIN_CONFIDENCE}"
        for name, _label, confidence in _field_problems(
            validation, {name: name for name in REQUIRED_FIELDS}
        )
    ]


# Every ValidationReport field except supplier_id/bu_id (always null pre-registry
# lookup) and notes/po_list (handled separately, below). Portuguese labels since
# alerts_list is reviewer-facing.
_ALERT_FIELD_LABELS = {
    "supplier_name": "Nome do fornecedor",
    "supplier_vat": "NIF do fornecedor",
    "document_number": "Número do documento",
    "bu_name": "Nome do cliente",
    "bu_vat": "NIF do cliente",
    "issue_date": "Data de emissão",
    "base_amount": "Valor base",
    "vat_amount": "Valor de IVA",
    "total_amount": "Valor total",
    "currency": "Moeda",
}


def build_alerts_list(result: PipelineResult) -> list[str]:
    """Alerts for one document: missing/low-confidence fields, PO checks.

    Written to `fct_documents.alerts_list`, so entries are short, human-readable
    Portuguese strings for a reviewer, not machine codes.
    """
    validation = result.validation
    if validation is None:
        return ["Documento não validado"]

    alerts = [
        f"Campo em falta: {label}" if confidence is None
        else f"Confiança baixa: {label} ({confidence:.2f})"
        for _name, label, confidence in _field_problems(validation, _ALERT_FIELD_LABELS)
    ]

    # Second, independent deterministic check — can only disagree with the
    # LLM's own tool-informed conclusion (formed using these same tools during
    # validation) if the LLM got it wrong - they can be calledusing invoke method independently
    supplier_vat = validation.supplier_vat.value if validation.supplier_vat else None
    if supplier_vat and supplier_requires_po.invoke({"supplier_vat": supplier_vat}):
        if not validation.po_list:
            alerts.append("Fornecedor requer nota de encomenda e nenhuma foi encontrada")
        else:
            for po in validation.po_list:
                if po.value and not po_exists.invoke({"po_reference": po.value}):
                    alerts.append(f"Nota de encomenda não encontrada: {po.value}")

    return alerts


@dataclass
class DocumentDecision:
    """What to do with one document, and why.

    `reply_text` is set only when `action` is REPLY, and is what the supplier is
    told. `reason` is internal and always set — it is what shows up in logs and
    in the process summary.
    """

    filename: str
    action: Action
    reason: str
    reply_text: Optional[str] = None


@dataclass
class EmailDecision:
    """The email-level outcome: one optional reply, plus each document's action.

    `documents` holds the FINAL per-document actions, after suppression — so it
    is what should be written to `fct_documents.action`.
    """

    action: Action
    reason: str
    documents: list[DocumentDecision] = field(default_factory=list)
    reply_lines: list[str] = field(default_factory=list)
    intent: Optional[EmailIntent] = None

    @property
    def should_reply(self) -> bool:
        return self.action == REPLY

    @property
    def reply_body(self) -> str:
        """The single reply sent to the supplier, one line per problem document."""
        return "\n".join(self.reply_lines)


# --------------------------------------------------------------------------- #
# Layer 1 — one document
# --------------------------------------------------------------------------- #


def _state_of(classification: DocumentClassification) -> str:
    """The document's legal state, with a null state read as "original".

    Matches the extraction gate: real documents rarely print the word "Original",
    so only an explicit proforma / copy / cancelled counts as non-original.
    """
    if classification.document_state is None:
        return "original"
    return classification.document_state.value


def _ingest_or_manual(result: PipelineResult, label: str) -> DocumentDecision:
    """Book it, or send it to a human — the two hurdles every SAP-bound doc clears.

    Two hurdles, not one: the pipeline must have finished AND the extraction must
    be confident enough to book. Either failure sends the document to a human,
    never to the supplier — the document itself is fine, it is our reading of it
    that fell short.

    `label` names the document in the reason (e.g. "invoice (original)",
    "receipt (condominio)").
    """
    if result.status != "validated":
        return DocumentDecision(
            filename=result.filename,
            action=MANUAL,
            reason=f"{label} did not validate: {result.message}",
        )

    blockers = ingestion_blockers(result.validation)
    if blockers:
        return DocumentDecision(
            filename=result.filename,
            action=MANUAL,
            reason=f"{label} not confident: {'; '.join(blockers)}",
        )

    return DocumentDecision(
        filename=result.filename,
        action=INGEST,
        reason=f"{label} validated",
    )


def decide_document(result: PipelineResult) -> DocumentDecision:
    """Route ONE document. The per-type/per-state matrix, in full.

    Cases (see also the tables agreed with the business):

    B1/B5/B7  invoice-like + original, confident            -> Ingest in SAP
    B1/B5/B7  invoice-like + original, NOT confident        -> Validate Manually
    B2        invoice-like + proforma                      -> reply (proforma)
    B3        invoice-like + copy                          -> reply (duplicate)
    B4/B6/B8  invoice-like + cancelled                     -> Left in Inbox
    C1-C3     receipt + exception, confident               -> Ingest in SAP
    C1-C3     receipt + exception, NOT confident           -> Validate Manually
    C4        receipt, no exception                        -> Forward to Treasury
    C5        other                                        -> Left in Inbox
    D1-D3     a stage raised                               -> Validate Manually
    """
    # --- D: the pipeline failed on this document ---------------------------
    # `classification` is None on the failure path today, so no type rule can
    # apply. A human triages it rather than the supplier being blamed for what
    # may well be our own LLM/parse error.
    if result.status == "failed":
        return DocumentDecision(
            filename=result.filename,
            action=MANUAL,
            reason=f"pipeline failed: {result.message or 'unknown error'}",
        )

    if result.classification is None:
        return DocumentDecision(
            filename=result.filename,
            action=MANUAL,
            reason="no classification available",
        )

    doc_type = result.classification.document_type.value
    state = _state_of(result.classification)

    # --- B: invoice-like documents ----------------------------------------
    if doc_type in _INVOICE_LIKE:
        if state == "original":
            # B1/B5/B7.
            return _ingest_or_manual(result, f"{doc_type} (original)")

        if state == "proforma":  # B2
            return DocumentDecision(
                filename=result.filename,
                action=REPLY,
                reason=f"{doc_type} is proforma",
                reply_text=REPLY_TEXT_PROFORMA,
            )

        if state == "copy":  # B3
            return DocumentDecision(
                filename=result.filename,
                action=REPLY,
                reason=f"{doc_type} is a duplicate",
                reply_text=REPLY_TEXT_COPY,
            )

        # B4/B6/B8 — cancelled. Nothing to ask for and nothing to book.
        return DocumentDecision(
            filename=result.filename,
            action=INBOX,
            reason=f"{doc_type} is cancelled",
        )

    # --- C: receipts -------------------------------------------------------
    if doc_type == "receipt":
        # C1-C3. `document_exception` is only meaningful on a receipt, per the
        # schema, so it is read only here. An exception receipt (condominio,
        # insurance, bank extract) is booked exactly like an invoice — the
        # extraction gate lets these through precisely so this can happen.
        exception = result.classification.document_exception
        if exception is not None:
            return _ingest_or_manual(result, f"receipt ({exception.value})")

        # C4 — an ordinary receipt is not ours to book; treasury owns it.
        return DocumentDecision(
            filename=result.filename,
            action=TREASURY,
            reason="receipt with no exception",
        )

    # --- C5: 'other' — shipping docs, POs, bank statements, ... -----------
    return DocumentDecision(
        filename=result.filename,
        action=INBOX,
        reason=f"document type '{doc_type}' is not processed",
    )


# --------------------------------------------------------------------------- #
# Layer 2 — one email
# --------------------------------------------------------------------------- #


def _dedupe_reply_lines(decisions: list[DocumentDecision]) -> list[str]:
    """One line per distinct reason, naming the files it applies to.

    Two proformas in one email produce a single line listing both filenames,
    rather than the same sentence twice.
    """
    by_text: dict[str, list[str]] = {}
    for decision in decisions:
        if decision.action == REPLY and decision.reply_text:
            by_text.setdefault(decision.reply_text, []).append(decision.filename)

    return [f"{', '.join(files)}: {text}" for text, files in by_text.items()]


def decide_email(
    ingestion: EmailIngestionResult,
    extractions: list[PipelineResult],
    intent: Optional[EmailIntent] = None,
) -> EmailDecision:
    """Decide one email: per-document actions plus the single reply, if any.

    `intent` is the body classification, and is required only for the
    no-usable-PDF cases (A1/A2) — pass None otherwise and those cases fall back
    to leaving the email in the inbox.

    Cases:

    A1  no attachments at all              -> body decides: reply or inbox
    A2  attachments but none a PDF         -> body decides: reply or inbox
    A3  ingestion failed                   -> Left in Inbox
    A4  ingestion skipped (already done)   -> Left in Inbox
    A5  PDFs produced but no extractions   -> Left in Inbox
    """
    # --- A3: ingestion itself failed — nothing was ever read. --------------
    if ingestion.status == "failed":
        return EmailDecision(
            action=INBOX,
            reason=f"ingestion failed: {ingestion.message or 'unknown error'}",
        )

    # --- A4: already processed; the earlier run owns the decision. ---------
    if ingestion.status == "skipped":
        return EmailDecision(action=INBOX, reason="already processed")

    # --- A1/A2: no usable PDF came out of this email. ----------------------
    # Both cases ask the same question of the body, so they share a branch; the
    # reason distinguishes them for the log.
    if not extractions:
        if not ingestion.attachments:
            reason = "email had no attachments"
        elif not any(a.status == "chunked" for a in ingestion.attachments):
            reason = "email had attachments but none was a PDF"
        else:
            # A5 — an attachment reported "chunked" yet produced no filenames, so
            # there was nothing to extract. Defensive: a splitter bug, not a
            # supplier problem.
            return EmailDecision(
                action=INBOX,
                reason="PDFs reported but no documents extracted",
            )

        # Only an invoice-related email with NO link is the supplier's mistake.
        # An invoice-related email WITH a link means the document exists and we
        # must fetch it — leaving it in the inbox is correct for now, though such
        # emails arguably deserve their own "fetch from portal" action later.
        if intent is None:
            return EmailDecision(
                action=INBOX,
                reason=f"{reason} (body not classified)",
                intent=None,
            )

        is_invoice = intent.is_invoice_related.value
        has_link = intent.has_invoice_link.value

        if is_invoice and not has_link:
            return EmailDecision(
                action=REPLY,
                reason=f"{reason}; body is invoice-related with no link",
                reply_lines=[REPLY_TEXT_NO_PDF],
                intent=intent,
            )

        if is_invoice and has_link:
            detail = "body is invoice-related but links to the document"
        else:
            detail = "body is not invoice-related"
        return EmailDecision(action=INBOX, reason=f"{reason}; {detail}", intent=intent)

    # --- Documents exist: decide each, then roll up. -----------------------
    decisions = [decide_document(result) for result in extractions]

    # SUPPRESSION. If anything in this email is going to SAP, we got what we
    # needed and the supplier is not chased — a duplicate alongside its original
    # is not a problem. Suppressed documents fall back to the inbox.
    if any(d.action == INGEST for d in decisions):
        for decision in decisions:
            if decision.action == REPLY:
                decision.action = INBOX
                decision.reason = f"{decision.reason} (suppressed: email also has an original)"
                decision.reply_text = None

    reply_lines = _dedupe_reply_lines(decisions)
    if reply_lines:
        return EmailDecision(
            action=REPLY,
            reason="; ".join(d.reason for d in decisions if d.action == REPLY),
            documents=decisions,
            reply_lines=reply_lines,
        )

    # No reply. The email-level action reports what dominated, in this order:
    # something booked > something for treasury > something needing a human.
    for action, reason in (
        (INGEST, "document(s) ready for SAP"),
        (TREASURY, "document(s) forwarded to treasury"),
        (MANUAL, "document(s) need manual validation"),
    ):
        if any(d.action == action for d in decisions):
            return EmailDecision(action=action, reason=reason, documents=decisions)

    return EmailDecision(action=INBOX, reason="no action required", documents=decisions)
