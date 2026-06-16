"""OpenAI function-calling schemas for Senpai's sales tools.

Same shape as demo/tools.py's TOOLS. These are the capabilities the junior
assistant (exp3) can call; every one is backed by the deterministic store /
scoring engine in senpai.tools.impl.
"""
from __future__ import annotations

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_spr",
            "description": "Look up deals and recent notes from the sales pipeline (SPR) "
                           "by customer name/ID or rep ID. Use this to prepare for a visit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer": {"type": "string", "description": "Customer name or ID (e.g. 'アクメ商事' or 'C01')"},
                    "rep_id": {"type": "string", "description": "Rep ID, e.g. 'R05'"},
                    "deal_id": {"type": "string", "description": "Specific deal ID, e.g. 'D012'"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_similar_deals",
            "description": "Find comparable past deals for a new or thin customer, matched on "
                           "industry, size and profile tags. Useful when the customer has little history.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer": {"type": "string", "description": "Customer name or ID"},
                    "industry": {"type": "string", "description": "Industry (e.g. '製造', '医療')"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_playbook",
            "description": "Retrieve senior reps' tactical advice for a situation, by keywords or "
                           "tags (e.g. '決定先延ばし', '値引き'). Returns attributed snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The situation in natural language"},
                    "tags": {"type": "array", "items": {"type": "string"},
                             "description": "Optional situation tags to match"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_customer_environment",
            "description": "Get the customer's IT environment record (PCs, OS, network) — the "
                           "handoff information a rep needs before a technical visit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer": {"type": "string", "description": "Customer name or ID"},
                },
                "required": ["customer"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_info",
            "description": "Get specs, price and a manual excerpt for a product by SKU or name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product": {"type": "string", "description": "Product SKU (e.g. 'MFP30') or name"},
                },
                "required": ["product"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "score_deal_health",
            "description": "Assess a deal's health: returns a red/yellow/green band, a risk score "
                           "and the concrete reasons behind it. Use to judge if a deal is really on track.",
            "parameters": {
                "type": "object",
                "properties": {
                    "deal_id": {"type": "string", "description": "Deal ID, e.g. 'D012'"},
                },
                "required": ["deal_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_daily_report",
            "description": "Draft an SPR-ready daily sales report (日報) in Japanese from a short "
                           "activity description and optional deal ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "activity": {"type": "string", "description": "What happened today, in natural language"},
                    "deal_id": {"type": "string", "description": "Related deal ID, if any"},
                },
                "required": ["activity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "route_to_expert",
            "description": "Find the right senior/expert rep to escalate a question to, matched on "
                           "their specialty tags, and draft a short intro message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The question to escalate"},
                    "tags": {"type": "array", "items": {"type": "string"},
                             "description": "Topic tags (e.g. 'ネットワーク', 'サーバー')"},
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_reports",
            "description": "Summarize a rep's recent reports and surface report-reliability flags "
                           "(stale/optimistic/missing-field deals). Manager-facing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "rep_id": {"type": "string", "description": "Rep ID, e.g. 'R05'"},
                },
                "required": ["rep_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_seasonal_context",
            "description": "Get Japanese fiscal-year budget-timing context (the year ends in March) "
                           "to advise on close-timing and budget conversations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "integer", "description": "Month number 1-12 (default: current)"},
                },
                "required": [],
            },
        },
    },
]
