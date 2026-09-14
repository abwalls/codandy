"use client";

import { useState } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { overviewLabels, type OverviewMetric } from "@/lib/overview-details";
import { AskButton } from "@/components/ask-codandy";

export type OverviewRow = { id: string; label: string; path: string; kind: string; detail: string };
export function OverviewDetails({ metric, rows, total, sample = false, onClose, onInspect }: {
  metric: OverviewMetric; rows: OverviewRow[]; total: number; sample?: boolean; onClose: () => void; onInspect: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(40);
  const filtered = rows.filter(node => `${node.label} ${node.path} ${node.detail}`.toLowerCase().includes(query.toLowerCase()));
  return <Sheet open onOpenChange={open => { if (!open) onClose(); }}><SheetContent className="w-[min(640px,95vw)] overflow-y-auto bg-background text-foreground sm:max-w-[640px]">
    <SheetHeader><SheetTitle>{overviewLabels[metric]}</SheetTitle><SheetDescription>{sample ? `${total.toLocaleString()} is an illustrative sample total; only the ${rows.length} examples included in this sample can be inspected.` : `${total.toLocaleString()} reported; ${rows.length.toLocaleString()} indexed entries available.`}</SheetDescription></SheetHeader>
    <div className="space-y-4 px-4 pb-6"><p className="text-xs leading-5 text-slate-400">{metric === "tests" ? "Candidate test files identified by naming conventions. Tests were not executed." : metric === "routes" ? "Static route candidates; framework configuration and runtime reachability are not verified." : metric === "files" ? "Indexed repository files, including manifests and documentation. Excluded files are not shown." : "Syntax declarations and inline handlers; compiler semantics are not verified."}</p>
      <Input autoFocus aria-label={`Search ${overviewLabels[metric]}`} placeholder="Search names or paths" value={query} onChange={event => { setQuery(event.target.value); setLimit(40); }} />
      <p className="text-sm text-slate-400">{filtered.length} matching entries</p>
      <AskButton scope={{ title: overviewLabels[metric], nodeIds: filtered.slice(0, 24).map(node => node.id), notes: `${filtered.length} matching entries; reported total ${total}. ${sample ? "Illustrative sample inventory only." : "Static indexed inventory only."}` }}>Ask about these entries</AskButton>
      {filtered.slice(0, limit).map(node => <button key={node.id} className="block w-full rounded-xl border border-white/10 bg-card p-4 text-left hover:border-cyan-300/40 focus-visible:outline-2 focus-visible:outline-cyan-300" onClick={() => onInspect(node.id)}><strong className="block break-all">{node.label}</strong><span className="mt-1 block break-all text-xs text-cyan-300">{node.path}</span><span className="mt-2 block text-sm text-slate-400">{node.detail}</span><span className="mt-2 block text-xs">Inspect evidence →</span></button>)}
      {!filtered.length && <p className="text-slate-400">{sample && !rows.length ? "No examples for this category are included in the sample. Analyze a repository to see its actual inventory." : "No matching entries. Try another search."}</p>}
      {filtered.length > limit && <Button variant="outline" onClick={() => setLimit(limit + 40)}>Show more</Button>}
      <Button variant="ghost" onClick={onClose}>Back to overview</Button>
    </div>
  </SheetContent></Sheet>;
}
