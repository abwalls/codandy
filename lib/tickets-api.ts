import { z } from "zod";

export const ticketReviewSchema = z.object({ schema_version: z.literal("ticket-review-0.1"), provider: z.literal("linear"), payload: z.object({ teamId: z.string().uuid(), projectId: z.string().uuid().optional(), priority: z.number().int().min(0).max(4).optional(), title: z.string(), description: z.string() }), digest: z.string().regex(/^[a-f0-9]{64}$/), redactions: z.number().int().nonnegative(), previous_submissions: z.number().int().nonnegative().default(0) });
export const ticketReceiptSchema = z.object({ schema_version: z.literal("ticket-link-0.1"), provider: z.literal("linear"), external_id: z.string().uuid(), external_key: z.string(), url: z.string().regex(/^https:\/\/linear\.app\/issue\/[A-Za-z0-9_-]{1,80}-[0-9]{1,20}$/), digest: z.string() });
// The backend truncates team names to 200 Unicode code points (Python str slicing). Count the same
// way here: .max(200) counts UTF-16 units, so one emoji near the limit would reject the whole page.
export const linearTeamsSchema = z.object({
  items: z.array(z.object({ id: z.string().uuid(), name: z.string().refine(value => [...value].length <= 200, "Team name exceeds 200 characters") })).max(50),
  has_more: z.boolean(),
  next_cursor: z.string().min(1).max(1024).nullable(),
}).refine(value => value.has_more === (value.next_cursor !== null));
export type TicketReview = z.infer<typeof ticketReviewSchema>;
export type TicketReceipt = z.infer<typeof ticketReceiptSchema>;
export type TicketSeed = { title: string; description: string; source_kind: "manual" | "board" | "recommendation" | "case"; source_id: string };
export async function integrationRequest(path = "", body?: unknown) {
  if (!["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname)) throw new Error("Open localhost:5173/integrations with the Python backend to connect Linear.");
  const response = await fetch(`/api/integrations${path}`, { method: body === undefined ? "GET" : "POST", headers: { "X-Codandy-Local": "1", "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(30000) });
  if (!response.ok) { const result = z.object({ detail: z.string() }).safeParse(await response.json().catch(() => null)); throw new Error(result.success ? result.data.detail : "Integration service unavailable. Start the local backend."); }
  return response.json();
}
