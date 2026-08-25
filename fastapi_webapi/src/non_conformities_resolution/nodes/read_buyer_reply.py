"""Interpret a buyer's reply message — simple parser today, possibly LLM node later.

A message that cannot be read goes for manual review.
"""

import re
from typing import Optional

from non_conformities_resolution.models.buyer_reply import BuyerReply
from non_conformities_resolution.resolution_rules import (
    ISSUE_AMOUNT_MISMATCH,
    ISSUE_NO_MIGO,
    ISSUE_NO_PO,
)
from utils.utils_db import normalize_key

# PO codes are always exactly 10 numeric digits (fct_purchase_orders.po_code is
# VARCHAR(10)), so a PO reference in free text is matched as a run of exactly
# 10 digits — no ordinary word can match this by accident.
_PO_PATTERN = re.compile(r"\b\d{10}\b")

_BYPASS_KEYWORDS = ("bypass",)
_PO_CHANGED_KEYWORDS = ("pc alterado", "pedido alterado", "pedido de compra alterado", "novo pc", "novo po")
_MIGO_KEYWORDS = ("migo", "receção efetuada", "receçao efetuada", "goods receipt")


def _find_po_code(content: str) -> str | None:
    match = _PO_PATTERN.search(content)
    if not match:
        return None
    return normalize_key(match.group(0))


def _contains_any(content_lower: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in content_lower for keyword in keywords)


def parse_buyer_reply(content: str, issue: Optional[str]) -> BuyerReply:
    """Interpret one buyer message in the context of the issue it answers.

    `content` is `sap_messages.content` for the message identified by
    `sap.sap_queries.fetch_buyer_replies` as the buyer's reply. `issue` is
    `sap_processes.issue` — nullable in the DB — so the same raw text is read
    differently depending on what was actually asked (a PO code means something
    different for ISSUE_NO_PO than for ISSUE_AMOUNT_MISMATCH). A missing issue
    falls to the same "unclear" outcome as an unrecognized one.
    """
    content_lower = (content or "").lower()

    if issue == ISSUE_NO_PO:
        po_code = _find_po_code(content)
        if po_code:
            return BuyerReply(
                intent="po_provided", po_code=po_code, raw_content=content, confidence=0.9
            )
        return BuyerReply(intent="unclear", raw_content=content, confidence=0.0)

    if issue == ISSUE_NO_MIGO:
        if _contains_any(content_lower, _MIGO_KEYWORDS):
            return BuyerReply(intent="migo_done", raw_content=content, confidence=0.9)
        return BuyerReply(intent="unclear", raw_content=content, confidence=0.0)

    if issue == ISSUE_AMOUNT_MISMATCH:
        if _contains_any(content_lower, _BYPASS_KEYWORDS):
            return BuyerReply(intent="bypass", raw_content=content, confidence=0.9)
        if _contains_any(content_lower, _PO_CHANGED_KEYWORDS):
            po_code = _find_po_code(content)
            return BuyerReply(intent="po_changed", po_code=po_code, raw_content=content, confidence=0.9)
        return BuyerReply(intent="unclear", raw_content=content, confidence=0.0)

    # An issue outside BUYER_ISSUES has no defined reply shape.
    return BuyerReply(intent="unclear", raw_content=content, confidence=0.0)
