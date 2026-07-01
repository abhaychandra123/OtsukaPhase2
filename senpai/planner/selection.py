"""What the planner decides: a `Selection` — which capabilities to gather from and
what document to produce — plus the deterministic resolver that grounds it.

The LLM's job (in llm_planner.py) is to pick *which capabilities* are worth
gathering. IDs are never trusted to the model: the customer/deal a document is
grounded in is resolved here, deterministically, from the store (the project's
"never invent an ID" rule). So even a hallucinated capability list can only widen
or narrow the gather — it can never point the document at the wrong deal.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from senpai import config
from senpai.data import store

# The gather capabilities the planner may select from (documents is always the
# terminal, so it is not part of the selectable gather set).
GATHER_CAPABILITIES = ("conversation", "workspace", "crm", "knowledge", "web")
DOC_KINDS = ("proposal", "pptx", "docx")

_DEAL_ID_RE = re.compile(r"\bD\d{3}\b", re.IGNORECASE)
_PROPOSAL_CUES = ("提案", "proposal", "提案書")
# 稟議 (ringisho) is intentionally NOT here: it has its own dedicated template/tool
# (generate_ringisho) and is routed to the ReAct loop, not the planner.
_DOCX_CUES = ("文書", "報告書", "レポート", "docx", "document")
# External/factual cue (stale-in-weights topics) — reuse the doc tools' own heuristic.
from senpai.tools.impl import _auto_web  # noqa: E402


@dataclass(frozen=True)
class Selection:
    """The plan the LLMPlanner emits: the capability set to gather from + the
    document to build (kind + the deterministically-resolved entity it grounds in)."""
    goal: str
    capabilities: tuple[str, ...]          # subset of GATHER_CAPABILITIES
    doc_kind: str                          # one of DOC_KINDS
    deal_id: str | None = None
    customer_id: str | None = None
    target: str = ""                       # display name of the entity in focus
    lang: str = "ja"
    title: str = ""
    reason: str = ""                       # why these capabilities (observability)

    def with_capabilities(self, caps) -> "Selection":
        ordered = tuple(c for c in GATHER_CAPABILITIES if c in set(caps))
        return replace(self, capabilities=ordered)


def _resolve_entity(goal: str, deal_hint: str | None = None) -> tuple[str | None, str | None, str]:
    """(deal_id, customer_id, display_target) for the document, from the store.
    A `deal_hint` (e.g. the deal the rep picked in the selector) is authoritative;
    then an explicit D### in the goal; otherwise a customer name resolves to its
    primary open deal (largest amount) so a proposal can be grounded. None/None when
    the entity isn't in the CRM (e.g. a workspace-only company) — then a free deck
    grounds on the workspace/conversation instead."""
    if deal_hint:
        d = store.get_deal(deal_hint.strip().upper())
        if d:
            did = d["deal_id"]
            return did, d["customer_id"], store.customer_name(d["customer_id"])
    m = _DEAL_ID_RE.search(goal or "")
    if m:
        did = m.group(0).upper()
        d = store.get_deal(did)
        if d:
            return did, d["customer_id"], store.customer_name(d["customer_id"])
    cust = store.match_customer_in_text(goal or "")
    if not cust:
        return None, None, ""
    cid = cust["customer_id"]
    open_deals = [d for d in store.deals_for_customer(cid)
                  if config.is_open_rank(d.get("order_rank"))]
    open_deals.sort(key=lambda d: d.get("total_order_amount", 0), reverse=True)
    deal_id = open_deals[0]["deal_id"] if open_deals else None
    return deal_id, cid, cust.get("name", "")


def _pick_doc_kind(goal: str, deal_id: str | None) -> str:
    g = (goal or "")
    if deal_id or any(c in g.lower() or c in g for c in _PROPOSAL_CUES):
        # A grounded proposal needs a deal; without one it degrades to a free deck.
        return "proposal" if deal_id else "pptx"
    if any(c in g.lower() or c in g for c in _DOCX_CUES):
        return "docx"
    return "pptx"


def _lang_of(goal: str) -> str:
    """JA unless the goal has no CJK at all (then EN)."""
    return "ja" if re.search(r"[぀-ヿ一-鿿]", goal or "") else "ja"


def heuristic_selection(goal: str, deal_hint: str | None = None) -> Selection:
    """Deterministic capability selection — the default, and the fallback whenever
    the LLM is off or returns junk. Always gathers conversation (session context);
    adds workspace (self-gated on a real file match), CRM when an entity resolved,
    knowledge for proposals (playbook grounding), and web for external/factual
    topics with no internal entity."""
    deal_id, customer_id, target = _resolve_entity(goal, deal_hint)
    doc_kind = _pick_doc_kind(goal, deal_id)

    caps = ["conversation", "workspace"]
    if customer_id or deal_id:
        caps.append("crm")
    if doc_kind == "proposal":
        caps.append("knowledge")
    if _auto_web(goal) and not (customer_id or deal_id):
        caps.append("web")

    return Selection(
        goal=goal, capabilities=tuple(caps), doc_kind=doc_kind,
        deal_id=deal_id, customer_id=customer_id, target=target,
        lang=_lang_of(goal),
        reason="heuristic: " + ("entity in CRM" if (customer_id or deal_id)
                                else "no CRM entity — workspace/conversation grounded"))


def ground_selection(goal: str, caps, doc_kind: str, reason: str = "",
                     deal_hint: str | None = None) -> Selection:
    """Build a Selection from an LLM-chosen capability set + doc_kind, but re-ground
    the entity/IDs deterministically and enforce invariants: conversation is always
    gathered; a `proposal` with no resolvable deal degrades to a free `pptx`; CRM is
    only kept when an entity actually resolved."""
    deal_id, customer_id, target = _resolve_entity(goal, deal_hint)
    if doc_kind not in DOC_KINDS:
        doc_kind = _pick_doc_kind(goal, deal_id)
    if doc_kind == "proposal" and not deal_id:
        doc_kind = "pptx"  # can't ground a proposal without a deal

    chosen = {c for c in caps if c in set(GATHER_CAPABILITIES)}
    chosen.add("conversation")             # session context is always worth gathering
    if "crm" in chosen and not (customer_id or deal_id):
        chosen.discard("crm")              # nothing for CRM to ground on
    if doc_kind == "proposal":
        chosen.add("knowledge")

    return Selection(
        goal=goal, capabilities=tuple(c for c in GATHER_CAPABILITIES if c in chosen),
        doc_kind=doc_kind, deal_id=deal_id, customer_id=customer_id, target=target,
        lang=_lang_of(goal), reason=reason or "llm-selected")
