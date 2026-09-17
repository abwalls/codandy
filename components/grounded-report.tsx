"use client";

import { useMemo, useState } from "react";
import { ArrowDown, ArrowUpRight, FileCode2, Network, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { CreateTicket } from "@/components/create-ticket";
import { AskButton } from "@/components/ask-codandy";
import type { AnalysisAtlas, GroundedReportItem, GroundedReportSection } from "@/lib/analysis-api";

const categoryLabels: Record<string, string> = {
  inferred_boundary: "Inferred boundaries", external_dependency: "Declared dependencies",
  boundary_dependency: "Cross-folder imports",
  project_dependency: "Project references",
  import_cycle: "Circular imports",
  project: "Projects", directory: "Source layout", shared_module: "Shared modules",
  route_flow: "Route paths", module_dependency: "Module dependencies", guide: "Change locations",
  maintainability: "Maintainability", potential_security_risk: "Potential security risks",
};

function EvidenceCard({ item, nodes, onInspect, recommendations, sourceScope }: { sourceScope: string; recommendations: boolean; item: GroundedReportItem; nodes: Map<string, AnalysisAtlas["nodes"][number]>; onInspect: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const visibleIds = expanded ? item.node_ids : item.node_ids.slice(0, 5);
  return <article className="min-w-0 rounded-2xl border border-white/10 bg-[var(--surface-4)] p-5 sm:p-6">
    <div className="mb-3 flex flex-wrap items-center gap-2 text-[11px] font-medium uppercase tracking-wider">
      <span className="text-cyan-300">{categoryLabels[item.category] || item.category}</span>
      <span className="rounded-full border border-white/10 px-2 py-1 text-slate-400">{item.basis} · {item.confidence}% confidence</span>
      {item.priority && <span className="rounded-full bg-amber-300/10 px-2 py-1 text-amber-200">{item.priority} priority</span>}
      {item.effort && <span className="text-slate-400">{item.effort} effort</span>}
    </div>
    <h3 className="break-words text-lg font-semibold leading-snug text-white">{item.title}</h3>
    <p className="mt-3 text-sm leading-6 text-slate-400">{item.description}</p>
    <div className="mt-3"><AskButton scope={{ title: `${item.priority ? "Finding" : "Report item"}: ${item.title}`, nodeIds: item.node_ids, notes: JSON.stringify({ description: item.description, basis: item.basis, approach: item.approach, verification: item.verification }) }}>Ask about this finding</AskButton></div>
    {Object.keys(item.metrics).length > 0 && <dl className="mt-4 flex flex-wrap gap-4 border-y border-white/[0.06] py-3">{Object.entries(item.metrics).map(([name, value]) => <div key={name}><dd className="text-xl font-semibold text-cyan-100">{value}</dd><dt className="text-xs capitalize text-slate-500">{name.replaceAll("_", " ")}</dt></div>)}</dl>}
    {item.steps.length > 0 && <div className="mt-5 space-y-2" aria-label={`Static path for ${item.title}`}>{item.steps.map((step, index) => <div key={`${index}-${step.source}`} className="rounded-xl border border-white/[0.07] bg-[var(--background)] p-3">
      <button className="block max-w-full break-all text-left text-sm text-slate-200 hover:text-cyan-200" onClick={() => onInspect(step.source)}>{nodes.get(step.source)?.label}</button>
      <div className="my-2 flex items-center gap-2 text-[11px] text-slate-500"><ArrowDown className="size-3" />{step.type.replaceAll("_", " ")} · {step.resolution}</div>
      <button className="block max-w-full break-all text-left text-sm text-cyan-200 hover:underline" onClick={() => onInspect(step.target)}>{nodes.get(step.target)?.label}</button>
    </div>)}</div>}
    {item.approach.length > 0 && <div className="mt-5"><h4 className="text-sm font-semibold text-slate-200">Recommended approach</h4><ol className="mt-2 list-decimal space-y-2 pl-5 text-sm leading-6 text-slate-400">{item.approach.map((line, i) => <li key={i}>{line}</li>)}</ol></div>}
    {item.verification.length > 0 && <div className="mt-5"><h4 className="flex items-center gap-2 text-sm font-semibold text-slate-200"><ShieldCheck className="size-4 text-emerald-300" />How to verify</h4><ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-6 text-slate-400">{item.verification.map((line, i) => <li key={i}>{line}</li>)}</ul></div>}
    {recommendations && <div className="mt-4"><CreateTicket key={JSON.stringify([sourceScope, item.id])} seed={{ title: item.title, source_kind: "recommendation", source_id: JSON.stringify([sourceScope, item.id]), description: [
      `Static review opportunity (${item.basis}); verify before implementation.`, item.description,
      "Suggested approach:", ...item.approach.map(value => `- ${value}`),
      "Verification:", ...item.verification.map(value => `- ${value}`),
      "Source references (no source bodies):", ...item.node_ids.slice(0, 30).map(id => { const node = nodes.get(id); return node ? `${node.path || "Repository root"}${node.evidence[0]?.lines ? `:${node.evidence[0].lines}` : ""}` : id; }),
      ...(item.node_ids.length > 30 ? ["Additional source references omitted; review the finding in Codandy."] : []),
    ].join("\n\n") }} /></div>}
    <div className="mt-5 border-t border-white/[0.07] pt-4"><h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">Source evidence</h4>
      <div className="space-y-2">{visibleIds.map(id => { const node = nodes.get(id); return node ? <button key={id} onClick={() => onInspect(id)} className="flex w-full min-w-0 items-start gap-2 rounded-lg px-2 py-2 text-left text-xs text-slate-400 hover:bg-white/5 hover:text-cyan-200"><FileCode2 className="mt-0.5 size-3.5 shrink-0" /><span className="min-w-0 flex-1 break-all"><span className="block font-medium text-slate-200">{node.label}</span>{node.path || "Repository root"}{node.evidence[0]?.lines ? `:${node.evidence[0].lines}` : ""}</span><ArrowUpRight className="size-3.5 shrink-0" /></button> : null; })}</div>
      {item.node_ids.length > 5 && <Button variant="ghost" size="sm" className="mt-2 text-cyan-200" onClick={() => setExpanded(!expanded)}>{expanded ? "Show fewer locations" : `Show all ${item.node_ids.length} locations`}</Button>}
    </div>
  </article>;
}

export function GroundedSection({ section, atlas, onInspect, recommendations = false }: { section: GroundedReportSection; atlas: AnalysisAtlas; onInspect: (id: string) => void; recommendations?: boolean }) {
  const [category, setCategory] = useState("all");
  const [search, setSearch] = useState("");
  const [limit, setLimit] = useState(12);
  const nodes = useMemo(() => new Map(atlas.nodes.map(node => [node.id, node])), [atlas]);
  const categories = [...new Set(section.items.map(item => item.category))];
  const filtered = section.items.filter(item => (category === "all" || item.category === category) &&
    `${item.title} ${item.description} ${item.node_ids.map(id => nodes.get(id)?.path).join(" ")}`.toLowerCase().includes(search.toLowerCase()));
  return <div className="space-y-5">
    <div className="rounded-xl border border-cyan-300/15 bg-cyan-300/[0.04] p-4 text-sm leading-6 text-slate-400"><Network className="mb-2 size-4 text-cyan-300" />{recommendations ? "Rule-based review opportunities, each with evidence, effort, and verification steps. Potential risks require investigation; no vulnerabilities are claimed as verified." : "Generated from this repository’s static graph. Open any evidence location to inspect its source and relationships."}</div>
    {section.items.length > 0 ? <>
      <div className="flex flex-wrap gap-3"><Input aria-label="Search report" placeholder="Search report or source paths" value={search} onChange={e => { setSearch(e.target.value); setLimit(12); }} className="min-w-0 flex-1" />
        <select aria-label="Report category" value={category} onChange={e => { setCategory(e.target.value); setLimit(12); }} className="max-w-full rounded-md border border-white/10 bg-[var(--surface-4)] p-2 text-sm"><option value="all">All categories</option>{categories.map(value => <option key={value} value={value}>{categoryLabels[value] || value}</option>)}</select></div>
      <p className="text-xs text-slate-500">{filtered.length} matching {recommendations ? "review opportunities" : "report items"}</p>
      <div className="grid items-start gap-4 xl:grid-cols-2">{filtered.slice(0, limit).map(item => <EvidenceCard key={item.id} item={item} nodes={nodes} onInspect={onInspect} recommendations={recommendations} sourceScope={JSON.stringify([atlas.repository.url || atlas.repository.name, atlas.repository.commit || atlas.repository.ref])} />)}</div>
      {!filtered.length && <p className="rounded-xl border border-white/10 p-6 text-slate-400">No report items match this search.</p>}
      {filtered.length > limit && <Button variant="outline" onClick={() => setLimit(limit + 12)}>Show more report items</Button>}
    </> : <div className="rounded-2xl border border-white/10 bg-[var(--surface-4)] p-6"><h3 className="text-lg font-semibold">{recommendations ? "No rule matches found" : "No supported evidence detected"}</h3><p className="mt-2 text-sm leading-6 text-slate-400">{recommendations ? "The supported rules did not identify a review opportunity in the indexed source. This does not establish that the repository is secure, fast, or free of defects." : "The current analyzer did not find enough supported graph evidence for this section. Check the codebase index and coverage limitations below."}</p></div>}
    <details className="rounded-xl border border-white/10 p-4"><summary className="cursor-pointer text-sm font-medium text-slate-300">Scope and limitations</summary><ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6 text-slate-400">{section.limitations.map((line, i) => <li key={i}>{line}</li>)}</ul></details>
  </div>;
}
