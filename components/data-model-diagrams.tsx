"use client";

import { useId, useMemo, useState } from "react";
import type { KeyboardEvent, ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { Braces, Check, Copy, Database, Focus, GitFork, KeyRound, Minus, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AskButton } from "@/components/ask-codandy";
import { RECORD_HEADER, RECORD_ROW, recordEdgePath, recordEndDirections, recordLayout } from "@/lib/architecture-layout";
import {
  contractAreas, contractsView, describeEntityLink, describeTypeLink, entityKeys, entitySubtitle, erdView,
  mermaidClassDiagram, mermaidErDiagram, TYPE_KIND_LABELS, typeFolder,
  type DiagramLink, type DiagramRecord, type LinkEndMark,
} from "@/lib/structure-diagram";
import type { AnalysisAtlas } from "@/lib/analysis-api";
import type { SchemaSourceKind, StructureDocument } from "@/lib/structure-api";

const RECORD_WIDTH = 250;
// Rendering budgets. Past these, search, focus or a narrower folder shrinks the view instead.
const DIAGRAM_LIMIT = 60;
const MOBILE_LIMIT = 12;
const SOURCE_LABELS: Record<SchemaSourceKind, string> = { prisma: "Prisma schema", sql: "SQL files", sqlalchemy: "SQLAlchemy models", django: "Django models" };
const BADGE_COLORS = { PK: "var(--chart-4)", FK: "var(--primary)", UQ: "var(--chart-2)" } as const;

type ViewProps = { structure: StructureDocument; atlas: AnalysisAtlas; onInspect: (id: string) => void };

const truncate = (value: string, length: number) => (value.length > length ? `${value.slice(0, length - 1)}…` : value);

function activate(event: KeyboardEvent, action: () => void) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    action();
  }
}

/** Crow's-foot mark at a record edge; `direction` points away from the record. */
function EndMark({ x, y, direction, mark }: { x: number; y: number; direction: 1 | -1; mark: LinkEndMark }) {
  const at = (distance: number) => x + direction * distance;
  const bar = (distance: number) => <path d={`M ${at(distance)} ${y - 6} L ${at(distance)} ${y + 6}`} />;
  const ring = (distance: number) => <circle cx={at(distance)} cy={y} r={4} fill="var(--background)" />;
  if (mark.cardinality === "unknown") {
    return <text x={at(12)} y={y - 5} textAnchor="middle" fontSize="11" fill="var(--muted-foreground)" stroke="none">?</text>;
  }
  if (mark.cardinality === "many") {
    return <g fill="none">
      <path d={`M ${at(14)} ${y} L ${x} ${y - 7} M ${at(14)} ${y} L ${x} ${y + 7}`} />
      {mark.optional === false ? bar(18) : mark.optional === true ? ring(23) : null}
    </g>;
  }
  return <g fill="none">{bar(8)}{mark.optional === false ? bar(13) : mark.optional === true ? ring(17) : null}</g>;
}

const headerPath = (x: number, y: number, width: number, height: number, radius = 10) =>
  `M ${x} ${y + height} V ${y + radius} Q ${x} ${y} ${x + radius} ${y} H ${x + width - radius} Q ${x + width} ${y} ${x + width} ${y + radius} V ${y + height} Z`;

export function RecordDiagram({ records, links, variant, zoom, focus, onFocus, label }: {
  records: DiagramRecord[];
  links: DiagramLink[];
  variant: "erd" | "contracts";
  zoom: number;
  focus: string | null;
  onFocus: (id: string | null) => void;
  label: string;
}) {
  const marker = useId().replaceAll(":", "");
  const layout = useMemo(() => recordLayout(records.map(record => ({ id: record.id, rows: record.rows.length + (record.hiddenRows ? 1 : 0) })), links, { width: RECORD_WIDTH }), [records, links]);
  const byId = useMemo(() => new Map(records.map(record => [record.id, record])), [records]);
  const focusRecord = records.find(record => record.refId === focus && !record.stub)?.id ?? null;
  const near = focusRecord ? new Set(links.filter(link => link.source === focusRecord || link.target === focusRecord).flatMap(link => [link.source, link.target])) : null;
  return <svg viewBox={`0 0 ${layout.width} ${layout.height}`} role="group" aria-label={label}
    style={{ width: `${layout.width * zoom}px`, maxWidth: "none" }} className="block">
    <defs>
      <marker id={`${marker}-uses`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--primary)" />
      </marker>
      <marker id={`${marker}-inferred`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--chart-4)" />
      </marker>
      <marker id={`${marker}-extends`} viewBox="0 0 12 12" refX="11" refY="6" markerWidth="10" markerHeight="10" orient="auto-start-reverse">
        <path d="M 1 1 L 11 6 L 1 11 z" fill="var(--background)" stroke="var(--chart-3)" strokeWidth="1.5" />
      </marker>
    </defs>
    {layout.edges.map(edge => {
      const link = edge.link;
      const dim = focusRecord !== null && link.source !== focusRecord && link.target !== focusRecord;
      const stroke = link.kind === "extends" ? "var(--chart-3)" : link.dashed ? "var(--chart-4)" : "var(--primary)";
      const first = edge.points[0];
      const last = edge.points[edge.points.length - 1];
      const directions = recordEndDirections(edge);
      const arrow = variant === "contracts" ? `url(#${marker}-${link.kind === "extends" ? "extends" : link.dashed ? "inferred" : "uses"})` : undefined;
      return <g key={link.id} opacity={dim ? 0.12 : 1} stroke={stroke} strokeWidth={1.6}>
        <path d={recordEdgePath(edge)} fill="none" strokeOpacity={0.85} strokeDasharray={link.dashed ? "6 5" : undefined} markerEnd={arrow}>
          <title>{link.description}</title>
        </path>
        {link.start && <EndMark x={first.x} y={first.y} direction={directions.start} mark={link.start} />}
        {link.end && <EndMark x={last.x} y={last.y} direction={directions.end} mark={link.end} />}
      </g>;
    })}
    {layout.isolatedTop !== null && <g>
      <line x1={24} x2={layout.width - 24} y1={layout.isolatedTop + 8} y2={layout.isolatedTop + 8} stroke="var(--border)" strokeDasharray="4 6" />
      <text x={24} y={layout.isolatedTop + 24} fontSize="11" fill="var(--muted-foreground)">{variant === "erd" ? "No relationships to other tables in this view" : "No links to other types in this view"}</text>
    </g>}
    {layout.records.map(placed => {
      const record = byId.get(placed.id)!;
      const active = focusRecord === record.id;
      const faded = near !== null && !near.has(record.id) && !active;
      const refId = record.refId;
      const toggle = () => { if (refId) onFocus(active ? null : refId); };
      const interactive = refId ? {
        role: "button", tabIndex: 0, "aria-pressed": active, onClick: toggle, onKeyDown: (event: KeyboardEvent) => activate(event, toggle),
        className: "cursor-pointer outline-none [&:focus-visible>rect:first-of-type]:stroke-[var(--foreground)]",
      } : { role: "img" };
      const { x, y, width, height } = placed;
      return <g key={record.id} {...interactive} opacity={faded ? 0.35 : 1}
        aria-label={`${record.title}${record.subtitle ? `, ${record.subtitle}` : ""}, ${record.rows.length + record.hiddenRows} ${variant === "erd" ? "columns" : "members"}${refId ? `; ${active ? "clear focus" : "focus its relationships"}` : ""}`}>
        <title>{`${record.title}${record.subtitle ? ` · ${record.subtitle}` : ""}`}</title>
        <rect x={x} y={y} width={width} height={height} rx={10} fill="var(--surface-4)" stroke={active ? "var(--primary)" : "var(--border)"}
          strokeWidth={active ? 2.5 : 1.2} strokeDasharray={record.stub ? "5 4" : undefined} />
        <path d={headerPath(x, y, width, record.rows.length ? RECORD_HEADER : height)} fill={record.stub ? "var(--muted-foreground)" : variant === "erd" ? "var(--primary)" : "var(--chart-3)"} fillOpacity={0.08} />
        <text x={x + 12} y={y + 18} fontSize="13" fontWeight="600" fill="var(--foreground)">{truncate(record.title, 30)}</text>
        <text x={x + 12} y={y + 32} fontSize="10.5" fill="var(--muted-foreground)">{truncate(record.subtitle, 42)}</text>
        {record.rows.length > 0 && <line x1={x} x2={x + width} y1={y + RECORD_HEADER} y2={y + RECORD_HEADER} stroke="var(--border)" />}
        {record.rows.map((row, index) => {
          const middle = y + RECORD_HEADER + index * RECORD_ROW + RECORD_ROW / 2;
          const indent = 12 + row.badges.length * 20;
          return <g key={`${row.name}:${index}`}>
            {row.badges.map((badge, position) => <text key={badge} x={x + 12 + position * 20} y={middle} dy="0.35em" fontSize="9" fontWeight="700" fill={BADGE_COLORS[badge]}>{badge}</text>)}
            <text x={x + indent} y={middle} dy="0.35em" fontSize="12" fill="var(--foreground)">{truncate(row.name, Math.max(8, 20 - row.badges.length * 3))}</text>
            <text x={x + width - 10} y={middle} dy="0.35em" textAnchor="end" fontSize="11" fill="var(--muted-foreground)">{truncate(`${row.type}${row.nullable ? "?" : ""}`, 15)}</text>
          </g>;
        })}
        {record.hiddenRows > 0 && <text x={x + 12} y={y + RECORD_HEADER + record.rows.length * RECORD_ROW + RECORD_ROW / 2} dy="0.35em" fontSize="11" fill="var(--muted-foreground)">{`+${record.hiddenRows} more`}</text>}
      </g>;
    })}
  </svg>;
}

function LegendMark({ mark, children }: { mark: LinkEndMark; children: ReactNode }) {
  return <span className="inline-flex items-center gap-1.5">
    <svg width="40" height="16" viewBox="0 0 40 16" aria-hidden="true" stroke="var(--primary)" strokeWidth="1.5">
      <line x1="0" x2="36" y1="8" y2="8" />
      <line x1="36" x2="36" y1="1" y2="15" stroke="var(--muted-foreground)" strokeWidth="2" />
      <EndMark x={36} y={8} direction={-1} mark={mark} />
    </svg>
    {children}
  </span>;
}

function useCopy() {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  const copy = (text: string) => {
    if (!navigator.clipboard) { setState("failed"); return; }
    navigator.clipboard.writeText(text).then(() => setState("copied"), () => setState("failed"));
  };
  return [state, copy] as const;
}

function useFileNodes(atlas: AnalysisAtlas) {
  return useMemo(() => new Map(atlas.nodes.filter(node => node.kind === "file").map(node => [node.path, node.id])), [atlas]);
}

function Evidence({ path, lines, reason, target, onInspect }: { path: string; lines?: string | null; reason: string; target: string | null | undefined; onInspect: (id: string) => void }) {
  const text = `${path}${lines ? `:${lines}` : ""}`;
  return target
    ? <button className="block break-all text-left text-xs text-cyan-200 hover:underline" title={reason} onClick={() => onInspect(target)}>{text}</button>
    : <span className="block break-all text-xs text-slate-500" title={reason}>{text}</span>;
}

function Controls({ zoom, onZoom, onReset, copy, onCopy, children }: { zoom: number; onZoom: (value: number) => void; onReset: () => void; copy: "idle" | "copied" | "failed"; onCopy: () => void; children: ReactNode }) {
  return <div className="flex flex-wrap items-center gap-3 p-4">
    {children}
    <div className="flex gap-1">
      <Button variant="ghost" size="icon" aria-label="Zoom out diagram" disabled={zoom <= 0.4} onClick={() => onZoom(Math.max(0.4, zoom - 0.2))}><Minus /></Button>
      <Button variant="ghost" size="icon" aria-label="Zoom in diagram" disabled={zoom >= 1.8} onClick={() => onZoom(Math.min(1.8, zoom + 0.2))}><Plus /></Button>
      <Button variant="ghost" size="icon" aria-label="Reset diagram" onClick={onReset}><Focus /></Button>
    </div>
    <Button variant="outline" size="sm" onClick={onCopy}>{copy === "copied" ? <Check /> : <Copy />}{copy === "copied" ? "Copied Mermaid" : "Copy as Mermaid"}</Button>
    {copy === "failed" && <span role="status" className="text-xs text-amber-300">The browser blocked clipboard access.</span>}
  </div>;
}

function Limitations({ items }: { items: string[] }) {
  if (!items.length) return null;
  return <details className="border-t border-white/10 px-5 py-3 text-xs text-slate-400">
    <summary className="cursor-pointer">Coverage and limitations</summary>
    <ul className="mt-2 list-disc space-y-1 pl-5">{items.map((item, index) => <li key={index}>{item}</li>)}</ul>
  </details>;
}

export function DiagramNotice({ icon: Icon, title, children, limitations = [] }: { icon: LucideIcon; title: string; children: ReactNode; limitations?: string[] }) {
  return <section className="overflow-hidden rounded-2xl border border-white/10 bg-[var(--surface-4)]">
    <div className="p-6">
      <p className="flex items-center gap-2 text-xs font-medium uppercase tracking-widest text-cyan-300"><Icon className="size-4" />{title}</p>
      <div className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">{children}</div>
    </div>
    <Limitations items={limitations} />
  </section>;
}

function Header({ icon: Icon, eyebrow, title, children, ask }: { icon: LucideIcon; eyebrow: string; title: string; children: ReactNode; ask: ReactNode }) {
  return <div className="flex flex-wrap items-start justify-between gap-4 border-b border-white/10 p-5 sm:p-6">
    <div>
      <p className="flex items-center gap-2 text-xs font-medium uppercase tracking-widest text-cyan-300"><Icon className="size-4" />{eyebrow}</p>
      <h3 className="mt-2 text-xl font-semibold">{title}</h3>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">{children}</p>
    </div>
    {ask}
  </div>;
}

export function DataModelView({ structure, atlas, onInspect }: ViewProps) {
  const sources = useMemo(() => structure.sources
    .map(source => ({ source, count: structure.entities.filter(entity => entity.source_id === source.id).length }))
    .sort((a, b) => b.count - a.count || a.source.kind.localeCompare(b.source.kind) || a.source.root.localeCompare(b.source.root)), [structure]);
  const [sourceId, setSourceId] = useState(() => sources[0]?.source.id ?? "");
  const [query, setQuery] = useState("");
  const [focus, setFocus] = useState<string | null>(null);
  const [keysOnly, setKeysOnly] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [copied, copy] = useCopy();
  const files = useFileNodes(atlas);
  const entities = useMemo(() => structure.entities.filter(entity => entity.source_id === sourceId), [structure, sourceId]);
  const links = useMemo(() => structure.entity_links.filter(link => link.source_id === sourceId), [structure, sourceId]);
  const view = useMemo(() => erdView(structure, sourceId, { query, focus, keysOnly, limit: DIAGRAM_LIMIT }), [structure, sourceId, query, focus, keysOnly]);
  const names = useMemo(() => new Map(structure.entities.map(entity => [entity.id, entity.name])), [structure]);
  const source = sources.find(item => item.source.id === sourceId)?.source;

  if (!source) {
    return <DiagramNotice icon={Database} title="No declared data models detected" limitations={structure.limitations}>
      Codandy draws tables from Prisma schema files, SQL files with CREATE TABLE statements, SQLAlchemy classes with a table name and Django models. None were found in the files indexed for this report.
    </DiagramNotice>;
  }
  const nameOf = (id: string | null) => (id ? names.get(id) ?? id : "unknown");
  const choose = (id: string | null) => { setFocus(id); if (id) setQuery(""); };
  const selected = entities.find(entity => entity.id === focus) ?? null;
  const related = selected ? links.filter(link => link.source.entity === selected.id || link.target.entity === selected.id) : links;
  const drawnEntities = view.records.filter(record => !record.stub);
  const shownEntities = entities.filter(entity => drawnEntities.some(record => record.id === entity.id));
  const scopeIds = [...new Set(shownEntities.map(entity => entity.node_id ?? files.get(entity.evidence[0].path)).filter((id): id is string => Boolean(id)))].slice(0, 24);

  return <section className="overflow-hidden rounded-2xl border border-white/10 bg-[var(--surface-4)]" aria-label="Data model diagram">
    <Header icon={Database} eyebrow="Data model" title="Tables and the references between them"
      ask={<AskButton scope={{ title: `Data model: ${SOURCE_LABELS[source.kind]}`, nodeIds: scopeIds, notes: JSON.stringify({ basis: "Declared schema read from source text; a live database can differ.", tables: shownEntities.slice(0, 20).map(entity => ({ name: entity.name, table: entity.table, columns: entity.fields.slice(0, 20).map(field => `${field.name} ${field.type}${entityKeys(field).map(key => ` ${key}`).join("")}`) })), relationships: links.slice(0, 30).map(link => describeEntityLink(link, nameOf)) }) }}>Ask about this data model</AskButton>}>
      Declared in {SOURCE_LABELS[source.kind]} under {source.root || "the repository root"}. Referenced tables sit to the left of the tables that point at them. This is what the code declares, not a live database.
    </Header>

    <Controls zoom={zoom} onZoom={setZoom} onReset={() => { choose(null); setQuery(""); setKeysOnly(false); setZoom(1); }} copy={copied} onCopy={() => copy(mermaidErDiagram(entities, links))}>
      <label className="flex items-center gap-2 text-xs text-slate-400">Schema
        <select className="max-w-60 rounded-lg border border-white/10 bg-card p-2" value={sourceId} onChange={event => { setSourceId(event.target.value); choose(null); setQuery(""); }}>
          {sources.map(({ source: item, count }) => <option key={item.id} value={item.id}>{`${SOURCE_LABELS[item.kind]} · ${item.root || "root"} (${count})`}</option>)}
        </select>
      </label>
      <Input className="min-w-40 flex-1" aria-label="Find a table" placeholder="Find a table…" value={query} onChange={event => { setQuery(event.target.value); setFocus(null); }} />
      <Button size="sm" variant={keysOnly ? "secondary" : "ghost"} aria-pressed={keysOnly} onClick={() => setKeysOnly(!keysOnly)}><KeyRound />Keys only</Button>
    </Controls>

    {!view.records.length ? <p className="border-y border-white/[0.06] p-8 text-slate-400">No tables match this search.</p> : <>
      <div className="space-y-2 border-y border-white/[0.06] bg-[var(--background)] p-4 sm:hidden" aria-label="Mobile data model list">
        {drawnEntities.slice(0, MOBILE_LIMIT).map(record => <button key={record.id} aria-pressed={focus === record.id} onClick={() => choose(focus === record.id ? null : record.refId)}
          className={`block w-full rounded-xl border bg-[var(--surface-4)] p-3 text-left ${focus === record.id ? "border-cyan-300/50" : "border-white/10"}`}>
          <span className="block break-all font-medium">{record.title}</span>
          <span className="block text-xs text-slate-500">{record.subtitle}</span>
          <span className="mt-2 block break-words text-xs text-slate-400">{record.rows.slice(0, 6).map(row => `${row.badges.length ? `${row.badges.join("/")} ` : ""}${row.name}`).join(" · ")}{record.hiddenRows ? ` · +${record.hiddenRows}` : ""}</span>
          {view.links.filter(link => link.target === record.id).map(link => <span key={link.id} className={`mt-1 block break-all text-xs ${link.dashed ? "text-amber-300" : "text-cyan-200"}`}>→ {view.records.find(item => item.id === link.source)?.title}</span>)}
        </button>)}
      </div>
      <div className="hidden overflow-auto border-y border-white/[0.06] bg-[var(--background)] p-3 sm:block" tabIndex={0} aria-label="Scrollable data model diagram">
        <RecordDiagram records={view.records} links={view.links} variant="erd" zoom={zoom} focus={focus} onFocus={choose} label={`Data model diagram of ${drawnEntities.length} tables`} />
      </div>
    </>}

    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 px-5 py-3 text-xs text-slate-400">
      <span className="text-cyan-300">━ Declared reference</span>
      <span className="text-amber-300">┄ ORM relation or undeclared target</span>
      <LegendMark mark={{ cardinality: "one", optional: false }}>exactly one</LegendMark>
      <LegendMark mark={{ cardinality: "one", optional: true }}>zero or one</LegendMark>
      <LegendMark mark={{ cardinality: "many", optional: true }}>zero or more</LegendMark>
      <span><b style={{ color: BADGE_COLORS.PK }}>PK</b> primary · <b style={{ color: BADGE_COLORS.FK }}>FK</b> foreign · <b style={{ color: BADGE_COLORS.UQ }}>UQ</b> unique · <span className="font-mono">?</span> nullable</span>
      <span>{drawnEntities.length}/{view.total} tables · {view.hiddenLinks} relationships outside view</span>
    </div>

    <div className="grid gap-5 border-t border-white/10 p-5 lg:grid-cols-2">
      <div className="min-w-0">
        {selected ? <>
          <h4 className="break-all font-medium">{selected.name}</h4>
          <p className="mt-1 text-xs text-slate-500">{entitySubtitle(selected)} · {SOURCE_LABELS[source.kind]}</p>
          <div className="mt-3 max-h-72 overflow-auto rounded-lg border border-white/[0.07]">
            <table className="w-full text-left text-xs">
              <thead className="text-slate-500"><tr><th className="p-2 font-medium">Column</th><th className="p-2 font-medium">Type</th><th className="p-2 font-medium">Keys</th><th className="p-2 font-medium">Nullable</th></tr></thead>
              <tbody>{selected.fields.map((field, index) => <tr key={index} className="border-t border-white/[0.05]">
                <td className="break-all p-2 text-slate-200">{field.name}</td>
                <td className="break-all p-2 text-slate-400">{field.type || "not stated"}</td>
                <td className="p-2">{entityKeys(field).map(key => <b key={key} className="mr-1" style={{ color: BADGE_COLORS[key] }}>{key}</b>)}</td>
                <td className="p-2 text-slate-400">{field.nullable === null ? "not stated" : field.nullable ? "yes" : "no"}</td>
              </tr>)}</tbody>
            </table>
          </div>
          {selected.omitted_fields > 0 && <p className="mt-2 text-xs text-amber-300">{selected.omitted_fields} more columns were omitted at the column budget.</p>}
          <h5 className="mt-4 text-xs font-medium uppercase tracking-widest text-slate-500">Declared in</h5>
          <div className="mt-2 space-y-1">{selected.evidence.map((item, index) => <Evidence key={index} path={item.path} lines={item.lines} reason={item.reason}
            target={index === 0 ? selected.node_id ?? files.get(item.path) : files.get(item.path)} onInspect={onInspect} />)}</div>
        </> : <>
          <h4 className="font-medium">Explore a table</h4>
          <p className="mt-2 text-sm leading-6 text-slate-400">Select a table to see its columns, where it is declared, and every reference to or from it. The diagram shows up to {DIAGRAM_LIMIT} tables, the most connected first; search, focus or Keys only narrows it.</p>
        </>}
      </div>
      <div className="min-w-0">
        <h4 className="font-medium">{selected ? "References to and from this table" : "References in this schema"}</h4>
        <div className="mt-3 max-h-80 space-y-2 overflow-auto">
          {related.slice(0, 40).map(link => <div key={link.id} className="rounded-lg border border-white/[0.07] p-3 text-xs">
            <p className={`break-words ${link.basis === "declared" && link.resolution === "resolved" ? "text-slate-300" : "text-amber-200"}`}>{describeEntityLink(link, nameOf)}</p>
            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
              {[link.source.entity, link.target.entity].filter((id): id is string => id !== null && id !== focus).map(id => <button key={id} className="text-cyan-200 hover:underline" onClick={() => choose(id)}>Focus {nameOf(id)}</button>)}
              {link.evidence.map((item, index) => <Evidence key={index} path={item.path} lines={item.lines} reason={item.reason} target={files.get(item.path)} onInspect={onInspect} />)}
            </div>
          </div>)}
          {related.length > 40 && <p className="text-xs text-slate-500">First 40 references shown.</p>}
          {!related.length && <p className="text-sm text-slate-500">No references are declared{selected ? " to or from this table" : " in this schema"}.</p>}
        </div>
      </div>
    </div>
    <Limitations items={structure.limitations} />
  </section>;
}

export function DataContractsView({ structure, atlas, onInspect }: ViewProps) {
  const areas = useMemo(() => contractAreas(structure), [structure]);
  const [area, setArea] = useState<string | null>(() => areas[0]?.id ?? null);
  const [query, setQuery] = useState("");
  const [focus, setFocus] = useState<string | null>(null);
  const [inheritance, setInheritance] = useState(true);
  const [zoom, setZoom] = useState(1);
  const [copied, copy] = useCopy();
  const files = useFileNodes(atlas);
  const types = useMemo(() => new Map(structure.types.map(type => [type.id, type])), [structure]);
  const view = useMemo(() => contractsView(structure, { area, query, focus, inheritance, limit: DIAGRAM_LIMIT }), [structure, area, query, focus, inheritance]);

  if (!structure.types.length) {
    return <DiagramNotice icon={Braces} title="No data contracts detected" limitations={structure.limitations}>
      Codandy draws Pydantic models, dataclasses and TypedDicts in Python, and TypeScript interfaces and object type aliases. None were found in the files indexed for this report.
    </DiagramNotice>;
  }
  const nameOf = (id: string) => types.get(id)?.name ?? id;
  const choose = (id: string | null) => { setFocus(id); if (id) setQuery(""); };
  const selected = focus ? types.get(focus) ?? null : null;
  const uses = selected ? structure.type_links.filter(link => link.source === selected.id) : [];
  const usedBy = selected ? structure.type_links.filter(link => link.target === selected.id) : [];
  const drawn = view.records.filter(record => !record.stub && record.refId).map(record => types.get(record.refId!)!);
  const drawnIds = new Set(drawn.map(type => type.id));
  const exportLinks = structure.type_links.filter(link => drawnIds.has(link.source) && drawnIds.has(link.target) && (inheritance || link.kind !== "extends"));
  const scopeIds = [...new Set(drawn.map(type => type.node_id ?? files.get(type.path)).filter((id): id is string => Boolean(id)))].slice(0, 24);
  const linkList = (items: typeof uses, other: "source" | "target") => items.slice(0, 30).map(link => <div key={link.id} className="rounded-lg border border-white/[0.07] p-3 text-xs">
    <p className={`break-words ${link.resolution === "inferred" ? "text-amber-200" : "text-slate-300"}`}>{describeTypeLink(link, nameOf)}</p>
    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
      <button className="text-cyan-200 hover:underline" onClick={() => choose(link[other])}>Focus {nameOf(link[other])}</button>
      {link.evidence.map((item, index) => <Evidence key={index} path={item.path} lines={item.lines} reason={item.reason} target={files.get(item.path)} onInspect={onInspect} />)}
    </div>
  </div>);

  return <section className="overflow-hidden rounded-2xl border border-white/10 bg-[var(--surface-4)]" aria-label="Data contracts diagram">
    <Header icon={Braces} eyebrow="Data contracts" title="Types and the shapes they contain"
      ask={<AskButton scope={{ title: focus ? `Data contract: ${nameOf(focus)}` : `Data contracts in ${area ?? "all folders"}`, nodeIds: scopeIds, notes: JSON.stringify({ basis: "Type declarations read from source text; runtime validation and serialization are not verified.", types: drawn.slice(0, 20).map(type => ({ name: type.name, kind: TYPE_KIND_LABELS[type.kind], path: type.path, members: type.members.slice(0, 20).map(member => `${member.name}: ${member.type}`) })), links: exportLinks.slice(0, 30).map(link => describeTypeLink(link, nameOf)) }) }}>Ask about these contracts</AskButton>}>
      An arrow points from a type to a type it contains; a hollow triangle points to a base type. Dashed amber links were matched by a unique name only.
    </Header>

    <Controls zoom={zoom} onZoom={setZoom} onReset={() => { choose(null); setQuery(""); setInheritance(true); setZoom(1); }} copy={copied} onCopy={() => copy(mermaidClassDiagram(drawn, exportLinks))}>
      <label className="flex items-center gap-2 text-xs text-slate-400">Folder
        <select className="max-w-60 rounded-lg border border-white/10 bg-card p-2" value={area ?? "__all__"} disabled={focus !== null}
          onChange={event => { setArea(event.target.value === "__all__" ? null : event.target.value); choose(null); }}>
          <option value="__all__">{`All folders (${structure.types.length})`}</option>
          {areas.map(item => <option key={item.id} value={item.id}>{`${item.label} (${item.count})`}</option>)}
        </select>
      </label>
      <Input className="min-w-40 flex-1" aria-label="Find a type" placeholder="Find a type…" value={query} onChange={event => { setQuery(event.target.value); setFocus(null); }} />
      <Button size="sm" variant={inheritance ? "secondary" : "ghost"} aria-pressed={inheritance} onClick={() => setInheritance(!inheritance)}><GitFork />Inheritance</Button>
    </Controls>
    {focus && <p className="mx-4 mb-3 text-xs text-slate-400">Showing {nameOf(focus)} and the types it links to, across folders. <button className="text-cyan-200 hover:underline" onClick={() => choose(null)}>Back to {area ?? "all folders"}</button></p>}

    {!view.records.length ? <p className="border-y border-white/[0.06] p-8 text-slate-400">No types match this search.</p> : <>
      <div className="space-y-2 border-y border-white/[0.06] bg-[var(--background)] p-4 sm:hidden" aria-label="Mobile data contracts list">
        {view.records.filter(record => !record.stub).slice(0, MOBILE_LIMIT).map(record => <button key={record.id} aria-pressed={focus === record.id} onClick={() => choose(focus === record.id ? null : record.refId)}
          className={`block w-full rounded-xl border bg-[var(--surface-4)] p-3 text-left ${focus === record.id ? "border-cyan-300/50" : "border-white/10"}`}>
          <span className="block break-all font-medium">{record.title}</span>
          <span className="block text-xs text-slate-500">{record.subtitle}</span>
          <span className="mt-2 block break-words text-xs text-slate-400">{record.rows.slice(0, 6).map(row => row.name).join(" · ")}{record.hiddenRows ? ` · +${record.hiddenRows}` : ""}</span>
          {view.links.filter(link => link.source === record.id).map(link => <span key={link.id} className={`mt-1 block break-all text-xs ${link.dashed ? "text-amber-300" : link.kind === "extends" ? "text-violet-300" : "text-cyan-200"}`}>{link.kind === "extends" ? "extends" : `${link.label} →`} {view.records.find(item => item.id === link.target)?.title}</span>)}
        </button>)}
      </div>
      <div className="hidden overflow-auto border-y border-white/[0.06] bg-[var(--background)] p-3 sm:block" tabIndex={0} aria-label="Scrollable data contracts diagram">
        <RecordDiagram records={view.records} links={view.links} variant="contracts" zoom={zoom} focus={focus} onFocus={choose} label={`Data contracts diagram of ${drawn.length} types`} />
      </div>
    </>}

    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 px-5 py-3 text-xs text-slate-400">
      <span className="text-cyan-300">━▶ Contains, resolved</span>
      <span className="text-amber-300">┄▶ Contains, matched by name</span>
      <span style={{ color: "var(--chart-3)" }}>━▷ Extends</span>
      <span>Dashed boxes are types in other folders</span>
      <span>{drawn.length}/{view.total} types · {view.hiddenLinks} incoming links from outside view</span>
    </div>

    <div className="grid gap-5 border-t border-white/10 p-5 lg:grid-cols-2">
      <div className="min-w-0">
        {selected ? <>
          <h4 className="break-all font-medium">{selected.name}</h4>
          <p className="mt-1 text-xs text-slate-500">{TYPE_KIND_LABELS[selected.kind]} · {selected.language} · {typeFolder(selected.path) || "repository root"}</p>
          <div className="mt-3 max-h-72 overflow-auto rounded-lg border border-white/[0.07]">
            <table className="w-full text-left text-xs">
              <thead className="text-slate-500"><tr><th className="p-2 font-medium">Member</th><th className="p-2 font-medium">Type</th><th className="p-2 font-medium">Line</th></tr></thead>
              <tbody>{selected.members.map((member, index) => <tr key={index} className="border-t border-white/[0.05]">
                <td className="break-all p-2 text-slate-200">{member.name}</td>
                <td className="break-all p-2 font-mono text-slate-400">{member.type || "not stated"}</td>
                <td className="p-2 text-slate-500">{member.line ?? ""}</td>
              </tr>)}</tbody>
            </table>
            {!selected.members.length && <p className="p-3 text-xs text-slate-500">No annotated members are declared on this type itself.</p>}
          </div>
          <h5 className="mt-4 text-xs font-medium uppercase tracking-widest text-slate-500">Declared in</h5>
          <div className="mt-2">{selected.evidence.map((item, index) => <Evidence key={index} path={item.path} lines={item.lines} reason={item.reason} target={selected.node_id ?? files.get(item.path)} onInspect={onInspect} />)}</div>
        </> : <>
          <h4 className="font-medium">Explore a type</h4>
          <p className="mt-2 text-sm leading-6 text-slate-400">Select a type to see its members and every type it uses or is used by. The diagram shows up to {DIAGRAM_LIMIT} types from the chosen folder, the most connected first; types they reference elsewhere appear as dashed boxes.</p>
        </>}
      </div>
      <div className="min-w-0">
        {selected ? <>
          <h4 className="font-medium">Uses</h4>
          <div className="mt-3 max-h-56 space-y-2 overflow-auto">{linkList(uses, "target")}{!uses.length && <p className="text-sm text-slate-500">This type does not reference other detected contracts.</p>}</div>
          <h4 className="mt-5 font-medium">Used by</h4>
          <div className="mt-3 max-h-56 space-y-2 overflow-auto">{linkList(usedBy, "source")}{!usedBy.length && <p className="text-sm text-slate-500">No detected contract references this type.</p>}</div>
        </> : <>
          <h4 className="font-medium">How links are matched</h4>
          <p className="mt-2 text-sm leading-6 text-slate-400">A member type is resolved when the named type is declared in the same file or in a local import Codandy resolved. Otherwise a unique name anywhere in the repository is shown as an inferred link, and ambiguous names are not linked.</p>
        </>}
      </div>
    </div>
    <Limitations items={structure.limitations} />
  </section>;
}
