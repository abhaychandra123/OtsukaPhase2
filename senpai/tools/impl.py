"""Tool implementations + dispatch — mirrors demo/tools.py's contract.

Every executor returns a SHORT string (what the model sees as the tool result)
and `dispatch` never raises, so the chat loop can't crash. All data comes from
the deterministic store / scoring engine, so these run GPU-free.

`python -m senpai.tools.impl` runs a canned call per tool (smoke test).
"""
from __future__ import annotations

import json

from senpai import config
from senpai.data import store
from senpai.health.flags import deal_flags
from senpai.health.scoring import score_deal
from senpai.retrieval.playbook import find_similar_deals, retrieve_playbook


def _resolve_customer(customer: str) -> dict | None:
    if not customer:
        return None
    return store.get_customer(customer) or store.find_customer_by_name(customer)


def _deal_line(d: dict) -> str:
    cust = store.customer_name(d["customer_id"])
    return (f"{d['deal_id']} {cust} / 担当{store.rep_name(d['rep_id'])} / "
            f"{d['stage']} / ¥{d['amount']:,} / 状態{d['status']} / "
            f"完了予定{d['expected_close_date']}")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
def query_spr(customer: str = "", rep_id: str = "", deal_id: str = "") -> str:
    if deal_id:
        d = store.get_deal(deal_id)
        if not d:
            return f"案件 {deal_id} は見つかりません。"
        notes = store.notes_for_deal(deal_id)
        head = _deal_line(d)
        note_lines = [f"  ・{n['date']} [{n['channel']}] {n['text']}" for n in notes[:3]]
        return head + ("\n直近メモ:\n" + "\n".join(note_lines) if note_lines else "")

    if customer:
        c = _resolve_customer(customer)
        if not c:
            return f"顧客「{customer}」は見つかりません。"
        deals = store.deals_for_customer(c["customer_id"])
        if not deals:
            return f"{c['name']} の案件はありません。"
        lines = [_deal_line(d) for d in deals]
        return f"{c['name']} の案件 {len(deals)}件:\n- " + "\n- ".join(lines)

    if rep_id:
        deals = store.deals_for_rep(rep_id)
        if not deals:
            return f"担当 {rep_id} の案件はありません。"
        lines = [_deal_line(d) for d in deals]
        return f"{store.rep_name(rep_id)} の案件 {len(deals)}件:\n- " + "\n- ".join(lines)

    return "customer / rep_id / deal_id のいずれかを指定してください。"


def find_similar_deals_tool(customer: str = "", industry: str = "") -> str:
    cid = ""
    if customer:
        c = _resolve_customer(customer)
        if c:
            cid = c["customer_id"]
    hits = find_similar_deals(customer_id=cid, industry=industry)
    if not hits:
        return "類似案件は見つかりませんでした。"
    lines = [_deal_line(d) for d in hits]
    return "類似案件:\n- " + "\n- ".join(lines)


def retrieve_playbook_tool(query: str = "", tags=None) -> str:
    if isinstance(tags, str):
        tags = [tags]
    hits = retrieve_playbook(query=query, tags=tags or [])
    if not hits:
        return "該当するプレイブックがありません。route_to_expert の利用を検討してください。"
    lines = []
    for e in hits:
        author = store.rep_name(e["author_rep_id"])
        lines.append(f"[{'/'.join(e['situation_tags'])}] {e['text']}(提供: {author})")
    return "プレイブック:\n- " + "\n- ".join(lines)


def lookup_customer_environment(customer: str = "") -> str:
    c = _resolve_customer(customer)
    if not c:
        return f"顧客「{customer}」は見つかりません。"
    env = store.get_environment(c["customer_id"])
    if not env:
        return f"{c['name']} の環境情報は未登録です。"
    return (f"{c['name']} の環境: PC={env['pc']} / OS={env['os']} / "
            f"ネットワーク={env['network']} / 備考: {env['notes']}")


def get_product_info(product: str = "") -> str:
    p = store.get_product(product.upper()) if product else None
    if not p:
        p = next((x for x in store.all_products()
                  if product and (product in x["name"] or product in x["name_ja"])), None)
    if not p:
        names = ", ".join(x["name_ja"] for x in store.all_products())
        return f"製品「{product}」は見つかりません。取扱: {names}"
    return (f"{p['name_ja']} ({p['sku']}) — ¥{p['price']:,}\n"
            f"仕様: {p['specs']}\nマニュアル抜粋: {p['manual_ja']}")


def score_deal_health(deal_id: str = "") -> str:
    d = store.get_deal(deal_id)
    if not d:
        return f"案件 {deal_id} は見つかりません。"
    notes = store.notes_for_deal(deal_id)
    res = score_deal(d, notes)
    emoji = {"red": "🔴", "yellow": "🟡", "green": "🟢"}[res.band]
    reasons = res.top_reasons(3)
    body = "／".join(reasons) if reasons else "目立ったリスク信号なし"
    return f"{emoji} {res.band}(リスク{res.score}/100): {body}"


def draft_daily_report(activity: str = "", deal_id: str = "") -> str:
    deal = store.get_deal(deal_id) if deal_id else None
    cust = store.customer_name(deal["customer_id"]) if deal else "(顧客未指定)"
    stage = deal["stage"] if deal else "-"
    next_action = "次回アクションを記入してください"
    if deal:
        res = score_deal(deal, store.notes_for_deal(deal_id))
        if res.band == "red":
            next_action = "健全度が赤。上長同席での再提案を打診"
    return ("【日報ドラフト】\n"
            f"顧客: {cust}\n"
            f"案件: {deal_id or '-'} / 段階: {stage}\n"
            f"活動内容: {activity}\n"
            f"次アクション: {next_action}")


def route_to_expert(question: str = "", tags=None) -> str:
    if isinstance(tags, str):
        tags = [tags]
    tags = tags or []
    experts = [r for r in store.all_reps() if r["role"] in ("senior", "expert")]
    best, best_score = None, -1
    for r in experts:
        score = sum(1 for t in tags
                    if any(t in s or s in t for s in r["specialty_tags"]))
        score += sum(1 for s in r["specialty_tags"] if question and s in question)
        if r["is_top_performer"]:
            score += 0.5
        if score > best_score:
            best, best_score = r, score
    if not best:
        return "適切な担当が見つかりませんでした。"
    return (f"エキスパート紹介: {best['name']}({'/'.join(best['specialty_tags'])})\n"
            f"紹介メッセージ案: 「{best['name']}さん、{question} の件でご相談です。"
            "お手すきの際にご助言いただけますか。」")


def summarize_reports(rep_id: str = "") -> str:
    reports = store.reports_for_rep(rep_id)
    if not reports:
        return f"担当 {rep_id} のレポートはありません。"
    lines = [f"{store.rep_name(rep_id)} のレポート {len(reports)}件の要約:"]
    flagged = 0
    for rp in reports:
        d = store.get_deal(rp["deal_id"])
        if not d:
            continue
        notes = store.notes_for_deal(d["deal_id"])
        band = score_deal(d, notes).band
        flags = deal_flags(d, notes, rp, band)
        if flags:
            flagged += 1
            msgs = "／".join(f.message for f in flags[:2])
            lines.append(f"⚠ {d['deal_id']} {store.customer_name(d['customer_id'])}: {msgs}")
    lines.append(f"信頼性フラグの立った案件: {flagged}件")
    return "\n".join(lines)


_FY_CONTEXT = {
    "q4": "1〜3月は年度末。予算消化の最後の好機。クロージングを強く。",
    "q1": "4〜6月は新年度。新規予算が付く時期。早期の種まきを。",
    "q2": "7〜9月は中間期。下期予算の検討が始まる。提案の仕込みを。",
    "q3": "10〜12月は下期序盤。年度末に向け案件を積み上げる時期。",
}


def get_seasonal_context(month: int = 0) -> str:
    m = int(month) if month else config.today().month
    if m in (1, 2, 3):
        key, label = "q4", "第4四半期(年度末)"
    elif m in (4, 5, 6):
        key, label = "q1", "第1四半期"
    elif m in (7, 8, 9):
        key, label = "q2", "第2四半期"
    else:
        key, label = "q3", "第3四半期"
    return f"{m}月 — {label}: {_FY_CONTEXT[key]}"


# ---------------------------------------------------------------------------
# Dispatch (mirrors demo/tools.py)
# ---------------------------------------------------------------------------
_DISPATCH = {
    "query_spr": query_spr,
    "find_similar_deals": find_similar_deals_tool,
    "retrieve_playbook": retrieve_playbook_tool,
    "lookup_customer_environment": lookup_customer_environment,
    "get_product_info": get_product_info,
    "score_deal_health": score_deal_health,
    "draft_daily_report": draft_daily_report,
    "route_to_expert": route_to_expert,
    "summarize_reports": summarize_reports,
    "get_seasonal_context": get_seasonal_context,
}


def dispatch(name: str, arguments: dict | str) -> str:
    """Execute a tool by name with arguments (dict or JSON string). Always
    returns a string; never raises (so the chat loop can't crash)."""
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments or "{}")
        except json.JSONDecodeError:
            return f"[error] could not parse arguments for {name}: {arguments!r}"
    if not isinstance(arguments, dict):
        arguments = {}
    fn = _DISPATCH.get(name)
    if fn is None:
        return f"[error] unknown tool: {name}"
    try:
        return str(fn(**arguments))
    except TypeError as e:
        return f"[error] bad arguments for {name}: {e}"
    except Exception as e:  # noqa: BLE001 — must never crash on a tool
        return f"[error] {name} failed: {e}"


if __name__ == "__main__":
    # Pick a deliberately dead deal so score/flags show real risk.
    for n, a in [
        ("query_spr", {"deal_id": "D001"}),
        ("query_spr", {"rep_id": "R05"}),
        ("find_similar_deals", {"customer": "C01"}),
        ("retrieve_playbook", {"query": "お客様が決定を先延ばし", "tags": ["決定先延ばし"]}),
        ("lookup_customer_environment", {"customer": "C01"}),
        ("get_product_info", {"product": "MFP30"}),
        ("score_deal_health", {"deal_id": "D001"}),
        ("draft_daily_report", {"activity": "アクメ商事を訪問しデモを実施", "deal_id": "D001"}),
        ("route_to_expert", {"question": "ネットワーク更改の構成相談", "tags": ["ネットワーク"]}),
        ("summarize_reports", {"rep_id": "R05"}),
        ("get_seasonal_context", {"month": 2}),
    ]:
        print(f"\n### {n}({a})\n{dispatch(n, a)}")
