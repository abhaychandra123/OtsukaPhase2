"""Manager assistant (Gradio) — ask the pipeline, in chat form.

A separate, self-contained chat for sales managers. Same exp3 tool loop as the
junior chat, but scoped to MANAGER_TOOLS: team risk, report digests, coaching
focus, drafting, and web_search. Every answer is grounded in the deterministic
store/scoring engine — the model phrases, it never invents numbers. The manager
dashboard is untouched; this runs on its own port.

Run:
  1. scripts/serve_model.sh                     # exp3 on :8765 (needs GPU)
  2. .venv/bin/python senpai/apps/manager_chat.py   # opens UI on :7861
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

# Run directly, so the repo root isn't on sys.path by default — add it so
# `import senpai` resolves (apps → senpai → repo root).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import gradio as gr

from senpai import config
from senpai.llm.client import stream_turn
from senpai.tools.schemas import MANAGER_TOOLS

SYSTEM_PROMPT = (
    "あなたは大塚商会の営業マネージャーを支えるアシスタントです。"
    "チーム全体の案件健全度・日報・パイプラインを把握し、リスクの高い案件や"
    "コーチングが必要な担当を、必ずツールで取得した社内データに基づいて示します。"
    "数字は与えられたものだけを使い、創作しないこと。外部情報が必要な時は "
    "web_search を使ってください。ツールが不要な一般的な質問には、そのまま"
    "簡潔に日本語で答えて構いません。"
    f"本日は {date.today().isoformat()} です。"
)

EXAMPLES = [
    "今週リスクが高い案件を担当別にまとめて",
    "チーム全体のパイプライン状況を教えて",
    "全員の日報を要約して、問題のある案件を挙げて",
    "コーチングが必要な担当は誰？",
    "伊藤さんにD003の進捗確認メッセージを下書きして",
    "製造業の最近のIT投資動向を調べて",
]


def _fmt_args(arguments) -> str:
    import json
    try:
        d = json.loads(arguments) if isinstance(arguments, str) else (arguments or {})
        return ", ".join(f"{k}={v!r}" for k, v in d.items())
    except Exception:
        return str(arguments)


def respond(user_msg: str, display: list, convo: list):
    """One manager turn; yields a natural-language answer plus a collapsible
    panel of the tools that produced it (same shape as junior_chat)."""
    user_msg = (user_msg or "").strip()
    display = list(display or [])
    if not user_msg:
        yield display, convo, ""
        return

    if not convo:
        convo = [{"role": "system", "content": SYSTEM_PROMPT}]
    convo.append({"role": "user", "content": user_msg})
    display = display + [{"role": "user", "content": user_msg}]
    status = {"role": "assistant", "content": "_ツールを実行中…_",
              "metadata": {"title": "⏳ Working", "status": "pending"}}
    yield display + [status], convo, ""

    tool_log, answer = [], None
    for tool_log, answer in stream_turn(convo, tools=MANAGER_TOOLS):
        if answer is None:
            running = "\n".join(f"• `{n}({a})`" for n, a, _ in tool_log)
            status = {"role": "assistant", "content": running,
                      "metadata": {"title": f"🔧 Ran {len(tool_log)} tool(s)…",
                                   "status": "pending"}}
            yield display + [status], convo, ""

    msgs = display + [{"role": "assistant", "content": answer}]
    if tool_log:
        detail = "\n\n".join(f"**{i}. `{n}({a})`**\n\n→ {r}"
                             for i, (n, a, r) in enumerate(tool_log, 1))
        msgs.append({"role": "assistant", "content": detail,
                     "metadata": {"title": f"🔧 {len(tool_log)} tool call(s) — show details"}})
    yield msgs, convo, ""


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="Senpai — Manager Assistant", fill_height=True) as ui:
        gr.Markdown(f"## 📊 Senpai — manager assistant — `{config.MODEL}`\n"
                    "チームの案件・日報について自然な日本語で質問してください。"
                    "リスクの高い案件、日報のダイジェスト、コーチング優先度などを、"
                    "社内データに基づいて返します。各回答の下の **tool call(s)** を"
                    "開くと、実際に呼び出したツールが確認できます。")
        chatbot = gr.Chatbot(value=[], height=460, show_label=False)
        convo = gr.State([])
        with gr.Row():
            box = gr.Textbox(placeholder="例: 今週リスクが高い案件を担当別にまとめて",
                             scale=8, show_label=False, autofocus=True)
            send = gr.Button("送信", variant="primary", scale=1)
        gr.Examples(EXAMPLES, inputs=box, label="例を試す")
        clear = gr.Button("クリア")

        send.click(respond, [box, chatbot, convo], [chatbot, convo, box])
        box.submit(respond, [box, chatbot, convo], [chatbot, convo, box])
        clear.click(lambda: ([], [], ""), None, [chatbot, convo, box])
    return ui


if __name__ == "__main__":
    build_ui().launch(
        server_name=os.environ.get("UI_HOST", "127.0.0.1"),
        server_port=int(os.environ.get("UI_PORT", 7861)),
    )
