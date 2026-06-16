"""Unit tests for the deterministic deal-health scorer (no GPU, no model)."""
from __future__ import annotations

from datetime import timedelta

from senpai import config
from senpai.health.scoring import score_deal

TODAY = config.today()


def _iso(days_ago: int) -> str:
    return (TODAY - timedelta(days=days_ago)).isoformat()


def _deal(**over):
    base = {
        "deal_id": "D999",
        "stage": "proposal",
        "stage_history": [{"stage": "proposal", "entered_date": _iso(10)}],
        "expected_close_date": _iso(-20),     # 20 days in the future
        "close_date_history": [_iso(-20)],
        "last_contact_date": _iso(3),
        "decision_maker_identified": True,
        "rep_close_likelihood": "med",
        "status": "open",
        "amount": 500000,
    }
    base.update(over)
    return base


def test_healthy_deal_is_green():
    deal = _deal()
    notes = [{"date": _iso(3), "text": "デモを実施。前向き。"}]
    res = score_deal(deal, notes, today=TODAY)
    assert res.band == "green"
    assert res.score < config.YELLOW_THRESHOLD


def test_dead_deal_is_red():
    """Stale + slipped twice + close date passed + no DM + stall language."""
    deal = _deal(
        stage="negotiation",
        stage_history=[{"stage": "negotiation", "entered_date": _iso(90)}],
        expected_close_date=_iso(25),                    # already past
        close_date_history=[_iso(55), _iso(40), _iso(25)],
        last_contact_date=_iso(45),
        decision_maker_identified=False,
        rep_close_likelihood="high",
    )
    notes = [{"date": _iso(45), "text": "担当者より「検討します」との返答。"}]
    res = score_deal(deal, notes, today=TODAY)
    assert res.band == "red"
    assert res.score >= config.RED_THRESHOLD
    fired = {s.name for s in res.signals}
    assert {"staleness", "close_date_past", "close_date_slips",
            "missing_dm", "stall_language", "low_activity"} <= fired


def test_close_date_past_signal_fires():
    deal = _deal(expected_close_date=_iso(5))             # 5 days ago
    res = score_deal(deal, [{"date": _iso(3), "text": "電話でフォロー。"}], today=TODAY)
    assert any(s.name == "close_date_past" for s in res.signals)


def test_slips_are_capped():
    deal = _deal(close_date_history=[_iso(60), _iso(50), _iso(40), _iso(30), _iso(20)])
    res = score_deal(deal, [{"date": _iso(2), "text": "x"}], today=TODAY)
    slip = next(s for s in res.signals if s.name == "close_date_slips")
    assert slip.points == 20      # capped, even with 4 slips


def test_missing_dm_only_in_late_stage():
    early = _deal(stage="lead",
                  stage_history=[{"stage": "lead", "entered_date": _iso(3)}],
                  decision_maker_identified=False)
    res = score_deal(early, [{"date": _iso(2), "text": "x"}], today=TODAY)
    assert not any(s.name == "missing_dm" for s in res.signals)


def test_every_signal_has_a_reason():
    deal = _deal(last_contact_date=_iso(60), decision_maker_identified=False,
                 expected_close_date=_iso(10))
    res = score_deal(deal, [], today=TODAY)
    assert res.signals
    assert all(s.reason for s in res.signals)
