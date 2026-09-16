import { z } from "zod";

export const ticketReviewSchema = z.object({ schema_version: z.literal("ticket-review-0.1"), provider: z.literal("linear"), payload: z.object({ teamId: z.string().uuid(), title: z.string(), description: z.string() }), digest: z.string().regex(/^[a-f0-9]{64}$/), redactions: z.number().int().nonnegative() });
export const ticketReceiptSchema = z.object({ schema_version: z.literal("ticket-link-0.1"), provider: z.literal("linear"), external_id: z.string().uuid(), external_key: z.string(), url: z.string().regex(/^https:\/\/linear\.app\/issue\/[A-Za-z0-9_-]{1,80}-[0-9]{1,20}$/), digest: z.string() });
export type TicketReview = z.infer<typeof ticketReviewSchema>;
export type TicketReceipt = z.infer<typeof ticketReceiptSchema>;
export type TicketSeed = { title: string; description: string; source_kind: "manual" | "board" | "recommendation" | "case"; source_id: string };
export async function integrationRequest(path = "", body?: unknown) {
  if (!["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname)) throw new Error("Open localhost:5173/integrations with the Python backend to connect Linear.");
  const response = await fetch(`/api/integrations${path}`, { method: body === undefined ? "GET" : "POST", headers: { "X-Codandy-Local": "1", "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(30000) });
  if (!response.ok) { const result = z.object({ detail: z.string() }).safeParse(await response.json().catch(() => null)); throw new Error(result.success ? result.data.detail : "Integration service unavailable. Start the local backend."); }
  return response.json();
}
