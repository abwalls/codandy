"use client";

import { Fragment, useId, useMemo, useState } from "react";
import type { KeyboardEvent, ReactNode } from "react";
import { Check, Copy, ListOrdered, Workflow } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useClipboard } from "@/hooks/use-clipboard";
import { formatDuration, mermaidSequence, stackSequence, traceSequence, type SequenceTone, type SequenceView } from "@/lib/sequence-diagram";
import type { Observation } from "@/lib/debugging-api";
import type { Trace } from "@/lib/trace-api";

const COLUMN = 168;
const HEADER = 46;
const TOP = 12;
const ROW = 40;
const SIDE = 16;
const BAR = 10;
const TONES: Record<SequenceTone, { stroke: string; dash?: string; fill: string }> = {
  app: { stroke: "var(--primary)", fill: "var(--card)" },
  service: { stroke: "var(--chart-3)", fill: "var(--card)" },
  external: { stroke: "var(--muted-foreground)", dash: "5 4", fill: "var(--card)" },
  unknown: { stroke: "var(--border)", fill: "var(--card)" },
  outside: { stroke: "var(--muted-foreground)", dash: "2 4", fill: "transparent" },
};

const truncate = (value: string, length: number) => (value.length > length ? `${value.slice(0, length - 1)}…` : value);

function activate(event: KeyboardEvent, action: () => void) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    action();
  }
}

/** Lifelines with ordered arrows. Row order is the evidence order; nothing else is implied. */
export function SequenceDiagram({ view, selected, onSelect, label }: { view: SequenceView; selected: string | null; onSelect: (id: string | null) => void; label: string }) {
  const marker = useId().replaceAll(":", "");
  const columns = useMemo(() => new Map(view.participants.map((participant, index) => [participant.id, index])), [view]);
  const activations = useMemo(() => {
    const bars: { key: string; column: number; from: number; until: number; depth: number; error: boolean }[] = [];
    view.messages.forEach((message, row) => {
      if (message.activeUntil === null) return;
      const column = columns.get(message.to)!;
      const until = Math.max(row, message.activeUntil);
      // Nested activations on one lifeline shift right so each stays visible.
      const depth = bars.filter(bar => bar.column === column && bar.from < row && bar.until >= row).length;
      bars.push({ key: message.id, column, from: row, until, depth, error: message.error });
    });
    return bars;
  }, [view, columns]);
  const center = (id: string) => SIDE + columns.get(id)! * COLUMN + COLUMN / 2;
  const rowY = (row: number) => TOP + HEADER + 30 + row * ROW;
  const width = SIDE * 2 + Math.max(1, view.participants.length) * COLUMN + 120;
  const height = rowY(Math.max(0, view.messages.length - 1)) + ROW;

  return <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} role="group" aria-label={label} className="block max-w-none">
    <defs>
      <marker id={`${marker}-arrow`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--primary)" />
      </marker>
      <marker id={`${marker}-open`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M 1 1 L 9 5 L 1 9" fill="none" stroke="var(--muted-foreground)" strokeWidth="1.5" />
      </marker>
      <marker id={`${marker}-error`} viewBox="0 0 10 10" refX="5" refY="5" markerWidth="9" markerHeight="9">
        <path d="M 1 1 L 9 9 M 9 1 L 1 9" fill="none" stroke="var(--destructive)" strokeWidth="2" />
      </marker>
    </defs>
    {view.participants.map((participant, index) => {
      const tone = TONES[participant.tone];
      const left = SIDE + index * COLUMN;
      return <g key={participant.id}>
        <title>{participant.detail}</title>
        <line x1={left + COLUMN / 2} x2={left + COLUMN / 2} y1={TOP + HEADER} y2={height - 6} stroke="var(--border)" strokeDasharray="4 5" />
        <rect x={left + 8} y={TOP} width={COLUMN - 16} height={HEADER} rx={8} fill={tone.fill} stroke={tone.stroke} strokeDasharray={tone.dash} />
        <text x={left + COLUMN / 2} y={TOP + HEADER / 2} dy="0.35em" textAnchor="middle" fontSize="12" fontWeight="600" fill="var(--foreground)">{truncate(participant.label, 20)}</text>
      </g>;
    })}
    {activations.map(bar => <rect key={`bar:${bar.key}`} x={SIDE + bar.column * COLUMN + COLUMN / 2 - BAR / 2 + bar.depth * 5} y={rowY(bar.from) - 6}
      width={BAR} height={rowY(bar.until) - rowY(bar.from) + 18} rx={2} fill="var(--card)" stroke={bar.error ? "var(--destructive)" : "var(--primary)"} strokeOpacity={0.7} />)}
    {view.messages.map((message, row) => {
      const y = rowY(row);
      const from = center(message.from);
      const to = center(message.to);
      const active = selected === message.id;
      const stroke = message.error ? "var(--destructive)" : message.kind === "gap" ? "var(--muted-foreground)" : "var(--primary)";
      const dash = message.kind === "async" ? "2 4" : message.kind === "gap" ? "6 5" : undefined;
      const end = `url(#${marker}-${message.error ? "error" : message.kind === "gap" || message.kind === "async" ? "open" : "arrow"})`;
      // Durations sit under the arrow so they never compete with the name for space.
      const duration = message.durationMs !== null ? formatDuration(message.durationMs) : null;
      const toggle = () => onSelect(active ? null : message.id);
      let shape: ReactNode;
      if (message.kind === "raise") {
        shape = <>
          <circle cx={to + 18} cy={y} r={7} fill="var(--card)" stroke="var(--destructive)" strokeWidth={1.6} />
          <path d={`M ${to + 14} ${y - 4} L ${to + 22} ${y + 4} M ${to + 22} ${y - 4} L ${to + 14} ${y + 4}`} stroke="var(--destructive)" strokeWidth={1.6} />
          <text x={to + 32} y={y} dy="0.35em" fontSize="12" fontWeight="600" fill="var(--destructive)">{truncate(message.label, 40)}</text>
        </>;
      } else if (message.from === message.to) {
        const start = from + BAR / 2 + 2;
        shape = <>
          <path d={`M ${start} ${y - 10} H ${start + 30} V ${y + 6} H ${start + 4}`} fill="none" stroke={stroke} strokeWidth={1.5} strokeDasharray={dash} markerEnd={end} />
          <text x={start + 36} y={y - 2} fontSize="11.5" fill="var(--foreground)">{truncate(message.label, 34)}</text>
          {duration && <text x={start + 36} y={y + 11} fontSize="10.5" fill="var(--muted-foreground)">{duration}</text>}
        </>;
      } else {
        const direction = to > from ? 1 : -1;
        const x1 = from + direction * (BAR / 2 + 2);
        const x2 = to - direction * (BAR / 2 + 2);
        shape = <>
          <line x1={x1} x2={x2} y1={y} y2={y} stroke={stroke} strokeWidth={1.5} strokeDasharray={dash} markerEnd={end} />
          <text x={(x1 + x2) / 2} y={y - 7} textAnchor="middle" fontSize="11.5" fill="var(--foreground)">{truncate(message.label, Math.max(12, Math.floor(Math.abs(x2 - x1) / 7)))}</text>
          {duration && <text x={(x1 + x2) / 2} y={y + 14} textAnchor="middle" fontSize="10.5" fill={message.error ? "var(--destructive)" : "var(--muted-foreground)"}>{duration}</text>}
        </>;
      }
      return <g key={message.id} role="button" tabIndex={0} aria-pressed={active} aria-label={`${message.label}. ${message.detail}`}
        onClick={toggle} onKeyDown={event => activate(event, toggle)} className="cursor-pointer outline-none [&:focus-visible>rect:first-of-type]:stroke-[var(--foreground)]">
        <title>{message.detail}</title>
        <rect x={4} y={y - ROW / 2} width={width - 8} height={ROW} rx={6} fill="var(--primary)" fillOpacity={active ? 0.08 : 0}
          stroke={active ? "var(--primary)" : "transparent"} strokeOpacity={0.4} />
        {shape}
      </g>;
    })}
  </svg>;
}

function CopyMermaid({ view }: { view: SequenceView }) {
  const [state, copy] = useClipboard();
  return <>
    <Button size="sm" variant="outline" onClick={() => copy(mermaidSequence(view))}>{state === "copied" ? <Check /> : <Copy />}{state === "copied" ? "Copied Mermaid" : "Copy as Mermaid"}</Button>
    {state === "failed" && <span role="status" className="text-xs text-destructive">The browser blocked clipboard access.</span>}
  </>;
}

function Notes({ view }: { view: SequenceView }) {
  return <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">{view.notes.map(note => <li key={note}>{note}</li>)}</ul>;
}

type ExceptionRecord = Observation["exceptions"][number];

/** Frames list or observed sequence diagram for one exception. */
export function StackViews({ exception, children }: { exception: ExceptionRecord; children: ReactNode }) {
  const [mode, setMode] = useState<"frames" | "sequence">("frames");
  const hasFrames = exception.frames.length > 0;
  return <div className="space-y-3">
    <div role="group" aria-label="Stack view" className="flex flex-wrap gap-2">
      <Button size="sm" variant={mode === "frames" ? "secondary" : "outline"} aria-pressed={mode === "frames"} onClick={() => setMode("frames")}><ListOrdered />Frames</Button>
      <Button size="sm" variant={mode === "sequence" ? "secondary" : "outline"} aria-pressed={mode === "sequence"} disabled={!hasFrames} onClick={() => setMode("sequence")}><Workflow />Sequence diagram</Button>
    </div>
    {mode === "sequence" && hasFrames ? <StackSequence exception={exception} /> : children}
  </div>;
}

function StackSequence({ exception }: { exception: ExceptionRecord }) {
  const mixed = exception.frames.some(frame => frame.in_app === false) && exception.frames.some(frame => frame.in_app !== false);
  const [groupBy, setGroupBy] = useState<"file" | "function">("file");
  const [appOnly, setAppOnly] = useState(mixed);
  const [selected, setSelected] = useState<string | null>(null);
  const view = useMemo(() => stackSequence(exception, { groupBy, appOnly }), [exception, groupBy, appOnly]);
  const message = view.messages.find(item => item.id === selected);
  const frameIndex = message?.ref && "frame" in message.ref ? message.ref.frame : null;
  const frame = frameIndex === null ? undefined : exception.frames[frameIndex];
  return <div className="space-y-3">
    <div className="flex flex-wrap items-center gap-3">
      <label className="flex items-center gap-2 text-sm">Lifelines
        <select className="rounded border bg-card p-1.5 text-sm" value={groupBy} onChange={event => { setGroupBy(event.target.value === "function" ? "function" : "file"); setSelected(null); }}>
          <option value="file">One per file</option>
          <option value="function">One per function</option>
        </select>
      </label>
      {mixed && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={appOnly} onChange={event => { setAppOnly(event.target.checked); setSelected(null); }} />Collapse library frames</label>}
      <CopyMermaid view={view} />
    </div>
    <div className="overflow-x-auto rounded-lg border bg-[var(--background)] p-2" tabIndex={0} aria-label="Scrollable stack sequence diagram">
      <SequenceDiagram view={view} selected={selected} onSelect={setSelected}
        label={`Observed call sequence for ${exception.type || "the exception"}: ${view.messages.length} arrows across ${view.participants.length} lifelines`} />
    </div>
    {message && <div role="status" className="rounded-lg border p-3 text-sm">
      <p className="break-words font-medium">{message.label}</p>
      <p className="mt-1 break-words text-muted-foreground">{message.detail}</p>
      {frame && <p className="mt-1 text-xs text-muted-foreground">{frame.in_app === null ? "Application ownership unknown" : frame.in_app ? "Application frame" : "External frame"} · Source revision unverified</p>}
      {frame && frame.context.length > 0 && <pre className="mt-2 max-h-48 overflow-auto text-xs">{frame.context.map(line => `${line.line}  ${line.text}`).join("\n")}</pre>}
    </div>}
    <Notes view={view} />
  </div>;
}

/** Sequence diagram of one imported trace. */
export function TraceSequence({ trace, traceId }: { trace: Trace; traceId: string }) {
  const [selected, setSelected] = useState<string | null>(null);
  const view = useMemo(() => traceSequence(trace, traceId), [trace, traceId]);
  const message = view.messages.find(item => item.id === selected);
  const spanId = message?.ref && "span" in message.ref ? message.ref.span : null;
  const span = spanId ? trace.spans.find(item => item.trace_id === traceId && item.span_id === spanId) : undefined;
  const services = view.participants.filter(participant => participant.tone === "service").length;
  return <div className="space-y-3">
    <div className="flex flex-wrap items-center gap-3">
      <p className="text-xs text-muted-foreground">{view.messages.length} spans across {services} service{services === 1 ? "" : "s"}</p>
      <CopyMermaid view={view} />
    </div>
    <div className="overflow-x-auto rounded-lg border bg-[var(--background)] p-2" tabIndex={0} aria-label="Scrollable trace sequence diagram">
      {view.messages.length
        ? <SequenceDiagram view={view} selected={selected} onSelect={setSelected} label={`Trace sequence: ${view.messages.length} spans across ${services} services`} />
        : <p className="p-3 text-sm">This trace has no spans.</p>}
    </div>
    {message && <div role="status" className="rounded-lg border p-3 text-sm">
      <p className="break-words font-medium">{message.label}</p>
      <p className="mt-1 break-words text-muted-foreground">{message.detail}</p>
      {span && Object.keys(span.attributes).length > 0 && <dl className="mt-2 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-xs">
        {Object.entries(span.attributes).map(([key, value]) => <Fragment key={key}><dt className="text-muted-foreground">{key}</dt><dd className="break-all font-mono">{value}</dd></Fragment>)}
      </dl>}
    </div>}
    <Notes view={view} />
  </div>;
}
