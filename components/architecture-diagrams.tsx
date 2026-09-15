"use client";

import { useId, useMemo } from "react";
import type { KeyboardEvent } from "react";
import type { ArchitectureGroup, ArchitectureLink } from "@/lib/architecture-map";
import { dependencyMatrix, edgePath, labelPoint, linkKey, type LayeredLayout } from "@/lib/architecture-layout";

const truncate = (value: string, length: number) => (value.length > length ? `${value.slice(0, length - 1)}…` : value);

function activate(event: KeyboardEvent, action: () => void) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    action();
  }
}

export function LayeredDiagram({ layout, groups, unit, zoom, focus, onFocus }: {
  layout: LayeredLayout;
  groups: ArchitectureGroup[];
  unit: string;
  zoom: number;
  focus: string | null;
  onFocus: (id: string | null) => void;
}) {
  const marker = useId().replaceAll(":", "");
  const byId = useMemo(() => new Map(groups.map(group => [group.id, group])), [groups]);
  const near = focus
    ? new Set(layout.edges.filter(edge => edge.link.source === focus || edge.link.target === focus).flatMap(edge => [edge.link.source, edge.link.target]))
    : null;
  return <svg viewBox={`0 0 ${layout.width} ${layout.height}`} role="group" aria-label={`Layered dependency diagram of ${layout.nodes.length} groups`}
    style={{ width: `${layout.width * zoom}px`, maxWidth: "none" }} className="mx-auto block">
    <defs>
      <marker id={marker} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke" />
      </marker>
    </defs>
    {layout.edges.map(edge => {
      const dim = focus !== null && edge.link.source !== focus && edge.link.target !== focus;
      const label = labelPoint(edge);
      const stroke = edge.back ? "var(--chart-5)" : edge.link.inferred ? "var(--chart-4)" : "var(--primary)";
      return <g key={edge.key} opacity={dim ? 0.15 : 1}>
        <path d={edgePath(edge)} fill="none" stroke={stroke} strokeOpacity={0.75}
          strokeWidth={Math.min(5, 1.2 + Math.log2(edge.link.count + 1))}
          strokeDasharray={edge.back ? "2 4" : edge.link.inferred ? "7 5" : undefined} markerEnd={`url(#${marker})`}>
          <title>{`${byId.get(edge.link.source)?.label} → ${byId.get(edge.link.target)?.label}: ${edge.link.count} import${edge.link.count === 1 ? "" : "s"}${edge.back ? " (back edge in an import cycle)" : ""}`}</title>
        </path>
        <text x={label.x} y={label.y} dy="0.35em" textAnchor="middle" fontSize="11" fill="var(--muted-foreground)"
          stroke="var(--background)" strokeWidth={4} paintOrder="stroke">{`×${edge.link.count}`}</text>
      </g>;
    })}
    {layout.isolatedTop !== null && <g>
      <line x1={24} x2={layout.width - 24} y1={layout.isolatedTop} y2={layout.isolatedTop} stroke="var(--border)" strokeDasharray="4 6" />
      <text x={24} y={layout.isolatedTop + 18} fontSize="11" fill="var(--muted-foreground)">No imports to or from other groups in this view</text>
    </g>}
    {layout.nodes.map(node => {
      const group = byId.get(node.id)!;
      const active = focus === node.id;
      const faded = near !== null && !near.has(node.id) && !active;
      const toggle = () => onFocus(active ? null : node.id);
      return <g key={node.id} role="button" tabIndex={0} aria-pressed={active}
        aria-label={`${group.label}, ${group.nodeIds.length} ${unit}; ${active ? "clear focus" : "focus its dependencies"}`}
        opacity={faded ? 0.35 : 1} onClick={toggle} onKeyDown={event => activate(event, toggle)}
        className="cursor-pointer outline-none [&:focus-visible_rect]:stroke-[var(--foreground)]">
        <title>{group.label}</title>
        <rect x={node.x} y={node.y} width={node.width} height={node.height} rx={10} fill="var(--surface-4)"
          stroke={active ? "var(--primary)" : "var(--border)"} strokeWidth={active ? 2.5 : 1.2} />
        <text x={node.x + node.width / 2} y={node.y + 23} textAnchor="middle" fontSize="13" fontWeight="600" fill="var(--foreground)">{truncate(group.label, 24)}</text>
        <text x={node.x + node.width / 2} y={node.y + 41} textAnchor="middle" fontSize="11" fill="var(--muted-foreground)">{`${group.nodeIds.length} ${unit} · ${group.internal} internal`}</text>
      </g>;
    })}
  </svg>;
}

export function DependencyMatrixView({ groups, links, zoom, selected, onSelect }: {
  groups: ArchitectureGroup[];
  links: ArchitectureLink[];
  zoom: number;
  selected: string | null;
  onSelect: (key: string | null) => void;
}) {
  const matrix = useMemo(() => dependencyMatrix(groups, links), [groups, links]);
  const labels = useMemo(() => new Map(groups.map(group => [group.id, group.label])), [groups]);
  const count = matrix.order.length;
  const size = count > 32 ? 18 : count > 16 ? 24 : 32;
  const left = 250;
  const top = 34;
  const width = left + count * size + 16;
  const height = top + count * size + 16;
  const intensity = (value: number) => 0.25 + 0.65 * (Math.log2(value + 1) / Math.log2(matrix.max + 1 || 2));
  return <svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label={`Dependency matrix of ${count} groups; rows import columns`}
    style={{ width: `${width * zoom}px`, maxWidth: "none" }} className="block">
    <text x={left - 10} y={18} textAnchor="end" fontSize="11" fill="var(--muted-foreground)">row imports column</text>
    <rect x={left} y={top} width={count * size} height={count * size} fill="var(--surface-4)" stroke="var(--border)" />
    {Array.from({ length: count + 1 }, (_, line) => <g key={`grid-${line}`}>
      <line x1={left} x2={left + count * size} y1={top + line * size} y2={top + line * size} stroke="var(--border)" />
      <line x1={left + line * size} x2={left + line * size} y1={top} y2={top + count * size} stroke="var(--border)" />
    </g>)}
    {matrix.order.map((id, position) => <g key={id}>
      <rect x={left + position * size} y={top + position * size} width={size} height={size} fill="var(--muted-foreground)" fillOpacity={0.16} />
      <text x={left + position * size + size / 2} y={top - 10} textAnchor="middle" fontSize="10" fill="var(--muted-foreground)">{position + 1}</text>
      <text x={left - 10} y={top + position * size + size / 2} dy="0.35em" textAnchor="end" fontSize="11" fill="var(--foreground)">
        <title>{labels.get(id)}</title>{`${truncate(labels.get(id) ?? id, 30)}  ${position + 1}`}
      </text>
    </g>)}
    {matrix.cells.map(cell => {
      const key = linkKey(cell);
      const active = selected === key;
      const strength = intensity(cell.count);
      const toggle = () => onSelect(active ? null : key);
      const description = `${labels.get(cell.source)} imports ${labels.get(cell.target)} ${cell.count} time${cell.count === 1 ? "" : "s"}${cell.below ? "; below the diagonal, a back edge in an import cycle" : ""}`;
      return <g key={key} role="button" tabIndex={0} aria-pressed={active} aria-label={description}
        onClick={toggle} onKeyDown={event => activate(event, toggle)}
        className="cursor-pointer outline-none [&:focus-visible_rect]:stroke-[var(--foreground)]">
        <title>{description}</title>
        <rect x={left + cell.column * size + 1} y={top + cell.row * size + 1} width={size - 2} height={size - 2}
          fill={cell.below ? "var(--chart-5)" : "var(--primary)"} fillOpacity={strength}
          stroke={active ? "var(--foreground)" : "transparent"} strokeWidth={2} />
        {size >= 24 && <text x={left + cell.column * size + size / 2} y={top + cell.row * size + size / 2} dy="0.35em" textAnchor="middle"
          fontSize="10" fontWeight="600" fill={strength > 0.6 ? "var(--background)" : "var(--foreground)"}>{cell.count}</text>}
      </g>;
    })}
  </svg>;
}
