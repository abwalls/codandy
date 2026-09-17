import { z } from "zod";

export const evidenceCardSchema = z.object({ id: z.string().uuid(), kind: z.enum(["source", "case"]), source_id: z.string(), source_revision: z.string(), snapshot_id: z.string().uuid().nullable(), captured_at: z.string(), title: z.string(), text: z.string(), basis: z.string() });
const finding = z.object({ text: z.string(), element_ids: z.array(z.string()), evidence_ids: z.array(z.string()).default([]), basis: z.enum(["drawn", "answered", "assumed", "visual_inference", "captured_evidence"]) });
const interpretation = z.object({ summary: z.string(), findings: z.array(finding), questions: z.array(z.string()), assumptions: z.array(z.string()) });
export const boardSchema = z.object({ schema_version: z.literal("board-0.1"), id: z.string().uuid(), revision: z.number().int(), title: z.string(), notes: z.string(), snapshot_id: z.string().nullable(), evidence_cards: z.array(evidenceCardSchema).max(10).default([]), scene: z.object({ elements: z.array(z.record(z.unknown())) }), artifacts: z.array(z.object({ id: z.string(), revision: z.number(), stage: z.enum(["interpret", "plan"]), model: z.string(), visual_input: z.boolean().default(false), interpretation: interpretation.nullable(), plan: z.object({ title: z.string(), objective: z.string() }).passthrough().nullable() })) });
export const planTaskSchema = z.object({ id: z.string(), title: z.string(), description: z.string(), depends_on: z.array(z.string()), acceptance_criteria: z.array(z.string()).min(1), verification: z.array(z.string()).min(1), proposed_paths: z.array(z.string()) });
export const planOutputsSchema = z.object({ plan: z.string(), ticket: z.string(), stale: z.boolean(), artifact_id: z.string().uuid(), revision: z.number().int().positive(), structured_plan: z.object({ title: z.string(), objective: z.string(), tasks: z.array(planTaskSchema).min(1), in_scope: z.array(z.string()), out_of_scope: z.array(z.string()), decisions: z.array(finding), risks: z.array(z.string()), open_questions: z.array(z.string()) }) });
export type PlanOutputs = z.infer<typeof planOutputsSchema>;
export type Board = z.infer<typeof boardSchema>;
export const reviewSchema = z.object({ digest: z.string(), revision: z.number(), stage: z.enum(["interpret", "plan"]), text: z.string(), image: z.string().startsWith("data:image/png;base64,").max(2800000).optional(), image_info: z.object({ width: z.number(), height: z.number(), sha256: z.string() }).optional(), visual_scene: z.array(z.record(z.unknown())).optional(), reading_guide: z.object({ included_elements: z.number().int().nonnegative(), omitted_elements: z.number().int().nonnegative(), freehand_elements: z.number().int().nonnegative(), unbound_connectors: z.number().int().nonnegative(), unlabeled_shapes: z.number().int().nonnegative() }).optional() });
export type Review = z.infer<typeof reviewSchema>;
export async function boardRequest(path = "", method = "GET", body?: unknown) {
  if (!["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname)) throw new Error("Open localhost:5173/whiteboard with the Python backend to work with local boards.");
  const response = await fetch(`/api/boards${path}`, { method, headers: { "X-Codandy-Local": "1", "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(190000) });
  if (!response.ok) { const error = z.object({ detail: z.string() }).safeParse(await response.json().catch(() => null)); throw new Error(error.success ? error.data.detail : "Whiteboard service is unavailable. Start the local backend."); }
  return response.status === 204 ? null : response.json();
}
export function downloadText(name: string, value: string, type = "text/markdown") {
  const url = URL.createObjectURL(new Blob([value], { type }));
  const a = document.createElement("a"); a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
