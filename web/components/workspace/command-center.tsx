"use client";

import type { Role } from "@/lib/session";
import type { CoachExample, DealRow, Principle } from "@/lib/types";
import { Workspace } from "./workspace";
import { ContextPane } from "./context-pane";

/**
 * The Junior home: one screen for the whole job. The Context pane (left) shows
 * the rep's live deals/accounts; the Copilot (right) is the existing Workspace,
 * unchanged. Clicking a deal on the left grounds the Copilot via shared focus
 * (see useWorkspaceFocus), so the rep alternates between "what's in front of me"
 * and "help me with it" without ever navigating away.
 *
 * Layout is a single responsive grid so each pane mounts exactly once (the
 * Workspace is stateful and stream-driven — mounting it twice would double its
 * effects). Desktop: context is a sticky left column beside the page-scrolling
 * Copilot, which keeps its own sticky composer. Mobile: the panes stack, with a
 * scrollable context box above the chat.
 */
export function CommandCenter({
  examples,
  deals,
  principles,
  role = "junior",
}: {
  examples: CoachExample[];
  deals: DealRow[];
  principles: Principle[];
  role?: Role;
}) {
  return (
    <div className="grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)] lg:items-start">
      <aside className="max-h-[42vh] overflow-y-auto rounded-xl border border-border bg-card/40 p-4 lg:sticky lg:top-[4.5rem] lg:max-h-[calc(100vh-5.5rem)]">
        <ContextPane deals={deals} role={role} />
      </aside>
      <div className="min-w-0">
        <Workspace examples={examples} deals={deals} principles={principles} role={role} />
      </div>
    </div>
  );
}
