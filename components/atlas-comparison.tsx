"use client";

import { useMemo, useRef, useState } from "react";
import { atlasSchema, type AnalysisAtlas } from "@/lib/analysis-api";
import { compareAtlases } from "@/lib/atlas-comparison";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AskButton } from "@/components/ask-codandy";

export function AtlasComparison({ atlas, onInspect }: { atlas: AnalysisAtlas; onInspect: (id: string) => void }) {
  const [baseline, setBaseline] = useState<AnalysisAtlas | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [limit, setLimit] = useState(50);
  const picker = useRef<HTMLInputElement>(null);
  const comparison = useMemo(() => baseline ? compareAtlases(baseline, atlas) : null, [baseline, atlas]);
  async function open(file: File) {
    setBusy(true); setError(null);
    try {
      if (file.size > 20 * 1024 * 1024) throw new Error("Atlas files must be 20 MB or smaller.");
      const result = atlasSchema.safeParse(JSON.parse(await file.text()));
      if (!result.success) throw new Error("This file is not a supported atlas or contains invalid graph evidence.");
      compareAtlases(result.data, atlas);
      setBaseline(result.data); setLimit(50); setQuery(""); setStatus("all");
    } catch (cause) {
      setError(cause instanceof SyntaxError ? "This file is not valid JSON." : cause instanceof Error ? cause.message : "Could not compare snapshots.");
    } finally { setBusy(false); if (picker.current) picker.current.value = ""; }
  }
  const filtered = comparison?.changes.filter(change => {
    const node = (change.after || change.before)!;
    return (status === "all" || status === change.status) && `${node.path} ${node.label}`.toLowerCase().includes(query.toLowerCase());
  }) || [];
  return <div className="space-y-5">
    <p className="rounded-xl border border-cyan-300/15 p-4 text-sm leading-6 text-slate-400">Compare this report with a saved atlas from the same repository. Changes describe indexed graph metadata, including line locations; they are not a source diff or proof of changed behavior. Renames can appear as removal and addition. Snapshots may differ in analyzer coverage.</p>
    <input ref={picker} type="file" accept=".json,application/json" className="hidden" aria-label="Choose baseline atlas" onChange={event => { const file = event.target.files?.[0]; if (file) void open(file); }} />
    <Button disabled={busy} variant="outline" onClick={() => picker.current?.click()}>{busy ? "Reading snapshot…" : baseline ? "Replace baseline atlas" : "Choose baseline atlas"}</Button>
    {error && <p role="alert" className="text-sm text-amber-200">{error}</p>}
    {baseline && comparison && <>
      <AskButton scope={{ title: "Snapshot comparison", nodeIds: comparison.changes.flatMap(change => change.after ? [change.after.id] : []), notes: JSON.stringify({ baseline: baseline.repository, current: atlas.repository, unchanged_nodes: comparison.unchangedNodes, added_relationships: comparison.addedRelationships, removed_relationships: comparison.removedRelationships, changes: comparison.changes.slice(0, 20).map(change => ({ status: change.status, before: change.before && { label: change.before.label, path: change.before.path }, after: change.after && { label: change.after.label, path: change.after.path } })), partial: comparison.changes.length > 20 }) }}>Ask about these changes</AskButton>
      <p className="break-all text-sm text-slate-400">Baseline: {baseline.repository.commit?.slice(0, 12) || "unknown commit"} · {baseline.repository.analyzed_at || "unknown analysis time"}<br />Current: {atlas.repository.commit?.slice(0, 12) || "unknown commit"} · {atlas.repository.analyzed_at || "unknown analysis time"}</p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">{["added", "removed", "changed"].map(value => <div key={value} className="rounded-xl border border-white/10 p-4"><div className="text-2xl text-cyan-100">{comparison.changes.filter(change => change.status === value).length}</div><div className="text-sm capitalize text-slate-400">{value} nodes</div></div>)}</div>
      <p className="text-sm text-slate-400">{comparison.unchangedNodes} unchanged nodes · {comparison.addedRelationships} added and {comparison.removedRelationships} removed relationship records. Changed relationship metadata counts as a removal and addition.</p>
      <div className="flex flex-wrap gap-3"><Input aria-label="Search snapshot changes" placeholder="Search changed names or paths" value={query} onChange={event => { setQuery(event.target.value); setLimit(50); }} /><select aria-label="Change type" className="rounded-lg bg-[var(--surface-4)] p-2" value={status} onChange={event => { setStatus(event.target.value); setLimit(50); }}><option value="all">All changes</option>{["added", "removed", "changed"].map(value => <option key={value}>{value}</option>)}</select></div>
      {!filtered.length && <p className="text-slate-400">No indexed node changes match this view.</p>}
      {filtered.slice(0, limit).map(change => { const node = (change.after || change.before)!; return <article key={node.id} className="min-w-0 rounded-xl border border-white/10 bg-[var(--surface-4)] p-4"><p className="text-xs uppercase text-cyan-300">{change.status} · {node.kind}</p><h3 className="mt-2 break-all font-semibold">{node.label}</h3><p className="break-all text-sm text-slate-400">{node.path || "Repository root"}</p>{change.before && <p className="mt-2 text-xs text-slate-500">Baseline location: {change.before.evidence[0]?.lines || "no line range"}</p>}{change.after ? <Button className="mt-3" variant="outline" size="sm" onClick={() => onInspect(node.id)}>Inspect current evidence</Button> : <p className="mt-3 text-sm text-slate-400">{node.detail} · This node exists only in the baseline; current source is unavailable.</p>}</article>; })}
      {filtered.length > limit && <Button variant="outline" onClick={() => setLimit(limit + 50)}>Show more changes</Button>}
    </>}
  </div>;
}
