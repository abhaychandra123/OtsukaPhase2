"""Strategic Tier + Regional stance — deterministic pre-query selection.

Before the model writes any account commentary, this module picks a *coaching
stance* from two hard facts on record:

  * the account's largest open-deal amount  → a Strategic Tier (mega / standard / volume)
  * the customer's region                    → a Regional modifier (関東 / 関西 / その他)

It returns both the **directives** that get injected into the prompt (so the
model narrates within the right posture) AND a transparent **rationale** that is
surfaced back to the salesperson — so they can see exactly *which* threshold and
*which* region produced the advice, and override it with their own judgement.

This is NOT a factual claim about the customer. Like account.summary's
`_recommended_focus`, the directives are authored heuristics; the only data they
rest on is the deal amount and the region field, both quoted verbatim in the
rationale. No LLM, no randomness.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

# --- tier thresholds (single tuning surface) --------------------------------
# Driven by the account's LARGEST open-deal amount (the biggest opportunity in
# play sets the posture for the whole relationship).
#
# Calibrated to Otsuka Shokai's SMB reality: this is an IT reseller whose deals
# run ¥200K–¥3M, not enterprise ¥100M megaprojects. Thresholds sit near the data's
# p95 / p60 so all three tiers occur naturally (≈5% mega / ≈35% standard / ≈60%
# volume). "Mega" here means "large for this book", not absolute enterprise scale.
TIER1_MIN_YEN = 1_500_000     # >= ¥1.5M  → mega-deal (top ~5%), high-touch advisory
TIER3_MAX_YEN = 300_000       # <  ¥300K  → volume deal, high-velocity close

TIER_MEGA = "tier1_mega"
TIER_STANDARD = "tier2_standard"
TIER_VOLUME = "tier3_volume"

_TIER_LABEL = {
    TIER_MEGA:     {"ja": "Tier 1・メガ案件", "en": "Tier 1 — Mega-Deal"},
    TIER_STANDARD: {"ja": "Tier 2・標準案件", "en": "Tier 2 — Standard"},
    TIER_VOLUME:   {"ja": "Tier 3・ボリューム案件", "en": "Tier 3 — Volume"},
}

# Authored stance directives per tier (JA — injected into the JA prompt; the EN
# prompt gets the EN list). Each is a posture cue, never a fact.
_TIER_DIRECTIVES: dict[str, dict[str, list[str]]] = {
    TIER_MEGA: {
        "ja": [
            "高単価のため、即決ではなく助言型（advisory）の姿勢で臨む。",
            "決裁前に関係者への根回し（nemawashi）を丁寧に行う。",
            "多層的な稟議（ringi）を見据え、各承認段階の論点を先回りして準備する。",
            "必要に応じて自社マネジメントを同席させ、組織対組織の信頼を築く。",
        ],
        "en": [
            "High contract value — take an advisory stance, not a quick close.",
            "Invest in nemawashi (pre-consensus) with stakeholders before the decision.",
            "Prepare for a multi-layered ringi: anticipate each approval layer's concerns.",
            "Bring in your own management where it builds org-to-org trust.",
        ],
    },
    TIER_STANDARD: {
        "ja": [
            "標準的なコンサルティング営業の姿勢でバランスよく進める。",
            "課題ヒアリングと費用対効果の提示を両立させる。",
            "通常の承認プロセスに沿って着実に前進させる。",
        ],
        "en": [
            "Run a balanced consultative-sales motion.",
            "Pair needs discovery with a clear cost/benefit case.",
            "Move steadily along the standard approval path.",
        ],
    },
    TIER_VOLUME: {
        "ja": [
            "低単価のため、高速クロージングを優先しタッチポイントを絞る。",
            "ROI（投資対効果）を前面に出した端的な提案で意思決定を加速する。",
            "過剰な根回しは避け、決裁者へ最短ルートで到達する。",
        ],
        "en": [
            "Lower value — prioritise a high-velocity close; minimise touch-points.",
            "Lead with a crisp ROI-based pitch to accelerate the decision.",
            "Avoid over-investing in nemawashi; reach the decision-maker by the shortest route.",
        ],
    },
}

# --- regional modifiers -----------------------------------------------------
REGION_KANTO = "関東"
REGION_KANSAI = "関西"
REGION_OTHER = "その他"
REGIONS = (REGION_KANTO, REGION_KANSAI, REGION_OTHER)

_REGION_LABEL = {
    REGION_KANTO:  {"ja": "関東", "en": "Kanto"},
    REGION_KANSAI: {"ja": "関西", "en": "Kansai"},
    REGION_OTHER:  {"ja": "その他地域", "en": "Other region"},
}

_REGION_DIRECTIVES: dict[str, dict[str, str]] = {
    REGION_KANTO: {
        "ja": "関東のため、形式・手順・組織の序列を重んじる丁寧な進め方を意識する。",
        "en": "Kanto market — respect formality, process, and organisational hierarchy.",
    },
    REGION_KANSAI: {
        "ja": "関西のため、率直で商人気質に合った、価値と価格に正直なアプローチを取る。",
        "en": "Kansai market — be direct and merchant-minded; be frank about value and price.",
    },
    REGION_OTHER: {
        "ja": "地域特性は中立。標準的な進め方で問題ない。",
        "en": "Region neutral — a standard approach is fine.",
    },
}


def select_tier(amount: int | float | None) -> str:
    """Pick a Strategic Tier from a yen amount (the account's largest open deal)."""
    a = amount or 0
    if a >= TIER1_MIN_YEN:
        return TIER_MEGA
    if a < TIER3_MAX_YEN:
        return TIER_VOLUME
    return TIER_STANDARD


def normalize_region(region: str | None) -> str:
    return region if region in REGIONS else REGION_OTHER


def _yen(n) -> str:
    try:
        return f"¥{int(n):,}"
    except (ValueError, TypeError):
        return "¥0"


@dataclass
class StrategicContext:
    tier_id: str
    tier_label_ja: str
    tier_label_en: str
    region: str
    region_label_ja: str
    region_label_en: str
    driver_amount: int            # the open-deal amount that set the tier
    directives_ja: list[str] = field(default_factory=list)
    directives_en: list[str] = field(default_factory=list)
    rationale_ja: str = ""        # transparent "why this stance" — for the rep
    rationale_en: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def as_prompt_block(self, lang: str = "ja") -> str:
        """The STRATEGIC STANCE block injected into the commentary prompt."""
        # Defensive: a hand-corrupted region must not KeyError — fall back to neutral.
        reg_dir = _REGION_DIRECTIVES.get(self.region, _REGION_DIRECTIVES[REGION_OTHER])
        if lang == "en":
            head = (f"STRATEGIC STANCE (deterministic, from deal size + region): "
                    f"{self.tier_label_en} · {self.region_label_en}")
            why = f"  why: {self.rationale_en}"
            lines = [f"  - {d}" for d in self.directives_en + [reg_dir["en"]]]
        else:
            head = (f"戦略スタンス（案件規模・地域から自動判定）: "
                    f"{self.tier_label_ja} · {self.region_label_ja}")
            why = f"  判定理由: {self.rationale_ja}"
            lines = [f"  - {d}" for d in self.directives_ja + [reg_dir["ja"]]]
        return "\n".join([head, why] + lines)


def strategic_context(amount: int | float | None,
                      region: str | None) -> StrategicContext:
    """Deterministic stance selection. `amount` is the account's largest open-deal
    value; `region` is the customer's region field."""
    tier = select_tier(amount)
    reg = normalize_region(region)
    amt = int(amount or 0)

    reg_ja = _REGION_LABEL[reg]["ja"]
    reg_en = _REGION_LABEL[reg]["en"]
    t1 = _yen(TIER1_MIN_YEN)
    t3 = _yen(TIER3_MAX_YEN)
    if tier == TIER_MEGA:
        rationale_ja = (f"最大の進行中案件が{_yen(amt)}（{t1}以上）のため"
                        f"メガ案件と判定。地域: {reg_ja}。")
        rationale_en = (f"Largest open deal is {_yen(amt)} (≥{t1}), "
                        f"so this is a mega-deal. Region: {reg_en}.")
    elif tier == TIER_VOLUME:
        rationale_ja = (f"最大の進行中案件が{_yen(amt)}（{t3}未満）のため"
                        f"ボリューム案件と判定。地域: {reg_ja}。")
        rationale_en = (f"Largest open deal is {_yen(amt)} (<{t3}), "
                        f"so this is a volume deal. Region: {reg_en}.")
    else:
        rationale_ja = (f"最大の進行中案件が{_yen(amt)}（{t3}〜{t1}）のため"
                        f"標準案件と判定。地域: {reg_ja}。")
        rationale_en = (f"Largest open deal is {_yen(amt)} ({t3}–{t1}), "
                        f"so this is a standard deal. Region: {reg_en}.")

    return StrategicContext(
        tier_id=tier,
        tier_label_ja=_TIER_LABEL[tier]["ja"],
        tier_label_en=_TIER_LABEL[tier]["en"],
        region=reg,
        region_label_ja=_REGION_LABEL[reg]["ja"],
        region_label_en=_REGION_LABEL[reg]["en"],
        driver_amount=amt,
        directives_ja=list(_TIER_DIRECTIVES[tier]["ja"]),
        directives_en=list(_TIER_DIRECTIVES[tier]["en"]),
        rationale_ja=rationale_ja,
        rationale_en=rationale_en,
    )
