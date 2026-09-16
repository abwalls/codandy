"use client";

import Link from "next/link";

import { useMemo, useState } from "react";
import { AnalysisAtlas, repositoryName } from "@/lib/analysis-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ArchitectureHub } from "@/components/architecture-hub";
import { GroundedSection } from "@/components/grounded-report";
import { AtlasComparison } from "@/components/atlas-comparison";
import { DependencyImpact } from "@/components/dependency-impact";
import { ThemePicker } from "@/components/theme-picker";
import { Dependencies } from "@/components/dependencies";
import { SourceView } from "@/components/source-view";
import { OverviewDetails } from "@/components/overview-details";
import { overviewLabels, overviewNodes, type OverviewMetric } from "@/lib/overview-details";
import { AskCodandyProvider, AskButton } from "@/components/ask-codandy";
import { buildAskContext } from "@/lib/ask-context";

export function LiveReport(props: { atlas: AnalysisAtlas; jobId: string | null; onExit: () => void }) {
  return <AskCodandyProvider jobId={props.jobId} contextFor={scope => buildAskContext(props.atlas, scope)}><LiveReportContent {...props} /></AskCodandyProvider>;
}

function LiveReportContent({ atlas, jobId, onExit }: { atlas: AnalysisAtlas; jobId: string | null; onExit: () => void }) {
  const [section, setSection] = useState("Overview");
  const [metric, setMetric] = useState<OverviewMetric | null>(null);
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");
  const [page, setPage] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [returnSection, setReturnSection] = useState<string | null>(null);
  const selected = atlas.nodes.find(node => node.id === selectedId);
  const nodesById = useMemo(() => new Map(atlas.nodes.map(node => [node.id, node])), [atlas]);
  // Only file paths are captured for the viewer, so directory and repository nodes skip it.
  const filePaths = useMemo(() => new Set(atlas.nodes.filter(node => node.kind === "file").map(node => node.path)), [atlas]);
  const filtered = useMemo(() => atlas.nodes.filter(node =>
    (kind === "all" || node.kind === kind) && `${node.label} ${node.path}`.toLowerCase().includes(query.toLowerCase())), [atlas, kind, query]);
  const selectedEdges = selected ? atlas.relationships.filter(edge => edge.source === selected.id || edge.target === selected.id) : [];
  const sections = ["Overview", "Codebase", "Architecture", "Application flows", "Developer guide", "Recommended changes", "Dependencies", "Snapshot comparison"];
  const reportSection = section === "Architecture" ? atlas.report?.architecture : section === "Application flows" ? atlas.report?.flows : section === "Developer guide" ? atlas.report?.guide : section === "Recommended changes" ? atlas.report?.recommendations : undefined;
  function inspect(id: string) {
    setReturnSection(section);
    setSelectedId(id); setQuery(""); setKind("all");
    setPage(Math.max(0, Math.floor(atlas.nodes.findIndex(node => node.id === id) / 50)));
    setSection("Codebase");
  }
  function download() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(atlas, null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = "atlas.json"; link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <main className="atlas-grid min-h-svh bg-[var(--background)] text-slate-100">
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-5 py-4">
      <div className="min-w-0"><div className="font-semibold text-cyan-200">Codandy <span className="ml-2 text-xs text-emerald-300">Real analysis</span></div>
        <h1 className="break-all text-lg">{repositoryName(atlas.repository)}</h1>
        <p className="text-xs text-slate-400">{atlas.repository.source === "archive" ? "Uploaded ZIP archive · no Git revision" : `${atlas.repository.branch || atlas.repository.ref} · commit ${atlas.repository.commit?.slice(0, 12) || "not detected"}`}</p></div>
      <div className="flex flex-wrap items-center gap-2"><ThemePicker /><Button variant="outline" onClick={download}>Download atlas</Button><Button onClick={onExit}>New analysis</Button></div>
    </header>
    <div className="mx-auto grid max-w-[1600px] gap-6 p-5 lg:grid-cols-[210px_minmax(0,1fr)]">
      <nav aria-label="Report sections" className="flex flex-wrap content-start gap-2 lg:flex-col"><Button variant="ghost" className="justify-start" asChild><Link href="/debugging">Errors & stacks</Link></Button><Button variant="outline" asChild><Link href="/whiteboard">Whiteboard</Link></Button><Button variant="outline" asChild><Link href="/integrations">Integrations</Link></Button>{sections.map(item => <Button key={item} variant="ghost" aria-current={section === item ? "page" : undefined} className={`justify-start ${section === item ? "bg-cyan-300/10 text-cyan-200" : "text-slate-400"}`} onClick={() => setSection(item)}>{item}</Button>)}<p className="p-3 text-xs text-slate-500">Ask Codandy can use your local ChatGPT/Codex connection. Your plan’s usage limits apply.</p></nav>
      <div className="min-w-0 space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-2xl font-semibold">{section}</h2><AskButton scope={{ title: section, nodeIds: section === "Codebase" ? filtered.slice(0, 24).map(node => node.id) : reportSection?.items.flatMap(item => item.node_ids), notes: reportSection ? JSON.stringify(reportSection.items.slice(0, 6).map(item => ({ title: item.title, description: item.description, basis: item.basis }))) : undefined }}>Ask about this page</AskButton></div>
        {!jobId && <p className="rounded-xl border border-amber-300/20 p-3 text-sm text-amber-200">Saved atlas snapshot. Reports and graph evidence are available offline; source text and commit freshness are not available.</p>}
        {section === "Codebase" && returnSection && <Button variant="outline" onClick={() => { setSection(returnSection); setReturnSection(null); }}>Back to {returnSection}</Button>}
        <div hidden={section !== "Dependencies"}><Dependencies atlas={atlas} jobId={jobId} onInspect={inspect} /></div>
        <div hidden={section !== "Snapshot comparison"}><AtlasComparison atlas={atlas} onInspect={inspect} /></div>
        {section === "Snapshot comparison" || section === "Dependencies" ? null : section === "Overview" ? <>
          <p className="text-slate-400">{atlas.report?.summary || "Manifest detection and syntax evidence from this repository. Routes and test files are candidates."}</p>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">{(Object.keys(overviewLabels) as OverviewMetric[]).map(key => <button key={key} onClick={() => setMetric(key)} className="rounded-xl border border-white/10 bg-[var(--surface-4)] p-4 text-left hover:border-cyan-300/40 focus-visible:outline-2 focus-visible:outline-cyan-300"><div className="text-2xl text-cyan-100">{atlas.counts[key] ?? 0}</div><div className="text-sm text-slate-400">{overviewLabels[key]}</div><span className="mt-2 block text-xs text-cyan-300">View details →</span></button>)}</div>
          <p className="text-sm text-slate-400">{atlas.counts.projects ?? 0} projects · {atlas.counts.relationships ?? 0} relationships · {atlas.counts.skipped ?? 0} skipped files</p>
          <section className="rounded-xl border border-white/10 bg-[var(--surface-4)] p-5"><h3 className="font-semibold">Detected technologies</h3><p className="mt-3 text-slate-400">{atlas.technologies.join(" · ") || "Not detected"}</p></section>
          <Button onClick={() => setSection("Codebase")}>Explore source evidence</Button>
          <section className="rounded-xl border border-white/10 p-5"><h3 className="font-semibold">Coverage and limitations</h3><ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-400">{atlas.limitations.map((item, i) => <li key={i}>{item}</li>)}</ul></section>
        </> : section === "Codebase" ? <>
          <div className="flex flex-wrap gap-3"><Input aria-label="Search codebase" placeholder="Search names or paths" className="min-w-0 flex-1" value={query} onChange={e => { setQuery(e.target.value); setPage(0); }} /><select aria-label="Node kind" className="rounded-md border border-white/10 bg-[var(--surface-4)] p-2" value={kind} onChange={e => { setKind(e.target.value); setPage(0); }}><option value="all">All kinds</option>{[...new Set(atlas.nodes.map(node => node.kind))].sort().map(value => <option key={value}>{value}</option>)}</select></div>
          <p className="text-sm text-slate-400">{filtered.length} matching nodes</p>
          <div className="grid gap-4 xl:grid-cols-2"><div className="space-y-2">{filtered.slice(page * 50, (page + 1) * 50).map(node => <button key={node.id} onClick={() => setSelectedId(node.id)} className={`block w-full rounded-xl border p-3 text-left ${selectedId === node.id ? "border-cyan-300/40 bg-cyan-300/10" : "border-white/10 bg-[var(--surface-4)]"}`}><span className="text-xs uppercase text-cyan-300">{node.kind}</span><div className="break-all font-medium">{node.label}</div><div className="break-all text-xs text-slate-500">{node.path || "Repository root"}</div></button>)}{!filtered.length && <p className="text-slate-400">No matching nodes detected.</p>}
            <div className="flex items-center gap-3"><Button disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</Button><span className="text-xs">Page {page + 1} of {Math.max(1, Math.ceil(filtered.length / 50))}</span><Button disabled={(page + 1) * 50 >= filtered.length} onClick={() => setPage(page + 1)}>Next</Button></div></div>
            <aside aria-label="Source evidence" className="order-first h-fit min-w-0 rounded-xl xl:order-last border border-white/10 bg-[var(--surface-4)] p-5">{selected ? <><h3 className="break-all text-lg font-semibold">{selected.label}</h3><p className="mt-2 text-sm text-slate-400">{selected.detail} · confidence {selected.confidence}%</p><h4 className="mt-5 font-medium">Evidence</h4>{selected.evidence.map((item, i) => <p key={i} className="mt-2 break-all text-sm text-slate-400">{item.path || "Repository root"}{item.lines ? `:${item.lines}` : ""} — {item.reason}</p>)}<h4 className="mt-5 font-medium">Relationships ({selectedEdges.length})</h4><div className="max-h-96 overflow-auto">{selectedEdges.map((edge, i) => <button key={i} className="mt-2 block w-full break-all rounded-lg bg-white/5 p-3 text-left text-xs" onClick={() => setSelectedId(edge.source === selected.id ? edge.target : edge.source)}>{nodesById.get(edge.source)?.label} → {nodesById.get(edge.target)?.label}<span className="mt-1 block text-cyan-200">{edge.type} · {edge.resolution} · {edge.confidence}%</span></button>)}</div>{!selectedEdges.length && <p className="mt-2 text-sm text-slate-400">No relationships detected.</p>}
              <div className="mt-4"><AskButton scope={{ title: `${selected.kind}: ${selected.label}`, nodeIds: [selected.id, ...selectedEdges.flatMap(edge => [edge.source, edge.target])] }}>Ask about this node</AskButton></div>
              {filePaths.has(selected.path) ? <><DependencyImpact key={`${selected.kind}:${selected.path}`} atlas={atlas} path={selected.path} kind={selected.kind === "project" ? "project" : "file"} onInspect={setSelectedId} /><h4 className="mt-5 font-medium">Source</h4>
              <SourceView key={`${jobId}:${selected.path}`} jobId={jobId} path={selected.path} lines={selected.evidence[0]?.lines} /></>
                : <p className="mt-5 text-sm text-slate-400">This node is not backed by a single source file.</p>}</> : <p className="text-sm text-slate-400">Select a node to inspect its source locations and relationships.</p>}</aside></div>
        </> : reportSection ? <>{section === "Architecture" && <ArchitectureHub key={jobId ?? "saved-atlas"} atlas={atlas} jobId={jobId} onInspect={inspect} />}<GroundedSection key={section} section={reportSection} atlas={atlas} onInspect={inspect} recommendations={section === "Recommended changes"} /></> : <section className="rounded-xl border border-white/10 bg-[var(--surface-4)] p-6"><p className="text-xs uppercase text-amber-300">Reanalysis needed</p><p className="mt-3 text-slate-400">This older atlas does not contain generated reports. Start a new analysis to build these sections.</p></section>}
      </div>
    </div>
    {metric && <OverviewDetails key={metric} metric={metric} total={atlas.counts[metric] ?? 0} rows={overviewNodes(atlas, metric)} onClose={() => setMetric(null)} onInspect={id => { setMetric(null); inspect(id); }} />}
  </main>;
}
