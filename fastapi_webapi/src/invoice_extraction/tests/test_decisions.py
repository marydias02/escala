"""Pytest suite for `invoice_extraction.decisions` — the routing rules.

Unlike the other modules in this folder (manual smoke scripts run directly),
this one is real pytest and is meant to run in CI:

    uv run pytest src/invoice_extraction/tests/test_decisions.py

Both layers are covered: `decide_document` (the per-type/per-state matrix) and
`decide_email` (the roll-up, the A-cases, the thread escalation, and the status
axis).

`missing_pos` reaches the database through `supplier_is_financial` / `po_exists`,
so every test that routes an ingestable document patches those two. The autouse
`no_db` fixture makes the safe default — supplier requires no PO — apply
everywhere, so a test only says something about POs when POs are its subject. A
test that forgot to patch would otherwise hit a real database and pass or fail on
its contents rather than on the rule.

Thresholds are read from `config`, never hardcoded, so tuning MIN_CONFIDENCE or
THREAD_ESCALATION_COUNT does not silently invalidate these tests.
"""

import pytest

from invoice_extraction import decisions
from invoice_extraction.config import (
    DOC_STATUS_BOOKED,
    DOC_STATUS_COMMUNICATED,
    DOC_STATUS_CREATED,
    DOC_STATUS_IGNORED,
    MIN_CONFIDENCE,
    THREAD_ESCALATION_COUNT,
)
from invoice_extraction.decisions import (
    DEFAULT_REPLY_LANGUAGE,
    EMAIL_ARCHIVE,
    EMAIL_INBOX,
    EMAIL_REPLY,
    EMAIL_STATUS_ACTION_REQUIRED,
    EMAIL_STATUS_CLOSED,
    EMAIL_STATUS_OPEN,
    EMAIL_TREASURY,
    IGNORE,
    INBOX,
    INGEST,
    MANUAL,
    NOT_CHECKED,
    PO_ALERT_NOT_CHECKED,
    REPLY,
    REPLY_TEXT_COPY,
    REPLY_TEXT_NO_PDF,
    REPLY_TEXT_NO_PO,
    REPLY_TEXT_PROFORMA,
    TREASURY,
    EmailDecision,
    build_alerts_list,
    close_prior_process,
    close_process_after_manual_send,
    decide_document,
    decide_email,
    ingestion_blockers,
    missing_pos,
    original_document_keys,
    roll_up_actions,
)
from invoice_extraction.extraction_pipeline import PipelineResult
from invoice_extraction.ingestion_pipeline import AttachmentResult, EmailIngestionResult
from invoice_extraction.models import (
    DocumentClassification,
    EmailIntent,
    ValidationReport,
)
from invoice_extraction.models.common import Checked, Confident
from invoice_extraction.tools.po_confirmation import FINANCIAL, LOGISTICS

# --------------------------------------------------------------------------- #
# Builders — the minimum shape each rule needs, with everything else defaulted.
# --------------------------------------------------------------------------- #

# Comfortably above and below the gate, so the tests do not sit on the boundary.
GOOD = min(MIN_CONFIDENCE + 0.2, 1.0)
POOR = MIN_CONFIDENCE - 0.2


def confident(value, confidence: float = GOOD) -> Confident:
    return Confident(value=value, confidence=confidence, evidence="")


def checked(value, confidence: float = GOOD) -> Checked:
    return Checked(value=value, confidence=confidence)


def classification(
    document_type: str = "invoice",
    state: str | None = "original",
    number: str | None = "FT 2024/1",
    exception: str | None = None,
    language: str | None = None,
) -> DocumentClassification:
    """A classification. `state=None` means the document printed no state at all,
    which `_state_of` reads as "original".

    `language=None` is a document whose language could not be read — the case
    that falls back rather than deciding anything.
    """
    return DocumentClassification(
        document_type=confident(document_type),
        document_state=confident(state) if state is not None else None,
        document_number=confident(number) if number is not None else None,
        document_exception=confident(exception) if exception is not None else None,
        language=confident(language) if language is not None else None,
    )


def validation(
    confidence: float = GOOD,
    po_list: list[str] | None = None,
    alert_fields: bool = False,
    **overrides,
) -> ValidationReport:
    """A report where every REQUIRED_FIELD is present at `confidence`.

    `alert_fields` additionally fills the three fields that only
    `build_alerts_list` looks at (`_ALERT_FIELD_LABELS` is a wider set than
    REQUIRED_FIELDS: it also covers supplier_name, document_number and bu_name).
    Routing ignores them, so they are off by default.

    `overrides` replaces one field — pass None to drop it entirely, which is the
    "missing field" case as distinct from the "low confidence" one.
    """
    report = {
        "supplier_vat": checked("PT123456789", confidence),
        "bu_vat": checked("PT987654321", confidence),
        # Filled by nodes.validate.resolve_registry_ids before routing sees the
        # report. Null is "not found in the registry", which blocks ingestion, so
        # the default report carries both — pass None to test that case.
        "supplier_id": checked("SUP-1", confidence),
        "bu_id": checked("BU-1", confidence),
        "issue_date": checked("01-01-2024", confidence),
        "base_amount": checked(100.0, confidence),
        "vat_amount": checked(23.0, confidence),
        "total_amount": checked(123.0, confidence),
        "currency": checked("EUR", confidence),
        "po_list": [checked(po) for po in (po_list or [])],
        "notes": "",
    }
    if alert_fields:
        report.update(
            supplier_name=checked("Fornecedor Lda", confidence),
            document_number=checked("FT 2024/1", confidence),
            bu_name=checked("Cliente SA", confidence),
        )
    report.update(overrides)
    return ValidationReport(**report)


def extraction(
    filename: str = "doc.pdf",
    status: str = "validated",
    document_type: str = "invoice",
    state: str | None = "original",
    number: str | None = "FT 2024/1",
    exception: str | None = None,
    confidence: float = GOOD,
    po_list: list[str] | None = None,
    with_validation: bool = True,
    message: str = "",
    language: str | None = None,
) -> PipelineResult:
    return PipelineResult(
        filename=filename,
        status=status,
        classification=classification(document_type, state, number, exception, language),
        validation=validation(confidence, po_list) if with_validation else None,
        message=message,
    )


def ingested(attachment_statuses: tuple[str, ...] = ("chunked",)) -> EmailIngestionResult:
    return EmailIngestionResult(
        source="mail",
        status="ingested",
        attachments=[
            AttachmentResult(filename=f"a{i}.pdf", status=status)
            for i, status in enumerate(attachment_statuses)
        ],
    )


def intent(is_delivery: bool, has_link: bool, language: str | None = None) -> EmailIntent:
    return EmailIntent(
        is_invoice_delivery=confident(is_delivery),
        has_invoice_link=confident(has_link),
        language=confident(language) if language is not None else None,
    )


class FakePoTool:
    """Stand-in for the `po_exists` LangChain tool.

    The real one is a pydantic model, so its `invoke` cannot be monkeypatched on
    the instance; the whole tool is replaced instead.
    """

    def __init__(self, known: bool = True):
        self.known = known

    def invoke(self, args: dict) -> bool:
        return self.known


def patch_po(monkeypatch, is_financial: int, po_known: bool = True) -> None:
    """Patch the PO lookups AS BOUND IN `decisions`.

    `decisions` does `from ... po_confirmation import po_exists,
    supplier_is_financial`, so the names it calls are its own module globals —
    patching `po_confirmation` would leave those references untouched and let the
    call reach the real database.
    """
    monkeypatch.setattr(decisions, "supplier_is_financial", lambda vat: is_financial)
    monkeypatch.setattr(decisions, "po_exists", FakePoTool(po_known))


def patch_preferred_language(monkeypatch, language: str | None) -> None:
    """Patch the registry language lookup, bound in `decisions` for the same
    reason as `patch_po`."""
    monkeypatch.setattr(decisions, "supplier_preferred_language", lambda supplier_id: language)


@pytest.fixture(autouse=True)
def no_db(monkeypatch):
    """Neutral PO and language answers, so no test touches the database by accident.

    The default is the case that changes no routing: a financial supplier, which
    requires no PO, with no recorded language preference. Tests about POs or
    languages override this.
    """
    patch_po(monkeypatch, FINANCIAL)
    patch_preferred_language(monkeypatch, None)


@pytest.fixture
def requires_po(monkeypatch):
    """A logistics supplier: a PO is required, and every PO carried is checked."""
    patch_po(monkeypatch, LOGISTICS)


# --------------------------------------------------------------------------- #
# Layer 1 — decide_document
# --------------------------------------------------------------------------- #


class TestDecideDocument:
    """The per-type/per-state matrix, case by case."""

    def test_b1_confident_original_invoice_is_ingested(self):
        assert decide_document(extraction()).action == INGEST

    @pytest.mark.parametrize("document_type", ["invoice", "credit_note", "debit_note"])
    def test_b1_b5_b7_every_invoice_like_type_is_ingested(self, document_type):
        assert decide_document(extraction(document_type=document_type)).action == INGEST

    def test_null_state_counts_as_original(self):
        """Real documents rarely print "Original", so a null state is one."""
        assert decide_document(extraction(state=None)).action == INGEST

    def test_b2_proforma_goes_back_to_the_supplier(self):
        decision = decide_document(extraction(state="proforma"))
        assert decision.action == REPLY
        assert decision.reply_text == REPLY_TEXT_PROFORMA

    def test_b3_copy_with_no_original_present_goes_back_to_the_supplier(self):
        decision = decide_document(extraction(state="copy"))
        assert decision.action == REPLY
        assert decision.reply_text == REPLY_TEXT_COPY

    def test_b4_cancelled_is_left_in_the_inbox(self):
        assert decide_document(extraction(state="cancelled")).action == INBOX

    def test_c4_ordinary_receipt_goes_to_treasury(self):
        assert decide_document(extraction(document_type="receipt")).action == TREASURY

    @pytest.mark.parametrize("exception", ["condominio", "insurance", "extract"])
    def test_c1_c3_exception_receipt_is_ingested_like_an_invoice(self, exception):
        decision = decide_document(extraction(document_type="receipt", exception=exception))
        assert decision.action == INGEST

    def test_c5_other_is_left_in_the_inbox(self):
        assert decide_document(extraction(document_type="other")).action == INBOX

    def test_d_failed_pipeline_goes_to_a_human_not_the_supplier(self):
        """Our error, so the supplier is not blamed for it."""
        result = PipelineResult(filename="x.pdf", status="failed", message="boom")
        decision = decide_document(result)
        assert decision.action == MANUAL
        assert "boom" in decision.reason

    def test_missing_classification_goes_to_a_human(self):
        result = PipelineResult(filename="x.pdf", status="validated", classification=None)
        assert decide_document(result).action == MANUAL

    def test_unvalidated_document_goes_to_a_human(self):
        assert decide_document(extraction(status="skipped")).action == MANUAL

    def test_low_confidence_goes_to_a_human_not_the_supplier(self):
        """Our reading fell short, not the supplier's document."""
        decision = decide_document(extraction(confidence=POOR))
        assert decision.action == MANUAL

    def test_missing_required_field_goes_to_a_human(self):
        result = PipelineResult(
            filename="doc.pdf",
            status="validated",
            classification=classification(),
            validation=validation(total_amount=None),
        )
        assert decide_document(result).action == MANUAL

    def test_no_validation_report_goes_to_a_human(self):
        assert decide_document(extraction(with_validation=False)).action == MANUAL

    # --- the PO hurdle, which splits by whose problem it is -----------------

    def test_no_po_when_the_supplier_requires_one_goes_back_to_the_supplier(self, requires_po):
        decision = decide_document(extraction(po_list=[]))
        assert decision.action == REPLY
        assert decision.reply_text == REPLY_TEXT_NO_PO

    def test_unknown_po_goes_to_a_human_to_investigate(self, monkeypatch):
        patch_po(monkeypatch, LOGISTICS, po_known=False)
        decision = decide_document(extraction(po_list=["PO-1"]))
        assert decision.action == MANUAL
        assert "PO-1" in decision.reason

    def test_known_po_is_ingested(self, requires_po):
        assert decide_document(extraction(po_list=["PO-1"])).action == INGEST

    def test_po_on_a_financial_supplier_is_ignored_as_a_misread(self):
        """A financial supplier should carry no PO, so one that appears is noise."""
        assert decide_document(extraction(po_list=["PO-1"])).action == INGEST

    def test_a_po_lookup_failure_never_blocks_routing(self, monkeypatch):
        def boom(vat):
            raise RuntimeError("db down")

        monkeypatch.setattr(decisions, "supplier_is_financial", boom)
        assert decide_document(extraction()).action == INGEST

    # --- B0/C0: the duplicate whose original is in the same email -----------

    def test_b0_copy_is_filed_away_when_its_original_is_present(self):
        keys = {("invoice", "ft20241")}
        decision = decide_document(extraction(state="copy"), keys)
        assert decision.action == IGNORE

    def test_a_copy_of_a_different_document_still_gets_its_reply(self):
        keys = {("invoice", "ft20249")}
        assert decide_document(extraction(state="copy"), keys).action == REPLY

    def test_document_number_matching_ignores_separators_and_case(self):
        """"FT 2024/1" and "ft-2024-1" are the same document."""
        keys = {("invoice", "ft20241")}
        decision = decide_document(extraction(state="copy", number="ft-2024-1"), keys)
        assert decision.action == IGNORE

    def test_a_receipt_original_does_not_file_away_an_invoice_copy(self):
        """Numbering is per series, so the type is part of the key."""
        keys = {("receipt", "ft20241")}
        assert decide_document(extraction(state="copy"), keys).action == REPLY

    def test_a_copy_with_no_number_cannot_be_matched_and_gets_its_reply(self):
        keys = {("invoice", "ft20241")}
        assert decide_document(extraction(state="copy", number=None), keys).action == REPLY


class TestOriginalDocumentKeys:
    def test_only_originals_are_collected(self):
        extractions = [
            extraction(number="FT 1", state="original"),
            extraction(number="FT 2", state="copy"),
        ]
        assert original_document_keys(extractions) == {("invoice", "ft1")}

    def test_a_null_state_counts_as_an_original(self):
        assert original_document_keys([extraction(number="FT 1", state=None)]) == {("invoice", "ft1")}

    def test_documents_with_no_number_are_skipped(self):
        assert original_document_keys([extraction(number=None)]) == set()


# --------------------------------------------------------------------------- #
# Helpers that feed both routing and the reviewer-facing alerts
# --------------------------------------------------------------------------- #


class TestIngestionBlockers:
    def test_a_full_confident_report_has_no_blockers(self):
        assert ingestion_blockers(validation()) == []

    def test_a_missing_report_is_itself_a_blocker(self):
        assert ingestion_blockers(None) == ["no validation report"]

    def test_each_low_confidence_field_is_named(self):
        blockers = ingestion_blockers(validation(confidence=POOR))
        assert len(blockers) == 7
        assert all("confidence" in blocker for blocker in blockers)

    def test_a_missing_field_is_reported_as_missing_not_low_confidence(self):
        assert ingestion_blockers(validation(currency=None)) == ["currency missing"]

    def test_a_supplier_absent_from_the_registry_blocks_ingestion(self):
        """A null id after `resolve_registry_ids` means "not found", not "not yet looked up"."""
        assert ingestion_blockers(validation(supplier_id=None)) == [
            "supplier_id not found in registry"
        ]

    def test_a_client_absent_from_the_registry_blocks_ingestion(self):
        assert ingestion_blockers(validation(bu_id=None)) == ["bu_id not found in registry"]

    def test_an_id_is_only_expected_when_there_was_something_to_look_up(self):
        """No VAT and no name means no lookup was owed, so the null id is not a miss."""
        report = validation(supplier_id=None, supplier_vat=None, supplier_name=None)
        assert "supplier_id not found in registry" not in ingestion_blockers(report)


class TestMissingPos:
    def test_none_when_there_is_no_report(self):
        assert missing_pos(None) is None

    def test_no_supplier_vat_is_not_a_po_problem(self):
        assert missing_pos(validation(supplier_vat=None)) is None

    def test_empty_list_when_a_required_po_is_absent(self, requires_po):
        assert missing_pos(validation()) == []

    def test_the_unknown_pos_are_returned(self, monkeypatch):
        patch_po(monkeypatch, LOGISTICS, po_known=False)
        assert missing_pos(validation(po_list=["PO-1", "PO-2"])) == ["PO-1", "PO-2"]


class TestBuildAlertsList:
    """`build_alerts_list` takes the document's own decision, so these build it
    with `decide_document` rather than by hand — the pairing of an action with
    its PO answer is exactly what the alerts must agree with.
    """

    def test_a_clean_document_raises_no_alerts(self):
        result = PipelineResult(
            filename="doc.pdf",
            status="validated",
            classification=classification(),
            validation=validation(alert_fields=True),
        )
        assert build_alerts_list(result, decide_document(result)) == []

    def test_alerts_cover_more_fields_than_ingestion_requires(self):
        """supplier_name/document_number/bu_name do not block ingestion but are
        still worth a reviewer's attention.
        """
        result = PipelineResult(
            filename="doc.pdf",
            status="validated",
            classification=classification(),
            validation=validation(),
        )
        assert ingestion_blockers(result.validation) == []
        assert build_alerts_list(result, decide_document(result)) == [
            "Campo em falta: Nome do fornecedor",
            "Campo em falta: Número do documento",
            "Campo em falta: Nome do cliente",
        ]

    def test_an_unvalidated_document_says_so(self):
        result = extraction(with_validation=False)
        assert build_alerts_list(result, decide_document(result)) == ["Documento não validado"]

    def test_alerts_are_reviewer_facing_portuguese_labels(self):
        result = PipelineResult(
            filename="doc.pdf",
            status="validated",
            classification=classification(),
            validation=validation(total_amount=None),
        )
        assert "Campo em falta: Valor total" in build_alerts_list(result, decide_document(result))

    def test_the_po_alert_agrees_with_the_routing(self, requires_po):
        """One `missing_pos` call, carried on the decision, so an alert and an
        action cannot disagree.
        """
        result = extraction(po_list=[])
        alerts = build_alerts_list(result, decide_document(result))
        assert "Fornecedor requer nota de encomenda e nenhuma foi encontrada" in alerts

    def test_a_document_that_never_reached_the_po_check_says_so(self):
        """A blocked document routes to MANUAL without the PO lookups running,
        so the reviewer is told the check never ran rather than reading its
        silence as "no PO problem".
        """
        result = PipelineResult(
            filename="doc.pdf",
            status="validated",
            classification=classification(),
            validation=validation(alert_fields=True, total_amount=None),
        )
        decision = decide_document(result)

        assert decision.action == MANUAL
        assert decision.po_problems == NOT_CHECKED
        assert PO_ALERT_NOT_CHECKED in build_alerts_list(result, decision)


# --------------------------------------------------------------------------- #
# Layer 2 — the roll-up
# --------------------------------------------------------------------------- #


def document(action, reply_text=None):
    from invoice_extraction.decisions import DocumentDecision

    return DocumentDecision(filename="d.pdf", action=action, reason="", reply_text=reply_text)


class TestRollUpActions:
    def test_all_finished_documents_archive_the_email(self):
        assert roll_up_actions([document(INGEST), document(IGNORE)]) == [EMAIL_ARCHIVE]

    def test_an_email_with_no_documents_falls_back_to_the_inbox(self):
        """"Nothing to do" is not "everything done"."""
        assert roll_up_actions([]) == [EMAIL_INBOX]

    def test_one_outstanding_document_prevents_archiving(self):
        assert roll_up_actions([document(INGEST), document(REPLY)]) == [EMAIL_REPLY]

    def test_an_email_can_warrant_several_actions_at_once(self):
        actions = roll_up_actions([document(REPLY), document(TREASURY), document(MANUAL)])
        assert actions == [EMAIL_REPLY, EMAIL_TREASURY, EMAIL_INBOX]

    def test_manual_and_inbox_both_roll_up_to_the_inbox(self):
        assert roll_up_actions([document(MANUAL)]) == [EMAIL_INBOX]
        assert roll_up_actions([document(INBOX)]) == [EMAIL_INBOX]


# --------------------------------------------------------------------------- #
# Layer 2 — decide_email
# --------------------------------------------------------------------------- #


class TestDecideEmailACases:
    """The cases decided before any document is looked at."""

    def test_a3_failed_ingestion_is_left_in_the_inbox(self):
        result = EmailIngestionResult(source="m", status="failed", message="boom")
        decision = decide_email(result, [])
        assert decision.actions == [EMAIL_INBOX]
        assert "boom" in decision.reason

    def test_a4_an_already_processed_email_is_left_alone(self):
        decision = decide_email(EmailIngestionResult(source="m", status="skipped"), [])
        assert decision.actions == [EMAIL_INBOX]
        assert decision.reason == "already processed"

    def test_a5_pdfs_that_produced_nothing_are_left_in_the_inbox(self):
        """A splitter bug, not a supplier problem."""
        decision = decide_email(ingested(("chunked",)), [])
        assert decision.actions == [EMAIL_INBOX]
        assert "no documents extracted" in decision.reason

    def test_an_unclassified_body_is_left_in_the_inbox(self):
        decision = decide_email(ingested(()), [], intent=None)
        assert decision.actions == [EMAIL_INBOX]
        assert "not classified" in decision.reason

    def test_a1_a_delivery_with_no_attachment_gets_a_reply(self):
        decision = decide_email(ingested(()), [], intent=intent(True, False))
        assert decision.actions == [EMAIL_REPLY]
        assert decision.reply_lines == [REPLY_TEXT_NO_PDF]
        assert "no attachments" in decision.reason

    def test_a2_a_delivery_with_no_pdf_gets_a_reply(self):
        decision = decide_email(ingested(("stored",)), [], intent=intent(True, False))
        assert decision.actions == [EMAIL_REPLY]
        assert "none was a PDF" in decision.reason

    def test_an_invoice_link_is_ours_to_fetch_so_the_email_stays_open(self):
        decision = decide_email(ingested(()), [], intent=intent(True, True))
        assert decision.actions == [EMAIL_INBOX]
        assert decision.out_of_scope is False
        assert decision.status == EMAIL_STATUS_OPEN


class TestOutOfScope:
    """No document and a body that delivers none: the pipeline ends there."""

    def test_a_non_delivery_email_is_flagged_out_of_scope(self):
        decision = decide_email(ingested(()), [], intent=intent(False, False))
        assert decision.out_of_scope is True

    def test_an_email_that_only_mentions_an_invoice_gets_no_reply(self):
        """A feedback survey naming an invoice is not a supplier mistake.

        Regression: a DNV satisfaction survey quoting an invoice number was
        classified invoice-related and answered with "the format of the file
        sent is not accepted". Only a DELIVERY warrants that reply.
        """
        decision = decide_email(ingested(()), [], intent=intent(False, False))
        assert decision.actions == [EMAIL_INBOX]
        assert decision.should_reply is False

    def test_an_out_of_scope_email_is_closed(self):
        decision = decide_email(ingested(()), [], intent=intent(False, False))
        assert decision.status == EMAIL_STATUS_CLOSED

    def test_it_still_stays_in_the_inbox_for_a_human_to_read(self):
        decision = decide_email(ingested(()), [], intent=intent(False, False))
        assert decision.actions == [EMAIL_INBOX]

    def test_closing_beats_escalation(self):
        """Out of scope is finished however deep the thread ran."""
        decision = decide_email(
            ingested(()),
            [],
            intent=intent(False, False),
            thread_message_count=THREAD_ESCALATION_COUNT,
        )
        assert decision.status == EMAIL_STATUS_CLOSED

    def test_a_non_delivery_email_with_a_link_is_still_out_of_scope(self):
        """The link is not the point — the body is not delivering a document."""
        decision = decide_email(ingested(()), [], intent=intent(False, True))
        assert decision.out_of_scope is True


class TestDecideEmailWithDocuments:
    def test_documents_are_decided_and_rolled_up(self):
        decision = decide_email(ingested(), [extraction()])
        assert decision.actions == [EMAIL_ARCHIVE]
        assert [d.action for d in decision.documents] == [INGEST]

    def test_a_duplicate_is_filed_away_against_the_originals_of_its_own_email(self):
        extractions = [
            extraction(filename="orig.pdf", state="original"),
            extraction(filename="copy.pdf", state="copy"),
        ]
        decision = decide_email(ingested(), extractions)
        assert [d.action for d in decision.documents] == [INGEST, IGNORE]
        assert decision.actions == [EMAIL_ARCHIVE]

    def test_repeated_reasons_are_stated_once_in_the_reply(self):
        extractions = [
            extraction(filename="a.pdf", state="proforma", number="FT 1"),
            extraction(filename="b.pdf", state="proforma", number="FT 2"),
        ]
        decision = decide_email(ingested(), extractions)
        assert decision.reply_lines == [REPLY_TEXT_PROFORMA]

    def test_one_email_can_owe_a_reply_and_a_treasury_forward(self):
        extractions = [
            extraction(filename="a.pdf", state="proforma", number="FT 1"),
            extraction(filename="b.pdf", document_type="receipt", number="RC 1"),
        ]
        decision = decide_email(ingested(), extractions)
        assert decision.actions == [EMAIL_REPLY, EMAIL_TREASURY]
        assert decision.should_reply and decision.should_forward_to_treasury

    def test_the_reason_names_only_the_documents_that_drove_an_action(self):
        extractions = [
            extraction(filename="ok.pdf", number="FT 1"),
            extraction(filename="bad.pdf", state="proforma", number="FT 2"),
        ]
        assert decide_email(ingested(), extractions).reason == "invoice is proforma"

    def test_a_fully_processed_email_says_nothing_is_outstanding(self):
        assert "nothing outstanding" in decide_email(ingested(), [extraction()]).reason

    def test_the_reply_body_lists_every_distinct_reason(self):
        extractions = [
            extraction(filename="a.pdf", state="proforma", number="FT 1", language="pt"),
            extraction(filename="b.pdf", state="copy", number="FT 2"),
        ]
        body = decide_email(ingested(), extractions).reply_body
        assert REPLY_TEXT_PROFORMA["pt"] in body and REPLY_TEXT_COPY["pt"] in body


class TestReplyLanguage:
    """Which of the two letters the supplier gets, and why."""

    def test_the_registry_preference_wins(self, monkeypatch):
        """The supplier told us, so the document's own language does not matter."""
        patch_preferred_language(monkeypatch, "pt")
        decision = decide_email(ingested(), [extraction(state="proforma", language="en")])
        assert decision.language == "pt"

    def test_the_document_language_decides_an_unidentified_supplier(self):
        decision = decide_email(ingested(), [extraction(state="proforma", language="pt")])
        assert decision.language == "pt"
        assert REPLY_TEXT_PROFORMA["pt"] in decision.reply_body

    def test_an_english_document_gets_the_english_letter(self):
        decision = decide_email(ingested(), [extraction(state="proforma", language="en")])
        assert decision.language == "en"
        assert REPLY_TEXT_PROFORMA["en"] in decision.reply_body

    def test_an_unreadable_language_falls_back(self):
        decision = decide_email(ingested(), [extraction(state="proforma", language=None)])
        assert decision.language == DEFAULT_REPLY_LANGUAGE

    def test_a_third_language_falls_back_rather_than_guessing(self):
        """We have no French letter, so a French supplier gets the default one."""
        decision = decide_email(ingested(), [extraction(state="proforma", language="fr")])
        assert decision.language == DEFAULT_REPLY_LANGUAGE

    def test_only_the_documents_driving_the_reply_have_a_say(self):
        """A booked invoice is not what the letter is about."""
        extractions = [
            extraction(filename="booked.pdf", number="FT 1", language="en"),
            extraction(filename="proforma.pdf", state="proforma", number="FT 2", language="pt"),
        ]
        assert decide_email(ingested(), extractions).language == "pt"

    def test_the_first_replying_document_settles_a_disagreement(self):
        extractions = [
            extraction(filename="a.pdf", state="proforma", number="FT 1", language="en"),
            extraction(filename="b.pdf", state="copy", number="FT 2", language="pt"),
        ]
        assert decide_email(ingested(), extractions).language == "en"

    def test_every_reason_is_written_in_the_letters_language(self):
        """One language per letter — a reason never keeps its own."""
        extractions = [
            extraction(filename="a.pdf", state="proforma", number="FT 1", language="en"),
            extraction(filename="b.pdf", state="copy", number="FT 2", language="pt"),
        ]
        body = decide_email(ingested(), extractions).reply_body
        assert REPLY_TEXT_PROFORMA["en"] in body and REPLY_TEXT_COPY["en"] in body
        assert REPLY_TEXT_COPY["pt"] not in body

    def test_a_no_po_reply_uses_the_identified_suppliers_language(self, monkeypatch, requires_po):
        """The one reply path that reaches the registry: the supplier IS identified."""
        patch_preferred_language(monkeypatch, "en")
        decision = decide_email(ingested(), [extraction(po_list=[])])
        assert decision.language == "en"
        assert REPLY_TEXT_NO_PO["en"] in decision.reply_body

    def test_the_email_body_decides_when_no_document_was_read(self):
        decision = decide_email(ingested(()), [], intent=intent(True, False, language="pt"))
        assert decision.language == "pt"
        assert REPLY_TEXT_NO_PDF["pt"] in decision.reply_body

    def test_an_unreadable_body_language_falls_back(self):
        decision = decide_email(ingested(()), [], intent=intent(True, False))
        assert decision.language == DEFAULT_REPLY_LANGUAGE

    def test_an_escalated_email_never_asks_the_registry(self, monkeypatch):
        """Nothing is sent, so no lookup is worth a database round trip."""

        def boom(supplier_id):
            raise AssertionError("registry consulted for an email that sends nothing")

        monkeypatch.setattr(decisions, "supplier_preferred_language", boom)
        decision = decide_email(
            ingested(),
            [extraction(state="proforma", language="pt")],
            thread_message_count=THREAD_ESCALATION_COUNT,
        )
        assert decision.actions == [EMAIL_INBOX]


class TestThreadEscalation:
    """From THREAD_ESCALATION_COUNT on, nothing more is sent outward."""

    BELOW = THREAD_ESCALATION_COUNT - 1

    def test_below_the_threshold_the_supplier_is_still_chased(self):
        decision = decide_email(
            ingested(), [extraction(state="proforma")], thread_message_count=self.BELOW
        )
        assert decision.actions == [EMAIL_REPLY]
        assert decision.thread_escalated is False

    def test_at_the_threshold_a_reply_is_parked_for_a_human(self):
        decision = decide_email(
            ingested(), [extraction(state="proforma")], thread_message_count=THREAD_ESCALATION_COUNT
        )
        assert decision.actions == [EMAIL_INBOX]
        assert decision.thread_escalated is True

    def test_a_treasury_forward_is_escalated_too(self):
        decision = decide_email(
            ingested(),
            [extraction(document_type="receipt")],
            thread_message_count=THREAD_ESCALATION_COUNT,
        )
        assert decision.actions == [EMAIL_INBOX]

    def test_the_reply_text_is_dropped_along_with_the_action(self):
        decision = decide_email(
            ingested(), [extraction(state="proforma")], thread_message_count=THREAD_ESCALATION_COUNT
        )
        assert decision.reply_lines == []
        assert decision.documents[0].reply_text is None

    def test_the_document_reason_records_why_it_was_not_chased(self):
        decision = decide_email(
            ingested(), [extraction(state="proforma")], thread_message_count=THREAD_ESCALATION_COUNT
        )
        assert "not chased further" in decision.documents[0].reason

    def test_ingestable_documents_are_untouched_by_escalation(self):
        decision = decide_email(
            ingested(), [extraction()], thread_message_count=THREAD_ESCALATION_COUNT
        )
        assert decision.documents[0].action == INGEST
        assert decision.actions == [EMAIL_ARCHIVE]

    def test_the_a1_reply_is_escalated_as_well(self):
        decision = decide_email(
            ingested(()),
            [],
            intent=intent(True, False),
            thread_message_count=THREAD_ESCALATION_COUNT,
        )
        assert decision.actions == [EMAIL_INBOX]
        assert decision.status == EMAIL_STATUS_ACTION_REQUIRED

    def test_an_email_with_no_thread_context_is_treated_as_the_first(self):
        decision = decide_email(ingested(), [extraction(state="proforma")], thread_message_count=None)
        assert decision.actions == [EMAIL_REPLY]

    def test_escalation_is_recorded_even_on_the_early_return_paths(self):
        """A-cases return before the documents are read, but the thread is still
        escalated — the flag says so.
        """
        decision = decide_email(
            EmailIngestionResult(source="m", status="skipped"),
            [],
            thread_message_count=THREAD_ESCALATION_COUNT,
        )
        assert decision.thread_escalated is True


class TestEmailStatus:
    """The lifecycle axis, read off a decision built directly."""

    @staticmethod
    def build(actions, **kwargs) -> EmailDecision:
        return EmailDecision(actions=actions, reason="", **kwargs)

    def test_an_archived_email_is_closed(self):
        assert self.build([EMAIL_ARCHIVE]).status == EMAIL_STATUS_CLOSED

    def test_a_treasury_only_email_is_closed(self):
        """Handed to treasury and off our books."""
        assert self.build([EMAIL_TREASURY]).status == EMAIL_STATUS_CLOSED

    def test_treasury_alongside_a_reply_is_still_open(self):
        assert self.build([EMAIL_REPLY, EMAIL_TREASURY]).status == EMAIL_STATUS_OPEN

    def test_an_inbox_email_is_open(self):
        assert self.build([EMAIL_INBOX]).status == EMAIL_STATUS_OPEN

    def test_an_outstanding_email_on_an_escalated_thread_requires_action(self):
        assert self.build([EMAIL_INBOX], thread_escalated=True).status == EMAIL_STATUS_ACTION_REQUIRED

    def test_closing_beats_escalation(self):
        assert self.build([EMAIL_ARCHIVE], thread_escalated=True).status == EMAIL_STATUS_CLOSED

    def test_out_of_scope_closes_the_process(self):
        assert self.build([EMAIL_INBOX], out_of_scope=True).status == EMAIL_STATUS_CLOSED

    def test_out_of_scope_beats_escalation(self):
        decision = self.build([EMAIL_INBOX], out_of_scope=True, thread_escalated=True)
        assert decision.status == EMAIL_STATUS_CLOSED

    def test_the_end_to_end_statuses_of_a_processed_email(self):
        assert decide_email(ingested(), [extraction()]).status == EMAIL_STATUS_CLOSED
        assert decide_email(ingested(), [extraction(state="proforma")]).status == EMAIL_STATUS_OPEN


class TestClosePriorProcess:
    """Layer 3 — an earlier email revisited because a newer one arrived.

    `documents` is (action, status) per fct_documents row of the EARLIER process.
    """

    def test_a_reply_only_process_is_closed(self):
        """The supplier answered what we asked; nothing else was pending."""
        assert close_prior_process([EMAIL_REPLY], []) is True

    def test_reply_plus_treasury_is_closed(self):
        """The forward is terminal on its own, so it adds nothing to wait for."""
        assert close_prior_process([EMAIL_REPLY, EMAIL_TREASURY], []) is True

    def test_a_process_that_never_asked_the_supplier_is_untouched(self):
        assert close_prior_process([EMAIL_INBOX], []) is False
        assert close_prior_process([EMAIL_TREASURY], []) is False
        assert close_prior_process([EMAIL_ARCHIVE], []) is False

    def test_a_process_with_no_recorded_action_is_untouched(self):
        """NULL email_action — written before the column existed."""
        assert close_prior_process(None, []) is False
        assert close_prior_process([], []) is False

    def test_reply_plus_inbox_closes_when_every_document_is_settled(self):
        documents = [
            (INBOX, DOC_STATUS_IGNORED),
            (INGEST, DOC_STATUS_BOOKED),
            (REPLY, DOC_STATUS_COMMUNICATED),
            (IGNORE, DOC_STATUS_IGNORED),
            (TREASURY, DOC_STATUS_COMMUNICATED),
        ]
        assert close_prior_process([EMAIL_REPLY, EMAIL_INBOX], documents) is True

    def test_reply_plus_inbox_stays_open_on_a_document_awaiting_review(self):
        documents = [(INBOX, DOC_STATUS_IGNORED), (MANUAL, DOC_STATUS_CREATED)]
        assert close_prior_process([EMAIL_REPLY, EMAIL_INBOX], documents) is False

    def test_reply_plus_inbox_stays_open_on_a_document_not_yet_booked(self):
        """Bound for SAP but `sap_pipeline` has not booked it — still owed."""
        documents = [(INGEST, DOC_STATUS_CREATED)]
        assert close_prior_process([EMAIL_REPLY, EMAIL_INBOX], documents) is False

    def test_reply_plus_inbox_with_no_documents_is_closed(self):
        """Vacuously settled: the INBOX came from the email body, not a document."""
        assert close_prior_process([EMAIL_REPLY, EMAIL_INBOX], []) is True


class TestCloseProcessAfterManualSend:
    """Layer 3 — a process revisited because a human sent a document to SAP.

    `documents` is (action, status) per fct_documents row of the process, read
    AFTER the booking has been written.
    """

    def test_closed_when_every_document_is_settled(self):
        documents = [
            (INGEST, DOC_STATUS_BOOKED),
            (REPLY, DOC_STATUS_COMMUNICATED),
            (TREASURY, DOC_STATUS_COMMUNICATED),
            (INBOX, DOC_STATUS_IGNORED),
            (IGNORE, DOC_STATUS_IGNORED),
        ]
        assert close_process_after_manual_send(documents) is True

    def test_the_just_booked_document_alone_closes_the_process(self):
        assert close_process_after_manual_send([(INGEST, DOC_STATUS_BOOKED)]) is True

    def test_stays_open_on_a_sibling_awaiting_review(self):
        """Another document still sitting in manual validation."""
        documents = [(INGEST, DOC_STATUS_BOOKED), (MANUAL, DOC_STATUS_CREATED)]
        assert close_process_after_manual_send(documents) is False

    def test_stays_open_on_a_sibling_not_yet_booked(self):
        documents = [(INGEST, DOC_STATUS_BOOKED), (INGEST, DOC_STATUS_CREATED)]
        assert close_process_after_manual_send(documents) is False

    def test_an_unbooked_document_does_not_close_the_process(self):
        """The booking failed, so `sap_pipeline` still owes this row."""
        assert close_process_after_manual_send([(INGEST, DOC_STATUS_CREATED)]) is False

    def test_no_documents_is_closed(self):
        """Vacuously settled, as in `close_prior_process`."""
        assert close_process_after_manual_send([]) is True
