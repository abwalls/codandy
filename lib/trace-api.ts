import { z } from "zod";
export const traceSchema = z.object({ schema_version: z.literal("trace-0.1"), spans: z.array(z.object({ trace_id: z.string().regex(/^[a-f0-9]{32}$/), span_id: z.string().regex(/^[a-f0-9]{16}$/), parent_id: z.string().nullable(), name: z.string(), service: z.string(), start_ns: z.string().regex(/^\d+$/), end_ns: z.string().regex(/^\d+$/), status: z.enum(["unset", "ok", "error"]), parent_state: z.enum(["root", "present", "missing", "cycle"]), attributes: z.record(z.string()) })).max(1000), omitted_spans: z.number().int().nonnegative(), withheld_attributes: z.number().int().nonnegative(), redactions: z.array(z.object({ section: z.string(), kind: z.string(), count: z.number() })), limitations: z.array(z.string()) });
export type Trace = z.infer<typeof traceSchema>;
export function traceRows(trace: Trace, id: string) {
  const spans = trace.spans.filter(s => s.trace_id === id);
  if (!spans.length) return [];
  const origin = spans.reduce((v, s) => BigInt(s.start_ns) < v ? BigInt(s.start_ns) : v, BigInt(spans[0].start_ns));
  const end = spans.reduce((v, s) => BigInt(s.end_ns) > v ? BigInt(s.end_ns) : v, origin);
  const duration = Number(end - origin) || 1;
  const byId = new Map(spans.map(s => [s.span_id, s]));
  return spans.map(span => { let depth = 0, current = span; const visited = new Set([span.span_id]);
    while (current.parent_id && span.parent_state !== "cycle") { const parent = byId.get(current.parent_id); if (!parent || visited.has(parent.span_id)) break; visited.add(parent.span_id); depth++; current = parent; }
    return { span, depth, offsetMs: Number(BigInt(span.start_ns) - origin) / 1e6, durationMs: Number(BigInt(span.end_ns) - BigInt(span.start_ns)) / 1e6,
      left: Number(BigInt(span.start_ns) - origin) / duration * 100, width: Number(BigInt(span.end_ns) - BigInt(span.start_ns)) / duration * 100 };
  });
}
