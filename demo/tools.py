"""Demo tools for the scoped tool-calling demo.

Six tools exposed to the model as OpenAI function schemas (`TOOLS`) plus a
`dispatch(name, arguments)` executor that runs them and returns a SHORT string
result (what the model sees as the `tool` message content).

Hybrid backend (chosen for a reliable recorded demo):
  * Real, keyless : get_weather (Open-Meteo), convert_currency (frankfurter.app),
                    create_file (writes a real local file under demo/output/).
  * Deterministic : web_search, send_email, get_calendar (canned realistic data).

Every real call is wrapped so a network failure falls back to a realistic
canned value — the demo never breaks live. Uses only the stdlib (urllib) so no
extra deps beyond what's already installed.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent / "output"

_HTTP_TIMEOUT = 6  # seconds; keep short so a hang can't stall the demo


def _load_dotenv() -> None:
    """Load repo-root .env keys into os.environ (stdlib only; never overrides
    a value already set in the environment)."""
    env = Path(__file__).resolve().parents[1] / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv()
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")


def _get_json(url: str) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "toolcalllm-demo/1.0"})
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _post_json(url: str, payload: dict, timeout: int = _HTTP_TIMEOUT) -> dict | None:
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={"Content-Type": "application/json",
                     "User-Agent": "toolcalllm-demo/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Tool schemas (OpenAI function-calling format)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name, e.g. 'Tokyo'"}
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "convert_currency",
            "description": "Convert an amount of money from one currency to another.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Amount to convert"},
                    "from_currency": {"type": "string", "description": "3-letter code, e.g. 'USD'"},
                    "to_currency": {"type": "string", "description": "3-letter code, e.g. 'JPY'"},
                },
                "required": ["amount", "from_currency", "to_currency"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web and return the top results for a query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a text file with the given name and content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "File name, e.g. 'plan.txt'"},
                    "content": {"type": "string", "description": "Text to write into the file"},
                },
                "required": ["filename", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email to a recipient.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address or name"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_calendar",
            "description": "Get the calendar events for a given date (YYYY-MM-DD, or 'today').",
            "parameters": {
                "type": "object",
                "properties": {
                    "day": {"type": "string", "description": "Date as YYYY-MM-DD or 'today'"}
                },
                "required": ["day"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search the product catalog by category, price range, or keyword. "
                           "Returns matching products with their SKU, name and price.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string",
                                 "description": "Product category, e.g. 'laptop', 'printer', 'server', 'monitor', 'software'"},
                    "max_price": {"type": "number", "description": "Maximum unit price in JPY"},
                    "min_price": {"type": "number", "description": "Minimum unit price in JPY"},
                    "keyword": {"type": "string", "description": "Free-text term to match in the product name/specs"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_info",
            "description": "Get full details (specs, price, stock, lead time) for a single product "
                           "by its SKU or name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product": {"type": "string", "description": "Product SKU (e.g. 'LP14') or name (e.g. 'Laptop Pro 14')"}
                },
                "required": ["product"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_quote",
            "description": "Build a price quote (estimate) for one or more catalog products. "
                           "Computes line totals, an optional discount, tax, and the grand total.",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "description": "Products to quote.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "sku": {"type": "string", "description": "Product SKU or name"},
                                "qty": {"type": "integer", "description": "Quantity"},
                            },
                            "required": ["sku", "qty"],
                        },
                    },
                    "discount_pct": {"type": "number", "description": "Discount percent applied to the subtotal (0-100)"},
                    "customer": {"type": "string", "description": "Customer/company name for the quote header"},
                    "tax_pct": {"type": "number", "description": "Sales-tax percent (default 10)"},
                },
                "required": ["items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_meeting",
            "description": "Schedule a meeting on the calendar. Resolve relative dates (e.g. 'next "
                           "Saturday') to a concrete date before calling.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Meeting title"},
                    "date": {"type": "string", "description": "Date as YYYY-MM-DD"},
                    "start_time": {"type": "string", "description": "Start time as 24h HH:MM (JST)"},
                    "duration_hours": {"type": "number", "description": "Length in hours (default 1)"},
                    "attendees": {"type": "array", "items": {"type": "string"},
                                  "description": "Attendee email addresses"},
                    "description": {"type": "string", "description": "Optional agenda/notes"},
                },
                "required": ["title", "date", "start_time"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Executors
# ---------------------------------------------------------------------------

_WMO = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "rime fog", 51: "light drizzle", 53: "drizzle", 55: "dense drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 71: "light snow", 73: "snow",
    75: "heavy snow", 80: "rain showers", 81: "rain showers", 82: "violent rain showers",
    95: "thunderstorm", 96: "thunderstorm w/ hail", 99: "thunderstorm w/ heavy hail",
}

# Canned fallbacks so a network hiccup never breaks the recording.
_WEATHER_FALLBACK = {
    "tokyo": "Tokyo: 18°C, partly cloudy, wind 12 km/h.",
    "paris": "Paris: 11°C, overcast, wind 18 km/h.",
    "new york": "New York: 14°C, light rain, wind 22 km/h.",
}


def get_weather(location: str) -> str:
    geo = _get_json(
        "https://geocoding-api.open-meteo.com/v1/search?"
        + urllib.parse.urlencode({"name": location, "count": 1})
    )
    if geo and geo.get("results"):
        r = geo["results"][0]
        fc = _get_json(
            "https://api.open-meteo.com/v1/forecast?"
            + urllib.parse.urlencode({
                "latitude": r["latitude"], "longitude": r["longitude"],
                "current": "temperature_2m,weather_code,wind_speed_10m",
            })
        )
        if fc and fc.get("current"):
            c = fc["current"]
            temp, wind = c.get("temperature_2m"), c.get("wind_speed_10m")
            if temp is not None and wind is not None:
                desc = _WMO.get(int(c.get("weather_code", -1)), "clear")
                name = r.get("name", location)
                return f"{name}: {round(temp)}°C, {desc}, wind {round(wind)} km/h."
    # fall through to canned fallback on missing fields / network failure
    return _WEATHER_FALLBACK.get(location.strip().lower(),
                                 f"{location}: 16°C, partly cloudy, wind 10 km/h.")


def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    amount = float(amount)
    fc, tc = from_currency.upper(), to_currency.upper()
    data = _get_json(
        "https://api.frankfurter.app/latest?"
        + urllib.parse.urlencode({"amount": amount, "from": fc, "to": tc})
    )
    if data and data.get("rates", {}).get(tc) is not None:
        return f"{amount:g} {fc} = {data['rates'][tc]:.2f} {tc}."
    # Fallback static rates (approximate) so the demo always answers.
    rates = {("USD", "JPY"): 157.0, ("USD", "EUR"): 0.92, ("USD", "GBP"): 0.79,
             ("EUR", "JPY"): 170.0, ("EUR", "USD"): 1.09}
    rate = rates.get((fc, tc))
    if rate:
        return f"{amount:g} {fc} = {amount * rate:.2f} {tc}."
    return f"Converted {amount:g} {fc} to {tc} (rate unavailable, approx)."


_SEARCH_CANNED = {
    "sushi": [
        "Sushi Tokami (Ginza) — Michelin-starred edomae sushi, ¥¥¥¥.",
        "Uobei Shibuya — fast conveyor sushi, budget-friendly, near the station.",
        "Sushi no Midori (Shibuya) — popular, great value, expect a queue.",
    ],
    "restaurant": [
        "Narisawa (Minato) — innovative Japanese, World's 50 Best.",
        "Den (Jimbocho) — playful kaiseki, 2 Michelin stars.",
        "Afuri (multiple) — yuzu shio ramen, casual.",
    ],
}


def web_search(query: str) -> str:
    # Real web search via Tavily when a key is configured; falls back to canned
    # results on missing key / network failure so the demo never breaks.
    if TAVILY_API_KEY:
        data = _post_json(
            "https://api.tavily.com/search",
            {"api_key": TAVILY_API_KEY, "query": query,
             "max_results": 4, "search_depth": "basic", "include_answer": True},
            timeout=12,
        )
        if data and data.get("results"):
            lines = []
            for r in data["results"][:4]:
                title = (r.get("title") or "").strip()
                snippet = (r.get("content") or "").strip().replace("\n", " ")
                if len(snippet) > 160:
                    snippet = snippet[:157] + "…"
                url = r.get("url", "")
                lines.append(f"{title} — {snippet} ({url})")
            answer = (data.get("answer") or "").strip()
            head = f"{answer}\n\n" if answer else ""
            return head + "Top results:\n- " + "\n- ".join(lines)
    # fallback: canned results
    q = query.lower()
    for key, results in _SEARCH_CANNED.items():
        if key in q:
            return "Top results:\n- " + "\n- ".join(results)
    return ("Top results:\n- Wikipedia: overview article.\n"
            "- Official site: primary source.\n- News: recent coverage.")


def create_file(filename: str, content: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name) or "file.txt"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / safe
    path.write_text(content, encoding="utf-8")
    return f"Created '{safe}' ({len(content)} chars) at {path}."


def send_email(to: str, subject: str, body: str) -> str:
    return f"Email sent to {to} — subject: \"{subject}\" ({len(body)} chars)."


def get_calendar(day: str) -> str:
    d = date.today().isoformat() if str(day).lower() == "today" else day
    return (f"Calendar for {d}:\n- 10:00 Standup\n- 13:00 Mid-term presentation\n"
            f"- 16:30 Demo recording")


# ---------------------------------------------------------------------------
# Sales tools — product catalog, quoting, meeting scheduling
# ---------------------------------------------------------------------------

# Demo product catalog (generic IT products). Prices in JPY.
_CATALOG = {
    "LP14":  {"name": "Laptop Pro 14",   "category": "laptop",
              "price": 168000, "specs": "14\" / Core i7 / 16GB / 512GB SSD",
              "stock": 24, "lead_time": "in stock, ships in 2 days"},
    "LP16":  {"name": "Laptop Pro 16",   "category": "laptop",
              "price": 232000, "specs": "16\" / Core i9 / 32GB / 1TB SSD",
              "stock": 11, "lead_time": "in stock, ships in 2 days"},
    "LB13":  {"name": "Laptop Air 13",   "category": "laptop",
              "price": 119000, "specs": "13\" / Core i5 / 16GB / 256GB SSD",
              "stock": 40, "lead_time": "in stock, ships next day"},
    "DT01":  {"name": "Desktop Tower T1", "category": "desktop",
              "price": 142000, "specs": "Core i7 / 32GB / 1TB SSD",
              "stock": 18, "lead_time": "in stock, ships in 3 days"},
    "MN27":  {"name": "27\" 4K Monitor",  "category": "monitor",
              "price": 38000, "specs": "27\" / 4K / IPS / USB-C",
              "stock": 60, "lead_time": "in stock, ships next day"},
    "MN24":  {"name": "24\" FHD Monitor", "category": "monitor",
              "price": 21000, "specs": "24\" / 1080p / IPS",
              "stock": 75, "lead_time": "in stock, ships next day"},
    "MFP30": {"name": "Color MFP 3000",   "category": "printer",
              "price": 240000, "specs": "A3 color multifunction / 30ppm / duplex",
              "stock": 6, "lead_time": "ships in 5 days"},
    "MFP15": {"name": "Mono MFP 1500",    "category": "printer",
              "price": 96000, "specs": "A4 mono multifunction / 25ppm",
              "stock": 14, "lead_time": "in stock, ships in 3 days"},
    "SRV20": {"name": "Rack Server R20",  "category": "server",
              "price": 520000, "specs": "1U / Xeon / 64GB / 2x1TB NVMe",
              "stock": 4, "lead_time": "ships in 7 days"},
    "NSW24": {"name": "Network Switch 24p", "category": "networking",
              "price": 54000, "specs": "24-port Gigabit / managed L2",
              "stock": 30, "lead_time": "in stock, ships in 2 days"},
    "OFFICE": {"name": "Office Suite (annual, per seat)", "category": "software",
               "price": 13800, "specs": "Docs/Sheets/Slides + 1TB cloud, 1 user/yr",
               "stock": 9999, "lead_time": "instant license delivery"},
    "AV365": {"name": "Endpoint Security (annual, per seat)", "category": "software",
              "price": 6800, "specs": "Antivirus + EDR, 1 device/yr",
              "stock": 9999, "lead_time": "instant license delivery"},
}


def _resolve_sku(product: str):
    """Return (sku, record) for a SKU or (fuzzy) name match, else (None, None)."""
    if not product:
        return None, None
    p = str(product).strip().lower()
    if p.upper() in _CATALOG:
        return p.upper(), _CATALOG[p.upper()]
    for sku, rec in _CATALOG.items():
        if p == rec["name"].lower():
            return sku, rec
    for sku, rec in _CATALOG.items():
        if p in rec["name"].lower() or rec["name"].lower() in p:
            return sku, rec
    return None, None


def search_products(category: str = None, max_price: float = None,
                    min_price: float = None, keyword: str = None) -> str:
    hits = []
    for sku, rec in _CATALOG.items():
        if category and category.strip().lower() not in rec["category"]:
            continue
        if max_price is not None and rec["price"] > float(max_price):
            continue
        if min_price is not None and rec["price"] < float(min_price):
            continue
        if keyword:
            k = keyword.strip().lower()
            if k not in rec["name"].lower() and k not in rec["specs"].lower():
                continue
        hits.append((sku, rec))
    if not hits:
        return "No products matched those criteria."
    hits.sort(key=lambda x: x[1]["price"])
    lines = [f"{sku} — {rec['name']} — ¥{rec['price']:,} ({rec['category']})"
             for sku, rec in hits]
    return f"Found {len(hits)} product(s):\n- " + "\n- ".join(lines)


def get_product_info(product: str) -> str:
    sku, rec = _resolve_sku(product)
    if not rec:
        names = ", ".join(r["name"] for r in _CATALOG.values())
        return f"No product found for {product!r}. Available products: {names}."
    return (f"{rec['name']} ({sku}) — ¥{rec['price']:,}\n"
            f"Category: {rec['category']}\nSpecs: {rec['specs']}\n"
            f"Stock: {rec['stock']} units ({rec['lead_time']}).")


def create_quote(items, discount_pct: float = 0, customer: str = None,
                 tax_pct: float = 10) -> str:
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except json.JSONDecodeError:
            return "[error] could not parse quote items."
    if not isinstance(items, list) or not items:
        return "[error] no items to quote."
    lines, skipped, subtotal = [], [], 0
    for it in items:
        if not isinstance(it, dict):
            continue
        sku, rec = _resolve_sku(it.get("sku") or it.get("name") or "")
        qty = int(it.get("qty", 1) or 1)
        if not rec:
            skipped.append(str(it.get("sku") or it.get("name")))
            continue
        line_total = rec["price"] * qty
        subtotal += line_total
        lines.append(f"  {qty} × {rec['name']} @ ¥{rec['price']:,} = ¥{line_total:,}")
    if not lines:
        return f"[error] none of the requested items were found: {', '.join(skipped)}"
    discount_pct = float(discount_pct or 0)
    tax_pct = float(tax_pct if tax_pct is not None else 10)
    discount = round(subtotal * discount_pct / 100)
    taxed_base = subtotal - discount
    tax = round(taxed_base * tax_pct / 100)
    total = taxed_base + tax
    header = f"Quote for {customer}" if customer else "Quote"
    out = [f"{header}", "Line items:", *lines,
           f"Subtotal: ¥{subtotal:,}"]
    if discount:
        out.append(f"Discount ({discount_pct:g}%): -¥{discount:,}")
    out.append(f"Tax ({tax_pct:g}%): ¥{tax:,}")
    out.append(f"Total: ¥{total:,}")
    if skipped:
        out.append(f"(Skipped unknown items: {', '.join(skipped)})")
    return "\n".join(out)


def schedule_meeting(title: str, date: str, start_time: str,
                     duration_hours: float = 1, attendees=None,
                     description: str = "") -> str:
    attendees = attendees or []
    if isinstance(attendees, str):
        attendees = [a.strip() for a in attendees.split(",") if a.strip()]
    try:
        import gcal  # lazy: a missing google lib must not break tool import
        ok, message = gcal.create_event(
            title=title, date=date, start_time=start_time,
            duration_hours=float(duration_hours or 1),
            attendees=attendees, description=description,
        )
        if ok:
            return message
    except Exception:  # noqa: BLE001 — fall back to a simulated confirmation
        pass
    # Fallback: simulated booking (same spirit as send_email) so the demo never breaks.
    who = f", {len(attendees)} attendee(s) invited" if attendees else ""
    return (f"Meeting booked: \"{title}\" on {date} at {start_time} JST "
            f"for {float(duration_hours or 1):g}h{who}. (simulated)")


_DISPATCH = {
    "get_weather": get_weather,
    "convert_currency": convert_currency,
    "web_search": web_search,
    "create_file": create_file,
    "send_email": send_email,
    "get_calendar": get_calendar,
    "search_products": search_products,
    "get_product_info": get_product_info,
    "create_quote": create_quote,
    "schedule_meeting": schedule_meeting,
}


def dispatch(name: str, arguments: dict | str) -> str:
    """Execute a tool by name with arguments (dict or JSON string). Always
    returns a string; never raises (so the demo loop can't crash)."""
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
    except Exception as e:  # noqa: BLE001 — demo must never crash on a tool
        return f"[error] {name} failed: {e}"


if __name__ == "__main__":
    # Quick manual smoke test.
    for n, a in [
        ("get_weather", {"location": "Tokyo"}),
        ("convert_currency", {"amount": 500, "from_currency": "USD", "to_currency": "JPY"}),
        ("web_search", {"query": "sushi in Shibuya"}),
        ("create_file", {"filename": "plan.txt", "content": "Sushi no Midori, Shibuya."}),
        ("send_email", {"to": "team@x.com", "subject": "Demo", "body": "ready"}),
        ("get_calendar", {"day": "today"}),
        ("search_products", {"category": "laptop", "max_price": 200000}),
        ("get_product_info", {"product": "Color MFP 3000"}),
        ("create_quote", {"items": [{"sku": "LP14", "qty": 8}, {"sku": "MFP30", "qty": 1}],
                          "discount_pct": 10, "customer": "Acme Corp"}),
        ("schedule_meeting", {"title": "Follow-up", "date": "2026-06-20",
                              "start_time": "14:00", "duration_hours": 2,
                              "attendees": ["client@acme.co"]}),
    ]:
        print(f"{n}({a}) -> {dispatch(n, a)}")
