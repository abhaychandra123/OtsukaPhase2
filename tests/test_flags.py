"""Unit tests for report-reliability flags (no GPU, no model)."""
from __future__ import annotations

from datetime import timedelta

from senpai import config
from senpai.health.flags import deal_flags

TODAY = config.today()


def _iso(days_ago: int) -> str:
    return (TODAY - timedelta(days=days_ago)).isoformat()


def _clean_deal(**over):
    """A deal with NO flags firing by default."""
    base = {
        "deal_id": "D999",
        "stage": "proposal",
        "stage_history": [{"stage": "proposal", "entered_date": _iso(5)}],
        "expected_close_date": _iso(-20),
        "close_date_history": [_iso(-20)],
        "last_contact_date": _iso(3),
        "decision_maker_identified": True,
        "rep_close_likelihood": "med",
        "status": "open",
        "amount": 500000,
    }
    base.update(over)
    return base


def _names(flags):
    return {f.name for f in flags}


def test_clean_deal_has_no_flags():
    deal = _clean_deal()
    notes = [{"date": _iso(5), "text": "提案提出"}]
    report = {"next_action": "次回訪問でクロージング", "close_likelihood": "med"}
    assert deal_flags(deal, notes, report, health_band="green", today=TODAY) == []


def test_close_date_passed_fires():
    deal = _clean_deal(expected_close_date=_iso(5))
    flags = deal_flags(deal, [{"date": _iso(5), "text": "x"}], today=TODAY)
    assert "close_date_passed" in _names(flags)


def test_stale_active_fires():
    deal = _clean_deal(last_contact_date=_iso(45))
    flags = deal_flags(deal, [{"date": _iso(45), "text": "x"}], today=TODAY)
    assert "stale_active" in _names(flags)


def test_missing_fields_fires():
    deal = _clean_deal(decision_maker_identified=False, amount=0)
    report = {"next_action": "", "close_likelihood": "med"}
    flags = deal_flags(deal, [{"date": _iso(5), "text": "x"}], report, today=TODAY)
    assert "missing_fields" in _names(flags)


def test_optimism_mismatch_fires():
    deal = _clean_deal()
    report = {"next_action": "x", "close_likelihood": "high"}
    flags = deal_flags(deal, [{"date": _iso(5), "text": "x"}], report,
                       health_band="red", today=TODAY)
    assert "optimism_mismatch" in _names(flags)


def test_optimism_mismatch_silent_when_band_green():
    deal = _clean_deal()
    report = {"next_action": "x", "close_likelihood": "high"}
    flags = deal_flags(deal, [{"date": _iso(5), "text": "x"}], report,
                       health_band="green", today=TODAY)
    assert "optimism_mismatch" not in _names(flags)


def test_unsupported_stage_fires_without_supporting_note():
    deal = _clean_deal(stage_history=[{"stage": "proposal", "entered_date": _iso(40)}])
    flags = deal_flags(deal, [{"date": _iso(3), "text": "x"}], today=TODAY)
    assert "unsupported_stage" in _names(flags)


def test_unsupported_stage_silent_with_supporting_note():
    deal = _clean_deal(stage_history=[{"stage": "proposal", "entered_date": _iso(10)}])
    flags = deal_flags(deal, [{"date": _iso(10), "text": "提案提出"}], today=TODAY)
    assert "unsupported_stage" not in _names(flags)
