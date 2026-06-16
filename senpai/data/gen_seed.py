"""Deterministic generator for Senpai's seed data (the 'capture layer', faked).

Run `python -m senpai.data.gen_seed` to (re)write senpai/data/seed/*.json. Output
is byte-stable: a fixed random seed + a fixed REFERENCE_DATE (config) mean
regenerating on any day produces an identical diff. The JSON is committed so the
dashboard and tests run with zero setup.

Content is Japanese (the data) to match the real Otsuka context; field names stay
English. Volumes: ~8 reps, ~35 SMB customers, ~60 deals, ~25 playbook entries,
products, environments and daily reports. A handful of deals are deliberately
authored as dead/dying so the manager dashboard flags real risk on first load.
"""
from __future__ import annotations

import json
import random
from datetime import timedelta

from senpai import config

REF = config.REFERENCE_DATE


def _iso(days_ago: int):
    """A date `days_ago` days before the fixed reference date, as YYYY-MM-DD."""
    return (REF - timedelta(days=days_ago)).isoformat()


# ---------------------------------------------------------------------------
# Static building blocks
# ---------------------------------------------------------------------------

REPS = [
    {"rep_id": "R01", "name": "田中健太", "role": "senior",
     "specialty_tags": ["複合機", "提案", "クロージング"], "is_top_performer": True},
    {"rep_id": "R02", "name": "佐藤美咲", "role": "expert",
     "specialty_tags": ["ネットワーク", "セキュリティ"], "is_top_performer": True},
    {"rep_id": "R03", "name": "鈴木大輔", "role": "expert",
     "specialty_tags": ["サーバー", "クラウド"], "is_top_performer": False},
    {"rep_id": "R04", "name": "高橋由美", "role": "senior",
     "specialty_tags": ["ソフトウェア", "保守"], "is_top_performer": True},
    {"rep_id": "R05", "name": "伊藤翔", "role": "junior",
     "specialty_tags": ["複合機"], "is_top_performer": False},
    {"rep_id": "R06", "name": "渡辺さくら", "role": "junior",
     "specialty_tags": ["ソフトウェア"], "is_top_performer": False},
    {"rep_id": "R07", "name": "山本健一", "role": "junior",
     "specialty_tags": ["ネットワーク"], "is_top_performer": False},
    {"rep_id": "R08", "name": "中村優子", "role": "senior",
     "specialty_tags": ["クラウド", "提案"], "is_top_performer": False},
]

# Company name parts for SMB customers (mostly no web presence).
_PREFIX = ["株式会社", "有限会社", ""]
_STEM = ["山田", "あけぼの", "丸越", "大和", "みどり", "東和", "ヤマト", "富士", "明光",
         "サンライズ", "第一", "中央", "北斗", "光", "新栄", "村田", "小林", "石川",
         "ひかり", "あおぞら", "三幸", "ニュー", "誠和", "協和", "宝", "松田", "森本"]
_SUFFIX = ["商事", "製作所", "工業", "システム", "物産", "建設", "サービス", "印刷",
           "運輸", "電機", "クリニック", "事務所", "食品", "産業"]
_INDUSTRY = ["製造", "小売", "医療", "建設", "飲食", "物流", "教育", "不動産", "士業", "IT"]
_SIZE = ["小規模", "小規模", "小規模", "中規模"]  # weighted toward SMB

_STAGES = ["lead", "qualified", "proposal", "negotiation", "closing"]

# Products — ported from demo/tools.py _CATALOG, with JP names + a manual excerpt.
PRODUCTS = [
    {"sku": "MFP30", "name": "Color MFP 3000", "name_ja": "カラー複合機 3000",
     "category": "printer", "price": 240000, "specs": "A3カラー複合機 / 30ppm / 両面",
     "manual_ja": "初期設定はネットワーク経由で自動検出。トナーは型番TN-30を使用。"},
    {"sku": "MFP15", "name": "Mono MFP 1500", "name_ja": "モノクロ複合機 1500",
     "category": "printer", "price": 96000, "specs": "A4モノクロ複合機 / 25ppm",
     "manual_ja": "省スペース設置可。両面印刷はオプション。"},
    {"sku": "LP14", "name": "Laptop Pro 14", "name_ja": "ノートPro 14",
     "category": "laptop", "price": 168000, "specs": "14型 / Core i7 / 16GB / 512GB SSD",
     "manual_ja": "法人向けキッティング対応。3年保証オプションあり。"},
    {"sku": "SRV20", "name": "Rack Server R20", "name_ja": "ラックサーバー R20",
     "category": "server", "price": 520000, "specs": "1U / Xeon / 64GB / NVMe x2",
     "manual_ja": "RAID1構成を推奨。設置にはラックと空調の確認が必要。"},
    {"sku": "NSW24", "name": "Network Switch 24p", "name_ja": "ネットワークスイッチ 24p",
     "category": "networking", "price": 54000, "specs": "24ポート ギガビット / L2管理型",
     "manual_ja": "VLAN設定は管理画面から。PoEは非対応。"},
    {"sku": "OFFICE", "name": "Office Suite", "name_ja": "オフィススイート(年間/席)",
     "category": "software", "price": 13800, "specs": "文書/表計算/スライド + 1TB",
     "manual_ja": "ライセンスは即時発行。管理コンソールで一括割当可能。"},
    {"sku": "AV365", "name": "Endpoint Security", "name_ja": "エンドポイントセキュリティ(年間/席)",
     "category": "software", "price": 6800, "specs": "アンチウイルス + EDR / 1台",
     "manual_ja": "EDRログは90日保持。導入後の初回スキャンを推奨。"},
]

_NOTE_NORMAL = [
    "担当者と仕様を確認。前向きな反応。",
    "見積を提出。社内で検討するとのこと。",
    "デモを実施。現場の評判は上々。",
    "電話でフォロー。導入時期を相談。",
    "競合製品と比較中とのこと。差別化を説明。",
]
_NOTE_STALL = [
    "担当者より「検討します」との返答。具体的な時期は未定。",
    "「予算が」厳しいとのことで保留。",
    "「時期を見て」改めて相談したいとの回答。",
    "決裁は「上と相談」してから、と先送りに。",
]

PLAYBOOK_SITUATIONS = [
    (["決定先延ばし", "クロージング"], "先延ばしには『次の一歩』を具体化する。次回訪問日とその場で決める事項を明確に提案する。"),
    (["予算", "価格"], "予算が理由の停滞は、年度末(3月)の予算消化タイミングを狙って再提案するのが有効。"),
    (["決裁者未特定", "提案"], "決裁者が見えない案件は、現場担当に『最終決定はどなたと進めますか』と早めに確認する。"),
    (["競合", "差別化"], "競合比較では保守体制と導入後のサポートを前面に。価格だけの勝負を避ける。"),
    (["複合機", "提案"], "複合機はランニングコスト(トナー・保守)込みの総額で比較表を作ると刺さる。"),
    (["ネットワーク", "導入"], "ネットワーク更改は現地調査を先に。既存配線とVLAN要件を押さえてから提案する。"),
    (["セキュリティ", "提案"], "セキュリティは『万一の事故コスト』を数字で示すと決裁が通りやすい。"),
    (["サーバー", "導入"], "サーバー導入は設置環境(ラック・空調・電源)の確認を提案前に済ませる。"),
    (["クラウド", "移行"], "クラウド移行は段階移行案を用意し、初期の不安を下げる。"),
    (["新規開拓", "アプローチ"], "Web情報の乏しいSMBは、近隣の同業導入事例を切り口にすると話が早い。"),
    (["保守", "更新"], "保守更新は満了3ヶ月前に接触。切替の手間より継続の安心を訴求。"),
    (["値引き", "交渉"], "値引き要求には台数増やオプション追加とセットで条件を返す。"),
    (["導入後", "フォロー"], "納品後2週間以内にフォロー訪問を入れると追加案件につながりやすい。"),
    (["決裁先送り", "稟議"], "稟議が止まる時は、決裁者向けの1枚要約(費用対効果)を担当者に渡す。"),
    (["飲食", "提案"], "飲食業はピーク時間を避けて訪問。短時間で要点を伝える資料を用意。"),
    (["医療", "提案"], "医療機関は個人情報保護の観点を最優先に説明すると信頼を得やすい。"),
    (["建設", "提案"], "建設業は現場とのネットワーク・モバイル環境の課題から入ると刺さる。"),
    (["小売", "提案"], "小売はPOS連携と複数店舗の一括管理を切り口にする。"),
    (["紹介", "拡大"], "満足度の高い顧客には同業他社の紹介を依頼。紹介は決裁が早い。"),
    (["失注", "再アプローチ"], "失注案件も半年後に状況が変わることが多い。定期的に軽く接触を続ける。"),
    (["初回訪問", "準備"], "初回は売り込まない。課題ヒアリングに徹し、次回の宿題をもらう。"),
    (["決裁者同席", "クロージング"], "最終局面は上長同席を打診し、その場で意思決定を促す。"),
    (["リプレース", "提案"], "更新案件は現行機の不満点を起点に、改善を具体的に見せる。"),
    (["コスト削減", "提案"], "コスト削減提案は年間総額の比較表を1枚にまとめる。"),
    (["スピード", "対応"], "SMBは即レス・即対応そのものが差別化になる。"),
]


def _company_name(rnd):
    return f"{rnd.choice(_PREFIX)}{rnd.choice(_STEM)}{rnd.choice(_SUFFIX)}"


def generate():
    rnd = random.Random(42)

    # --- customers ---------------------------------------------------------
    customers = []
    seen = set()
    while len(customers) < 35:
        name = _company_name(rnd)
        if name in seen:
            continue
        seen.add(name)
        cid = f"C{len(customers) + 1:02d}"
        industry = rnd.choice(_INDUSTRY)
        customers.append({
            "customer_id": cid,
            "name": name,
            "industry": industry,
            "size": rnd.choice(_SIZE),
            # ~78% SMB → mostly no web presence
            "has_web_presence": rnd.random() < 0.25,
            "profile_tags": sorted({industry, rnd.choice(_SIZE),
                                    rnd.choice(["既存", "新規", "紹介"])}),
        })

    # --- environments (one per customer) -----------------------------------
    pcs = ["デスクトップ12台", "ノートPC8台", "デスクトップ5台/ノート3台", "ノートPC20台"]
    oses = ["Windows 11", "Windows 10", "Windows 10/11混在"]
    nets = ["光回線/無線LAN", "有線LANのみ", "光回線/VPN有", "ADSL(更改検討中)"]
    environments = []
    for c in customers:
        environments.append({
            "customer_id": c["customer_id"],
            "pc": rnd.choice(pcs),
            "os": rnd.choice(oses),
            "network": rnd.choice(nets),
            "notes": rnd.choice(["前任者からの引継ぎ情報。", "現地調査は未実施。",
                                 "サーバー室の空調に余裕なし。", "プリンタは共有設定済み。"]),
        })

    # --- deals + notes + reports ------------------------------------------
    deals, notes, reports = [], [], []
    note_id = 1
    report_id = 1
    cust_ids = [c["customer_id"] for c in customers]
    rep_ids = [r["rep_id"] for r in REPS]
    expert_ids = [r["rep_id"] for r in REPS if r["role"] == "expert"]

    # Indexes of deals we deliberately make dead/dying (authored explicitly below).
    DEAD_COUNT = 4
    total = 60

    for i in range(total):
        did = f"D{i + 1:03d}"
        cid = rnd.choice(cust_ids)
        rid = rnd.choice(rep_ids)
        is_dead = i < DEAD_COUNT
        prod = rnd.sample([p["sku"] for p in PRODUCTS], k=rnd.randint(1, 2))
        amount = sum(next(p for p in PRODUCTS if p["sku"] == s)["price"]
                     for s in prod) * rnd.randint(1, 4)

        if is_dead:
            # Dead/dying: stale, slipped close date(s), optimistic rep, no DM.
            stage = rnd.choice(["proposal", "negotiation", "closing"])
            entered = rnd.randint(70, 120)
            last_contact = rnd.randint(40, 75)
            orig_close = rnd.randint(20, 35)           # already past
            slips = [_iso(orig_close + 30), _iso(orig_close + 15), _iso(orig_close)]
            close_hist = slips
            expected_close = _iso(orig_close)          # in the past
            dm = False
            likelihood = "high"                         # optimism mismatch
            status = "open"
        else:
            stage = rnd.choice(_STAGES)
            entered = rnd.randint(2, 40)
            last_contact = rnd.randint(0, 25)
            future = rnd.randint(5, 60)
            close_hist = [_iso(-future)]
            if rnd.random() < 0.3:                      # some healthy deals slipped once
                close_hist = [_iso(-future - 20), _iso(-future)]
            expected_close = _iso(-future)
            dm = rnd.random() < 0.6
            likelihood = rnd.choice(["low", "med", "med", "high"])
            status = rnd.choices(["open", "won", "lost"], weights=[0.7, 0.15, 0.15])[0]

        stage_idx = _STAGES.index(stage)
        stage_history = []
        cursor = entered + 10 * (stage_idx)
        for s in _STAGES[:stage_idx + 1]:
            stage_history.append({"stage": s, "entered_date": _iso(max(cursor, entered))})
            cursor -= 10
        stage_history[-1]["entered_date"] = _iso(entered)

        deals.append({
            "deal_id": did,
            "customer_id": cid,
            "rep_id": rid,
            "products": prod,
            "amount": amount,
            "stage": stage,
            "stage_history": stage_history,
            "expected_close_date": expected_close,
            "close_date_history": close_hist,
            "last_contact_date": _iso(last_contact),
            "decision_maker_identified": dm,
            "rep_close_likelihood": likelihood,
            "status": status,
        })

        # notes: 1–3 per deal; dead/stalled deals get stall language in the latest.
        n_notes = rnd.randint(1, 3)
        for j in range(n_notes):
            latest = j == n_notes - 1
            if is_dead and latest:
                text = rnd.choice(_NOTE_STALL)
            elif is_dead:
                text = rnd.choice(_NOTE_NORMAL)
            else:
                text = rnd.choice(_NOTE_NORMAL + (_NOTE_STALL if rnd.random() < 0.2 else []))
            notes.append({
                "note_id": f"N{note_id:04d}",
                "deal_id": did,
                "date": _iso(last_contact + (n_notes - 1 - j) * 7),
                "rep_id": rid,
                "channel": rnd.choice(["訪問", "電話", "メール"]),
                "text": text,
            })
            note_id += 1

        # daily report for most open deals
        if status == "open" and rnd.random() < 0.8:
            reports.append({
                "report_id": f"RP{report_id:04d}",
                "rep_id": rid,
                "date": _iso(last_contact),
                "deal_id": did,
                "summary": f"{stage}段階。" + rnd.choice(_NOTE_NORMAL),
                "next_action": "" if is_dead else rnd.choice(
                    ["次回訪問でクロージング", "見積の再提出", "デモ日程の調整", "上長同席を打診"]),
                "close_likelihood": likelihood,
            })
            report_id += 1

    # --- playbook ----------------------------------------------------------
    playbook = []
    for k, (tags, text) in enumerate(PLAYBOOK_SITUATIONS):
        author = rnd.choice([r for r in REPS if r["role"] in ("senior", "expert")])
        playbook.append({
            "entry_id": f"PB{k + 1:02d}",
            "situation_tags": tags,
            "text": text,
            "source_deal_id": rnd.choice([d["deal_id"] for d in deals]),
            "author_rep_id": author["rep_id"],
        })

    return {
        "reps": REPS,
        "customers": customers,
        "products": PRODUCTS,
        "environments": environments,
        "deals": deals,
        "notes": notes,
        "reports": reports,
        "playbook": playbook,
    }


def write():
    config.SEED_DIR.mkdir(parents=True, exist_ok=True)
    data = generate()
    for name, rows in data.items():
        path = config.SEED_DIR / f"{name}.json"
        path.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {path.relative_to(config.PKG_DIR.parent)} ({len(rows)} rows)")


if __name__ == "__main__":
    write()
