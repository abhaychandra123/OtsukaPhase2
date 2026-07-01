"""The planner's capabilities: one per grounding source, plus the terminal document
producer. Every one is a THIN adapter over logic that already exists — no retrieval,
scoring, or rendering is reimplemented here. This is the whole point of the
capability graph: the planner selects *which* of these run; the engine runs them;
their Evidence lands in one bundle; the Documents capability consumes that bundle.

    conversation ─┐
    workspace ────┤
    crm ──────────┼──►  documents   (depends on all gathered; authors the artifact)
    knowledge ────┤
    web ──────────┘

Gather capabilities emit a uniform `{"text": <grounding>, "label": <section>}` so the
Documents capability can concatenate them into one grounding block regardless of
which were selected. All are READ/SEARCH and degrade to empty — never raise.
"""
from __future__ import annotations

from typing import Any, Mapping

from senpai.orchestration import ExecContext
from senpai.orchestration.evidence import Evidence
from senpai.orchestration.metadata import CapabilityMetadata, OperationKind

# Section-header labels mirror the doc tools' inline grounding blocks, so a deck
# authored via the planner reads identically to one authored via generate_pptx.
_LABELS = {
    "conversation": "これまでの会話・確定済みの文脈",
    "workspace": "ローカル文書（あなたのファイル）",
    "crm": "社内データ",
    "knowledge": "社内ナレッジ",
    "web": "Web検索",
}


def _text_evidence(name: str, text: str, citations=()) -> Evidence:
    text = (text or "").strip()
    if not text:
        return Evidence.empty(provenance={"capability": name})
    return Evidence.ok({"text": text, "label": _LABELS.get(name, name)},
                       citations=tuple(citations), status="ok")


class ConversationCapability:
    """Grounding from the live session — a company/quote/deal already discussed.
    Reuses the doc tools' own `_conversation_grounding` over the published convo."""
    name = "conversation"
    metadata = CapabilityMetadata(OperationKind.READ)

    def run(self, op: str, inputs: Mapping[str, Any], ctx: ExecContext) -> Evidence:
        from senpai.tools.impl import _conversation_grounding
        text = _conversation_grounding(str(inputs.get("query", "")))
        ctx.emit("会話文脈あり" if text else "会話文脈なし")
        return _text_evidence("conversation", text)


class WorkspaceCapability:
    """Relevant LOCAL documents (sandboxed, read-only). Reuses the doc tools'
    relevance-gated `_workspace_grounding`, which runs the real find→extract."""
    name = "workspace"
    metadata = CapabilityMetadata(OperationKind.SEARCH, max_concurrency=4)

    def run(self, op: str, inputs: Mapping[str, Any], ctx: ExecContext) -> Evidence:
        from senpai.tools.impl import _workspace_grounding
        text = _workspace_grounding(str(inputs.get("query", "")))
        ctx.emit("該当文書あり" if text else "該当文書なし")
        # Citations are the file provenance already embedded in the text ("出典: file://…").
        return _text_evidence("workspace", text)


class CRMCapability:
    """Internal SPR records for the resolved deal/customer. Reuses `impl.query_spr`."""
    name = "crm"
    metadata = CapabilityMetadata(OperationKind.READ, cacheable=True)

    def run(self, op: str, inputs: Mapping[str, Any], ctx: ExecContext) -> Evidence:
        from senpai.tools.impl import query_spr
        deal_id = str(inputs.get("deal_id") or "")
        customer_id = str(inputs.get("customer_id") or "")
        if deal_id:
            text, cite = query_spr(deal_id=deal_id), f"SPR {deal_id}"
        elif customer_id:
            text, cite = query_spr(customer=customer_id), f"SPR {customer_id}"
        else:
            return Evidence.empty(provenance={"capability": "crm"})
        ctx.emit("社内記録を取得")
        return _text_evidence("crm", text, citations=[cite])


class KnowledgeCapability:
    """Validated playbook / approved coaching knowledge for the goal. Reuses
    `impl.search_knowledge` (attributed, cited snippets)."""
    name = "knowledge"
    metadata = CapabilityMetadata(OperationKind.SEARCH, cacheable=True)

    def run(self, op: str, inputs: Mapping[str, Any], ctx: ExecContext) -> Evidence:
        from senpai.tools.impl import search_knowledge
        text = search_knowledge(query=str(inputs.get("query", "")), limit=3)
        if "見つかりません" in text:
            return Evidence.empty(provenance={"capability": "knowledge"})
        ctx.emit("社内ナレッジを取得")
        return _text_evidence("knowledge", text)


class WebCapability:
    """External web search for factual/current topics. Reuses `impl.web_search`."""
    name = "web"
    metadata = CapabilityMetadata(OperationKind.SEARCH, max_concurrency=4, retries=1)

    def run(self, op: str, inputs: Mapping[str, Any], ctx: ExecContext) -> Evidence:
        from senpai.tools.impl import web_search
        try:
            text = web_search(query=str(inputs.get("query", "")))
        except Exception as e:  # noqa: BLE001 — web is best-effort grounding
            return Evidence.empty(provenance={"capability": "web", "error": str(e)})
        ctx.emit("Web検索を実施")
        return _text_evidence("web", text)


# Order gathered grounding lands in the document, most-specific first.
_GATHER_ORDER = ("conversation", "workspace", "crm", "knowledge", "web")


class DocumentsCapability:
    """The terminal producer: consume the gathered EvidenceBundle (via ctx.deps),
    assemble one grounding block, and author + render + register the artifact —
    reusing the existing author/proposal/render/registry logic. `op` is the doc kind
    (proposal | pptx | docx). This capability does NOT re-gather: its grounding is
    exactly what the selected capabilities put in the bundle."""
    name = "documents"
    metadata = CapabilityMetadata(OperationKind.WRITE, parallel_safe=False,
                                  idempotent=False, retries=0)

    def run(self, op: str, inputs: Mapping[str, Any], ctx: ExecContext) -> Evidence:
        kind = op or "pptx"
        if kind == "proposal":
            return self._proposal(inputs, ctx)
        return self._authored(kind, inputs, ctx)

    # -- grounding assembled from the bundle (not re-gathered) -------------------
    def _grounding(self, ctx: ExecContext) -> str:
        by_cap = {ev.capability: ev for ev in ctx.deps.values()}
        blocks = []
        for cap in _GATHER_ORDER:
            ev = by_cap.get(cap)
            if ev and ev.status in ("ok", "partial") and ev.data.get("text"):
                blocks.append(f"【{ev.data.get('label', cap)}】\n{ev.data['text']}")
        return "\n\n".join(blocks)

    def _citations(self, ctx: ExecContext) -> list[str]:
        cites: list[str] = []
        for ev in ctx.deps.values():
            cites.extend(ev.citations)
        return cites

    # -- proposal: deal-scoped, deterministic (GPU-free) ------------------------
    def _proposal(self, inputs: Mapping[str, Any], ctx: ExecContext) -> Evidence:
        from senpai.documents import proposal, registry
        deal_id = str(inputs.get("deal_id") or "")
        if not deal_id:
            return Evidence.error("proposal requires a deal_id",
                                  provenance={"capability": "documents"})
        res = proposal.generate(deal_id, lang=str(inputs.get("lang", "ja")))
        if res is None:
            return Evidence.error(f"deal {deal_id} not found",
                                  provenance={"capability": "documents"})
        path, _pctx, spec = res
        rec = registry.register("proposal", path, deal_id=deal_id)
        ctx.emit(f"提案書を生成: {rec['filename']}")
        return self._artifact_evidence(rec, ctx,
                                       f"提案書(PPTX)を生成しました: {rec['filename']}")

    # -- pptx/docx: free-prompt, authored over the gathered grounding -----------
    def _authored(self, kind: str, inputs: Mapping[str, Any], ctx: ExecContext) -> Evidence:
        from senpai.documents import author, registry
        from senpai.documents.render import output_path, render_docx, render_pptx
        goal = str(inputs.get("goal") or inputs.get("prompt") or "")
        lang = str(inputs.get("lang", "ja"))
        grounding = self._grounding(ctx)
        if not author._use_llm():
            return Evidence.error("model required for pptx/docx authoring",
                                  provenance={"capability": "documents", "kind": kind})
        if kind == "docx":
            spec = author.author_doc(goal, grounding=grounding, lang=lang)
            if spec is None:
                return Evidence.error("author unavailable",
                                      provenance={"capability": "documents"})
            path = output_path("docx", spec.get("_title") or goal[:30], "docx")
            render_docx(spec, path)
            rec = registry.register("docx", path)
            n = len(spec.get("sections", []))
            msg = f"文書(DOCX)を生成しました: {rec['filename']}（{n}セクション）。"
        else:
            spec = author.author_deck(goal, grounding=grounding, lang=lang)
            if spec is None:
                return Evidence.error("author unavailable",
                                      provenance={"capability": "documents"})
            path = output_path("pptx", spec.get("_title") or goal[:30], "pptx")
            render_pptx(spec, path)
            rec = registry.register("pptx", path)
            n = len(spec.get("slides", []))
            msg = f"プレゼン(PPTX)を生成しました: {rec['filename']}（{n}スライド）。"
        ctx.emit(f"資料を生成: {rec['filename']}")
        return self._artifact_evidence(rec, ctx, msg)

    def _artifact_evidence(self, rec: dict, ctx: ExecContext, msg: str) -> Evidence:
        document = {"doc_id": rec["doc_id"], "kind": rec["kind"],
                    "filename": rec["filename"], "download_url": rec["download_url"]}
        return Evidence.ok(
            {"text": msg, "document": document, "grounded_on": sorted(
                ev.capability for ev in ctx.deps.values()
                if ev.status in ("ok", "partial") and ev.data.get("text"))},
            citations=[*self._citations(ctx), f"doc://{rec['doc_id']}"], status="ok")


def build_registry():
    """A registry with all planner capabilities, ready for the ExecutionEngine."""
    from senpai.orchestration import CapabilityRegistry
    reg = CapabilityRegistry()
    for cap in (ConversationCapability(), WorkspaceCapability(), CRMCapability(),
                KnowledgeCapability(), WebCapability(), DocumentsCapability()):
        reg.register(cap)
    return reg
