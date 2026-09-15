import type { AnalysisAtlas } from "./analysis-api";

export type ArchitectureGroup = { id: string; label: string; nodeIds: string[]; internal: number };
export type ArchitectureLink = { source: string; target: string; count: number; inferred: number; nodeIds: string[] };

export function architectureMap(atlas: AnalysisAtlas, mode: "folders" | "projects", depth = 1, expanded: ReadonlySet<string> = new Set()) {
  const nodes = new Map(atlas.nodes.map(node => [node.id, node]));
  const groups = new Map<string, ArchitectureGroup>();
  const membership = new Map<string, string>();
  // An expanded folder splits into its subfolders; files directly inside it stay in its group.
  const folderGroup = (folders: string[]) => {
    let size = Math.max(1, Math.min(depth, 3));
    while (size < folders.length && expanded.has(folders.slice(0, size).join("/"))) size++;
    return folders.slice(0, size).join("/") || ".";
  };
  for (const node of atlas.nodes) {
    if (node.kind !== (mode === "projects" ? "project" : "file")) continue;
    const folders = node.path.replaceAll("\\", "/").split("/").slice(0, -1);
    const id = mode === "projects" ? node.id : folderGroup(folders);
    if (!groups.has(id)) groups.set(id, { id, label: mode === "projects" ? node.path || node.label : id === "." ? "Repository root" : id, nodeIds: [], internal: 0 });
    groups.get(id)!.nodeIds.push(node.id); membership.set(node.id, id);
  }
  if (mode === "folders") for (const node of atlas.nodes) if (node.kind === "directory") {
    const id = folderGroup(node.path.replaceAll("\\", "/").split("/"));
    if (groups.has(id)) membership.set(node.id, id);
  }
  const links = new Map<string, ArchitectureLink>();
  // Local imports with no resolved target: real gaps in the drawn graph.
  let unresolved = 0;
  // Undrawn imports the analyzer did not mark as local: packages, standard library and
  // namespaces, or every undrawn import from an atlas that predates the classification.
  let external = 0;
  const classified = atlas.nodes.some(node => node.kind === "import" && typeof node.attributes.local_import === "boolean");
  const seen = new Set<string>();
  function connect(source: string, target: string, key: string, inferred: boolean, evidence: string[]) {
    const from = membership.get(source), to = membership.get(target);
    if (from === undefined || to === undefined || seen.has(key)) return;
    seen.add(key);
    if (from === to) { groups.get(from)!.internal++; return; }
    const pair = JSON.stringify([from, to]);
    if (!links.has(pair)) links.set(pair, { source: from, target: to, count: 0, inferred: 0, nodeIds: [] });
    const link = links.get(pair)!; link.count++; if (inferred) link.inferred++;
    link.nodeIds = [...new Set([...link.nodeIds, ...evidence])].slice(0, 48);
  }
  if (mode === "projects") {
    for (const edge of atlas.relationships) if (edge.type === "DEPENDS_ON" && edge.resolution !== "unresolved") {
      connect(edge.source, edge.target, JSON.stringify([edge.source, edge.target]), edge.resolution === "inferred", [edge.source, edge.target]);
    }
  } else {
    const resolved = new Map<string, typeof atlas.relationships>();
    for (const edge of atlas.relationships) if (edge.type === "RESOLVES_TO" && edge.resolution !== "unresolved" && ["file", "directory"].includes(nodes.get(edge.target)?.kind || "")) {
      resolved.set(edge.source, [...(resolved.get(edge.source) || []), edge]);
    }
    for (const edge of atlas.relationships) if (edge.type === "IMPORTS") {
      if (!(resolved.get(edge.target) || []).some(target => membership.has(target.target))) {
        if (nodes.get(edge.target)?.attributes.local_import === true) unresolved++; else external++;
      }
      for (const target of resolved.get(edge.target) || []) connect(edge.source, target.target,
        JSON.stringify([edge.source, edge.target, target.target]), target.resolution === "inferred", [edge.source, edge.target, target.target]);
    }
  }
  const degree = new Map<string, number>();
  for (const link of links.values()) for (const id of [link.source, link.target]) degree.set(id, (degree.get(id) || 0) + link.count);
  return { groups: [...groups.values()].map(group => ({ ...group, nodeIds: group.nodeIds.sort() }))
    .sort((a, b) => (degree.get(b.id) || 0) - (degree.get(a.id) || 0) || a.label.localeCompare(b.label)),
    links: [...links.values()].sort((a, b) => b.count - a.count || a.source.localeCompare(b.source) || a.target.localeCompare(b.target)),
    classified: mode === "projects" || classified,
    external: mode === "folders" ? external : 0,
    unresolved: mode === "folders" ? unresolved : atlas.relationships.filter(edge => edge.resolution === "unresolved" && edge.type === "DEPENDS_ON").length };
}
