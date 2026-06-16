"""Scoped tool-calling demo UI for the ToolCallLM model (exp3).

A small Gradio chat app that points the OpenAI client at our local vLLM server
and runs the tool-calling loop. It behaves like a **normal chatbot**: the model
answers in natural language using real tool results, and the raw tool calls are
tucked into a collapsible "tools used" panel below each answer (click to expand).

Run order:
  1. ./demo/serve_demo.sh                 # serves exp3 on :8765 (needs GPU free)
  2. .venv/bin/python demo/app.py         # opens the UI (needs `pip install gradio`)

Env:
  BASE_URL   default http://127.0.0.1:8765/v1
  MODEL      default exp3
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import gradio as gr
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tools import TOOLS, dispatch  # noqa: E402

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8765/v1")
MODEL = os.environ.get("MODEL", "exp3")
MAX_TOOL_ROUNDS = 4

client = OpenAI(base_url=BASE_URL, api_key="dummy")

SYSTEM_PROMPT = (
    "You are a sales assistant for an IT and office-equipment company, with access "
    "to tools for product lookup, quoting, scheduling, weather, currency and more. "
    f"Today's date is {date.today().isoformat()} ({date.today():%A}); resolve relative "
    "dates like 'next Saturday' to a concrete YYYY-MM-DD before scheduling. When a "
    "request needs a tool, call it directly — you may issue several tool calls in "
    "parallel when the request has independent parts. Do not narrate or describe the "
    "call; just call it. After tools return, give a short, friendly answer using the "
    "results."
)


def _fmt_args(arguments) -> str:
    try:
        d = json.loads(arguments) if isinstance(arguments, str) else (arguments or {})
        return ", ".join(f"{k}={v!r}" for k, v in d.items())
    except Exception:
        return str(arguments)


def _parse_xlam(content: str | None):
    """exp3 sometimes emits XLAM-style `[func(a=1, b='x'), ...]` as plain text
    instead of OpenAI tool_calls (the hermes parser misses that format). Parse it
    safely with `ast` — only literal arg values are evaluated, never code — so the
    chatbot can still execute the tools. Returns a list of (name, args_dict) or None.
    """
    if not content:
        return None
    text = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip().strip("`")
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        return None
    try:
        node = ast.parse(text[start:end + 1], mode="eval").body
    except SyntaxError:
        return None
    if not isinstance(node, ast.List):
        return None
    calls = []
    for el in node.elts:
        if isinstance(el, ast.Call) and isinstance(el.func, ast.Name):
            try:
                kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in el.keywords}
            except (ValueError, SyntaxError):
                continue
            calls.append((el.func.id, kwargs))
    return calls or None


def respond(user_msg: str, display: list, convo: list):
    """Generator: drives one user turn. Yields a natural-language answer plus a
    collapsible panel listing the tools that were called to produce it."""
    user_msg = (user_msg or "").strip()
    display = list(display or [])   # Chatbot value can be None on first turn
    if not user_msg:
        yield display, convo, ""
        return

    if not convo:
        convo = [{"role": "system", "content": SYSTEM_PROMPT}]
    convo.append({"role": "user", "content": user_msg})
    display = display + [{"role": "user", "content": user_msg}]
    # Live "working" indicator (collapsible, shows a spinner) while tools run.
    status = {"role": "assistant", "content": "_calling tools…_",
              "metadata": {"title": " Working", "status": "pending"}}
    yield display + [status], convo, ""

    tool_log: list[tuple[str, str, str]] = []   # (name, fmt_args, result)
    answer = None
    for _ in range(MAX_TOOL_ROUNDS):
        try:
            resp = client.chat.completions.create(
                model=MODEL, messages=convo, tools=TOOLS,
                tool_choice="auto", temperature=0.0,
            )
        except Exception as e:  # noqa: BLE001
            answer = f"⚠️ server error: {e}"
            break

        msg = resp.choices[0].message

        # Normalise tool calls: native OpenAI tool_calls, else XLAM-in-content.
        if msg.tool_calls:
            calls = [(tc.id, tc.function.name, tc.function.arguments)
                     for tc in msg.tool_calls]
        else:
            parsed = _parse_xlam(msg.content)
            calls = [(f"call_{len(tool_log) + i}", name, json.dumps(args))
                     for i, (name, args) in enumerate(parsed)] if parsed else []

        if not calls:   # model answered in natural language → done
            answer = (msg.content or "").strip() or "(no response)"
            break

        # Well-formed assistant turn so the follow-up tool messages are valid.
        convo.append({"role": "assistant", "content": None, "tool_calls": [
            {"id": cid, "type": "function",
             "function": {"name": name, "arguments": args}}
            for cid, name, args in calls]})
        for cid, name, args in calls:
            result = dispatch(name, args)
            tool_log.append((name, _fmt_args(args), result))
            convo.append({"role": "tool", "tool_call_id": cid, "content": result})

        running = "\n".join(f"• `{n}({a})`" for n, a, _ in tool_log)
        status = {"role": "assistant", "content": running,
                  "metadata": {"title": f" Ran {len(tool_log)} tool(s)…",
                               "status": "pending"}}
        yield display + [status], convo, ""
    else:
        answer = answer or "⚠️ stopped after max tool rounds."

    # Final render: natural-language answer + one collapsible tool panel below it.
    msgs = display + [{"role": "assistant", "content": answer}]
    if tool_log:
        detail = "\n\n".join(
            f"**{i}. `{n}({a})`**\n\n→ {r}"
            for i, (n, a, r) in enumerate(tool_log, 1))
        msgs.append({"role": "assistant", "content": detail,
                     "metadata": {"title": f" {len(tool_log)} tool call(s) — show details"}})
    yield msgs, convo, ""


EXAMPLES = [
    "Find laptops under ¥200,000 and tell me the best one.",
    "What are the specs and price of the Color MFP 3000?",
    "Quote 8 Laptop Pro 14s and one Color MFP 3000 with a 10% discount for Acme Corp.",
    "Schedule a 2-hour meeting next Saturday at 2pm with client@acme.co.",
    "A customer needs 8 Laptop Pro 14s and a color MFP under ¥800k — find options, "
    "build a quote with 10% off, and book a 2-hour follow-up next Saturday 2pm with "
    "client@acme.co.",
]


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="ToolCallLM — Tool-Calling Demo", fill_height=True) as ui:
        gr.Markdown(f"##  ToolCallLM live demo — `{MODEL}`\n"
                    "Ask in natural language. The model uses real tools behind the "
                    "scenes and answers conversationally — expand ** tool call(s)** "
                    "under any reply to see exactly what it called.")
        chatbot = gr.Chatbot(value=[], height=460, show_label=False)
        convo = gr.State([])
        with gr.Row():
            box = gr.Textbox(placeholder="Ask something that needs a tool…",
                             scale=8, show_label=False, autofocus=True)
            send = gr.Button("Send", variant="primary", scale=1)
        gr.Examples(EXAMPLES, inputs=box, label="Try one (showcases single + parallel calls)")
        clear = gr.Button("Clear")

        send.click(respond, [box, chatbot, convo], [chatbot, convo, box])
        box.submit(respond, [box, chatbot, convo], [chatbot, convo, box])
        clear.click(lambda: ([], [], ""), None, [chatbot, convo, box])
    return ui


if __name__ == "__main__":
    # Bind to localhost by default; set UI_HOST=0.0.0.0 only when you knowingly
    # want it reachable from the network (the create_file tool writes files).
    build_ui().launch(
        server_name=os.environ.get("UI_HOST", "127.0.0.1"),
        server_port=int(os.environ.get("UI_PORT", 7860)),
    )
