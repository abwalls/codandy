import { z } from "zod";

export const connectionSchema = z.object({ connected: z.boolean(), plan: z.string().nullable(), models: z.array(z.object({
  id: z.string(), name: z.string(), default: z.boolean(), default_effort: z.string(), efforts: z.array(z.string()),
})) });
export const answerSchema = z.object({ answer: z.string(), citations: z.array(z.string()) });
export const loginSchema = z.object({ url: z.string().url().refine(value => new URL(value).origin === "https://auth.openai.com") });
export async function assistantApi(path: string, body?: unknown) {
  const response = await fetch(`/api/analyses/assistant/${path}`, {
    method: body === undefined ? "GET" : "POST", headers: { "X-Codandy-Local": "1", "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(path === "ask" ? 190000 : 35000),
  });
  const result = await response.json().catch(() => null);
  if (!response.ok) { const error = z.object({ detail: z.string() }).safeParse(result); throw new Error(error.success ? error.data.detail : "Local AI connection unavailable. Start or restart your local backend."); }
  return result;
}
