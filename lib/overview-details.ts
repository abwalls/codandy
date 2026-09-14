import type { AnalysisAtlas } from "./analysis-api";

export const overviewLabels = { files: "Source files", symbols: "Symbols", routes: "API routes", tests: "Tests" } as const;
export type OverviewMetric = keyof typeof overviewLabels;
const symbolKinds = new Set(["class", "interface", "method", "function", "enum", "type", "component", "handler"]);
export function overviewNodes(atlas: AnalysisAtlas, metric: OverviewMetric) {
  return atlas.nodes.filter(node => metric === "symbols" ? symbolKinds.has(node.kind) :
    node.kind === ({ files: "file", routes: "route", tests: "test" } as const)[metric]);
}
