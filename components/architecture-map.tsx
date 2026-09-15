"use client";

import { useMemo, useState } from "react";
import { ArrowRight, Boxes, Focus, FolderTree, LayoutGrid, Minus, Network, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AskButton } from "@/components/ask-codandy";
import { DependencyMatrixView, LayeredDiagram } from "@/components/architecture-diagrams";
import { layeredLayout, linkKey } from "@/lib/architecture-layout";
import { architectureMap } from "@/lib/architecture-map";
import type { AnalysisAtlas } from "@/lib/analysis-api";

// Rendering budgets. Past these, search, focus or expansion narrows the view instead of shrinking labels.
const LAYERED_LIMIT = 40;
const MATRIX_LIMIT = 60;
const MOBILE_LIMIT = 12;

export function ArchitectureMap({ atlas, onInspect }: { atlas: AnalysisAtlas; onInspect: (id: string) => void }) {
  const [mode, setMode] = useState<"folders" | "projects">("folders");
  const [view, setView] = useState<"layered" | "matrix">("layered");
  const [depth, setDepth] = useState(1);
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(() => new Set());
  const [query, setQuery] = useState("");
  const [focus, setFocus] = useState<string | null>(null);
  const [selectedLink, setSelectedLink] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const graph = useMemo(() => architectureMap(atlas, mode, depth, expanded), [atlas, mode, depth, expanded]);
  const byId = useMemo(() => new Map(atlas.nodes.map(node => [node.id, node])), [atlas]);
  const unit = mode === "folders" ? "files" : "project";
  const limit = view === "matrix" ? MATRIX_LIMIT : LAYERED_LIMIT;

  const { ordered, shown, links } = useMemo(() => {
    const adjacent = new Set(graph.links.filter(link => link.source === focus || link.target === focus).flatMap(link => [link.source, link.target]));
    const eligible = graph.groups.filter(group => group.label.toLowerCase().includes(query.toLowerCase()) && (!focus || group.id === focus || adjacent.has(group.id)));
    const ordered = focus ? [...eligible.filter(group => group.id === focus), ...eligible.filter(group => group.id !== focus)] : eligible;
    const shown = ordered.slice(0, limit);
    const ids = new Set(shown.map(group => group.id));
    return { ordered, shown, links: graph.links.filter(link => ids.has(link.source) && ids.has(link.target)) };
  }, [graph, query, focus, limit]);
  const layout = useMemo(() => layeredLayout(shown, links), [shown, links]);
  const mobile = ordered.slice(0, MOBILE_LIMIT);
  const mobileIds = new Set(mobile.map(group => group.id));
  const mobileLinks = links.filter(link => mobileIds.has(link.source) && mobileIds.has(link.target));
  const labelOf = (id: string) => graph.groups.find(group => group.id === id)?.label ?? id;

  const selected = graph.groups.find(group => group.id === focus);
  const chosenLink = graph.links.find(link => linkKey(link) === selectedLink) ?? null;
  const relevant = focus ? graph.links.filter(link => link.source === focus || link.target === focus) : links;
  const expandable = mode === "folders" && !!selected && selected.id !== "."
    && selected.nodeIds.some(id => (byId.get(id)?.path ?? "").split("/").length - 1 > selected.id.split("/").length);

  function reset() { setFocus(null); setSelectedLink(null); setQuery(""); setExpanded(new Set()); }
  function changeMode(value: "folders" | "projects") { setMode(value); reset(); }
  function chooseFocus(id: string | null) { setFocus(id); setSelectedLink(null); }

  return <section className="overflow-hidden rounded-2xl border border-white/10 bg-[var(--surface-4)]" aria-label="Interactive architecture map">
    <div className="flex flex-wrap items-start justify-between gap-4 border-b border-white/10 p-5 sm:p-6">
      <div>
        <p className="flex items-center gap-2 text-xs font-medium uppercase tracking-widest text-cyan-300"><Network className="size-4" />Architecture map</p>
        <h3 className="mt-2 text-xl font-semibold">See the dependencies between {mode === "folders" ? "source areas" : "projects"}</h3>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">{view === "layered"
          ? "Importers sit above what they depend on. Select a group to focus its neighbours, or split a folder into its subfolders."
          : "Each row imports the columns it has marks in. Rows follow the layer order, so marks below the diagonal are import cycles."}</p>
      </div>
      <AskButton scope={{ title: "Architecture dependency map", nodeIds: (selected?.nodeIds || shown.flatMap(group => group.nodeIds)).slice(0, 24), notes: "Static dependency map; folder grouping is based on source paths, not verified runtime services." }}>Ask about this map</AskButton>
    </div>

    <div className="flex flex-wrap items-center gap-3 p-4">
      <div className="flex gap-1 rounded-lg border border-white/10 p-1" role="group" aria-label="Group by">
        <Button size="sm" variant={mode === "folders" ? "secondary" : "ghost"} aria-pressed={mode === "folders"} onClick={() => changeMode("folders")}><FolderTree className="size-4" />Source areas</Button>
        <Button size="sm" variant={mode === "projects" ? "secondary" : "ghost"} aria-pressed={mode === "projects"} onClick={() => changeMode("projects")}><Boxes className="size-4" />Projects</Button>
      </div>
      <div className="flex gap-1 rounded-lg border border-white/10 p-1" role="group" aria-label="Diagram">
        <Button size="sm" variant={view === "layered" ? "secondary" : "ghost"} aria-pressed={view === "layered"} onClick={() => setView("layered")}><Network className="size-4" />Layered</Button>
        <Button size="sm" variant={view === "matrix" ? "secondary" : "ghost"} aria-pressed={view === "matrix"} onClick={() => setView("matrix")}><LayoutGrid className="size-4" />Matrix</Button>
      </div>
      {mode === "folders" && <label className="flex items-center gap-2 text-xs text-slate-400">Folder depth
        <select className="rounded-lg border border-white/10 bg-card p-2" value={depth} onChange={event => { setDepth(Number(event.target.value)); reset(); }}>
          <option value={1}>1 level</option><option value={2}>2 levels</option><option value={3}>3 levels</option>
        </select>
      </label>}
      <Input className="min-w-40 flex-1" aria-label="Find architecture group" placeholder="Find a source area…" value={query} onChange={event => { setQuery(event.target.value); chooseFocus(null); }} />
      <div className="flex gap-1">
        <Button variant="ghost" size="icon" aria-label="Zoom out architecture map" disabled={zoom <= 0.6} onClick={() => setZoom(value => Math.max(0.6, value - 0.2))}><Minus /></Button>
        <Button variant="ghost" size="icon" aria-label="Zoom in architecture map" disabled={zoom >= 1.8} onClick={() => setZoom(value => Math.min(1.8, value + 0.2))}><Plus /></Button>
        <Button variant="ghost" size="icon" aria-label="Reset architecture map" onClick={() => { reset(); setZoom(1); }}><Focus /></Button>
      </div>
    </div>

    {layout.cycles.length > 0 && <p role="status" className="mx-4 mb-3 rounded-lg border p-3 text-sm leading-6" style={{ borderColor: "var(--chart-5)" }}>
      {layout.cycles.length} import cycle{layout.cycles.length === 1 ? "" : "s"} between groups in view: {layout.cycles.map(cycle => cycle.map(labelOf).join(" ↔ ")).join("; ")}. {view === "layered" ? "The edge that closes each cycle is drawn dotted on the right." : "The edge that closes each cycle sits below the diagonal."}
    </p>}

    {!shown.length ? <p className="p-8 text-slate-400">{graph.groups.length ? "No groups match this search." : "No supported projects were detected. Switch to Source areas to explore indexed files."}</p> : <>
      <div className="space-y-3 border-y border-white/[0.06] bg-[var(--background)] p-4 sm:hidden" aria-label="Mobile dependency diagram">
        <p className="text-xs text-slate-400">Select an area or follow an arrow to explore its dependencies.</p>
        <div className="flex flex-wrap gap-2">{mobile.map(group => <button key={group.id} aria-pressed={focus === group.id} onClick={() => chooseFocus(focus === group.id ? null : group.id)} className={`rounded-lg border px-3 py-2 text-left text-xs ${focus === group.id ? "border-cyan-300/50 text-cyan-200" : "border-white/10 text-slate-300"}`}>{group.label}<span className="mt-1 block text-slate-500">{group.nodeIds.length} {unit}</span></button>)}</div>
        {mobileLinks.map(link => <div key={linkKey(link)} className={`rounded-xl border bg-[var(--surface-4)] p-3 ${link.inferred ? "border-amber-300/20" : "border-cyan-300/20"}`}>
          <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
            <button className="break-all text-left text-sm" onClick={() => chooseFocus(link.source)}>{labelOf(link.source)}</button>
            <ArrowRight aria-label="depends on" className={`size-4 ${link.inferred ? "text-amber-300" : "text-cyan-300"}`} />
            <button className="break-all text-right text-sm" onClick={() => chooseFocus(link.target)}>{labelOf(link.target)}</button>
          </div>
          <p className="mt-2 text-xs text-slate-500">{link.count} relationships · {link.inferred ? "includes inferred" : "resolved"}</p>
        </div>)}
        {!mobileLinks.length && <p className="text-sm text-slate-500">No supported connections in this view.</p>}
      </div>
      <div className="hidden overflow-auto border-y border-white/[0.06] bg-[var(--background)] p-3 sm:block" tabIndex={0} aria-label="Scrollable dependency diagram">
        {view === "layered"
          ? <LayeredDiagram layout={layout} groups={shown} unit={unit} zoom={zoom} focus={focus} onFocus={chooseFocus} />
          : <DependencyMatrixView groups={shown} links={links} zoom={zoom} selected={selectedLink} onSelect={setSelectedLink} />}
      </div>
    </>}

    <div className="flex flex-wrap gap-x-5 gap-y-2 px-5 py-3 text-xs text-slate-400">
      {view === "layered"
        ? <><span className="text-cyan-300">━ Resolved</span><span className="text-amber-300">┄ Inferred</span><span style={{ color: "var(--chart-5)" }}>⋯ Closes an import cycle</span><span>Thicker lines = more imports</span></>
        : <><span className="text-cyan-300">■ Above the diagonal: follows the layers</span><span style={{ color: "var(--chart-5)" }}>■ Below: closes an import cycle</span><span>Darker = more imports</span></>}
      <span>{shown.length}/{graph.groups.length} groups · {graph.links.length - links.length} connections outside view · {mode === "projects" ? `${graph.unresolved} unresolved project references omitted` : graph.classified ? `${graph.unresolved} unresolved local imports · ${graph.external} package, standard-library or namespace imports not drawn` : `${graph.external} imports without a resolved local target not drawn (reanalyze to separate packages from unresolved local imports)`}</span>
    </div>

    <div className="grid gap-5 border-t border-white/10 p-5 lg:grid-cols-2">
      <div>
        <h4 className="font-medium">{selected ? selected.label : "Explore a source area"}</h4>
        <p className="mt-2 text-sm leading-6 text-slate-400">{selected
          ? "Open a captured node below, or choose a connection to focus its source group."
          : `The ${view} view shows up to ${limit} groups, ranked by dependency activity. Search, focus or split a folder to narrow it. Folder names do not establish architectural layers or runtime services.`}</p>
        {(expandable || expanded.size > 0) && <div className="mt-3 flex flex-wrap gap-2">
          {expandable && <Button size="sm" variant="outline" onClick={() => { setExpanded(new Set([...expanded, selected!.id])); chooseFocus(null); }}>Split {selected!.label} into subfolders</Button>}
          {expanded.size > 0 && <Button size="sm" variant="ghost" onClick={() => { setExpanded(new Set()); chooseFocus(null); }}>Collapse all folders</Button>}
        </div>}
        {selected && <div className="mt-3 max-h-52 space-y-1 overflow-auto">
          {selected.nodeIds.slice(0, 40).map(id => <button key={id} className="block w-full break-all rounded-lg p-2 text-left text-xs text-cyan-200 hover:bg-white/5" onClick={() => onInspect(id)}>{byId.get(id)?.path || byId.get(id)?.label}</button>)}
          {selected.nodeIds.length > 40 && <p className="text-xs text-slate-500">First 40 locations shown. Use Codebase to inspect the complete inventory.</p>}
        </div>}
      </div>
      <div>
        {chosenLink && <div className="mb-4 rounded-lg border border-white/[0.07] p-3" role="status">
          <p className="text-sm font-medium">{labelOf(chosenLink.source)} → {labelOf(chosenLink.target)}</p>
          <p className="mt-1 text-xs text-slate-500">{chosenLink.count} import{chosenLink.count === 1 ? "" : "s"} · {chosenLink.inferred} inferred</p>
          <div className="mt-2 max-h-40 space-y-1 overflow-auto">{chosenLink.nodeIds.filter(id => byId.get(id)?.kind === "file").slice(0, 16).map(id => <button key={id} className="block w-full break-all rounded p-1 text-left text-xs text-cyan-200 hover:bg-white/5" onClick={() => onInspect(id)}>{byId.get(id)?.path}</button>)}</div>
        </div>}
        <h4 className="font-medium">{selected ? "Connected groups" : "Visible connections"}</h4>
        <div className="mt-3 max-h-60 space-y-2 overflow-auto">
          {relevant.slice(0, 30).map(link => <div key={linkKey(link)} className="rounded-lg border border-white/[0.07] p-3">
            <button className="flex w-full items-center gap-2 text-left text-xs text-slate-300" onClick={() => { chooseFocus(link.source); setQuery(""); }}>
              <span className="min-w-0 flex-1 break-all">{labelOf(link.source)}</span>
              <ArrowRight className="size-3 shrink-0 text-cyan-300" />
              <span className="min-w-0 flex-1 break-all">{labelOf(link.target)}</span>
            </button>
            <div className="mt-2 flex items-center justify-between gap-2 text-xs text-slate-500">
              <span>{link.count} links · {link.inferred} inferred</span>
              <button className="text-cyan-200 hover:underline" onClick={() => onInspect(link.nodeIds[0])}>Inspect evidence</button>
            </div>
          </div>)}
          {!relevant.length && <p className="text-sm text-slate-500">No supported connections for this view. Disconnected groups remain visible; unresolved relationships are not filled in.</p>}
        </div>
      </div>
    </div>
  </section>;
}
