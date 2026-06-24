import { api } from "@/lib/api";
import { Workspace } from "@/components/workspace/workspace";

export const dynamic = "force-dynamic";

// Manager Workspace — the same unified surface as junior, but chat runs the
// manager tool-loop (team pipeline / at-risk deals / coaching focus) via
// role="manager". This is what lets the standalone manager Assistant be retired:
// managers get skills + grounded tool-calling chat in one place.
export default async function ManagerWorkspacePage() {
  const [{ data: ex }, { data: db }, { data: pr }] = await Promise.all([
    api.coachExamples(),
    api.dashboard(),
    api.principles(),
  ]);

  return (
    <Workspace examples={ex.examples} deals={db.deals} principles={pr.principles} role="manager" />
  );
}
