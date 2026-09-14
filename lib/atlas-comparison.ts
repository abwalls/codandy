import type { AnalysisAtlas } from "./analysis-api";

type Node = AnalysisAtlas["nodes"][number];
export type NodeChange = { status: "added" | "removed" | "changed"; before?: Node; after?: Node };

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).sort().join(",")}]`;
  if (value && typeof value === "object") return `{${Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, entry]) => `${JSON.stringify(key)}:${canonical(entry)}`).join(",")}}`;
  return JSON.stringify(value) ?? "null";
}

function repositoryKey(atlas: AnalysisAtlas): string {
  return (atlas.repository.url || "").replace(/\/$/, "").replace(/\.git$/i, "").toLowerCase();
}

export function compareAtlases(before: AnalysisAtlas, after: AnalysisAtlas) {
  if (!repositoryKey(before) || repositoryKey(before) !== repositoryKey(after)) {
    throw new Error("Choose an atlas from the same repository.");
  }
  if (before.schema_version !== after.schema_version) {
    throw new Error("These snapshots use different atlas schema versions. Reanalyze them with the same version before comparing.");
  }
  const previous = new Map(before.nodes.map(node => [node.id, node]));
  const current = new Map(after.nodes.map(node => [node.id, node]));
  const changes: NodeChange[] = [];
  for (const node of after.nodes) {
    const old = previous.get(node.id);
    if (!old) changes.push({ status: "added", after: node });
    else if (canonical(old) !== canonical(node)) changes.push({ status: "changed", before: old, after: node });
  }
  for (const node of before.nodes) if (!current.has(node.id)) changes.push({ status: "removed", before: node });
  changes.sort((a, b) => (a.after || a.before)!.path.localeCompare((b.after || b.before)!.path) || (a.after || a.before)!.id.localeCompare((b.after || b.before)!.id));
  const oldEdges = new Set(before.relationships.map(canonical));
  const newEdges = new Set(after.relationships.map(canonical));
  return { changes,
    addedRelationships: [...newEdges].filter(edge => !oldEdges.has(edge)).length,
    removedRelationships: [...oldEdges].filter(edge => !newEdges.has(edge)).length,
    unchangedNodes: after.nodes.length - changes.filter(change => change.status !== "removed").length,
  };
}
