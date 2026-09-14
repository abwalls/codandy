import { z } from "zod";

const text = z.string().nullable();
const integer = z.number().int().nonnegative();
export const observationSchema = z.object({
  schema_version: z.literal("debugging-0.1"), id: z.string().uuid(), kind: z.literal("exception"),
  normalized_at: z.string(), occurred_at: text, received_at: text,
  title: text, message: text, platform: text, environment: text, release: text,
  source: z.object({ provider: z.enum(["sentry", "pasted"]),
    format: z.enum(["sentry_rest_event", "python_traceback", "javascript_stack", "dotnet_stack"]),
    event_id: text, issue_id: text, project_id: text, fetched_at: text, interpretation: z.array(z.string()) }),
  exceptions: z.array(z.object({ index: integer, type: text, value: text, module: text,
    relation_to_next: z.enum(["direct_cause", "during_handling", "inner_exception", "group_member", "chained"]).nullable(),
    provider_exception_id: integer.nullable(), provider_parent_id: integer.nullable(), handled: z.boolean().nullable(),
    frames_omitted: integer, frames: z.array(z.object({ index: integer, provider_index: integer,
      function: text, module: text, path: text, abs_path: text, line: integer.nullable(), column: integer.nullable(),
      in_app: z.boolean().nullable(), after_async_boundary: z.boolean(),
      context: z.array(z.object({ line: integer, text: z.string() })) })) })),
  breadcrumbs: z.array(z.object({ timestamp: text, type: text, category: text, level: text, message: text })),
  provider_notes: z.array(z.object({ type: z.string(), message: text })),
  truncations: z.array(z.object({ section: z.string(), reason: z.string(), original: integer, retained: integer })),
  redactions: z.array(z.object({ section: z.string(), kind: z.string(), count: integer })),
  withheld: z.array(z.string()), limitations: z.array(z.string()),
});
export const sentryStatusSchema = z.object({ configured: z.boolean(), host: z.string(), organization: z.string(), verified: z.boolean() });
export type Observation = z.infer<typeof observationSchema>;

export async function debuggingRequest(path: string, options?: RequestInit) {
  if (typeof window !== "undefined" && !["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname)) {
    throw new Error("Open Codandy on localhost:5173 with its Python backend to import private debugging evidence.");
  }
  const response = await fetch(`/api/debugging${path}`, { ...options,
    headers: { ...options?.headers, "X-Codandy-Local": "1" } });
  if (!response.ok) {
    const data = z.object({ detail: z.string() }).safeParse(await response.json().catch(() => null));
    throw new Error(data.success ? data.data.detail : "Debugging service is unavailable. Start the local backend.");
  }
  return response.json();
}
