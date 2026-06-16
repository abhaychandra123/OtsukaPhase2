"""Lightweight keyword/tag retrieval over the playbook and similar deals.

No embeddings — deliberately simple, deterministic scoring on tags and substring
matches. Good enough for grounding the junior assistant and fully GPU-free.
"""
from __future__ import annotations

from senpai.data import store


def _tokens(text: str) -> list[str]:
    return [t for t in (text or "").replace("、", " ").replace("。", " ").split() if t]


def retrieve_playbook(query: str = "", tags: list[str] | None = None,
                      limit: int = 3) -> list[dict]:
    """Rank playbook entries by tag overlap + substring hits against the query.
    Returns the top `limit` entries (each the raw playbook dict)."""
    tags = [t.strip() for t in (tags or []) if t.strip()]
    q = (query or "").strip()
    scored = []
    for entry in store.all_playbook():
        score = 0
        etags = entry.get("situation_tags", [])
        for t in tags:
            if any(t in et or et in t for et in etags):
                score += 3
        for et in etags:
            if q and et in q:
                score += 2
        for tok in _tokens(q):
            if len(tok) >= 2 and tok in entry.get("text", ""):
                score += 1
        if score:
            scored.append((score, entry))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in scored[:limit]]


def find_similar_deals(customer_id: str = "", industry: str = "",
                       profile_tags: list[str] | None = None,
                       limit: int = 3) -> list[dict]:
    """Feature-match deals on the customer's industry / size / profile tags —
    useful for new or thin customers with little history of their own."""
    target = store.get_customer(customer_id) if customer_id else None
    if target:
        industry = industry or target.get("industry", "")
        profile_tags = profile_tags or target.get("profile_tags", [])
    profile_tags = profile_tags or []

    scored = []
    for deal in store.all_deals():
        if customer_id and deal["customer_id"] == customer_id:
            continue
        cust = store.get_customer(deal["customer_id"])
        if not cust:
            continue
        score = 0
        if industry and cust.get("industry") == industry:
            score += 3
        score += len(set(profile_tags) & set(cust.get("profile_tags", [])))
        if target and cust.get("size") == target.get("size"):
            score += 1
        if score:
            scored.append((score, deal))
    scored.sort(key=lambda x: (x[0], x[1]["deal_id"]), reverse=True)
    return [d for _, d in scored[:limit]]
