"""In-memory data store — the single source of truth for tools and front ends.

Loads the committed seed JSON once (module-level cache) and exposes small,
pure-Python query helpers. Everything downstream (scoring, tools, dashboard,
chat) reads through here, so the data model is defined in exactly one place.
"""
from __future__ import annotations

import json
from functools import lru_cache

from senpai import config

_FILES = ["reps", "customers", "products", "environments",
          "deals", "notes", "reports", "playbook"]


@lru_cache(maxsize=1)
def _load() -> dict[str, list[dict]]:
    data: dict[str, list[dict]] = {}
    for name in _FILES:
        path = config.SEED_DIR / f"{name}.json"
        data[name] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    return data


def reload() -> None:
    """Drop the cache (used by tests / after regenerating seed)."""
    _load.cache_clear()


# --- collections -----------------------------------------------------------
def all_deals() -> list[dict]:
    return _load()["deals"]


def all_reps() -> list[dict]:
    return _load()["reps"]


def all_customers() -> list[dict]:
    return _load()["customers"]


def all_products() -> list[dict]:
    return _load()["products"]


def all_reports() -> list[dict]:
    return _load()["reports"]


def all_playbook() -> list[dict]:
    return _load()["playbook"]


def open_deals() -> list[dict]:
    return [d for d in all_deals() if d.get("status") == "open"]


# --- lookups ---------------------------------------------------------------
def get_deal(deal_id: str) -> dict | None:
    return next((d for d in all_deals() if d["deal_id"] == deal_id), None)


def get_customer(customer_id: str) -> dict | None:
    return next((c for c in all_customers() if c["customer_id"] == customer_id), None)


def get_rep(rep_id: str) -> dict | None:
    return next((r for r in all_reps() if r["rep_id"] == rep_id), None)


def get_product(sku: str) -> dict | None:
    return next((p for p in all_products() if p["sku"] == sku), None)


def get_environment(customer_id: str) -> dict | None:
    return next((e for e in _load()["environments"]
                 if e["customer_id"] == customer_id), None)


# --- relations -------------------------------------------------------------
def deals_for_rep(rep_id: str) -> list[dict]:
    return [d for d in all_deals() if d["rep_id"] == rep_id]


def deals_for_customer(customer_id: str) -> list[dict]:
    return [d for d in all_deals() if d["customer_id"] == customer_id]


def notes_for_deal(deal_id: str) -> list[dict]:
    """Notes for a deal, newest first."""
    rows = [n for n in _load()["notes"] if n["deal_id"] == deal_id]
    return sorted(rows, key=lambda n: n["date"], reverse=True)


def reports_for_rep(rep_id: str) -> list[dict]:
    return [r for r in all_reports() if r["rep_id"] == rep_id]


def report_for_deal(deal_id: str) -> dict | None:
    return next((r for r in all_reports() if r["deal_id"] == deal_id), None)


def customer_name(customer_id: str) -> str:
    c = get_customer(customer_id)
    return c["name"] if c else customer_id


def rep_name(rep_id: str) -> str:
    r = get_rep(rep_id)
    return r["name"] if r else rep_id


def find_customer_by_name(name: str) -> dict | None:
    """Loose match: exact, then substring (handles 'アクメ商事' vs '株式会社アクメ商事')."""
    if not name:
        return None
    n = name.strip()
    for c in all_customers():
        if c["name"] == n:
            return c
    for c in all_customers():
        if n in c["name"] or c["name"] in n:
            return c
    return None
