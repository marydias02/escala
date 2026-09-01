"""Email- and document-level routing decisions — THE place to change the rules.

Three layers, deliberately separated:

1. `decide_document(result)` — what to do with ONE document, from its
   classification alone. Pure, no I/O, no LLM.
2. `decide_email(...)` — rolls the per-document decisions up into the single
   reply the email may get, and SUPPRESSES replies the email does not warrant.
3. `close_prior_process(...)` — whether an EARLIER email of the same thread is
   settled by a newer one arriving. The only rule that looks backwards.

The suppression in step 2 is why step 1's answers are not final: a duplicate
invoice asks for a reply on its own, but if the same email also carried the
original there is nothing to ask for.

Step 2 suppresses on a second ground: a thread that has run to its
THREAD_ESCALATION_COUNT-th message has not converged, so anything still owing an
outbound message is parked in the inbox for a human instead of being chased
again. See `_downgrade_to_inbox`.

Separately, `EmailDecision.status` reads the rolled-up actions back as a
lifecycle state — whether the process is still owed something (`Aberto`) or is
finished (`Fechado`). An email still owed something on an escalated thread is
`Requer Ação` instead: it will get no further automatic reply, so it is waiting
on a human rather than on the pipeline.

The full case matrix lives in `DOCUMENT_RULES` and `decide_email` below so the
business rules can be read without reading the pipeline.
"""

from dataclasses import dataclass, field, replace
from typing import Final, Literal, Optional

from loguru import logger

from invoice_extraction.config import (
    DOC_STATUS_BOOKED,
    MIN_CONFIDENCE,
    THREAD_ESCALATION_COUNT,
)
from invoice_extraction.extraction_pipeline import PipelineResult
from invoice_extraction.ingestion_pipeline import EmailIngestionResult
from invoice_extraction.models import (
    DocumentClassification,
    EmailIntent,
    ValidationReport,
    document_number_of,
    normalize_document_number,
)
from invoice_extraction.tools.po_confirmation import (
    FINANCIAL,
    FINANCIAL_AND_LOGISTICS,
    po_exists,
    supplier_is_financial,
)

# Two vocabularies, because the layers answer different questions. A DOCUMENT
# gets exactly one action — what to do with that piece of paper. An EMAIL can
# warrant several at once: a reply to the supplier for one document AND a
# treasury forward for another.
#
# Each string is written once, as a `Final` constant, and the Literal is built
# from those constants — so the names and the type cannot drift apart. `Final` is
# what makes a constant usable inside `Literal[...]`; a plain assignment is not.

INGEST: Final = "Ingerir em SAP" #Ingest in SAP
REPLY: Final = "Retornado ao Fornecedor" #Sent back to Supplier
TREASURY: Final = "Encaminhar para Tesouraria" #Forward to Treasury
INBOX: Final = "Manter na Caixa de Entrada" #Keep in Inbox
MANUAL: Final = "Validação Manual" #Manual Validation
# A duplicate whose original is in the same email: not booked, not chased, but
# still recorded, so the audit trail shows the copy arrived.
IGNORE: Final = "Ignorar (tem original)" #Ignore (original exists)

# What reaches `fct_documents.action`.
DocumentAction = Literal[
    INGEST,
    REPLY,
    TREASURY,
    INBOX,
    MANUAL,
    IGNORE,
]

EMAIL_ARCHIVE: Final = "Arquivar" #Archive
EMAIL_INBOX: Final = "Manter na Caixa de Entrada" #Keep in Inbox
EMAIL_REPLY: Final = "Retornado ao Fornecedor" #Reply to Supplier
EMAIL_TREASURY: Final = "Encaminhar para Tesouraria" #Forward to Treasury

EmailAction = Literal[
    EMAIL_ARCHIVE,
    EMAIL_INBOX,
    EMAIL_REPLY,
    EMAIL_TREASURY,
]

# How the per-document actions roll up into the email's own. Ordered, and read in
# order, so the resulting list runs from most to least consequential.
#
# ARCHIVE is deliberately absent: it is not "at least one" like the others but
# "all of them", and is handled separately in `decide_email`.
EMAIL_ACTION_RULES: Final = (
    (EMAIL_REPLY, (REPLY,)),
    (EMAIL_TREASURY, (TREASURY,)),
    (EMAIL_INBOX, (INBOX, MANUAL)),
)

# An email whose documents are ALL in this set is finished — nothing is owed to
# anyone, so it leaves the inbox.
_ARCHIVABLE: Final = (INGEST, IGNORE)

# Document actions that send something outward, and so are what the thread
# escalation suppresses.
_OUTBOUND: Final = (REPLY, TREASURY)

# The process lifecycle — a SEPARATE axis from the actions above. `actions` says
# what the email warrants; status says whether anyone still owes it something.
EMAIL_STATUS_OPEN: Final = "Aberto"
EMAIL_STATUS_CLOSED: Final = "Fechado"
EMAIL_STATUS_ACTION_REQUIRED: Final = "Requer Ação"

EmailStatus = Literal[
    EMAIL_STATUS_OPEN,
    EMAIL_STATUS_CLOSED,
    EMAIL_STATUS_ACTION_REQUIRED,
]

# Reply wording, in Portuguese, per reason. Only reasons that can produce a
# REPLY appear here. Each is the "Motivo" clause slotted into REPLY_LETTER_TEMPLATE
# below — a fragment, not a standalone sentence, so it must read naturally after
# "pelo facto de".
REPLY_TEXT_NO_PDF = "o formato do ficheiro enviado não é aceite"
REPLY_TEXT_PROFORMA = "o documento enviado é proforma"
REPLY_TEXT_COPY = "o documento enviado é duplicado"
REPLY_TEXT_NO_PO = "o documento não ter nota de encomenda"

# TREASURY's equivalent of REPLY_TEXT_*: the one reason a document reaches
# TREASURY (C4, an ordinary receipt), so there is only one line.
REPLY_TEXT_TREASURY = "Recibo encaminhado para tesouraria"

# Full supplier-facing letter. One "Motivo" line per distinct reason (see
# `_dedupe_lines_for`), so a single email can list several problems without
# repeating the greeting/sign-off for each.
REPLY_LETTER_TEMPLATE = """Exmos. Senhores,

O documento enviado não pode ser aceite pelo facto de {reasons}.

Ficamos a aguardar o envio do documento original em formato PDF, com os dados da empresa corretos.

Obrigado"""

# Full treasury-facing letter. Reasons are always the same (C4 is the only
# document action that reaches TREASURY), so there is nothing to slot in.
TREASURY_LETTER = """Exmos. Senhores,

Seguem em anexo recibos para processamento.

Obrigado"""

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

# Every field here must be present AND clear MIN_CONFIDENCE. 
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

    blockers = [
        f"{name} missing" if confidence is None
        else f"{name} confidence {confidence:.2f} < {MIN_CONFIDENCE}"
        for name, _label, confidence in _field_problems(
            validation, {name: name for name in REQUIRED_FIELDS}
        )
    ]

    # supplier_id/bu_id are filled by nodes.validate.resolve_registry_ids. 
    # Null means - "not found in registry"
    if validation.supplier_id is None and (
        validation.supplier_vat is not None or validation.supplier_name is not None
    ):
        blockers.append("supplier_id not found in registry")

    if validation.bu_id is None and (
        validation.bu_vat is not None or validation.bu_name is not None
    ):
        blockers.append("bu_id not found in registry")

    return blockers


def missing_pos(validation: Optional[ValidationReport]) -> Optional[list[str]]:
    """The PO problem on this document, if any. One source of truth for routing
    and alerts.

    Returns None when there is nothing wrong — the supplier does not require a
    PO, or it requires one and every PO on the document was found. Otherwise:

    - `[]`  the supplier requires a PO and the document carries none.
    - list  the PO references the document carries that we cannot find.

    The two cases route differently (see `_ingest_or_manual`), so they are
    distinguished by the empty list rather than collapsed into a bool.

    What a PO on the document means depends on `dim_suppliers.is_financial`:

    - logistics (0) — a PO is required, and every one carried is checked.
    - financial (1) — there should be no PO at all, so one that appears is a
      misread rather than a real reference. It is dropped, with a log line.
    - both (2)      — no PO is demanded, but any carried is checked as usual.

    Second, independent deterministic check — can only disagree with the LLM's
    own tool-informed conclusion (formed using these same tools during
    validation) if the LLM got it wrong. The tools are invoked directly so the
    answer does not depend on the LLM having called them.

    A supplier VAT we never read is not a PO problem: with no VAT there is no
    requirement to look up, and the missing VAT already blocks ingestion via
    REQUIRED_FIELDS.
    """
    if validation is None:
        return None

    supplier_vat = validation.supplier_vat.value if validation.supplier_vat else None
    if not supplier_vat:
        return None

    # The tools swallow their own database errors, but this runs outside the
    # extraction pipeline's error handling — an unexpected failure here would
    # take down the whole email rather than one document.
    try:
        is_financial = supplier_is_financial(supplier_vat)

        if not validation.po_list:
            # Only a supplier that requires one is missing anything.
            return [] if is_financial not in (FINANCIAL, FINANCIAL_AND_LOGISTICS) else None

        if is_financial == FINANCIAL:
            pos = [po.value for po in validation.po_list if po.value]
            logger.info(
                f"Ignoring PO(s) {pos} on a financial supplier ({supplier_vat}) — "
                "likely something else read as a PO"
            )
            return None

        unknown = [
            po.value
            for po in validation.po_list
            if po.value and not po_exists.invoke({"po_reference": po.value})
        ]
        return unknown or None
    except Exception as exc:  # noqa: BLE001 - never fail routing on a PO lookup
        logger.warning(f"PO check failed for supplier {supplier_vat}, skipping it: {exc!r}")
        return None


# Every ValidationReport field except supplier_id/bu_id (checked separately,
# below — a missing id means "not found in the registry", not "low confidence")
# and notes/po_list (handled separately too). Portuguese labels since
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

    # Same check that routes the document, so an alert and its action can never
    # disagree.
    pos = missing_pos(validation)
    if pos == []:
        alerts.append("Fornecedor requer nota de encomenda e nenhuma foi encontrada")
    elif pos:
        alerts.extend(f"Nota de encomenda não encontrada: {po}" for po in pos)

    # supplier_id/bu_id are filled by nodes.validate.resolve_registry_ids, from a VAT/name lookup 
    if validation.supplier_id is None and (
        validation.supplier_vat is not None or validation.supplier_name is not None
    ):
        alerts.append("Fornecedor não identificado no registo")

    if validation.bu_id is None and (
        validation.bu_vat is not None or validation.bu_name is not None
    ):
        alerts.append("Cliente não identificado no registo")

    return alerts


@dataclass
class DocumentDecision:
    """What to do with one document, and why.

    `reply_text` is set only when `action` is REPLY, and is what the supplier is
    told. `reason` is internal and always set — it is what shows up in logs and
    in the process summary.
    """

    filename: str
    action: DocumentAction
    reason: str
    reply_text: Optional[str] = None


@dataclass
class EmailDecision:
    """The email-level outcome: what the email warrants, plus each document's action.

    `actions` is a LIST: one email can owe several things at once — a reply to
    the supplier for one document and a treasury forward for another.

    `documents` holds the per-document actions, and is what is written to
    `fct_documents.action`.

    `thread_escalated` records that the thread had run to
    THREAD_ESCALATION_COUNT when this email was decided. It cannot be read back
    from `actions` — an escalated email looks exactly like an ordinary inbox one
    — so it is carried here for `status`.

    `out_of_scope` says the email carried no document and is not invoice-related."""

    actions: list[EmailAction]
    reason: str
    documents: list[DocumentDecision] = field(default_factory=list)
    reply_lines: list[str] = field(default_factory=list)
    treasury_lines: list[str] = field(default_factory=list)
    intent: Optional[EmailIntent] = None
    thread_escalated: bool = False
    out_of_scope: bool = False

    @property
    def should_reply(self) -> bool:
        return EMAIL_REPLY in self.actions

    @property
    def should_archive(self) -> bool:
        return EMAIL_ARCHIVE in self.actions

    @property
    def reply_body(self) -> str:
        """The single reply sent to the supplier: REPLY_LETTER_TEMPLATE with one
        "Motivo" clause per distinct reason, joined so the sentence still reads
        naturally whether there is one problem or several.
        """
        return REPLY_LETTER_TEMPLATE.format(reasons="; ".join(self.reply_lines))

    @property
    def should_forward_to_treasury(self) -> bool:
        return EMAIL_TREASURY in self.actions

    @property
    def status(self) -> EmailStatus:
        """Whether anyone still owes this email something. THE status rule

        Closed wins over escalation, out_of_scope included. An email that IS
        outstanding on an escalated thread is "Requer Ação" rather than "Aberto".
        """
        if (
            EMAIL_ARCHIVE in self.actions
            or self.actions == [EMAIL_TREASURY]
            or self.out_of_scope
        ):
            return EMAIL_STATUS_CLOSED
        if self.thread_escalated:
            return EMAIL_STATUS_ACTION_REQUIRED
        return EMAIL_STATUS_OPEN

    @property
    def treasury_body(self) -> str:
        """The single email sent to treasury. Fixed wording — C4 (ordinary
        receipt) is the only action that reaches TREASURY, so there is only one
        reason and nothing to slot in.
        """
        return TREASURY_LETTER


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


def original_document_keys(extractions: list[PipelineResult]) -> set[tuple[str, str]]:
    """(document_type, normalized number) of every ORIGINAL in one email.

    "Original" is `_state_of` — an explicit `original`, or a NULL state, since
    real documents rarely print the word. No type is excluded: two copies of the
    same receipt are as redundant as two copies of the same invoice, and only one
    of each should be acted on.

    The type is part of the key, not just the number. Numbering is per document
    series, so an invoice and a receipt can legitimately share a number — keying
    on the number alone would let a receipt original file away an invoice copy,
    silently dropping a real invoice.

    Feeds `decide_document`, which files a duplicate away when its own key is in
    here. Computed once per email rather than per document so the comparison is
    O(n) and every document is judged against the same set.
    """
    return {
        (result.classification.document_type.value, number)
        for result in extractions
        if result.classification is not None
        and _state_of(result.classification) == "original"
        and (number := normalize_document_number(document_number_of(result.classification)))
    }


def _ingest_or_escalate(result: PipelineResult, label: str) -> DocumentDecision:
    """Book it, or escalate — the hurdles every SAP-bound document clears.

    Three hurdles: the pipeline must have finished, the extraction must be
    confident enough to book, and the document must satisfy its supplier's PO
    requirement.

    The first two failures send the document to a human, never to the supplier —
    the document itself is fine, it is our reading of it that fell short. The PO
    hurdle splits: a document with NO PO from a supplier that requires one is
    the supplier's omission and only the supplier can fix it, so it goes back to
    them; a PO we cannot find in the PO list is ours to investigate, so a human
    gets it.

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

    pos = missing_pos(result.validation)
    if pos == []:
        return DocumentDecision(
            filename=result.filename,
            action=REPLY,
            reason=f"{label} has no PO and the supplier requires one",
            reply_text=REPLY_TEXT_NO_PO,
        )
    if pos:
        return DocumentDecision(
            filename=result.filename,
            action=MANUAL,
            reason=f"{label} has PO(s) not found in the PO list: {', '.join(pos)}",
        )

    return DocumentDecision(
        filename=result.filename,
        action=INGEST,
        reason=f"{label} validated",
    )


def decide_document(
    result: PipelineResult,
    original_keys: Optional[set[tuple[str, str]]] = None,
) -> DocumentDecision:
    """Route ONE document. The per-type/per-state matrix, in full.

    `original_keys` is the (document_type, number) pairs this email already holds
    an original of (see `original_document_keys`). A non-original matching one of
    them is filed away before any other rule is considered — we have the real
    thing, so there is nothing to ask for and nothing to book. Pass None to
    decide a document in isolation.

    Cases (see also the tables agreed with the business):

    B0/C0     any non-original whose original is in the email -> Ignore (original exists)
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

    The PO requirement cuts across the ingestable cases (B1/B5/B7 and C1-C3):
    a confident document whose supplier requires a PO but that carries none is
    sent back to the supplier, and one carrying a PO absent from the PO list
    goes to a human. See `_ingest_or_escalate`.
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

    # --- B0/C0: we already hold the original of this document --------------
    # Matched on (type, number): numbering is per document series, so an invoice
    # and a receipt may share a number without being the same document.
    #
    # This is why `document_number` is read at CLASSIFICATION: a copy never
    # reaches extraction.
    if state != "original" and original_keys:
        number = normalize_document_number(document_number_of(result.classification))
        if number is not None and (doc_type, number) in original_keys:
            raw = document_number_of(result.classification)
            return DocumentDecision(
                filename=result.filename,
                action=IGNORE,
                reason=(
                    f"{doc_type} is {state}; original with document number "
                    f"{raw} is in this email"
                ),
            )

    # --- B: invoice-like documents ----------------------------------------
    if doc_type in _INVOICE_LIKE:
        if state == "original":
            # B1/B5/B7.
            return _ingest_or_escalate(result, f"{doc_type} (original)")

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
            return _ingest_or_escalate(result, f"receipt ({exception.value})")

        # C4 — an ordinary receipt is not ours to book; treasury owns it.
        return DocumentDecision(
            filename=result.filename,
            action=TREASURY,
            reason="receipt with no exception",
            reply_text=REPLY_TEXT_TREASURY,
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


def _dedupe_lines_for(decisions: list[DocumentDecision], action: DocumentAction) -> list[str]:
    """Distinct reply_text values among documents with the given action, in
    first-seen order. Two proformas in one email still yield one reason, not
    the same sentence twice.
    """
    lines: list[str] = []
    for decision in decisions:
        if decision.action == action and decision.reply_text and decision.reply_text not in lines:
            lines.append(decision.reply_text)
    return lines


def _thread_escalated(thread_message_count: Optional[int]) -> bool:
    """Whether this email is deep enough into its thread to stop chasing.

    None when Graph gave us no conversationId — an email we cannot place in a
    thread is treated as the first of one.
    """
    return (
        thread_message_count is not None
        and thread_message_count >= THREAD_ESCALATION_COUNT
    )


def _downgrade_to_inbox(
    decisions: list[DocumentDecision], thread_message_count: Optional[int]
) -> list[DocumentDecision]:
    """On a thread's Nth message, park what would be sent outward.

    N rounds of asking the supplier — or of forwarding to treasury — have not
    settled this thread, so anything still owing an outbound message goes to a
    human instead. INGEST/MANUAL/IGNORE are untouched.

    `reply_text` is dropped along with the action.
    """
    if not _thread_escalated(thread_message_count):
        return decisions

    return [
        replace(
            decision,
            action=INBOX,
            reason=(
                f"{decision.reason}; thread on message "
                f"{thread_message_count}, not chased further"
            ),
            reply_text=None,
        )
        if decision.action in _OUTBOUND
        else decision
        for decision in decisions
    ]


def roll_up_actions(decisions: list[DocumentDecision]) -> list[EmailAction]:
    """The email-level actions its documents add up to. THE roll-up rule.

    An email can warrant several things at once, so this returns a LIST, ordered
    by `EMAIL_ACTION_RULES` (most consequential first). One document contributing
    a reply and another a treasury forward yields both.

    ARCHIVE is exclusive and is tested first: it means every document is finished
    (booked, or ignored as a duplicate) and so nothing is owed to anyone. It can
    never appear next to another action — an email still owing a reply is not
    archived.

    An email with no documents at all falls back to the inbox rather than being
    archived, since "nothing to do" and "everything done" are different states.
    """
    if not decisions:
        return [EMAIL_INBOX]

    if all(d.action in _ARCHIVABLE for d in decisions):
        return [EMAIL_ARCHIVE]

    actions = [
        email_action
        for email_action, document_actions in EMAIL_ACTION_RULES
        if any(d.action in document_actions for d in decisions)
    ]

    # Defensive: every non-archivable document action appears in
    # EMAIL_ACTION_RULES, so this is unreachable unless a new DocumentAction is
    # added without a rule. Falling back to the inbox keeps such an email visible
    # to a human instead of silently actionless.
    return actions or [EMAIL_INBOX]


def _email_reason(decisions: list[DocumentDecision]) -> str:
    """One line summarising why the email got its actions.

    Names only the documents that DROVE an action — a booked or ignored document
    needs no explanation, so a mixed email reads as the problems it still has.
    """
    driving = [d for d in decisions if d.action not in _ARCHIVABLE]
    if not driving:
        return f"{len(decisions)} document(s) processed, nothing outstanding"
    return "; ".join(d.reason for d in driving)


def decide_email(
    ingestion: EmailIngestionResult,
    extractions: list[PipelineResult],
    intent: Optional[EmailIntent] = None,
    thread_message_count: Optional[int] = None,
) -> EmailDecision:
    """Decide one email: per-document actions plus the single reply, if any.

    `intent` is the body classification, and is required only for the
    no-usable-PDF cases (A1/A2) — pass None otherwise and those cases fall back
    to leaving the email in the inbox.

    `thread_message_count` is this email's position in its thread. From
    THREAD_ESCALATION_COUNT on, the thread has not converged: nothing more is
    sent outward, and everything that would have been goes to a human instead.
    Pass None (the default) to decide an email without thread context.

    Cases:

    A1  no attachments at all              -> body decides: reply or inbox
    A2  attachments but none a PDF         -> body decides: reply or inbox
    A3  ingestion failed                   -> Left in Inbox
    A4  ingestion skipped (already done)   -> Left in Inbox
    A5  PDFs produced but no extractions   -> Left in Inbox

    Documents are decided against the email's set of originals
    (`original_document_keys`), so a duplicate whose original is in the same
    email is filed away rather than acted on. A duplicate with no matching
    original still gets its reply.

    The thread escalation cuts across every case that would send something
    outward — the A1/A2 reply below, and any document reaching REPLY or TREASURY.
    It is also recorded on every decision as `thread_escalated`, which is what
    turns an otherwise-open status into "Requer Ação".
    """
    escalated = _thread_escalated(thread_message_count)

    # --- A3: ingestion itself failed — nothing was ever read. --------------
    if ingestion.status == "failed":
        return EmailDecision(
            actions=[EMAIL_INBOX],
            reason=f"ingestion failed: {ingestion.message or 'unknown error'}",
            thread_escalated=escalated,
        )

    # --- A4: already processed; the earlier run owns the decision. ---------
    if ingestion.status == "skipped":
        return EmailDecision(
            actions=[EMAIL_INBOX],
            reason="already processed",
            thread_escalated=escalated,
        )

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
                actions=[EMAIL_INBOX],
                reason="PDFs reported but no documents extracted",
                thread_escalated=escalated,
            )

        # Only an invoice-related email with NO link is the supplier's mistake.
        # An invoice-related email WITH a link means the document exists and we
        # must fetch it — leaving it in the inbox is correct for now, though such
        # emails arguably deserve their own "fetch from portal" action later.
        if intent is None:
            return EmailDecision(
                actions=[EMAIL_INBOX],
                reason=f"{reason} (body not classified)",
                intent=None,
                thread_escalated=escalated,
            )

        is_invoice = intent.is_invoice_related.value
        has_link = intent.has_invoice_link.value

        if is_invoice and not has_link:
            if escalated:
                return EmailDecision(
                    actions=[EMAIL_INBOX],
                    reason=(
                        f"{reason}; body is invoice-related with no link; thread on "
                        f"message {thread_message_count}, not chased further"
                    ),
                    intent=intent,
                    thread_escalated=escalated,
                )

            return EmailDecision(
                actions=[EMAIL_REPLY],
                reason=f"{reason}; body is invoice-related with no link",
                reply_lines=[REPLY_TEXT_NO_PDF],
                intent=intent,
            )

        if is_invoice and has_link:
            return EmailDecision(
                actions=[EMAIL_INBOX],
                reason=f"{reason}; body is invoice-related but links to the document",
                intent=intent,
                thread_escalated=escalated,
            )

        # Out of scope: no document, and the body is not about one. The pipeline
        # has nothing further to do, so the process is finished even though the
        # email stays in the inbox for a human to read.
        return EmailDecision(
            actions=[EMAIL_INBOX],
            reason=f"{reason}; body is not invoice-related",
            intent=intent,
            thread_escalated=escalated,
            out_of_scope=True,
        )

    # --- Documents exist: decide each, then roll up. -----------------------
    # The originals are gathered first so every document is judged against the
    # same set — a duplicate is filed away inside decide_document, not corrected
    # afterwards.
    original_keys = original_document_keys(extractions)
    decisions = _downgrade_to_inbox(
        [decide_document(result, original_keys) for result in extractions],
        thread_message_count,
    )

    return EmailDecision(
        actions=roll_up_actions(decisions),
        reason=_email_reason(decisions),
        documents=decisions,
        reply_lines=_dedupe_lines_for(decisions, REPLY),
        treasury_lines=_dedupe_lines_for(decisions, TREASURY),
        thread_escalated=escalated,
    )


# --------------------------------------------------------------------------- #
# Layer 3 — an EARLIER email, revisited because a newer one arrived
# --------------------------------------------------------------------------- #

# A prior process's document is settled when its action needs nothing further,
# or when the one action that does — booking to SAP — has actually happened.
# MANUAL is deliberately absent: a human has not looked at it yet.
_SETTLED_DOCUMENT_ACTIONS: Final = (INBOX, REPLY, TREASURY, IGNORE)


def _document_is_settled(action: Optional[str], status: Optional[str]) -> bool:
    """Whether one prior document has nothing left owing on it."""
    if action == INGEST:
        return status == DOC_STATUS_BOOKED
    return action in _SETTLED_DOCUMENT_ACTIONS


def close_prior_process(
    email_action: Optional[list[str]],
    documents: list[tuple[Optional[str], Optional[str]]],
) -> bool:
    """Whether an earlier, still-`Aberto` process is closed by a newer email in
    its thread

    - REPLY alone, or REPLY + TREASURY  -> closed. 
    - REPLY + INBOX                     -> closed only if every document is
      settled (`_document_is_settled`)
    - anything without REPLY            -> untouched. 

    `documents` is (action, status) per `fct_documents` row of the earlier
    process. Pure: the caller does the reading and the writing.
    """
    if not email_action or EMAIL_REPLY not in email_action:
        return False

    if EMAIL_INBOX not in email_action:
        return True

    return all(_document_is_settled(action, status) for action, status in documents)
