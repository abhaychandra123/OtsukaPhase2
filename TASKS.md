# Senpai — Task Checklist

> Living tracker for the Senpai deal-health copilot. Check items off as they land;
> add new features/ideas under **Backlog** and promote them to **In progress** when started.
> Keep this honest — only tick a box when it's actually done and verified.
>
> Last updated: 2026-06-23 (added morning briefing; logged sales-assist feature backlog)

---

## ✅ Done

### Data
- [x] Generate large multi-year synthetic dataset in the real SPR schema (150 customers,
      520 deals, FY2023–2026) for demo/training. Regen via `senpai/data/gen_seed.py`.
- [x] Preserve test/demo anchors (D001/村田印刷, C28/松田, R05/伊藤翔, Aozora-unique /
      Yamato-ambiguous aliases).
- [x] Keep seed JSON byte-stable & committed; `_fy()` Japanese fiscal-year helper.
- [x] Move `rank_history` out of `Schema.md` into a separate supplementary file
      (Schema.md reverted to ground truth).

### Hybrid retrieval (Phase 1)
- [x] `senpai/retrieval/semantic.py` — BM25 (rank_bm25) + dense embeddings (fastembed/ONNX, CPU)
      fused via Reciprocal Rank Fusion (RRF).
- [x] Japanese tokenization: Janome with POS filtering + stopword/suffix/lone-hiragana removal.
- [x] `senpai/retrieval/build_index.py` — precompute + commit corpus vectors
      (`data/index/*.npy/.meta.json/.tokens.json/manifest.json`), byte-stable.
- [x] Optional-with-fallback: dense → BM25 → keyword degrade (mirrors `SENPAI_USE_LLM`).
- [x] New `search_notes` tool wired into `tools/impl.py` + `schemas.py` + role sets.
- [x] `retrieve_playbook` upgraded to rank via semantic internally (same signature/return).
- [x] Retrieval config in `config.py` (`EMBED_MODEL`, `RRF_K`, `BM25_WEIGHT`, `DENSE_WEIGHT`, …).
- [x] Stress harness `scripts/stress_retrieval.py` (19/19 checks passing); fixed 3 fusion bugs
      (duplicate flooding, zero-score BM25 noise, JA function-word pollution).
- [x] Tests `tests/test_semantic.py` (hermetic BM25 default; dense gated by `SENPAI_TEST_DENSE`).

### Knowledge graph (Phase 2)
- [x] `senpai/graph/build.py` — networkx MultiDiGraph (customer→deal→activity→rep→product),
      built from the store at runtime.
- [x] `senpai/graph/query.py` — `reps_who_win` / `account_graph` / `connections` / `similar_by_graph`.
- [x] New `query_graph` tool wired into tools + role sets.
- [x] Tests `tests/test_graph.py`.

### Multimodal ingestion (prototype)
- [x] Review/verify the standalone ingestion prototype (`senpai/ingestion/multimodal.py`).
- [x] Wire it to Groq's free tier (Whisper STT + vision OCR + LLM structuring → pydantic
      `ActivityExtraction`).
- [x] Ingestion config in `config.py` (`INGEST_*`, `have_multimodal()`); load both repo-root
      `.env` and `senpai/.env`.
- [x] Verified end-to-end on Groq (real text structuring + real image OCR); 76 tests still pass.
- [x] Integration brief `docs/ingestion_integration_prompt.md` for wiring ingestion into the
      main pipeline later.

### Sales-assist features
- [x] **Morning briefing / next-best-action** (`senpai/briefing.py`) — per-rep (or team)
      prioritized worklist: open deals ranked by urgency × value, one concrete next action each,
      plus a predictive cadence nudge before a deal goes yellow. Exposed as the `morning_briefing`
      tool (junior + manager role sets); tests in `tests/test_briefing.py`.

### Docs
- [x] `docs/retrieval.md`, `docs/synthetic_dataset.md`, updated `senpai/README.md`.

---

## 🔜 To do — multimodal ingestion integration
> Tracked in detail in `docs/ingestion_integration_prompt.md`. Deferred by user until §7 filled in.

- [ ] Consolidate to ONE ingestion module; delete `pipeline.py` + duplicate `ActivityExtraction`.
- [ ] Add a real persistence path: `store.add_activity(record)` → writes disk + `reload()`.
- [ ] Decide persistence target (recommended: separate `data/ingested/` overlay, keep seed pristine).
- [ ] Keep the retrieval index in sync after a write (auto-reindex or documented manual step).
- [ ] Fix field bugs: JA fiscal quarter via `_fy()`, rep-resolved `sales_info`, drop bogus
      `opportunity_id`.
- [ ] Add `pydantic` to `requirements.txt`.
- [ ] Add hermetic `tests/test_ingestion.py` (mock the API).
- [ ] Fill in §7 of the integration brief (surface, attribution, persistence, reindex, provider).

---

## 🧹 Housekeeping / not yet committed
- [ ] Commit the accumulated work (retrieval + dataset + ingestion/Groq wiring + docs).
      Exclude external (non-mine) changes; never commit `.env` / `senpai/.env` (Groq secret).

---

## 💡 Backlog / future ideas

### Sales-assist features (make the rep's day easier)
- [ ] **Meeting-prep brief (one-pager)** — before a customer visit, auto-assemble account health,
      open deals + ranks, last interactions, unresolved `customer_challenge`s, expansion
      opportunities, and suggested talking points + likely objections.
      *Reuses:* `account/context.py`, `account/expansion.py`, `search_notes`, `coach/cases.py`,
      `matsuda/synthesize.py`.
- [ ] **Win-probability + pipeline forecast** — calibrated close-probability per deal from
      historical win-rates by `order_rank`/category/rep (graph already computes win-rates);
      roll up to expected-revenue forecast for the manager dashboard.
      *Reuses:* `graph/query.py:reps_who_win`, order/deal data.
- [ ] **Commitment / action-item extraction** — parse daily reports for promises (見積もり送付,
      予算確認後に連絡…) → tracked follow-ups with due dates. Pairs with the ingestion work
      (a voice note becomes an activity *and* a task).
- [ ] **Competitive battlecard** — when `COMPETITION_LEXICON` fires on a deal, surface which reps
      beat that competitor, the winning playbook, and similar won cases.
      *Reuses:* `query_graph`, `retrieve_playbook`, `coach/cases.py`.
- [ ] Surface the morning briefing in the UI (a Streamlit "Today" page / Home widget), not just
      the chat tool.

### Retrieval / graph polish
- [ ] Phase 2b: GraphRAG community summaries (Louvain/greedy-modularity → per-cluster LLM summary
      → retrieve over summaries) for fuzzy global questions. Documented, not built.
- [ ] Optional cross-encoder reranker (`SENPAI_USE_RERANKER`, currently off).
- [ ] Blend `similar_by_graph` into `find_similar_deals` for richer matches.
- [ ] Have `coach/context.py` pull semantically-relevant recent activities (not just newest-first).

- [ ] _(add new feature ideas here as they come up)_
