import type { AnalysisAtlas, dependencyCheckSchema } from "./analysis-api";
import type { z } from "zod";

export type DependencyCheck = z.infer<typeof dependencyCheckSchema>;
export type DependencyReview = "all" | "unchecked" | "updates" | "advisories" | "uncertain";

export function matchesDependencyReview(check: DependencyCheck | undefined, review: DependencyReview) {
  if (review === "all") return true;
  if (review === "unchecked") return !check;
  if (!check) return false;
  if (review === "updates") return check.update_status === "newer_available";
  if (review === "advisories") return check.advisories.length > 0;
  return check.registry_status === "unavailable" || check.update_status === "unknown" ||
    !["reported", "no_matches"].includes(check.vulnerability_status) || check.advisories_truncated;
}

export function dependencyReport(atlas: AnalysisAtlas, checks: Record<string, DependencyCheck>, exportedAt: string) {
  const inventory = atlas.nodes.filter(node => node.kind === "dependency");
  return {
    format: "code-atlas-dependency-review",
    format_version: "1",
    exported_at: exportedAt,
    repository: atlas.repository,
    atlas_schema_version: atlas.schema_version,
    limitations: [
      "Direct manifest inventory only; not a complete transitive SBOM or installed/runtime inventory.",
      "Public checks are separate, time-stamped observations. Missing checks mean not checked, never clean.",
      "Registry updates do not establish compatibility; advisory matches do not establish runtime exposure.",
      "Central NuGet declarations are candidates only; MSBuild conditions, imports and overrides are not evaluated.",
      ...atlas.limitations,
    ],
    inventory: inventory.map(node => ({
      node_id: node.id,
      name: node.label,
      manifest: node.path,
      ecosystem: node.attributes.ecosystem || null,
      group: node.attributes.group || null,
      declared_version: node.attributes.declared_version || null,
      identified_version: node.attributes.checked_version || null,
      version_basis: node.attributes.version_basis || "unknown",
      version_note: node.attributes.version_note || null,
      lockfile: node.attributes.lockfile || null,
      central_version_candidates: node.attributes.central_version_candidates || null,
      central_version_file: node.attributes.central_version_file || null,
      central_candidates_truncated: node.attributes.central_candidates_truncated || false,
      evidence: node.evidence,
    })),
    public_checks: inventory.flatMap(node => checks[node.id]?.node_id === node.id ? [checks[node.id]] : []),
  };
}
