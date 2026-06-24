"use client";

// Shared "Experience" surface for a review: real past deals that rhyme with the
// current note (each carrying its outcome + the validated principle it teaches)
// plus the principles most relevant to the note. Extracted so the unified
// Workspace review keeps the Experience pillar and principle grounding the
// standalone Review Coach had. Deterministic: cases come from the store
// (find_similar_cases); principles are approved, interview-traceable knowledge —
// never invented advice.

import { useEffect, useState } from "react";
import { Award, ChevronDown, History, Lightbulb, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import type { Principle, SimilarCase } from "@/lib/types";
import { cn, formatYen } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { PRINCIPLE_KEYWORDS, customerText, productCategoryText, principleText } from "@/lib/content-i18n";
import { Badge } from "@/components/ui/badge";

export function relevantPrinciples(note: string, principles: Principle[], max = 3): Principle[] {
  const scored = principles.map((p) => {
    const kws = PRINCIPLE_KEYWORDS[p.principle_id] ?? [];
    let score = kws.reduce((s, k) => (note.includes(k) ? s + 1 : s), 0);
    score += p.tags.reduce((s, tg) => (note.includes(tg) ? s + 1 : s), 0);
    if (p.n_interviews >= 2) score += 0.5;
    return { p, score };
  });
  const hits = scored.filter((s) => s.score >= 1).sort((a, b) => b.score - a.score);
  const pool = hits.length
    ? hits
    : scored
        .filter((s) => s.p.status === "approved" && s.p.n_interviews >= 2)
        .sort((a, b) => b.score - a.score);
  return pool.slice(0, max).map((s) => s.p);
}

function CaseCard({ c, principles }: { c: SimilarCase; principles: Principle[] }) {
  const { t, lang } = useT();
  const won = c.outcome === "won";
  const lessons = c.principle_ids
    .map((id) => principles.find((p) => p.principle_id === id))
    .filter((p): p is Principle => Boolean(p));
  return (
    <div className={cn(
      "overflow-hidden rounded-xl border bg-card shadow-[0_1px_2px_rgba(16,24,40,0.04)]",
      won ? "border-conf-high/30" : "border-band-red/30",
    )}>
      <div className={cn(
        "flex items-center justify-between gap-2 px-4 py-2.5",
        won ? "bg-conf-high/[0.06]" : "bg-band-red/[0.05]",
      )}>
        <span className="flex items-center gap-2">
          <span className={cn(
            "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold",
            won ? "bg-conf-high/15 text-conf-high" : "bg-band-red/15 text-band-red",
          )}>
            {won ? <Award className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
            {won ? t("chat.caseWon") : t("chat.caseLost")}
          </span>
          <span className="font-mono text-[10px] text-muted-foreground">{c.deal_id}</span>
        </span>
        <span className="text-[11px] text-muted-foreground">{formatYen(c.amount)}</span>
      </div>
      <div className="px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-jp text-[13px] font-medium text-foreground">{customerText(lang, c.customer).text}</span>
          <Badge variant="default">{productCategoryText(lang, c.product_category).text}</Badge>
        </div>
        <p className={cn("mt-1.5 text-[13px] leading-snug text-foreground/85", lang === "ja" && "font-jp")}>
          {t(`chat.caseTheme.${c.theme}`)}
        </p>
        {lessons.length > 0 && (
          <div className="mt-3 border-t border-border pt-2.5">
            <div className="eyebrow mb-1.5 flex items-center gap-1"><Lightbulb className="h-3 w-3" /> {t("chat.caseLessons")}</div>
            <ul className="space-y-1.5">
              {lessons.map((p) => (
                <li key={p.principle_id} className="flex gap-2">
                  <span className="mt-[3px] font-mono text-[10px] text-muted-foreground">{p.principle_id}</span>
                  <span className="flex-1 text-[12.5px] leading-snug text-foreground/85">
                    {principleText(lang, p).text}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

function Dots() {
  return (
    <span className="flex gap-1">
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.3s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.15s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary" />
    </span>
  );
}

function SimilarCasesList({ note, dealId, principles }: { note: string; dealId?: string; principles: Principle[] }) {
  const { t } = useT();
  const [cases, setCases] = useState<SimilarCase[] | null>(null);
  useEffect(() => {
    let alive = true;
    api.similarCases(note, dealId).then(({ data }) => { if (alive) setCases(data.cases); });
    return () => { alive = false; };
  }, [note, dealId]);
  return (
    <div>
      <div className="eyebrow mb-1 flex items-center gap-1.5"><History className="h-3.5 w-3.5" /> {t("chat.similarCases")}</div>
      <p className="mb-2.5 text-[11.5px] text-muted-foreground">{t("chat.similarCasesSub")}</p>
      {cases === null ? (
        <div className="flex items-center gap-2 rounded-xl border border-border bg-card px-4 py-3 text-[13px] text-muted-foreground">
          <Dots /> {t("chat.caseLoading")}
        </div>
      ) : cases.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border bg-muted/30 p-4 text-[13px] text-muted-foreground">
          {t("chat.caseNone")}
        </div>
      ) : (
        <div className="grid gap-2.5">
          {cases.map((c) => <CaseCard key={c.deal_id} c={c} principles={principles} />)}
        </div>
      )}
    </div>
  );
}

function RelevantPrinciples({ note, principles }: { note: string; principles: Principle[] }) {
  const { t, lang } = useT();
  const rel = relevantPrinciples(note, principles);
  if (!rel.length) return null;
  return (
    <div>
      <div className="eyebrow mb-2 flex items-center gap-1.5"><Lightbulb className="h-3.5 w-3.5" /> {t("chat.relevantPrinciples")}</div>
      <ul className="space-y-2">
        {rel.map((p) => (
          <li key={p.principle_id} className="flex gap-2 rounded-xl border border-border bg-card p-3 shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
            <span className="mt-[2px] font-mono text-[10px] text-muted-foreground">{p.principle_id}</span>
            <span className="flex-1 text-[12.5px] leading-snug text-foreground/85">
              {principleText(lang, p).text}
              {p.interview_ids?.length > 0 && (
                <span className="ml-1.5 font-mono text-[10px] text-muted-foreground">({p.interview_ids.join(", ")})</span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Collapsible "Experience" panel for a review turn — past cases + relevant
// principles. Collapsed by default (and only fetches similar cases when opened),
// so the thread stays clean and we don't fire an extra call per review.
export function ExperiencePanel({
  note, dealId, principles,
}: { note: string; dealId?: string; principles: Principle[] }) {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 rounded-xl border border-border bg-card px-4 py-2.5 text-left transition-colors hover:border-primary/40"
      >
        <span className="flex items-center gap-1.5 text-[13px] font-medium text-foreground">
          <History className="h-3.5 w-3.5 text-muted-foreground" />
          {t("chat.experiencePanel")}
        </span>
        <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="animate-fade-up mt-3 space-y-5">
          <SimilarCasesList note={note} dealId={dealId} principles={principles} />
          <RelevantPrinciples note={note} principles={principles} />
        </div>
      )}
    </div>
  );
}
