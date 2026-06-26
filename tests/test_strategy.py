"""Tests for the Strategic Tier + Regional stance engine.

Hermetic: pure functions + the committed seed, no model/network. The engine is
deterministic, so tier boundaries and the round-trip through AccountSummary are
exactly assertable.
"""
from __future__ import annotations

from senpai.account import build_account_summary
from senpai.account.strategy import (
    StrategicContext,
    TIER1_MIN_YEN,
    TIER3_MAX_YEN,
    TIER_MEGA,
    TIER_STANDARD,
    TIER_VOLUME,
    REGION_OTHER,
    select_tier,
    strategic_context,
    normalize_region,
)


def test_tier_boundaries_are_inclusive_lower():
    # >= TIER1_MIN_YEN is mega; the boundary itself counts as mega.
    assert select_tier(TIER1_MIN_YEN) == TIER_MEGA
    assert select_tier(TIER1_MIN_YEN + 1) == TIER_MEGA
    assert select_tier(TIER1_MIN_YEN - 1) == TIER_STANDARD
    # < TIER3_MAX_YEN is volume; the boundary itself is standard.
    assert select_tier(TIER3_MAX_YEN) == TIER_STANDARD
    assert select_tier(TIER3_MAX_YEN - 1) == TIER_VOLUME
    assert select_tier(0) == TIER_VOLUME
    assert select_tier(None) == TIER_VOLUME


def test_unknown_region_normalizes_to_other():
    assert normalize_region("関東") == "関東"
    assert normalize_region("Mars") == REGION_OTHER
    assert normalize_region(None) == REGION_OTHER


def test_rationale_quotes_the_driver_amount_and_region():
    sc = strategic_context(TIER1_MIN_YEN + 500_000, "関西")
    assert sc.tier_id == TIER_MEGA
    assert sc.region == "関西"
    # The rationale is the transparency surface: it must name the amount + region.
    assert "関西" in sc.rationale_ja
    assert f"{sc.driver_amount:,}" in sc.rationale_ja
    assert "Kansai" in sc.rationale_en


def test_prompt_block_carries_directives_and_why():
    sc = strategic_context(0, "関東")  # volume / Kanto
    block = sc.as_prompt_block(lang="ja")
    assert "戦略スタンス" in block
    assert "判定理由" in block        # the why line
    assert sc.directives_ja[0] in block
    block_en = sc.as_prompt_block(lang="en")
    assert "STRATEGIC STANCE" in block_en
    assert "why:" in block_en


def test_strategic_context_roundtrips_through_dict():
    sc = strategic_context(TIER3_MAX_YEN + 1, "関東")  # standard
    assert sc.tier_id == TIER_STANDARD
    rebuilt = StrategicContext(**sc.to_dict())
    assert rebuilt.tier_id == sc.tier_id
    assert rebuilt.as_prompt_block("en") == sc.as_prompt_block("en")


def test_account_summary_carries_region_and_strategy():
    # Every real account gets a region and a fully-populated strategy block.
    s = build_account_summary("C01")
    assert s is not None
    assert s.region in ("関東", "関西", "その他")
    assert s.strategy["tier_id"] in (TIER_MEGA, TIER_STANDARD, TIER_VOLUME)
    assert s.strategy["region_label_ja"]
    assert s.strategy["rationale_ja"]
    # to_dict must stay JSON-serialisable for the API.
    import json
    json.dumps(s.to_dict(), ensure_ascii=False)


def test_all_three_tiers_occur_in_the_seed():
    # Calibrated thresholds must yield a real spread (not everything Tier 3),
    # otherwise the feature is invisible in the product.
    from senpai.data import store
    tiers = {build_account_summary(c["customer_id"]).strategy["tier_id"]
             for c in store.all_customers()}
    assert {TIER_MEGA, TIER_STANDARD, TIER_VOLUME} <= tiers
