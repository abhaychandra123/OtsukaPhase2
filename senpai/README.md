# Senpai — Sales Knowledge & Deal-Health Copilot

Senpai turns the Phase-1 fine-tuned tool-calling model (**exp3**) into a usable product
for a Japanese B2B IT sales org. One shared, deterministic engine serves **three front
ends** and two audiences:

| Front end | Who | What | Needs GPU? |
|---|---|---|---|
| **Junior chat** (`apps/junior_chat.py`, Gradio :7860) | New sales reps | Pre-call briefs, playbook tactics, daily-report drafting, expert routing | yes (exp3) |
| **Manager chat** (`apps/manager_chat.py`, Gradio :7861) | Managers | "Which deals are dying?", report digests, coaching focus, draft a nudge | yes (exp3) |
| **Manager dashboard** (`apps/manager_dashboard.py`, Streamlit :8501) | Managers | Pipeline table with 🔴🟡🟢 health + report-reliability flags | **no** |

**Design thesis.** Onboarding is the relatable face; the real daily pain is pipeline
reliability — *"nobody knows if a deal is real."* So the technical core is a **hybrid
deal-health engine**: deterministic Python produces the score and the reasons
(trustworthy, GPU-free, never hallucinates a number); exp3 only *narrates* the "why" and
drives the chat. If the model server is down, narration degrades to a templated string
and scoring/flags/dashboard are unaffected.

---

## Architecture

```
data/store.py  ── single source of truth (committed seed JSON)
   │
   ├─ health/scoring.py   ── deterministic 0–100 risk score + reasons   ┐
   ├─ health/flags.py     ── report-reliability flags                   │ GPU-free core
   ├─ retrieval/playbook.py ── playbook + similar-deal lookup           │
   ├─ tools/impl.py       ── tool executors + dispatch() (never raises) │
   ├─ tools/web.py        ── web_search (Tavily + canned fallback)      │
   ├─ tools/schemas.py    ── OpenAI schemas + JUNIOR_TOOLS/MANAGER_TOOLS ┘
   └─ llm/
        client.py         ── OpenAI client → exp3 + tool loop (stream_turn)
        narrate.py        ── LLM narration of health, templated fallback
   │
   apps/manager_dashboard.py (Streamlit, GPU-free) ◄── scoring/flags
   apps/junior_chat.py       (Gradio, JUNIOR_TOOLS) ◄── stream_turn
   apps/manager_chat.py      (Gradio, MANAGER_TOOLS) ◄── stream_turn
```

Everything reads through `data/store.py`, so the data model is defined in exactly one
place. The two chats share one tool loop (`llm/client.py:stream_turn`) and differ only by
which tool set they pass.

---

## Components

### `config.py`
Central config: model server (`BASE_URL`, `MODEL`, `MAX_TOOL_ROUNDS`), seed paths, and all
**tunable scoring parameters** (`STAGE_BENCHMARKS`, `DECISION_MAKER_STAGES`,
`STALL_LEXICON`, band thresholds). `today()` returns `date.today()` unless `SENPAI_TODAY`
pins it — used to get reproducible bands against the committed seed (anchored 2026-06-16).

### `data/`
- `gen_seed.py` — deterministic generator (re-runnable, byte-stable) for the synthetic,
  **bilingual** (Japanese content) dataset: ~8 reps, ~35 SMB customers, ~60 deals, notes,
  playbook entries, environments, products, reports. Seeds **4 deliberately dead deals
  (D001–D004)** so the dashboard flags real risk on first load.
- `seed/*.json` — the committed data (so everything runs with zero setup).
- `store.py` — loads seed JSON once (cached) and exposes query helpers
  (`get_deal`, `deals_for_rep`, `open_deals`, `notes_for_deal`, `report_for_deal`, …).

### `health/` — the deterministic core
- `scoring.py` → `score_deal(deal, notes)` returns `HealthResult(score, band, signals)`.
  Seven stage-aware signals (staleness, stage age, close-date past, close-date slips,
  missing decision-maker, Japanese stall language, low activity) sum to a 0–100 **risk**
  score → 🔴 ≥55 / 🟡 25–54 / 🟢 <25. Every signal carries a Japanese `reason`.
- `flags.py` → `deal_flags(...)` returns report-reliability `Flag`s: `close_date_passed`,
  `stale_active`, `missing_fields`, `optimism_mismatch`, `unsupported_stage`.

### `tools/`
- `schemas.py` — OpenAI function schemas (full registry `TOOLS`) plus the role-scoped
  subsets `JUNIOR_TOOLS` and `MANAGER_TOOLS`, built by name from `TOOLS`.
- `impl.py` — executors + `dispatch(name, args)` (always returns a string, never raises).
  Shared `_score_open_deals()` backs the manager analytics tools and `summarize_reports`.
- `web.py` — `web_search` (Tavily when `TAVILY_API_KEY` is set, canned JP fallback otherwise).

### `llm/`
- `client.py` — `OpenAI` client pointed at the vLLM endpoint; `stream_turn(convo, tools=…)`
  runs the tool loop (native `tool_calls` + a safe XLAM-text fallback parser); `simple_complete`
  for one-shot narration.
- `narrate.py` — `narrate_deal(...)` phrases a deal's flag + suggested action via exp3, with a
  deterministic templated fallback when the server is unreachable.

### `apps/`
The three front ends in the table above. The chats import their tool set from
`tools/schemas.py` and stream through `llm/client.py`; the dashboard calls the scoring/flags
engine directly and only touches the model for optional narration.

---

## Tools

| Tool | Junior | Manager | Purpose |
|---|:--:|:--:|---|
| `query_spr` | ✓ | ✓ | Look up deals/notes by customer / rep / deal |
| `find_similar_deals` | ✓ | | Comparable past deals for a new/thin customer |
| `retrieve_playbook` | ✓ | | Attributed senior tactics by tags/keywords |
| `lookup_customer_environment` | ✓ | | Customer PC/OS/network record |
| `get_product_info` | ✓ | | Specs/price/manual excerpt |
| `score_deal_health` | ✓ | ✓ | A deal's band + risk + reasons |
| `draft_daily_report` | ✓ | | SPR-ready 日報 draft |
| `route_to_expert` | ✓ | | Match a senior/expert + intro message |
| `get_seasonal_context` | ✓ | | Japanese fiscal-year budget timing |
| `summarize_reports` | | (✓) | One rep's open deals + flags |
| `list_at_risk_deals` | | ✓ | Team-wide at-risk deals, worst-first |
| `team_pipeline_overview` | | ✓ | Counts, ¥, stage spread, health split, flags |
| `team_report_digest` | | ✓ | All reps' flagged deals, grouped |
| `rep_coaching_focus` | | ✓ | Per-rep rollup → where to coach |
| `draft_message` | | ✓ | Editable rep-nudge / client follow-up (never sent) |
| `web_search` | ✓ | ✓ | External research; also enables normal chatbot use |

---

## Setup

From the repo root (`OtsukaPhase2/`):

```bash
.venv/bin/pip install -r requirements.txt      # gradio, openai, streamlit, pandas, pytest
```

The model is **served** by the external vLLM venv (same as the Phase-1 demo) — nothing to
install there. The dashboard and tests need none of it (pure Python).

## Run

```bash
# Manager dashboard — no GPU, no model server
.venv/bin/streamlit run senpai/apps/manager_dashboard.py     # http://localhost:8501

# Chats — need exp3 served
./scripts/serve_model.sh                                     # exp3 on :8765 (needs GPU)
.venv/bin/python senpai/apps/junior_chat.py                  # junior  → http://localhost:7860
.venv/bin/python senpai/apps/manager_chat.py                 # manager → http://localhost:7861
```

Sanity-check the server before a chat demo:

```bash
curl -s localhost:8765/v1/models | python3 -m json.tool      # should list "exp3"
```

### Reproducible demo dates

The committed seed is anchored to **2026-06-16**. Pin scoring's "today" to it so the same
deals show the same bands regardless of the real date:

```bash
export SENPAI_TODAY=2026-06-16
```

### Optional: real web search

`web_search` returns canned (Japanese) results offline. For live results, put
`TAVILY_API_KEY=...` in a repo-root `.env` (loaded automatically by `tools/web.py`).

---

## Configuration (env vars)

| Var | Default | Used by | Meaning |
|---|---|---|---|
| `BASE_URL` | `http://127.0.0.1:8765/v1` | `llm/client.py` | vLLM OpenAI endpoint |
| `MODEL` | `exp3` | `llm/client.py` | Served model name (matches `serve_model.sh`) |
| `SENPAI_TODAY` | unset → real date | `config.today()` | Pin scoring's "today" (e.g. `2026-06-16`) |
| `UI_HOST` | `127.0.0.1` | both chats | Bind address (`0.0.0.0` to expose) |
| `UI_PORT` | `7860` / `7861` | junior / manager chat | UI port |
| `TAVILY_API_KEY` | — | `tools/web.py` | Enables real web search |

---

## Verify (no GPU)

```bash
export SENPAI_TODAY=2026-06-16
.venv/bin/pytest tests/                          # scoring, flags, manager tools
.venv/bin/python -m senpai.tools.impl            # one canned call per tool
python -m senpai.data.gen_seed && git diff --exit-code senpai/data/seed/   # reproducible seed
```

The dashboard and chats render even without the model server (the chats just can't answer
until exp3 is up; the dashboard's narration falls back to a templated string).

---

## PM demo run sheet

1. **Lead with the human story** — junior chat:
   「明日アクメ商事に訪問。準備をお願い」 → deal + playbook + environment + health in one brief;
   「お客様が決定を先延ばしにします。先輩ならどうしますか？」 → an attributed senior tactic.
2. **Switch to business impact** — manager chat or dashboard:
   「今週リスクが高い案件を担当別にまとめて」 / drill into **D001** to show the signal-by-signal
   breakdown; the report-reliability panel is "the dead deals we flag in week one."
3. **Show it never breaks** — stop the model server, reload the dashboard: narration falls
   back to a templated reason; scoring and flags are unchanged.

Same engine, two audiences: the junior's pre-call brief and the manager's risk view are the
*same* deterministic health read, phrased for each.
```
