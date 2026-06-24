"use client";

// Workspace artifact dispatcher — every kind now renders through one unified
// ArtifactBody (kind-aware header + alert + commentary placement). The three
// per-kind card files were collapsed into ArtifactBody to stop them drifting.

import type { Artifact } from "@/lib/artifacts";
import { ArtifactBody } from "./cards/artifact-body";

export function ArtifactCard({ artifact }: { artifact: Artifact }) {
  return <ArtifactBody artifact={artifact} />;
}
