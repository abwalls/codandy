import type { AnalysisAtlas } from "./analysis-api";

export function dependencyImpact(atlas: AnalysisAtlas, path: string, kind: "file" | "project" = "file") {
  const file = atlas.nodes.find(node => node.kind === kind && node.path === path);
  if (!file) return [];
  const nodes = new Map(atlas.nodes.map(node => [node.id, node]));
  const resolved = new Map<string, string[]>();
  for (const edge of atlas.relationships) if (edge.type === "RESOLVES_TO" && edge.resolution !== "unresolved") {
    resolved.set(edge.source, [...(resolved.get(edge.source) || []), edge.target]);
  }
  const importers = new Map<string, Set<string>>();
  for (const edge of atlas.relationships) if (kind === "file" && edge.type === "IMPORTS") {
    for (const target of resolved.get(edge.target) || []) {
      if (!importers.has(target)) importers.set(target, new Set());
      importers.get(target)!.add(edge.source);
    }
  } else if (kind === "project" && edge.type === "DEPENDS_ON" && edge.resolution !== "unresolved" &&
    nodes.get(edge.source)?.kind === "project" && nodes.get(edge.target)?.kind === "project") {
    if (!importers.has(edge.target)) importers.set(edge.target, new Set());
    importers.get(edge.target)!.add(edge.source);
  }
  const seen = new Set([file.id]);
  const queue = [{ id: file.id, distance: 0 }];
  for (let index = 0; index < queue.length; index++) {
    const entry = queue[index];
    for (const id of importers.get(entry.id) || []) if (!seen.has(id)) {
      seen.add(id); queue.push({ id, distance: entry.distance + 1 });
    }
  }
  return queue.slice(1).map(entry => ({ node: nodes.get(entry.id)!, distance: entry.distance }))
    .filter(entry => entry.node?.kind === kind)
    .sort((a, b) => a.distance - b.distance || a.node.path.localeCompare(b.node.path));
}
