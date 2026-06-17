# Senpai — Sales Knowledge & Deal-Health Copilot (Phase 2)

Senpai turns the Phase-1 tool-calling model (**exp3**) into a usable product with
**three front ends over one shared engine**:

- **Junior assistant** (Gradio chat) — pre-call briefs, in-the-moment playbook
  answers, daily-report drafting, and expert routing. The human, relatable story.
- **Manager assistant** (Gradio chat) — ask the team pipeline in words: which deals
  are at risk, a digest of everyone's reports, who needs coaching, draft a nudge.
- **Manager dashboard** (Streamlit) — the team pipeline with red/yellow/green deal
  health and report-reliability flags. The business-impact layer.

Both chats also have a `web_search` tool (Tavily when `TAVILY_API_KEY` is set, canned
fallback otherwise) so they double as a normal assistant for ad-hoc research.

The shared core is a **hybrid deal-health scorer**: deterministic Python produces the
score and the reasons (trustworthy, GPU-free, never hallucinates a number); exp3 only
*narrates* the "why". **If the model server is down, narration degrades to a templated
string and the dashboard/scoring are unaffected.**

```
senpai/data/store.py  ── single source of truth (seed JSON)
        │
        ├─ health/{scoring,flags}.py ── deterministic, no GPU ──┐
        ├─ retrieval/playbook.py                                │
        ├─ tools/{schemas,impl}.py  ── dispatch(), never raises │
        └─ llm/{client,narrate}.py  ── exp3 + templated fallback│
                                                                │
   apps/manager_dashboard.py (Streamlit, GPU-free) ◄───────────┤
   apps/junior_chat.py       (Gradio, needs exp3)  ◄───────────┘
```

## Setup

```bash
.venv/bin/pip install -r requirements.txt      # adds streamlit, pandas, pytest
```

The model is *served* by the external vLLM venv (same as the demo); nothing to install
there. The dashboard and tests need **none** of that — they are pure Python.

## Run

```bash
# Manager dashboard — no GPU, no model server needed
.venv/bin/streamlit run senpai/apps/manager_dashboard.py     # http://localhost:8501

# Chats — need exp3 served
./scripts/serve_model.sh                                      # exp3 on :8765 (needs GPU)
.venv/bin/python senpai/apps/junior_chat.py                  # junior  → http://localhost:7860
.venv/bin/python senpai/apps/manager_chat.py                 # manager → http://localhost:7861
```

Both chats share the exp3 server; they listen on different ports (7860 / 7861) so you
can run them side by side. The manager chat is scoped to manager tools
(`list_at_risk_deals`, `team_pipeline_overview`, `team_report_digest`,
`rep_coaching_focus`, `draft_message`, `query_spr`, `score_deal_health`, `web_search`);
the junior chat keeps its coaching tools plus `web_search`.

### Optional: real web search

`web_search` returns canned (Japanese) results offline. For live results, put
`TAVILY_API_KEY=...` in a repo-root `.env` (loaded automatically) — same mechanism as the
Phase-1 demo.

Sanity-check the server before the chat demo:

```bash
curl -s localhost:8765/v1/models | python3 -m json.tool      # should list "exp3"
```

### Reproducible demo dates

The committed seed data is anchored to **2026-06-16**. To pin scoring's "today" to that
anchor (so the same deals show the same bands regardless of the real date):

```bash
export SENPAI_TODAY=2026-06-16
```

## Data

`senpai/data/seed/*.json` is synthetic, bilingual (Japanese content), and **committed** so
everything runs with zero setup. Regenerate deterministically with:

```bash
python -m senpai.data.gen_seed       # byte-stable; re-running leaves git clean
```

It seeds ~8 reps, ~35 SMB customers, ~60 deals, ~25 playbook entries, environments and
daily reports — including **4 deliberately dead/dying deals** (D001–D004) so the dashboard
flags real risk on first load.

## Verify (no GPU)

```bash
.venv/bin/pytest tests/                          # scoring + flag unit tests
.venv/bin/python -m senpai.tools.impl            # one canned call per tool
python -m senpai.data.gen_seed && git diff --exit-code senpai/data/seed/   # reproducible
```

## PM demo run sheet

1. **Lead with the human story.** Open the **junior chat** and run:
   - 「明日アクメ商事に訪問。準備をお願い」 → pulls the deal, playbook tactics, the
     customer's IT environment, and the deal-health read in one brief.
   - 「お客様が決定を先延ばしにします。先輩ならどうしますか？」 → an attributed senior
     tactic (or an expert hand-off if the playbook is thin).
   - 「今日の活動から日報を作成して…」 → an SPR-ready draft.
2. **Switch to business impact.** Open the **manager dashboard** and:
   - Point at the KPI row (🔴 at-risk count, flagged reports).
   - Sort the pipeline by health and drill into **D001** — show the signal-by-signal
     breakdown and the manager flag + suggested action.
   - Scroll to the **report-reliability panel**: "these deals say one thing but the data
     says another — that's the three dead deals we flag in week one."
3. **Show it never breaks.** Stop the model server and reload the dashboard: narration
   falls back to a templated reason; scoring and flags are unchanged.

Same engine, two audiences: the junior's pre-call brief and the manager's risk view are
the *same* deterministic health read, phrased for each.
