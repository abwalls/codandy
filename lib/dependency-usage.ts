import type { AnalysisAtlas } from "./analysis-api";
type Node = AnalysisAtlas["nodes"][number];

export function dependencyUsage(atlas: AnalysisAtlas, dependency: Node) {
  const project = atlas.relationships.find(edge => edge.type === "DEPENDS_ON" && edge.target === dependency.id)?.source;
  const members = new Set(atlas.relationships.filter(edge => edge.type === "CONTAINS" && edge.source === project).map(edge => edge.target));
  const paths = new Set(atlas.nodes.filter(node => members.has(node.id)).map(node => node.path));
  const name = dependency.label;
  return atlas.nodes.filter(node => node.kind === "import" && paths.has(node.path) &&
    (node.label === name || node.label.startsWith(name + "/") ||
     dependency.attributes.ecosystem === "NuGet" && node.label.startsWith(name + ".") ||
     dependency.attributes.ecosystem === "PyPI" && node.label.split(".")[0].toLowerCase() === name.replaceAll("-", "_").toLowerCase()));
}
