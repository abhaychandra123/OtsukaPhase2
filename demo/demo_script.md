# Tool-Calling Demo — Run Sheet & Talking Points

Goal: an impressive, **reliable** demo of our model (exp3) using real tools, for a
mixed (mostly non-technical) audience. Plays to the model's strength — **single &
parallel tool calls (BFCL 92–96%)** — and avoids long agent loops (its weak regime).

## One-time setup (needs GPU free — after exp5 gen finishes)
```bash
# 1. install the UI + real-tool deps into the vLLM venv (one-time)
/home/team-a/Desktop/ToolCallLM_finetune/.venv/bin/pip install \
    gradio google-api-python-client google-auth-httplib2 google-auth-oauthlib

# 2. serve the model (terminal A) — waits for GPU
./demo/serve_demo.sh                      # exp3 on http://127.0.0.1:8765

# 3. launch the UI (terminal B)
/home/team-a/Desktop/ToolCallLM_finetune/.venv/bin/python demo/app.py
#    → open http://localhost:7860
```
Sanity check before recording:
```bash
curl -s localhost:8765/v1/models | python3 -m json.tool   # should list "exp3"
```

### Real-tool keys (one-time)
- **Web search (Tavily):** put `TAVILY_API_KEY=...` in the repo-root `.env`
  (already loaded by `demo/tools.py`). Without it, `web_search` falls back to canned results.
- **Calendar (Google):** `schedule_meeting` books a real event via the Google Calendar API.
  1. Google Cloud Console → create/select a project → **enable the Google Calendar API**.
  2. **Create OAuth client ID → Desktop app** → download JSON → save as `demo/credentials.json`.
  3. On the OAuth consent screen, add your Google account as a **test user**.
  4. **Pre-warm the token before recording:** run the smoke test once interactively —
     it opens a browser consent and writes `demo/token.json`:
     ```bash
     /home/team-a/Desktop/ToolCallLM_finetune/.venv/bin/python -c \
       "import sys; sys.path.insert(0,'demo'); import gcal; \
        print(gcal.create_event('Test', '2026-06-20', '14:00', 1, ['you@example.com'], 'pre-warm'))"
     ```
  Both `credentials.json` and `token.json` are git-ignored. If anything is missing,
  `schedule_meeting` degrades to a "(simulated)" confirmation so the demo never breaks.

## The script (run these in order — they're the example buttons in the UI)

| # | Prompt | Shows | Expected tool calls |
|---|--------|-------|---------------------|
| 1 | "What's the weather in Tokyo right now?" | basic tool use | `get_weather` ×1 |
| 2 | **"Compare the weather in Tokyo, Paris, and New York."** | **parallel calls (hero shot)** | `get_weather` ×3 in one turn |
| 3 | "How much is 500 USD in JPY and EUR?" | parallel, different tool | `convert_currency` ×2 |
| 4 | "Find a good sushi spot in Shibuya and save the top pick to plan.txt." | multi-tool + real artifact | `web_search` → `create_file` (a real file appears under `demo/output/`) |
| 5 | "Email the team at team@toolcalllm.ai that the demo is ready." | action tool | `send_email` ×1 |
| 6 | "Find laptops under ¥200,000 and tell me the best one." | sales: catalog search | `search_products` (→ optional `get_product_info`) |
| 7 | "What are the specs and price of the Color MFP 3000?" | sales: product lookup | `get_product_info` ×1 |
| 8 | "Quote 8 Laptop Pro 14s and one Color MFP 3000 with a 10% discount for Acme Corp." | sales: quoting | `create_quote` ×1 |
| 9 | "Schedule a 2-hour meeting next Saturday at 2pm with client@acme.co." | sales: real calendar | `schedule_meeting` (real Google Calendar event) |
| 10 | **"A customer needs 8 Laptop Pro 14s and a color MFP under ¥800k — find options, build a quote with 10% off, and book a 2-hour follow-up next Saturday 2pm with client@acme.co."** | **chained sales flow (hero shot)** | `search_products` → `create_quote` → `schedule_meeting` |

**Talking points (for non-technical viewers):**
- #1–2: "I ask in plain English; the model decides *which* API to call, fills the
  arguments itself, and for the 3-city question fires **three calls at once**."
- #3: "Same skill, different domain — it's not scripted to weather; it picks the right tool."
- #4: "It chains a search and a file-write, and a real file lands on disk." (Open `demo/output/plan.txt`.)
- Close: "Every '🔧' line is the model choosing and calling a tool — no hard-coding."

## (Optional, high-impact) Base-vs-final before/after
Single GPU → do this **sequentially**, record as a separate clip.
```bash
# serve the stock base model instead, same flags
MODEL=Qwen/Qwen3-8B ./demo/serve_demo.sh      # or your local base path
```
Run prompt #2 on both. Expected contrast: **base** narrates / malforms / hallucinates
calls; **exp3** emits clean parallel calls and completes. This before/after is the
strongest single "wow" for the deck.

## Recording checklist (reliability first)
- [ ] Greedy decoding (temp 0, already set in `app.py`) → deterministic, rehearsable.
- [ ] Dry-run all 5 prompts once; confirm 🔧 lines + results render and `plan.txt` is created.
- [ ] Record the screen capture. **Present the recording**; go live only if rehearsal was flawless.
- [ ] Keep to single-shot prompts — do NOT improvise long multi-step requests (model's weak spot).
- [ ] Tools are hybrid: weather/currency are real (keyless) with canned fallbacks; search/email/
      calendar are deterministic stubs — so nothing fails on stage even without network.

## Notes
- Files: `demo/serve_demo.sh`, `demo/tools.py`, `demo/app.py`, output under `demo/output/`.
- Serve flags mirror `src/toolcall_lm/eval/taubench_runner.py` (proven for Qwen3 tool calling).
- If `--tool-call-parser hermes` ever mis-parses, the fallback is the FastAPI server
  (`scripts/serve.py`), but hermes is the validated path.
