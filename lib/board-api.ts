import { z } from "zod";

const finding = z.object({ text: z.string(), element_ids: z.array(z.string()), basis: z.enum(["drawn", "answered", "assumed"]) });
const interpretation = z.object({ summary: z.string(), findings: z.array(finding), questions: z.array(z.string()), assumptions: z.array(z.string()) });
export const boardSchema = z.object({ schema_version: z.literal("board-0.1"), id: z.string().uuid(), revision: z.number().int(), title: z.string(), notes: z.string(), snapshot_id: z.string().nullable(), scene: z.object({ elements: z.array(z.record(z.unknown())) }), artifacts: z.array(z.object({ id: z.string(), revision: z.number(), stage: z.enum(["interpret", "plan"]), model: z.string(), interpretation: interpretation.nullable(), plan: z.object({ title: z.string(), objective: z.string() }).passthrough().nullable() })) });
export type Board = z.infer<typeof boardSchema>;
export const reviewSchema = z.object({ digest: z.string(), revision: z.number(), stage: z.enum(["interpret", "plan"]), text: z.string() });
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
