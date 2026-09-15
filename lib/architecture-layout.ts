import type { ArchitectureGroup, ArchitectureLink } from "./architecture-map";

export type Point = { x: number; y: number };
export type PlacedNode = { id: string; layer: number; x: number; y: number; width: number; height: number; isolated: boolean };
export type RoutedEdge = { key: string; link: ArchitectureLink; points: Point[]; back: boolean; cyclic: boolean };
export type LayeredLayout = {
  nodes: PlacedNode[];
  edges: RoutedEdge[];
  /** Real groups in layer order, then isolated groups; the dependency matrix uses this order. */
  order: string[];
  /** Groups that import each other directly or indirectly, one list per cycle. */
  cycles: string[][];
  /** Top of the separate row for groups with no cross-group imports, if any. */
  isolatedTop: number | null;
  width: number;
  height: number;
};
export type LayoutOptions = { nodeWidth?: number; nodeHeight?: number; gapX?: number; gapY?: number; padding?: number; sweeps?: number };

type Endpoints = { source: string; target: string };
export type LayerOrder<L extends Endpoints> = {
  /** Links between known, distinct nodes. */
  valid: L[];
  /** Keys of depth-first back edges, which close cycles and are left out of layering. */
  back: Set<string>;
  cycles: string[][];
  cycleOf: Map<string, number>;
  /** Node and waypoint IDs per layer, in crossing-reduced order. */
  rows: string[][];
  waypoints: Set<string>;
  /** Forward link key -> source, waypoints for each intermediate layer, target. */
  chains: Map<string, string[]>;
  connected: Set<string>;
};

const BEND = 56;

export const linkKey = (link: Pick<ArchitectureLink, "source" | "target">) => JSON.stringify([link.source, link.target]);

/** Tarjan's strongly connected components; a component of more than one node is a cycle. */
function stronglyConnected(ids: string[], adjacency: Map<string, string[]>) {
  let counter = 0;
  const index = new Map<string, number>();
  const low = new Map<string, number>();
  const stack: string[] = [];
  const onStack = new Set<string>();
  const found: string[][] = [];
  const visit = (id: string) => {
    index.set(id, counter);
    low.set(id, counter);
    counter++;
    stack.push(id);
    onStack.add(id);
    for (const target of adjacency.get(id) ?? []) {
      if (!index.has(target)) {
        visit(target);
        low.set(id, Math.min(low.get(id)!, low.get(target)!));
      } else if (onStack.has(target)) {
        low.set(id, Math.min(low.get(id)!, index.get(target)!));
      }
    }
    if (low.get(id) === index.get(id)) {
      const component: string[] = [];
      let member: string;
      do {
        member = stack.pop()!;
        onStack.delete(member);
        component.push(member);
      } while (member !== id);
      found.push(component);
    }
  };
  for (const id of ids) if (!index.has(id)) visit(id);
  return found;
}

/**
 * Layer assignment and crossing reduction shared by the group and record layouts.
 *
 * Depth-first back edges are removed, the remaining acyclic graph gets longest-path layers
 * (a link's source is always in an earlier layer than its target), long links pass through one
 * waypoint per intermediate layer, and barycenter sweeps reorder each layer. Ties keep the input
 * order, so results are deterministic.
 */
export function orderLayers<L extends Endpoints>(ids: string[], links: L[], sweeps = 4): LayerOrder<L> {
  const rank = new Map(ids.map((id, position) => [id, position]));
  const valid = links.filter(link => rank.has(link.source) && rank.has(link.target) && link.source !== link.target);
  const adjacency = new Map<string, string[]>(ids.map(id => [id, []]));
  for (const link of valid) adjacency.get(link.source)!.push(link.target);
  for (const targets of adjacency.values()) targets.sort((a, b) => rank.get(a)! - rank.get(b)!);

  // Removing depth-first back edges leaves an acyclic graph that can be layered.
  const state = new Map<string, "open" | "done">();
  const back = new Set<string>();
  const explore = (id: string) => {
    state.set(id, "open");
    for (const target of adjacency.get(id)!) {
      if (state.get(target) === "open") back.add(linkKey({ source: id, target }));
      else if (!state.has(target)) explore(target);
    }
    state.set(id, "done");
  };
  for (const id of ids) if (!state.has(id)) explore(id);

  const cycles = stronglyConnected(ids, adjacency)
    .filter(component => component.length > 1)
    .map(component => component.sort((a, b) => rank.get(a)! - rank.get(b)!))
    .sort((a, b) => rank.get(a[0])! - rank.get(b[0])!);
  const cycleOf = new Map<string, number>();
  cycles.forEach((cycle, position) => cycle.forEach(id => cycleOf.set(id, position)));

  // Longest-path layering over the forward (acyclic) edges.
  const forward = valid.filter(link => !back.has(linkKey(link)));
  const connected = new Set(valid.flatMap(link => [link.source, link.target]));
  const incoming = new Map(ids.map(id => [id, 0]));
  const outgoing = new Map<string, string[]>(ids.map(id => [id, []]));
  for (const link of forward) {
    incoming.set(link.target, incoming.get(link.target)! + 1);
    outgoing.get(link.source)!.push(link.target);
  }
  const layer = new Map<string, number>();
  const queue = ids.filter(id => connected.has(id) && incoming.get(id) === 0);
  queue.forEach(id => layer.set(id, 0));
  for (let cursor = 0; cursor < queue.length; cursor++) {
    const id = queue[cursor];
    for (const target of outgoing.get(id)!) {
      layer.set(target, Math.max(layer.get(target) ?? 0, layer.get(id)! + 1));
      incoming.set(target, incoming.get(target)! - 1);
      if (incoming.get(target) === 0) queue.push(target);
    }
  }

  const rows: string[][] = Array.from({ length: layer.size ? Math.max(...layer.values()) + 1 : 0 }, () => []);
  for (const id of ids) if (layer.has(id)) rows[layer.get(id)!].push(id);
  // Long edges pass through waypoints, one per intermediate layer. Waypoint IDs are tracked
  // explicitly and never reuse a node ID, so no prefix convention can collide with a real name.
  const waypoints = new Set<string>();
  const above = new Map<string, string[]>();
  const below = new Map<string, string[]>();
  const chains = new Map<string, string[]>();
  for (const link of forward) {
    const chain = [link.source];
    for (let row = layer.get(link.source)! + 1; row < layer.get(link.target)!; row++) {
      let waypoint = `${linkKey(link)}@${row}`;
      while (rank.has(waypoint) || waypoints.has(waypoint)) waypoint += "~";
      waypoints.add(waypoint);
      rows[row].push(waypoint);
      chain.push(waypoint);
    }
    chain.push(link.target);
    for (let step = 1; step < chain.length; step++) {
      below.set(chain[step - 1], [...(below.get(chain[step - 1]) ?? []), chain[step]]);
      above.set(chain[step], [...(above.get(chain[step]) ?? []), chain[step - 1]]);
    }
    chains.set(linkKey(link), chain);
  }

  // Barycenter sweeps reduce crossings; ties keep the previous order, so results are stable.
  const position = new Map<string, number>();
  const renumber = (row: string[]) => row.forEach((id, slot) => position.set(id, slot));
  rows.forEach(renumber);
  const reorder = (row: string[], neighbours: Map<string, string[]>) => {
    const score = new Map(row.map(id => {
      const around = neighbours.get(id) ?? [];
      return [id, around.length ? around.reduce((sum, other) => sum + position.get(other)!, 0) / around.length : position.get(id)!];
    }));
    row.sort((a, b) => score.get(a)! - score.get(b)! || position.get(a)! - position.get(b)!);
    renumber(row);
  };
  for (let sweep = 0; sweep < sweeps; sweep++) {
    for (let row = 1; row < rows.length; row++) reorder(rows[row], above);
    for (let row = rows.length - 2; row >= 0; row--) reorder(rows[row], below);
  }
  return { valid, back, cycles, cycleOf, rows, waypoints, chains, connected };
}

/**
 * Deterministic layered layout for group dependency graphs.
 *
 * Importers sit above their dependencies. Depth-first back edges are left out of layering and
 * returned with `back: true`, so an import cycle is drawn as an explicit upward edge instead of
 * being hidden. Sized for tens of groups; adopt a layout library before rendering hundreds.
 */
export function layeredLayout(groups: ArchitectureGroup[], links: ArchitectureLink[], options: LayoutOptions = {}): LayeredLayout {
  const { nodeWidth = 190, nodeHeight = 56, gapX = 40, gapY = 70, padding = 24, sweeps = 4 } = options;
  const ids = groups.map(group => group.id);
  const { valid, back, cycles, cycleOf, rows, waypoints, chains, connected } = orderLayers(ids, links, sweeps);

  const isWaypoint = (id: string) => waypoints.has(id);
  const widthOf = (id: string) => (isWaypoint(id) ? 18 : nodeWidth);
  const span = (row: string[]) => row.reduce((sum, id) => sum + widthOf(id), 0) + Math.max(0, row.length - 1) * gapX;
  const isolated = ids.filter(id => !connected.has(id));
  const perRow = Math.max(3, ...rows.map(row => row.filter(id => !isWaypoint(id)).length));
  const isolatedRows = Array.from({ length: Math.ceil(isolated.length / perRow) }, (_, row) => isolated.slice(row * perRow, (row + 1) * perRow));
  const contentWidth = Math.max(nodeWidth, ...rows.map(span), ...isolatedRows.map(span));
  const width = padding * 2 + contentWidth + (back.size ? BEND + 24 : 0);

  const nodes: PlacedNode[] = [];
  const centers = new Map<string, Point>();
  const place = (row: string[], top: number, layerIndex: number, isolatedRow: boolean) => {
    let cursor = padding + (contentWidth - span(row)) / 2;
    for (const id of row) {
      centers.set(id, { x: cursor + widthOf(id) / 2, y: top + nodeHeight / 2 });
      if (!isWaypoint(id)) nodes.push({ id, layer: layerIndex, x: cursor, y: top, width: nodeWidth, height: nodeHeight, isolated: isolatedRow });
      cursor += widthOf(id) + gapX;
    }
  };
  rows.forEach((row, index) => place(row, padding + index * (nodeHeight + gapY), index, false));
  const isolatedTop = isolatedRows.length ? padding + rows.length * (nodeHeight + gapY) : null;
  isolatedRows.forEach((row, index) => place(row, isolatedTop! + 28 + index * (nodeHeight + 24), rows.length + index, true));
  const height = isolatedTop === null
    ? padding * 2 + Math.max(1, rows.length) * (nodeHeight + gapY) - gapY
    : isolatedTop + 28 + isolatedRows.length * (nodeHeight + 24) - 24 + padding;

  const edges = valid.map(link => {
    const key = linkKey(link);
    const source = centers.get(link.source)!;
    const target = centers.get(link.target)!;
    const isBack = back.has(key);
    const points = isBack
      ? [{ x: source.x + nodeWidth / 2, y: source.y }, { x: target.x + nodeWidth / 2, y: target.y }]
      : [{ x: source.x, y: source.y + nodeHeight / 2 }, ...chains.get(key)!.slice(1, -1).map(id => centers.get(id)!), { x: target.x, y: target.y - nodeHeight / 2 }];
    const cyclic = cycleOf.has(link.source) && cycleOf.get(link.source) === cycleOf.get(link.target);
    return { key, link, points, back: isBack, cyclic };
  });

  return { nodes, edges, order: [...rows.flat().filter(id => !isWaypoint(id)), ...isolated], cycles, isolatedTop, width, height };
}

/** SVG path for an edge: vertical S-curves through waypoints, or an arc to the right for back edges. */
export function edgePath(edge: RoutedEdge) {
  const [first, ...rest] = edge.points;
  if (edge.back) {
    const end = rest[0];
    return `M ${first.x} ${first.y} C ${first.x + BEND} ${first.y}, ${end.x + BEND} ${end.y}, ${end.x} ${end.y}`;
  }
  let path = `M ${first.x} ${first.y}`;
  let previous = first;
  for (const point of rest) {
    const middle = (previous.y + point.y) / 2;
    path += ` C ${previous.x} ${middle}, ${point.x} ${middle}, ${point.x} ${point.y}`;
    previous = point;
  }
  return path;
}

/** Where to place an edge's count label. */
export function labelPoint(edge: RoutedEdge): Point {
  const [first, ...rest] = edge.points;
  if (edge.back) return { x: Math.max(first.x, rest[0].x) + BEND * 0.75, y: (first.y + rest[0].y) / 2 };
  if (edge.points.length > 2) return edge.points[Math.floor(edge.points.length / 2)];
  const end = rest[0];
  return { x: (first.x + end.x) / 2, y: (first.y + end.y) / 2 };
}

export type MatrixCell = ArchitectureLink & { row: number; column: number; below: boolean };

/**
 * Dependency structure matrix in layer order. Forward dependencies always land above the
 * diagonal; a cell below the diagonal is a back edge, which only exists inside an import cycle.
 */
export function dependencyMatrix(groups: ArchitectureGroup[], links: ArchitectureLink[]) {
  const { order, cycles } = layeredLayout(groups, links);
  const index = new Map(order.map((id, position) => [id, position]));
  const cells: MatrixCell[] = links
    .filter(link => index.has(link.source) && index.has(link.target) && link.source !== link.target)
    .map(link => ({ ...link, row: index.get(link.source)!, column: index.get(link.target)!, below: index.get(link.source)! > index.get(link.target)! }));
  return { order, cells, cycles, max: Math.max(0, ...cells.map(cell => cell.count)) };
}

// Record diagrams: tables and types drawn as boxes with one row per column or member.
export const RECORD_HEADER = 40;
export const RECORD_ROW = 22;
const RECORD_FOOT = 8;
const WAYPOINT_HEIGHT = 14;
const ISOLATED_LABEL = 34;
const SELF_LOOP = 34;

export type RecordInput = { id: string; rows: number };
export type RecordLinkInput = { id: string; source: string; target: string; sourceRow?: number | null; targetRow?: number | null };
export type PlacedRecord = { id: string; x: number; y: number; width: number; height: number; layer: number; isolated: boolean };
export type RecordEdge<L extends RecordLinkInput = RecordLinkInput> = { link: L; points: Point[]; back: boolean; self: boolean; cyclic: boolean };
export type RecordLayout<L extends RecordLinkInput = RecordLinkInput> = {
  records: PlacedRecord[];
  edges: RecordEdge<L>[];
  cycles: string[][];
  /** Top of the area for records with no links to others in view, when there are also linked records. */
  isolatedTop: number | null;
  width: number;
  height: number;
};
export type RecordOptions = { width?: number; gapX?: number; gapY?: number; padding?: number; sweeps?: number };

export const recordHeight = (rows: number) => RECORD_HEADER + rows * RECORD_ROW + (rows ? RECORD_FOOT : 0);

/**
 * Left-to-right layered layout for record diagrams. A link's source sits in an earlier column
 * than its target; a link that closes a cycle runs right to left with `back: true`, and a record
 * linked to itself gets a loop on its right side. Links attach to a row when one is given,
 * otherwise to the record's header.
 */
export function recordLayout<L extends RecordLinkInput>(records: RecordInput[], links: L[], options: RecordOptions = {}): RecordLayout<L> {
  const { width: recordWidth = 250, gapX = 110, gapY = 28, padding = 24, sweeps = 4 } = options;
  const ids = records.map(record => record.id);
  const heights = new Map(records.map(record => [record.id, recordHeight(record.rows)]));
  const usable = links.filter(link => heights.has(link.source) && heights.has(link.target));
  const pairs = new Map<string, Endpoints>();
  for (const link of usable) if (link.source !== link.target) pairs.set(linkKey(link), { source: link.source, target: link.target });
  const order = orderLayers(ids, [...pairs.values()], sweeps);

  const heightOf = (id: string) => (order.waypoints.has(id) ? WAYPOINT_HEIGHT : heights.get(id)!);
  const columnHeight = (column: string[]) => column.reduce((sum, id) => sum + heightOf(id), 0) + Math.max(0, column.length - 1) * gapY;
  const tallest = Math.max(0, ...order.rows.map(columnHeight));
  const origin = new Map<string, Point>();
  const placed: PlacedRecord[] = [];
  order.rows.forEach((column, layer) => {
    const x = padding + layer * (recordWidth + gapX);
    let y = padding + (tallest - columnHeight(column)) / 2;
    for (const id of column) {
      origin.set(id, { x, y });
      if (!order.waypoints.has(id)) placed.push({ id, x, y, width: recordWidth, height: heights.get(id)!, layer, isolated: false });
      y += heightOf(id) + gapY;
    }
  });
  let width = order.rows.length ? padding * 2 + order.rows.length * recordWidth + (order.rows.length - 1) * gapX : 0;
  let height = order.rows.length ? padding * 2 + tallest : 0;

  const isolated = ids.filter(id => !order.connected.has(id));
  let isolatedTop: number | null = null;
  if (isolated.length) {
    const gap = 36;
    const top = order.rows.length ? height + ISOLATED_LABEL : padding;
    isolatedTop = order.rows.length ? height : null;
    const columns = Math.min(isolated.length, Math.max(3, order.rows.length));
    const bottoms = Array.from({ length: columns }, () => top);
    for (const id of isolated) {
      const column = bottoms.indexOf(Math.min(...bottoms));
      const x = padding + column * (recordWidth + gap);
      origin.set(id, { x, y: bottoms[column] });
      placed.push({ id, x, y: bottoms[column], width: recordWidth, height: heights.get(id)!, layer: order.rows.length, isolated: true });
      bottoms[column] += heights.get(id)! + gapY;
    }
    height = Math.max(...bottoms) - gapY + padding;
    width = Math.max(width, padding * 2 + columns * recordWidth + (columns - 1) * gap);
  }

  const anchorY = (id: string, row: number | null | undefined) => {
    const top = origin.get(id)!.y;
    return row === null || row === undefined || row < 0 ? top + RECORD_HEADER / 2 : top + RECORD_HEADER + row * RECORD_ROW + RECORD_ROW / 2;
  };
  let loops = false;
  const edges = usable.map(link => {
    const source = origin.get(link.source)!;
    const target = origin.get(link.target)!;
    const sourceY = anchorY(link.source, link.sourceRow);
    const targetY = anchorY(link.target, link.targetRow);
    if (link.source === link.target) {
      loops = true;
      const end = Math.abs(targetY - sourceY) < 8 ? sourceY + 14 : targetY;
      return { link, points: [{ x: source.x + recordWidth, y: sourceY }, { x: source.x + recordWidth, y: end }], back: false, self: true, cyclic: false };
    }
    const key = linkKey(link);
    const cyclic = order.cycleOf.has(link.source) && order.cycleOf.get(link.source) === order.cycleOf.get(link.target);
    if (order.back.has(key)) {
      return { link, points: [{ x: source.x, y: sourceY }, { x: target.x + recordWidth, y: targetY }], back: true, self: false, cyclic };
    }
    const points: Point[] = [{ x: source.x + recordWidth, y: sourceY }];
    for (const waypoint of order.chains.get(key)!.slice(1, -1)) {
      const at = origin.get(waypoint)!;
      points.push({ x: at.x, y: at.y + WAYPOINT_HEIGHT / 2 }, { x: at.x + recordWidth, y: at.y + WAYPOINT_HEIGHT / 2 });
    }
    points.push({ x: target.x, y: targetY });
    return { link, points, back: false, self: false, cyclic };
  });
  return { records: placed, edges, cycles: order.cycles, isolatedTop, width: width + (loops ? SELF_LOOP + 8 : 0), height };
}

/** Horizontal S-curves between record sides; back edges leave leftward and self links loop right. */
export function recordEdgePath(edge: RecordEdge) {
  const [first, ...rest] = edge.points;
  if (edge.self) {
    const end = rest[0];
    const out = first.x + SELF_LOOP;
    return `M ${first.x} ${first.y} C ${out} ${first.y}, ${out} ${end.y}, ${end.x} ${end.y}`;
  }
  let path = `M ${first.x} ${first.y}`;
  let previous = first;
  for (const point of rest) {
    const bend = Math.max(24, Math.abs(point.x - previous.x) / 2) * (edge.back ? -1 : 1);
    path += ` C ${previous.x + bend} ${previous.y}, ${point.x - bend} ${point.y}, ${point.x} ${point.y}`;
    previous = point;
  }
  return path;
}

/** Outward direction along x at each end of an edge: +1 leaves a record to the right. */
export function recordEndDirections(edge: RecordEdge): { start: 1 | -1; end: 1 | -1 } {
  return { start: edge.back ? -1 : 1, end: edge.self || edge.back ? 1 : -1 };
}
