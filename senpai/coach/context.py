"""Context Retrieval Layer for Senior Commentary.

Before the model is asked for its read, this assembles a *grounded* context
package from the store: the customer, the deal it most likely refers to, its
deterministic health, recent activity, quote/order history, prior deals, and a
similar past case. The model then reasons over real business context — not the
meeting note alone — so commentary can say "59 days inactive, stuck at 3_A for
two months" instead of generic "decision maker unclear".

Hard grounding rule: every fact here comes from an actual store record. Nothing
is inferred or invented. When the note can't be linked to a known customer, that
is stated explicitly so the model knows to read from the note alone and must not
fabricate customer facts.
"""
from __future__ import annotations

from datetime import date

from senpai import config
from senpai.coach.cases import find_similar_cases
from senpai.data import store
from senpai.health.flags import deal_flags
from senpai.health.scoring import score_deal

# Corporate tokens stripped when trying to spot a customer name inside free text.
_CORP_TOKENS = ["株式会社", "有限会社", "合同会社", "(株)", "（株）", "(有)", "（有）"]


def _parse(d: str | None) -> date | None:
    try:
        return date.fromisoformat(d) if d else None
    except (ValueError, TypeError):
        return None


def _days_since(d: str | None, today: date) -> int | None:
    dt = _parse(d)
    return (today - dt).days if dt else None


def _yen(n) -> str:
    try:
        return f"¥{int(n):,}"
    except (ValueError, TypeError):
        return "¥0"


def _name_forms(name: str) -> list[str]:
    """A customer name plus its bare form (corporate prefix/suffix removed), so
    '有限会社村田印刷' is found from a note that just says '村田印刷'."""
    forms = {name}
    bare = name
    for tok in _CORP_TOKENS:
        bare = bare.replace(tok, "")
    bare = bare.strip()
    if len(bare) >= 2:
        forms.add(bare)
    return [f for f in forms if f]


def match_customer_in_note(note: str) -> dict | None:
    """Find the most specific known customer named in the note (substring match
    on the full or bare name). Longest match wins, so '大和商事システム' beats
    '大和'. Returns the customer record or None."""
    text = note or ""
    best: tuple[int, dict] | None = None
    for c in store.all_customers():
        for form in _name_forms(c.get("name", "")):
            if form and form in text:
                if best is None or len(form) > best[0]:
                    best = (len(form), c)
    return best[1] if best else None


def _pick_deal(customer_id: str) -> dict | None:
    """The deal a note about this customer most likely concerns: prefer an open
    deal, most recently updated; else the most recent deal of any status."""
    deals = store.deals_for_customer(customer_id)
    if not deals:
        return None
    open_deals = [d for d in deals if config.is_open_rank(d.get("order_rank"))]
    pool = open_deals or deals
    return max(pool, key=lambda d: d.get("rank_updated_at")
               or d.get("registered_at") or "")


def _customer_history(customer_id: str, exclude_deal_id: str) -> str:
    deals = [d for d in store.deals_for_customer(customer_id)
             if d["deal_id"] != exclude_deal_id]
    if not deals:
        return "no other deals on record for this customer"
    won = sum(1 for d in deals if d.get("order_rank") in config.WON_RANKS)
    lost = sum(1 for d in deals if d.get("order_rank") in config.DEAD_RANKS)
    open_ = sum(1 for d in deals if config.is_open_rank(d.get("order_rank")))
    return f"{len(deals)} prior deal(s) — {won} won, {lost} lost, {open_} open"


def build_commentary_context(note: str, deal_id: str | None = None,
                             today: date | None = None) -> tuple[str, dict]:
    """Return (context_text, meta). `meta` carries has_customer_context and the
    resolved customer/deal for the UI. context_text is the grounded package fed
    to the model (English labels; values verbatim from records)."""
    today = today or config.today()

    deal = store.get_deal(deal_id) if deal_id else None
    customer = None
    if deal is None:
        customer = match_customer_in_note(note)
        if customer:
            deal = _pick_deal(customer["customer_id"])
    if deal is not None and customer is None:
        customer = store.get_customer(deal["customer_id"])

    meta = {
        "has_customer_context": bool(deal),
        "customer": customer.get("name") if customer else None,
        "deal_id": deal["deal_id"] if deal else None,
    }

    if deal is None:
        return (
            "NO MATCHING CUSTOMER OR DEAL FOUND IN RECORDS.\n"
            "The note could not be linked to a known customer. Base the read on "
            "the note text and the coach findings only. Do NOT invent any "
            "customer facts, history, numbers, or deal status.",
            meta,
        )

    acts = store.activities_for_deal(deal["deal_id"])
    res = score_deal(deal, acts, today=today)
    flags = deal_flags(deal, acts, res.band, today=today)
    last_act = acts[0].get("activity_date") if acts else None
    inactive = _days_since(last_act, today)
    rank_since = _days_since(deal.get("rank_updated_at"), today)
    quote = store.quote_for_deal(deal["deal_id"])
    orders = store.orders_for_deal(deal["deal_id"])

    lines: list[str] = []
    cn = customer.get("name", deal["customer_id"]) if customer else deal["customer_id"]
    ind = customer.get("industry", "?") if customer else "?"
    size = customer.get("size", "?") if customer else "?"
    lines.append(f"CUSTOMER: {cn} (industry: {ind}, size: {size})")
    lines.append(
        f"DEAL {deal['deal_id']}: {deal.get('deal_name', '-')} | "
        f"category {deal.get('product_category', '-')} | "
        f"rank {deal.get('order_rank', '-')} | "
        f"amount {_yen(deal.get('total_order_amount', 0))} | "
        f"expected order {deal.get('expected_order_date', '-')}"
    )
    if rank_since is not None:
        lines.append(f"RANK AGE: at rank {deal.get('order_rank','-')} for {rank_since} days")
    reasons = res.top_reasons(3)
    lines.append(
        f"DEAL HEALTH: {res.band} (risk {res.score}/100)"
        + (f" — signals: {'; '.join(reasons)}" if reasons else "")
    )
    if flags:
        lines.append("RELIABILITY FLAGS: " + "; ".join(f.message for f in flags))
    if inactive is not None:
        lines.append(f"INACTIVITY: last activity {last_act} ({inactive} days ago)")
    else:
        lines.append("INACTIVITY: no recorded activity")
    if quote:
        disc = quote.get("discount_rate")
        lines.append("QUOTE: on record"
                     + (f" (discount {disc}%)" if disc else ""))
    else:
        lines.append("QUOTE: none on record")
    lines.append(f"ORDERS: {len(orders)} line(s) on record" if orders
                 else "ORDERS: none on record")
    lines.append("CUSTOMER HISTORY: "
                 + _customer_history(deal["customer_id"], deal["deal_id"]))

    recent = acts[:3]
    if recent:
        lines.append("RECENT ACTIVITY:")
        for a in recent:
            snippet = (a.get("daily_report") or "").strip().replace("\n", " ")
            if len(snippet) > 90:
                snippet = snippet[:90] + "…"
            lines.append(f"  - {a.get('activity_date','?')} "
                         f"[{a.get('activity_type','-')}] {snippet}")

    similar = find_similar_cases(note, deal=deal, max_n=1, today=today)
    if similar:
        s = similar[0]
        lines.append(
            f"SIMILAR PAST CASE: {s['customer']} ({s['product_category']}) "
            f"— {s['outcome']}; teaches principle(s) {', '.join(s['principle_ids'])}"
        )

    return "\n".join(lines), meta
