"""Report-reliability flags — the 'is this deal real?' engine.

Each flag is an independent check that fires only when its specific condition is
met, returning a Flag with a severity and a Japanese message. These power the
manager dashboard's reliability panel and the `summarize_reports` tool: they
surface deals whose written status quietly contradicts their actual signals.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from senpai import config
from senpai.health.scoring import _d


@dataclass
class Flag:
    name: str
    severity: str    # 'high' | 'medium' | 'low'
    message: str     # Japanese, manager-facing


def deal_flags(deal: dict, notes: list[dict] | None = None,
               report: dict | None = None, health_band: str | None = None,
               today: date | None = None) -> list[Flag]:
    """Return all reliability flags that fire for a deal. `report` is the deal's
    latest daily report (for next-action / optimism checks); `health_band` is the
    band from scoring (for the optimism-mismatch check)."""
    today = today or config.today()
    notes = notes or []
    flags: list[Flag] = []
    is_open = deal.get("status") == "open"

    # close_date_passed — expected close in the past, deal still open.
    expected = _d(deal.get("expected_close_date"))
    if is_open and expected is not None and expected < today:
        flags.append(Flag("close_date_passed", "high",
                          f"完了予定日({expected.isoformat()})を過ぎても案件がオープン"))

    # stale_active — no contact > 30 days but still marked active.
    last = _d(deal.get("last_contact_date"))
    if is_open and last is not None and (today - last).days > 30:
        flags.append(Flag("stale_active", "high",
                          f"{(today - last).days}日連絡がないままアクティブ扱い"))

    # missing_fields — empty decision-maker / next-action / amount / close date.
    missing = []
    if not deal.get("decision_maker_identified"):
        missing.append("決裁者")
    if not deal.get("amount"):
        missing.append("金額")
    if not deal.get("expected_close_date"):
        missing.append("完了予定日")
    if report is not None and not report.get("next_action"):
        missing.append("次アクション")
    if missing:
        flags.append(Flag("missing_fields", "medium",
                          "必須項目が未入力: " + "・".join(missing)))

    # optimism_mismatch — rep says 'high' but health is red.
    likelihood = (report or {}).get("close_likelihood") or deal.get("rep_close_likelihood")
    if likelihood == "high" and health_band == "red":
        flags.append(Flag("optimism_mismatch", "high",
                          "担当の見込みは『高』だが健全度は赤"))

    # unsupported_stage — entered current stage with no note within ±3 days.
    stage = deal.get("stage")
    entered = None
    for h in reversed(deal.get("stage_history", [])):
        if h.get("stage") == stage:
            entered = _d(h.get("entered_date"))
            break
    if entered is not None:
        supported = any((nd := _d(n.get("date"))) and abs((nd - entered).days) <= 3
                        for n in notes)
        if not supported:
            flags.append(Flag("unsupported_stage", "low",
                              f"{stage}段階への移行を裏づけるメモがない"))

    return flags
