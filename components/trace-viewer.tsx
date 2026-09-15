"use client";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { debuggingRequest } from "@/lib/debugging-api";
import { downloadText } from "@/lib/board-api";
import { traceRows, traceSchema, type Trace } from "@/lib/trace-api";

export function TraceViewer() {
  const [trace, setTrace] = useState<Trace | null>(null), [id, setId] = useState("");
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [query, setQuery] = useState(""), [errorsOnly, setErrorsOnly] = useState(false), [reviewed, setReviewed] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const rows = useMemo(() => trace ? traceRows(trace, id) : [], [trace, id]);
  const visible = rows.filter(r => (!errorsOnly || r.span.status === "error") && `${r.span.name} ${r.span.service}`.toLowerCase().includes(query.toLowerCase()));
  const detail = rows.find(r => r.span.span_id === selected);
  return <section className="space-y-4 rounded-xl border bg-card p-5" aria-label="OpenTelemetry traces">
    <div><h2 className="text-xl font-semibold">OpenTelemetry traces</h2><p className="mt-2 text-sm text-muted-foreground">Import an OTLP JSON file to see where an operation spent time and which spans failed. This is a file viewer; live collection is not enabled.</p></div>
    <label className="block text-sm">OTLP JSON trace file<Input type="file" accept=".json" disabled={busy} onChange={async e => {
      const file = e.target.files?.[0]; e.target.value = ""; if (!file) return;
      setBusy(true); setError(""); setReviewed(false); setTrace(null); setSelected(null); setQuery(""); setErrorsOnly(false);
      try { if (file.size > 2 * 1024 * 1024) throw new Error("Trace files must be 2 MiB or smaller");
        const result = traceSchema.parse(await debuggingRequest("/traces/import", { method: "POST", headers: { "Content-Type": "application/json" }, body: await file.text(), signal: AbortSignal.timeout(30000) }));
        setTrace(result); setId(result.spans[0].trace_id);
      } catch (cause) { setError(cause instanceof Error ? cause.message : "Trace import failed"); } finally { setBusy(false); }
    }} /></label>
    <p className="text-xs text-muted-foreground">Up to 1,000 spans. Sanitized results remain in this tab until you clear or reload it; raw telemetry is not saved.</p>
    {busy && <p role="status">Reading trace…</p>}{error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    {trace && <><div className="flex flex-wrap gap-3"><label className="min-w-0 text-sm">Trace<select aria-label="Trace ID" className="mt-1 block max-w-full rounded border bg-card p-2 font-mono text-xs" value={id} onChange={e => { setId(e.target.value); setSelected(null); }}>{[...new Set(trace.spans.map(s => s.trace_id))].map(value => <option key={value}>{value}</option>)}</select></label><label className="flex-1 text-sm">Find span or service<Input value={query} onChange={e => setQuery(e.target.value)} /></label><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={errorsOnly} onChange={e => setErrorsOnly(e.target.checked)} />Errors only</label></div>
      <p className="text-xs text-muted-foreground">{visible.length} of {rows.length} spans shown · elapsed wall time, not CPU time. Parent nesting comes from imported IDs. Overlapping bars may run concurrently.</p>
      <div className="max-h-[520px] space-y-2 overflow-auto" aria-label="Trace waterfall">{visible.map(row => <button key={row.span.span_id} aria-pressed={selected === row.span.span_id} onClick={() => setSelected(row.span.span_id)} className={`block w-full rounded-lg border p-3 text-left ${selected === row.span.span_id ? "border-primary" : "hover:bg-muted"}`}>
        <div className="flex flex-wrap justify-between gap-2 text-xs"><span className="min-w-0 break-words" style={{ paddingLeft: Math.min(row.depth, 5) * 8 }}><span className="font-semibold">{row.span.service}</span> · {row.span.name}</span><span>{row.durationMs.toFixed(3)} ms · {row.span.status}</span></div>
        <div className="relative my-2 h-3 rounded bg-muted"><div className={`absolute h-3 min-w-[2px] rounded ${row.span.status === "error" ? "bg-destructive" : "bg-primary"}`} style={{ left: `${Math.min(row.left, 99.8)}%`, width: `${Math.max(row.width, 0.2)}%` }} /></div>
        <p className="text-xs text-muted-foreground">+{row.offsetMs.toFixed(3)} ms from trace start{row.span.parent_state === "missing" ? " · parent absent from import" : row.span.parent_state === "cycle" ? " · cyclic parent chain; nesting unavailable" : ` · nesting depth ${row.depth}`}</p>
      </button>)}{!visible.length && <p className="p-3 text-sm">No spans match these filters.</p>}</div>
      {detail && <div className="rounded-lg border p-3"><h3 className="font-semibold">Selected span</h3><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-all text-xs">{JSON.stringify(detail.span, null, 2)}</pre></div>}
      <details><summary className="cursor-pointer text-sm">Import limits and scrubbing</summary><ul className="mt-2 list-disc space-y-1 pl-5 text-xs">{trace.limitations.map(item => <li key={item}>{item}</li>)}<li>{trace.omitted_spans} spans omitted · {trace.withheld_attributes} attributes withheld · {trace.redactions.reduce((n, r) => n + r.count, 0)} text redactions</li></ul></details>
      <details><summary className="cursor-pointer text-sm">Review the full sanitized trace</summary><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-all text-xs">{JSON.stringify(trace, null, 2)}</pre></details>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} />I reviewed the sanitized trace before sharing.</label>
      <div className="flex flex-wrap gap-2"><Button disabled={!reviewed} onClick={() => downloadText("codandy-trace.json", JSON.stringify(trace, null, 2), "application/json")}>Download sanitized trace</Button><Button variant="outline" onClick={() => { setTrace(null); setReviewed(false); setSelected(null); }}>Clear trace</Button></div>
    </>}
  </section>;
}
