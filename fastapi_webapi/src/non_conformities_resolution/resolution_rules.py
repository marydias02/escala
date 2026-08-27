"""Non-conformity statuses, issues and transitions — THE place to change the rules.

Every other module in this package imports its vocabulary from here, 
so the business rules can be read — and tested — without a
SAP connection or a running Postgres.

Two vocabularies, mirroring `invoice_extraction.decisions`:

- STATUS_* is what reaches `sap_processes.status`. A process moves through them
  and stops at one of `TERMINAL_STATUSES`.
- ISSUE_* is what SAP wrote to `sap_processes.issue`, i.e. why the process is
  non-conforming in the first place. We read these; we never invent them.

Each string is written once as a `Final` constant and the `Literal` is built from
those constants, so the names and the type cannot drift apart. `Final` is what
makes a constant usable inside `Literal[...]`; a plain assignment is not.
"""

from typing import Callable, Final, Literal, Optional

# -- Statuses ---------------------------------------------------------------
# -> sap_processes.status (VARCHAR(50), free text today — there is no CHECK
# constraint and no enum, so these constants are the only thing keeping the
# vocabulary consistent).

STATUS_NEW: Final = "Novo processo não conforme"  # New non-conforming process
STATUS_AUTO: Final = "Processamento automático"  # Automatic processing (never reached the agent)
STATUS_BY_AGENT: Final = "Processado pelo agente"  # Processed by the agent
STATUS_MANUAL: Final = "Processado manualmente"  # Processed manually
STATUS_BUYER_REPLIED: Final = "Com resposta do buyer - a processar"  # Buyer replied, to process
STATUS_WITH_BUYER: Final = "Em resolução pelo buyer"  # Being resolved by the buyer
STATUS_NEEDS_MANUAL: Final = "Necessita de validação manual"  # Needs manual validation

ProcessStatus = Literal[
    STATUS_NEW,
    STATUS_AUTO,
    STATUS_BY_AGENT,
    STATUS_MANUAL,
    STATUS_BUYER_REPLIED,
    STATUS_WITH_BUYER,
    STATUS_NEEDS_MANUAL,
]

# The two statuses the pipeline picks up, in processing order: a buyer who has
# already answered is waiting on us, so those go first.
PIPELINE_STATUSES: Final = (STATUS_BUYER_REPLIED, STATUS_NEW)

# Nothing more happens to a process in one of these. `STATUS_NEEDS_MANUAL` is
# terminal *for the pipeline* — a human still acts on it, outside this codebase.
TERMINAL_STATUSES: Final = (
    STATUS_BY_AGENT,
    STATUS_MANUAL,
    STATUS_AUTO,
    STATUS_NEEDS_MANUAL,
)

# "Someone already processed this" — the guard for the reconciliation rule below.
# Narrower than TERMINAL_STATUSES: a process that needs manual validation has NOT
# been processed, so a reconciled one may still be marked STATUS_MANUAL.
PROCESSED_STATUSES: Final = (STATUS_BY_AGENT, STATUS_MANUAL, STATUS_AUTO)

# -- Issues -----------------------------------------------------------------
# -> sap_processes.issue (VARCHAR(100), free text today). SAP writes these; the
# strings must match what it produces or every process falls through to manual.

ISSUE_NO_PO: Final = "Falta PC"  # Missing purchase order
ISSUE_NO_MIGO: Final = "Falta MIGO"  # Missing goods receipt
ISSUE_AMOUNT_MISMATCH: Final = "Valor FT <> Valor PC"  # Invoice amount != PO amount
ISSUE_WRONG_VAT: Final = "Iva incorreto"  # Wrong VAT

ProcessIssue = Literal[
    ISSUE_NO_PO,
    ISSUE_NO_MIGO,
    ISSUE_AMOUNT_MISMATCH,
    ISSUE_WRONG_VAT,
]

# The issues that get a message to the buyer and a handler for their reply.
#
# ISSUE_WRONG_VAT has no defined buyer message so it falls through to 
# STATUS_NEEDS_MANUAL. Revise when understading the action needed
BUYER_ISSUES: Final = (ISSUE_NO_PO, ISSUE_NO_MIGO, ISSUE_AMOUNT_MISMATCH)

# What we write into SAP when handing an issue back to the buyer. Exact wording
# matters — these land in the SAP message log and are read by people.
ISSUE_MESSAGES: Final[dict[str, str]] = {
    ISSUE_NO_PO: "Falta PC, enviado para o Buyer para informar PC ou devolver fatura por falta de PC",
    ISSUE_NO_MIGO: "Falta MIGO, enviado para o Buyer para efetuar Migo",
    ISSUE_AMOUNT_MISMATCH: """PC divergente FT, enviado para o Buyer para confirmar 
    diferença (Bypass) qual o valor a consumir ou alterar o pedido de compra""",
}

# Issues the agent can fix on its own, without ever involving the buyer.
# To be added in this format:
#
#     from non_conformities_resolution.handlers.wrong_vat import handle
#     SOLVABLE_ISSUES = {ISSUE_WRONG_VAT: handle}
#
SOLVABLE_ISSUES: Final[dict[str, Callable]] = {}


# -- Pure predicates ---------------------------------------------------------


def is_terminal(status: Optional[str]) -> bool:
    """Whether the pipeline is finished with a process in this status."""
    return status in TERMINAL_STATUSES


def needs_buyer_message(issue: Optional[str]) -> bool:
    """Whether this issue is handed back to the buyer rather than solved here."""
    return issue in BUYER_ISSUES


def message_for_issue(issue: Optional[str]) -> Optional[str]:
    """The SAP message text for an issue, or None if it does not get one."""
    if issue is None:
        return None
    return ISSUE_MESSAGES.get(issue)


def is_solvable_by_agent(issue: Optional[str]) -> bool:
    """Whether the agent has a registered handler for this issue.

    Only consulted for issues outside BUYER_ISSUES; see SOLVABLE_ISSUES.
    """
    return issue in SOLVABLE_ISSUES


# -- Reconciliation ----------------------------------------------------------

def status_after_reconciliation(current: Optional[str], reconciled: Optional[bool]) -> Optional[str]:
    """A reconciled process that nobody here marked processed was resolved outside
    the pipeline — someone acted directly in SAP.

    Applied BEFORE `status_after_buyer_reply`, so a process that was reconciled
    exits as processed even if a buyer message also arrived. 

    Returns STATUS_MANUAL (if processed outside the pipeline), or None to leave the status alone.
    """
    if not reconciled:
        return None
    if current in PROCESSED_STATUSES:
        return None
    return STATUS_MANUAL


def status_after_buyer_reply(current: Optional[str], has_newer_buyer_message: bool) -> Optional[str]:
    """A process awaiting the buyer that has since received a message is ready for us.

    `has_newer_buyer_message` means: a `sap_messages` row for this process, from
    the buyer, timestamped after `last_interaction_datetime` — i.e. after our own
    last message. Establishing that is the caller's job (see
    `sap.sap_queries.fetch_reconcile_candidates`), because it needs the database.

    Returns STATUS_BUYER_REPLIED, or None to leave the status alone.
    """
    if current != STATUS_WITH_BUYER:
        return None
    if not has_newer_buyer_message:
        return None
    return STATUS_BUYER_REPLIED