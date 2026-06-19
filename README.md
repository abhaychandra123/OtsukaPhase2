# Senpai — Sales Knowledge & Onboarding Copilot (Otsuka, Phase 2)

Senpai makes the knowledge that lives in Otsuka's best salespeople available to every rep —
on demand and in context — while giving managers one place to read deal health and catch
dying deals early. It is a **fine-tuned, tool-calling assistant (exp3)** anchored to Otsuka's
real SPR data, not a generic sales chatbot.

The pitch in one line: **onboarding is the relatable face; pipeline reliability — "nobody
knows if a deal is real" — is the engine underneath.** The same deterministic deal-health
read that briefs a junior before a call also flags a manager's dying deal.

---

## Repository map

| Path | What it is | Owner |
|---|---|---|
| **`senpai/`** | **Our pipeline** — the deterministic deal-health engine on Otsuka's real SPR schema, plus the junior chat, manager chat, and manager dashboard. **Start here.** | this team |
| `Schema.md` | The real Otsuka SPR schema (4 tables) + how our pipeline maps to it | this team |
| `senpai/api/`, `web/`, `senpai/coach/`, `senpai/knowledge/` | A separate, in-progress **web-app experiment** (FastAPI + Next.js frontend, Sales Review Coach, Knowledge Explorer) | another team member |
| `demo/` | Phase-1 tool-calling demo (the exp3 Gradio showcase that proved the model) | this team |

> Our pipeline does **not** import or depend on the web-app experiment; the two are
> decoupled and can run independently. See `senpai/README.md` → *Isolation* for details.

---

## Quickstart (web app)

Run the **backend** and **frontend** in two separate terminals. `SENPAI_USE_LLM=1` switches
live Coach commentary ON (default off = deterministic only).

### Windows (PowerShell)

```powershell
# install deps (Python bridge + frontend)
.\.venv\Scripts\pip.exe install -r requirements.txt
cd web; npm install; cd ..

# Terminal 1 — Backend bridge (FastAPI) → http://localhost:8000
$env:SENPAI_USE_LLM = '1'
$env:SENPAI_TODAY   = '2026-06-16'        # pin scoring's "today" to the seed anchor
.\.venv\Scripts\python.exe -m uvicorn senpai.api.server:app --port 8000 --host 127.0.0.1

# Terminal 2 — Frontend (Next.js) → http://localhost:3000   (defaults to the :8000 backend)
cd web; npm run dev
```

### Linux / macOS (bash)

```bash
# install deps (Python bridge + frontend)
.venv/bin/pip install -r requirements.txt
( cd web && npm install )

# Terminal 1 — Backend bridge (FastAPI) → http://localhost:8000
export SENPAI_USE_LLM=1
export SENPAI_TODAY=2026-06-16            # pin scoring's "today" to the seed anchor
.venv/bin/python -m uvicorn senpai.api.server:app --port 8000 --host 127.0.0.1

# Terminal 2 — Frontend (Next.js) → http://localhost:3000   (defaults to the :8000 backend)
cd web && npm run dev
```

The deal-health engine and unit tests are **pure Python (no GPU)**. Live Senior Commentary
additionally needs a GPU-served model on `:8765` — see **[Web app: switching on live Coach
commentary](#web-app-frontend--backend--switching-on-live-coach-commentary)** below for the
model server, the `SENPAI_USE_LLM` switch, and the `.env` wiring.

**→ Full engineering reference, tool list, env vars, and verify steps:
[`senpai/README.md`](senpai/README.md).**
**→ The data shape we build against: [`Schema.md`](Schema.md).**

---

## Web app (frontend + backend) — switching on live Coach commentary

The Next.js web app (`web/`) talks to the FastAPI bridge (`senpai/api/server.py`), which in
turn streams the optional **Senior Commentary** from a GPU-served, OpenAI-compatible model
(llama.cpp `llama-server`). The deterministic Review Coach always works without a model; the
LLM only *rephrases* the same findings. Live commentary is **gated OFF by default** — you turn
it on with one backend env var.

Start three things, in order:

### 1. Model server (GPU box) — `:8765`

The model is served by `llama-server` on the GPU box and reached over an OpenAI-compatible
endpoint. The bridge reads the endpoint + model name from the **repo-root `.env`** (loaded
automatically by `senpai/config.py`):

```bash
# E:\my_stuff\OtsukaPhase2\.env
BASE_URL="http://100.101.186.29:8765/v1"                    # direct over Tailscale (no tunnel)
MODEL="Qwen3.6-27B-Claude-Opus-Reasoning-Distilled"          # llama-server ignores this field; label only
```

Reach it directly over Tailscale (as above), or via an SSH tunnel and point `BASE_URL` at
`http://127.0.0.1:8765/v1`:

```bash
ssh -N -L 8765:127.0.0.1:8765 team-a@100.101.186.29
```

Sanity check it's up: `curl http://127.0.0.1:8765/v1/models` (or the Tailscale IP).
> A `couldn't bind … 0.0.0.0:8765` line in the llama-server log just means a **second** launch
> hit an already-running instance — the first one is fine.

### 2. Backend bridge (FastAPI) — `:8000`  ← **this is the switch**

```bash
# PowerShell (Windows)
$env:SENPAI_USE_LLM = '1'        # ← switches live commentary ON (default '0' = deterministic only)
$env:SENPAI_TODAY   = '2026-06-16'   # pin scoring's "today" to the seed anchor
python -m uvicorn senpai.api.server:app --port 8000 --host 127.0.0.1
```

```bash
# bash / macOS / Linux
export SENPAI_USE_LLM=1
export SENPAI_TODAY=2026-06-16
.venv/bin/python -m uvicorn senpai.api.server:app --port 8000 --host 127.0.0.1
```

- **`SENPAI_USE_LLM=1` is the on/off switch.** Without it, `/api/coach/narrate` returns
  `unavailable: llm_disabled` and the UI shows *"Couldn't reach the explanation model…"*.
- The bridge has **no `--reload`**: after editing `.env` (or any Python), **restart it** to pick
  up the change.
- Verify: `curl http://localhost:8000/api/health` → `{"status":"ok", …}`.

### 3. Frontend (Next.js) — `:3000`

```bash
cd web
npm install            # first time only
npm run dev            # → http://localhost:3000
```

The frontend points at the backend via `NEXT_PUBLIC_API_BASE`, which **defaults to
`http://localhost:8000`** — so if the bridge runs on :8000 you need no config. To target a
different host, create `web/.env.local`:

```bash
# web/.env.local
NEXT_PUBLIC_API_BASE="http://localhost:8000"
```

Then open **Review Coach → Generate Senior Commentary**: with the backend switch on and the
model reachable, the thinking phase and answer stream in live. With either off, the page falls
back cleanly to the deterministic coaching.

---

## What's inside the pipeline (at a glance)

- **Real SPR schema.** `senpai/data/gen_seed.py` generates byte-stable synthetic data in
  Otsuka's production shape (`deals`, `orders`, `quotes`, `sales_activities`), so the real
  data is a drop-in when we get access. `order_rank` (`1_Confirmed … 8_Cancelled`) is the spine.
- **Deterministic deal-health engine.** Seven rank-aware signals (staleness, rank stagnation,
  order-date passed, rank regression, missing decision-maker, stall language, low activity) →
  a 🔴🟡🟢 score with a Japanese reason for every signal. No number is ever invented by a model.
- **Report-reliability flags.** Surfaces deals whose recorded rank contradicts their activity
  signals (`optimism_mismatch`, `stale_active`, `close_date_passed`, …).
- **Web app over one shared engine.** A Next.js frontend (Review Coach, Knowledge Explorer,
  manager workspace, growth) on a FastAPI bridge — junior briefs/playbook/report drafting and
  manager at-risk deals, report digests, and coaching focus, all reading the same deterministic
  engine, with optional GPU-served Senior Commentary.

## Verify (no GPU)

```bash
export SENPAI_TODAY=2026-06-16
.venv/bin/pytest tests/test_scoring.py tests/test_flags.py tests/test_manager_tools.py
.venv/bin/python -m senpai.tools.impl        # one canned call per tool
```

## Phase-1 demo

The original tool-calling showcase (exp3 answering in natural language while calling real
tools) lives in [`demo/`](demo/) with its own run sheet at `demo/demo_script.md`.
