"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, Send } from "lucide-react";
import { chatStream, type ChatEvent, type ChatRole, type ChatTurn, type ResolveCandidate } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { useCachedState, useCachedConversationId } from "@/lib/chat-store";
import { MessageBubble, type Msg } from "@/components/assistant/message";

// Role/lang-scoped example prompts (content, so kept here rather than i18n keys).
const EXAMPLES: Record<"junior" | "manager", Record<"ja" | "en", string[]>> = {
  junior: {
    ja: [
      "お客様が値引きを要求。先輩の原則ではどう対応すべき？",
      "アクメ商事について教えて",
      "カラー複合機3000を3台で見積を作って（アクメ商事向け、10%値引き）",
      "D001の健全度を見て",
    ],
    en: [
      "The customer wants a discount. What do the senior principles say?",
      "Tell me about Acme",
      "Build a quote for 3× Color MFP 3000 for Acme, 10% off",
      "Check the health of deal D001",
    ],
  },
  manager: {
    ja: [
      "今週リスクが高い案件を担当別にまとめて",
      "チーム全体のパイプライン状況を教えて",
      "値引き要求への対応、メンバーにどう指導すべき？",
    ],
    en: [
      "Summarize this week's at-risk deals by rep",
      "Show me the team pipeline overview",
      "How should I coach the team on discount requests?",
    ],
  },
};

export function AssistantChat({ role }: { role: "junior" | "manager" }) {
  const { t, lang } = useT();
  // Transcript is cached per role so it survives switching tabs (e.g. to Review
  // Coach) and back, instead of being thrown away when the route unmounts.
  const [messages, setMessages] = useCachedState<Msg[]>(`assistant:${role}:messages`, []);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [model, setModel] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  // One conversation id per chat session, so the backend can keep the account in
  // focus across turns ("what should I do next?" stays scoped to this customer).
  // Persisted alongside the transcript so the account stays in focus across tabs.
  const convId = useCachedConversationId(`assistant:${role}:convId`);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  // A stream started before a tab switch keeps writing to the external store, so
  // on remount the trailing message may still be "running" — and will finish on
  // its own. Treat that as busy so we don't start a second turn over it.
  const streaming = messages.length > 0 && messages[messages.length - 1].status === "running";

  function stop() {
    abortRef.current?.abort();
  }

  async function send(text: string) {
    const msg = text.trim();
    if (!msg || busy || streaming) return;
    setInput("");
    setBusy(true);

    // History = completed turns only (the API prepends its own system prompt).
    const history: ChatTurn[] = messages
      .filter((m) => m.content && m.status !== "error")
      .map((m) => ({ role: m.role, content: m.content }));

    setMessages((prev) => [
      ...prev,
      { role: "user", content: msg, tools: [] },
      { role: "assistant", content: "", tools: [], status: "running" },
    ]);

    // Mutate the trailing assistant message as events stream in.
    const patch = (fn: (m: Msg) => Msg) =>
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = fn(next[next.length - 1]);
        return next;
      });

    const ctrl = new AbortController();
    abortRef.current = ctrl;
    let answered = false;
    await chatStream(msg, history, role as ChatRole, (e: ChatEvent) => {
      switch (e.type) {
        case "start":
          if (e.model) setModel(e.model);
          if (e.role === "research") patch((m) => ({ ...m, research: true, sources: [] }));
          break;
        case "tool":
          patch((m) => ({
            ...m,
            tools: [...m.tools, { name: e.name, args: e.args, result: e.result }],
            retrieval: e.retrieval ? [...(m.retrieval ?? []), ...e.retrieval] : m.retrieval,
          }));
          break;
        case "source":
          patch((m) => ({
            ...m,
            research: true,
            sources: [
              ...(m.sources ?? []).filter((s) => s.key !== e.key),
              { key: e.key, label: e.label, status: e.status, count: e.count, detail: e.detail },
            ],
          }));
          break;
        case "web":
          patch((m) => ({
            ...m,
            webUrls: (e.results ?? [])
              .filter((r) => r.url)
              .map((r) => ({ title: r.title, url: r.url })),
          }));
          break;
        case "routing":
          patch((m) => ({ ...m, routing: { think: e.think, reason: e.reason, confidence: e.confidence, mode: e.mode } }));
          break;
        case "resolve":
          if (e.status === "ambiguous" && e.candidates?.length) {
            patch((m) => ({ ...m, candidates: e.candidates, query: e.query }));
          }
          break;
        case "delta":
          answered = true;
          patch((m) => ({ ...m, content: m.content + e.text, status: "running" }));
          break;
        case "answer":
          answered = true;
          patch((m) => ({ ...m, content: e.text || m.content, status: "done" }));
          break;
        case "done":
          if (e.model) setModel(e.model);
          patch((m) => (m.status === "running" && m.content ? { ...m, status: "done" } : m));
          break;
        case "unavailable":
        case "error":
          patch((m) => ({ ...m, status: "error" }));
          break;
      }
    }, { signal: ctrl.signal, conversationId: convId.current });

    // Stream ended without an answer → surface a clear error.
    patch((m) => (m.status === "running" || (!answered && !m.content)
      ? { ...m, status: m.content ? "done" : "error" } : { ...m, status: m.status ?? "done" }));
    abortRef.current = null;
    setBusy(false);
  }

  return (
    <div className="space-y-5">
      <header className="space-y-1.5">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-semibold tracking-tight">{t(`assistant.title.${role}`)}</h1>
          {model && (
            <span className="rounded-full bg-muted px-2 py-0.5 font-mono text-[10.5px] text-muted-foreground">
              {model}
            </span>
          )}
        </div>
        <p className="max-w-3xl text-[13.5px] leading-relaxed text-muted-foreground">
          {t(`assistant.lead.${role}`)}
        </p>
      </header>

      {/* Conversation */}
      <div
        ref={scrollRef}
        className="max-h-[56vh] min-h-[220px] space-y-4 overflow-y-auto rounded-xl border border-border bg-card p-4"
      >
        {messages.length === 0 ? (
          <p className="py-10 text-center text-[13px] text-muted-foreground">{t("assistant.empty")}</p>
        ) : (
          messages.map((m, i) => (
            <MessageBubble
              key={i} m={m} t={t} lang={lang}
              onPick={(c) => send(`${c.name}：${m.query ?? input}`)}
            />
          ))
        )}
      </div>

      {/* Examples */}
      <div className="flex flex-wrap gap-2">
        <span className="self-center text-[11.5px] font-medium text-muted-foreground">
          {t("assistant.examplesLabel")}:
        </span>
        {EXAMPLES[role][lang].map((ex) => (
          <button
            key={ex}
            onClick={() => send(ex)}
            disabled={busy || streaming}
            className="rounded-full border border-border bg-card px-3 py-1 text-[12px] text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground disabled:opacity-50"
          >
            {ex}
          </button>
        ))}
      </div>

      {/* Composer */}
      <form
        onSubmit={(e) => { e.preventDefault(); send(input); }}
        className="flex items-end gap-2"
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); }
          }}
          rows={1}
          placeholder={t("assistant.placeholder")}
          className="min-h-[44px] flex-1 resize-none rounded-lg border border-border bg-background px-3.5 py-2.5 text-[14px] outline-none focus:border-primary/50"
        />
        {busy ? (
          <button
            type="button"
            onClick={stop}
            className="inline-flex h-[44px] items-center gap-1.5 rounded-lg border border-border bg-card px-4 text-[13px] font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            <Loader2 className="h-4 w-4 animate-spin" /> {t("assistant.stop")}
          </button>
        ) : (
          <button
            type="submit"
            disabled={!input.trim() || streaming}
            className="inline-flex h-[44px] items-center gap-1.5 rounded-lg bg-primary px-4 text-[13px] font-medium text-primary-foreground transition-opacity disabled:opacity-50"
          >
            <Send className="h-4 w-4" /> {t("assistant.send")}
          </button>
        )}
        {messages.length > 0 && (
          <button
            type="button"
            onClick={() => { setMessages([]); setInput(""); convId.reset(); }}
            disabled={busy || streaming}
            className="h-[44px] rounded-lg border border-border bg-card px-3 text-[13px] font-medium text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
          >
            {t("assistant.clear")}
          </button>
        )}
      </form>
    </div>
  );
}
