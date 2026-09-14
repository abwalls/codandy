import { z } from "zod";

const evidence = z.object({ path: z.string(), lines: z.string().nullable().optional(), reason: z.string() });
const resolution = z.enum(["resolved", "inferred", "unresolved"]);
const reportItem = z.object({
  id: z.string(), title: z.string(), description: z.string(), basis: z.enum(["observed", "inferred"]),
  confidence: z.number().int().min(0).max(100), node_ids: z.array(z.string()).min(1),
  evidence: z.array(evidence).min(1), category: z.string(), metrics: z.record(z.number().int()),
  steps: z.array(z.object({ source: z.string(), target: z.string(), type: z.string(), resolution })),
  priority: z.enum(["low", "medium", "high"]).nullable(), effort: z.enum(["small", "medium", "large"]).nullable(),
  approach: z.array(z.string()), verification: z.array(z.string()),
});
const reportSection = z.object({ status: z.enum(["generated", "not_detected"]), items: z.array(reportItem), limitations: z.array(z.string()) });
const report = z.object({ summary: z.string(), architecture: reportSection, flows: reportSection, guide: reportSection, recommendations: reportSection });
export type GroundedReportItem = z.infer<typeof reportItem>;
export type GroundedReportSection = z.infer<typeof reportSection>;
export const atlasSchema = z.object({
  schema_version: z.enum(["0.1", "0.2"]),
  repository: z.record(z.string()),
  technologies: z.array(z.string()),
  nodes: z.array(z.object({ id: z.string(), kind: z.string(), label: z.string(), detail: z.string(),
    path: z.string(), confidence: z.number().int().min(0).max(100), evidence: z.array(evidence),
    attributes: z.record(z.union([z.string(), z.number().int(), z.boolean()])).default({}) })),
  relationships: z.array(z.object({ source: z.string(), target: z.string(),
    type: z.enum(["CONTAINS", "IMPORTS", "RESOLVES_TO", "DEPENDS_ON", "ROUTES_TO", "CALLS"]), resolution,
    confidence: z.number().int().min(0).max(100), evidence: z.array(evidence) })),
  counts: z.record(z.number().int()), limitations: z.array(z.string()),
  report: report.nullable().optional(),
}).superRefine((atlas, context) => {
  const ids = new Set(atlas.nodes.map(node => node.id));
  const nodesById = new Map(atlas.nodes.map(node => [node.id, node]));
  if (ids.size !== atlas.nodes.length || atlas.relationships.some(edge => !ids.has(edge.source) || !ids.has(edge.target))) {
    context.addIssue({ code: z.ZodIssueCode.custom, message: "Invalid atlas graph" });
  }
  if (atlas.report) {
    const edgeKeys = new Set(atlas.relationships.map(edge => JSON.stringify([edge.source, edge.target, edge.type, edge.resolution])));
    const reportIds = new Set<string>();
    for (const section of [atlas.report.architecture, atlas.report.flows, atlas.report.guide, atlas.report.recommendations]) {
      if ((section.status === "generated") !== Boolean(section.items.length)) context.addIssue({ code: z.ZodIssueCode.custom, message: "Invalid report status" });
      for (const item of section.items) {
        const evidenceKey = (entry: z.infer<typeof evidence>) => JSON.stringify([entry.path, entry.lines ?? null, entry.reason]);
        const evidenceKeys = new Set(item.node_ids.flatMap(id => nodesById.get(id)?.evidence.map(evidenceKey) ?? []));
        if (item.evidence.some(entry => !evidenceKeys.has(evidenceKey(entry)))) {
          context.addIssue({ code: z.ZodIssueCode.custom, message: "Report evidence must come from its cited nodes" });
        }
        if (reportIds.has(item.id) || item.node_ids.some(id => !ids.has(id)) || item.steps.some(step => !edgeKeys.has(JSON.stringify([step.source, step.target, step.type, step.resolution])))) {
          context.addIssue({ code: z.ZodIssueCode.custom, message: "Report references invalid graph evidence" });
        }
        reportIds.add(item.id);
      }
    }
  }
});
export type AnalysisAtlas = z.infer<typeof atlasSchema>;
export const dependencyCheckSchema = z.object({
  node_id: z.string(), checked_at: z.string(), version: z.string().nullable(), version_basis: z.string(),
  latest_version: z.string().nullable(), registry_status: z.enum(["checked", "unavailable"]), registry_basis: z.string(),
  update_status: z.enum(["unknown", "same_version", "newer_available", "not_newer"]),
  vulnerability_status: z.enum(["unknown_version", "unavailable", "reported", "no_matches", "incomplete"]),
  advisories: z.array(z.object({ id: z.string(), summary: z.string(), url: z.string().url().refine(value => new URL(value).origin === "https://osv.dev") })),
  advisories_truncated: z.boolean(),
});
// Source text is served per path instead of being embedded, so the atlas artifact
// stays a graph document and the viewer only transfers what is opened.
export const sourceFileSchema = z.object({
  path: z.string(), text: z.string(), lines: z.number().int().min(0), truncated: z.boolean(),
});
export type AnalysisSourceFile = z.infer<typeof sourceFileSchema>;
export const jobSchema = z.object({
  id: z.string().uuid(), status: z.enum(["queued", "analyzing", "complete", "failed"]),
  phase: z.string(), progress: z.number().int().min(0).max(100), error: z.string().nullable(), created_at: z.string(),
});
export type AnalysisJob = z.infer<typeof jobSchema>;
export const recentReportsSchema = z.object({
  persistent: z.boolean(),
  reports: z.array(z.object({ id: z.string().uuid(), repository: z.record(z.string()), created_at: z.string() })),
});

// Relative URLs work behind a production reverse proxy; Vite proxies them locally.
export async function api(path: string, init?: RequestInit) {
  const response = await fetch(`/api/analyses${path}`, { ...init, signal: init?.signal ?? AbortSignal.timeout(15000) });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: unknown } | null;
    throw new Error(typeof body?.detail === "string" ? body.detail :
      response.status === 422 ? "Enter a public HTTPS github.com/owner/repository URL and a valid branch or tag." :
        `Analysis service returned ${response.status}. Check that the backend is running.`);
  }
  return response.json();
}
