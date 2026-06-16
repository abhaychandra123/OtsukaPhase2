"""Deterministic deal-health scoring — the trustworthy core.

Pure Python, stage-aware, fully explainable. Produces a 0–100 *risk* score
(higher = worse) as the sum of independent signal contributions, plus a
red/yellow/green band. Every signal carries a human-readable Japanese `reason`,
so nothing is a black box and no number is ever invented by a model.

All thresholds live in senpai.config (STAGE_BENCHMARKS, STALL_LEXICON, band
cutoffs) so the rules stay auditable in one place.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from senpai import config


@dataclass
class Signal:
    name: str
    points: int
    reason: str   # Japanese, manager-facing


@dataclass
class HealthResult:
    score: int
    band: str                       # 'red' | 'yellow' | 'green'
    signals: list[Signal] = field(default_factory=list)

    def top_reasons(self, n: int = 3) -> list[str]:
        ordered = sorted(self.signals, key=lambda s: s.points, reverse=True)
        return [s.reason for s in ordered[:n]]


def _d(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _current_stage_entered(deal: dict) -> date | None:
    """The date the deal entered its *current* stage."""
    stage = deal.get("stage")
    for h in reversed(deal.get("stage_history", [])):
        if h.get("stage") == stage:
            return _d(h.get("entered_date"))
    return None


def score_deal(deal: dict, notes: list[dict] | None = None,
               today: date | None = None) -> HealthResult:
    """Score one deal. `notes` should be that deal's notes (newest first); if
    omitted, note-based signals are simply skipped."""
    today = today or config.today()
    notes = notes or []
    stage = deal.get("stage", "lead")
    max_days, cadence = config.STAGE_BENCHMARKS.get(stage, (30, 14))
    signals: list[Signal] = []

    # 1. Staleness — days since last contact vs the stage's expected cadence.
    last = _d(deal.get("last_contact_date"))
    if last is not None:
        stale = (today - last).days
        if stale > 2 * cadence:
            signals.append(Signal("staleness", 30,
                                  f"{stale}日間連絡なし(目安{cadence}日の2倍超)"))
        elif stale > cadence:
            signals.append(Signal("staleness", 15,
                                  f"{stale}日間連絡なし(目安{cadence}日超)"))

    # 2. Stage age — days in the current stage beyond the benchmark (scaled).
    entered = _current_stage_entered(deal)
    if entered is not None:
        in_stage = (today - entered).days
        if in_stage > max_days:
            pts = min(25, round((in_stage - max_days) / max_days * 25))
            if pts > 0:
                signals.append(Signal("stage_age", pts,
                                      f"{stage}段階に{in_stage}日滞留(目安{max_days}日)"))

    # 3. Close date already past while still open.
    expected = _d(deal.get("expected_close_date"))
    if expected is not None and expected < today and deal.get("status") == "open":
        signals.append(Signal("close_date_past", 25,
                              f"完了予定日({expected.isoformat()})を過ぎても未完了"))

    # 4. Close-date slips — each prior slip in the history.
    slips = max(0, len(deal.get("close_date_history", [])) - 1)
    if slips:
        pts = min(20, slips * 10)
        signals.append(Signal("close_date_slips", pts,
                              f"完了予定日が{slips}回後ろ倒し"))

    # 5. Missing decision-maker at proposal stage or later.
    if stage in config.DECISION_MAKER_STAGES and not deal.get("decision_maker_identified"):
        signals.append(Signal("missing_dm", 15, "決裁者が未特定"))

    # 6. Stall language in the latest note.
    if notes:
        latest_text = notes[0].get("text", "")
        hit = next((w for w in config.STALL_LEXICON if w in latest_text), None)
        if hit:
            signals.append(Signal("stall_language", 10,
                                  f"直近メモに停滞サイン「{hit}」"))

    # 7. Low activity — fewer than one touch in the last 30 days.
    recent = [n for n in notes if (d := _d(n.get("date"))) and (today - d).days <= 30]
    if not recent:
        signals.append(Signal("low_activity", 10, "直近30日の接触が0件"))

    score = min(100, sum(s.points for s in signals))
    return HealthResult(score=score, band=config.band_for_score(score), signals=signals)
