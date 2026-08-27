"""Non-conformities resolution: RECONCILE -> FETCH -> APPLY REPLY -> REVALIDATE -> RESOLVE.

Advances SAP processes stuck on a non-conformity (missing PO, missing MIGO,
amount mismatch, ...) by reading buyer replies, applying what they say, and
either closing the process or handing it back to the buyer with a message.

Run standalone (`uv run python -m non_conformities_resolution.resolution_pipeline`), 
the same convention as `invoice_extraction.sap_pipeline`
— there is no scheduler/cron in this repo yet.

Stages, per process:

0. RECONCILE   — local-DB-only status corrections, over every non-terminal
                 process, before the fetch below. See `resolution_rules`:
                 - a reconciled process nobody marked processed -> Processado manualmente
                 - a buyer message newer than our last one    -> Com resposta do buyer - a processar
1. FETCH       — every process in PIPELINE_STATUSES, buyer-replied ones first.
2. APPLY REPLY — buyer-replied processes only: parse the reply, dispatch to the
                 issue's handler (HANDLERS). Handlers execute actions
3. REVALIDATE  — a process the handler resolved is re-checked against SAP; no
                 issue left -> consume and stop here, otherwise fall through.
4. RESOLVE     — new processes, and buyer-replied ones still failing: a known
                 buyer issue gets a message and STATUS_WITH_BUYER; a
                 SOLVABLE_ISSUES issue gets solved directly (by agent / RPA actions); 
                 anything else is STATUS_NEEDS_MANUAL.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Optional

from loguru import logger

from non_conformities_resolution import config
from non_conformities_resolution.handlers import HANDLERS
from non_conformities_resolution.handlers.types import MissingSapColumnError
from non_conformities_resolution.nodes.read_buyer_reply import parse_buyer_reply
from non_conformities_resolution.resolution_rules import (
    STATUS_BUYER_REPLIED,
    STATUS_BY_AGENT,
    STATUS_NEEDS_MANUAL,
    STATUS_WITH_BUYER,
    is_solvable_by_agent,
    message_for_issue,
    needs_buyer_message,
    status_after_buyer_reply,
    status_after_reconciliation,
)
from non_conformities_resolution.sap import sap_queries
from non_conformities_resolution.sap.sap_client import consume_process, revalidate_process, send_message_to_buyer
from utils.utils_db import get_pool

Stage = Literal["reconcile", "buyer_reply", "revalidate", "resolve", "skipped"]


@dataclass
class ResolutionOutcome:
    reference_no: str
    issue: Optional[str]
    previous_status: str
    new_status: str
    stage: Stage
    detail: str = ""


# --- STAGE 0: RECONCILE ------------------------------------------------------


async def reconcile_statuses() -> list[ResolutionOutcome]:
    """Correct stale statuses over every non-terminal process, before FETCH runs.

    Applies `status_after_reconciliation` before `status_after_buyer_reply` for
    each candidate — see that function's docstring for why the order matters.
    """
    candidates = await sap_queries.fetch_reconcile_candidates()
    outcomes: list[ResolutionOutcome] = []

    for row in candidates:
        current = row["status"]

        new_status = status_after_reconciliation(current, row.get("reconciled"))
        if new_status is None:
            new_status = status_after_buyer_reply(current, row.get("has_newer_buyer_message", False))
        if new_status is None:
            continue

        if config.WRITE_TO_DB:
            await sap_queries.set_status(row["reference_no"], new_status)

        outcomes.append(
            ResolutionOutcome(
                reference_no=row["reference_no"],
                issue=row.get("issue"),
                previous_status=current,
                new_status=new_status,
                stage="reconcile",
            )
        )

    return outcomes


# --- STAGE 2: APPLY BUYER REPLY ----------------------------------------------


async def apply_buyer_reply(process: dict) -> ResolutionOutcome:
    """For a STATUS_BUYER_REPLIED process: parse the reply and dispatch to its
    issue's handler. Falls to STATUS_NEEDS_MANUAL if the issue has no handler or
    the reply could not be parsed with enough confidence.

    A process with no issue at all has nothing for a buyer reply to resolve —
    it is handed straight to REVALIDATE.
    """
    reference_no = process["reference_no"]
    issue = process.get("issue")
    current = process["status"]

    if issue is None:
        return await revalidate(process)

    handler = HANDLERS.get(issue)
    if handler is None:
        return ResolutionOutcome(
            reference_no=reference_no,
            issue=issue,
            previous_status=current,
            new_status=STATUS_NEEDS_MANUAL,
            stage="buyer_reply",
            detail=f"no handler registered for issue {issue!r}",
        )

    replies = await sap_queries.fetch_buyer_replies(
        reference_no, since=process.get("last_interaction_datetime")
    )
    if not replies:
        return ResolutionOutcome(
            reference_no=reference_no,
            issue=issue,
            previous_status=current,
            new_status=STATUS_NEEDS_MANUAL,
            stage="buyer_reply",
            detail="status says the buyer replied, but no message was found",
        )

    latest_reply = replies[-1]
    reply = parse_buyer_reply(latest_reply.get("content") or "", issue)

    if reply.confidence < config.BUYER_REPLY_MIN_CONFIDENCE:
        return ResolutionOutcome(
            reference_no=reference_no,
            issue=issue,
            previous_status=current,
            new_status=STATUS_NEEDS_MANUAL,
            stage="buyer_reply",
            detail=f"reply parsed with low confidence, go for manual review ({reply.confidence}): {reply.intent}",
        )

    outcome = await handler(process, reply)
    if not outcome.resolved:
        return ResolutionOutcome(
            reference_no=reference_no,
            issue=issue,
            previous_status=current,
            new_status=STATUS_NEEDS_MANUAL,
            stage="buyer_reply",
            detail=outcome.detail,
        )

    # Resolved by the handler; REVALIDATE decides whether that's enough to
    # close. bypassed carries forward so SAP's own check does not re-flag the
    # amount mismatch the buyer just accepted.
    return await revalidate(process, bypassed=outcome.bypassed)


# --- STAGE 3: REVALIDATE -----------------------------------------------------


async def revalidate(process: dict, bypassed: bool = False) -> ResolutionOutcome:
    """Re-check a handler-resolved process against SAP. Clean -> consume and
    stop; still failing -> fall through to RESOLVE, keeping its current status.

    `bypassed` comes from `HandlerOutcome.bypassed` (amount_mismatch's bypass
    path) — SAP needs that instruction or it will re-flag the mismatch the
    buyer just accepted.
    """
    reference_no = process["reference_no"]
    issue = process.get("issue")
    current = process["status"]

    remaining_issues = await revalidate_process(reference_no, bypassed=bypassed)
    if remaining_issues:
        return ResolutionOutcome(
            reference_no=reference_no,
            issue=issue,
            previous_status=current,
            new_status=current,
            stage="revalidate",
            detail=f"still failing: {remaining_issues}",
        )

    result = await consume_process(reference_no)
    new_status = STATUS_BY_AGENT if result.status == "ok" else current
    if config.WRITE_TO_DB and new_status != current:
        await sap_queries.set_status(reference_no, new_status)

    return ResolutionOutcome(
        reference_no=reference_no,
        issue=issue,
        previous_status=current,
        new_status=new_status,
        stage="revalidate",
        detail=result.detail or "",
    )


# --- STAGE 4: RESOLVE ---------------------------------------------------------


async def resolve_process(process: dict) -> ResolutionOutcome:
    """For a new process, or a buyer-replied one still failing: send the buyer a
    message, solve it directly if the agent can, or hand it to manual review.

    A process with no issue at all has nothing to resolve — it goes straight to
    REVALIDATE, which consumes it if SAP agrees it is clean.
    """
    reference_no = process["reference_no"]
    issue = process.get("issue")
    current = process["status"]

    if issue is None:
        return await revalidate(process)

    if needs_buyer_message(issue):
        content = message_for_issue(issue) or ""
        result = await send_message_to_buyer(reference_no, content)
        new_status = STATUS_WITH_BUYER if result.status == "ok" else current
        detail = content
    elif is_solvable_by_agent(issue):
        #for now no issues solvable by agent. To be added later
        handler = HANDLERS.get(issue)
        if handler is None:
            new_status = STATUS_NEEDS_MANUAL
            detail = f"issue {issue!r} is in SOLVABLE_ISSUES but has no HANDLERS entry"
        else:
            # If the handler resolves it, it is STATUS_BY_AGENT; otherwise STATUS_NEEDS_MANUAL.
            outcome = await handler(process, None)
            new_status = STATUS_BY_AGENT if outcome.resolved else STATUS_NEEDS_MANUAL
            detail = outcome.detail
    else:
        new_status = STATUS_NEEDS_MANUAL
        detail = f"issue {issue!r} has no buyer message and no registered handler"

    if config.WRITE_TO_DB and new_status != current:
        await sap_queries.set_status(reference_no, new_status)
        if new_status == STATUS_WITH_BUYER:
            await sap_queries.record_interaction(reference_no, "agent", datetime.now(timezone.utc))

    return ResolutionOutcome(
        reference_no=reference_no,
        issue=issue,
        previous_status=current,
        new_status=new_status,
        stage="resolve",
        detail=detail,
    )


# --- BATCH --------------------------------------------------------------------


async def _process_one(process: dict) -> ResolutionOutcome:
    """Steps 2-4 for a single process, dispatched by its current status.

    apply_buyer_reply calls into REVALIDATE itself once a handler resolves the
    issue, so there is nothing left to sequence here.
    """
    current = process["status"]

    if current == STATUS_BUYER_REPLIED:
        return await apply_buyer_reply(process)

    return await resolve_process(process)


async def run(limit: Optional[int] = None) -> list[ResolutionOutcome]:
    """Reconcile, then process every pipeline-eligible process. Isolates
    failures per row, so one bad process cannot stop the batch."""
    outcomes: list[ResolutionOutcome] = await reconcile_statuses()

    processes = await sap_queries.fetch_pipeline_processes(limit=limit or config.BATCH_LIMIT)
    for process in processes:
        try:
            outcome = await _process_one(process)
        except MissingSapColumnError as exc:
            logger.warning(f"  ⚠️  {process['reference_no']}: {exc}")
            continue
        except Exception as exc:  # noqa: BLE001 - keep the batch alive, inspect after
            logger.error(f"  ❌ {process['reference_no']}: {type(exc).__name__}: {exc}")
            continue
        outcomes.append(outcome)

    return outcomes


def print_summary(outcomes: list[ResolutionOutcome]) -> None:
    print("\n" + "=" * 70)
    print("NON-CONFORMITIES RESOLUTION")
    print("=" * 70)
    for outcome in outcomes:
        marker = "➡️ " if outcome.new_status != outcome.previous_status else "·  "
        print(
            f"  {marker}[{outcome.stage}] {outcome.reference_no} "
            f"({outcome.issue}): {outcome.previous_status!r} -> {outcome.new_status!r}"
            + (f" — {outcome.detail}" if outcome.detail else "")
        )


async def main() -> None:
    pool = await get_pool()
    try:
        outcomes = await run()
        print_summary(outcomes)
    finally:
        pool.terminate()


if __name__ == "__main__":
    asyncio.run(main())
