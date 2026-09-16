import type { Observation } from "./debugging-api";
import type { Trace } from "./trace-api";

// Sequence views drawn from evidence that already carries an order: the frames active when an
// exception was raised (observed order at failure) and imported spans (traced start order).
// Static call-site order is a separate, later source and never mixes with these.

export type SequenceTone = "app" | "external" | "unknown" | "service" | "outside";
export type SequenceParticipant = { id: string; label: string; detail: string; tone: SequenceTone };
export type SequenceMessage = {
  id: string;
  from: string;
  to: string;
  label: string;
  detail: string;
  kind: "call" | "async" | "gap" | "raise" | "span";
  error: boolean;
  /** Last row (inclusive) during which the callee stays active; null when no activation opens. */
  activeUntil: number | null;
  durationMs: number | null;
  offsetMs: number | null;
  ref: { exception: number; frame: number } | { span: string } | null;
};
export type SequenceView = {
  basis: "observed_stack" | "traced_spans";
  participants: SequenceParticipant[];
  messages: SequenceMessage[];
  omitted: number;
  notes: string[];
};

type ExceptionRecord = Observation["exceptions"][number];
type Frame = ExceptionRecord["frames"][number];

const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? "" : "s"}`;
const baseName = (value: string) => value.replace(/\\/g, "/").split("/").filter(Boolean).pop() || value;
const locationOf = (frame: Frame) => frame.path || frame.abs_path || frame.module || null;

export function formatDuration(ms: number) {
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)} s`;
  if (ms >= 1) return `${ms.toFixed(1)} ms`;
  return `${Math.round(ms * 1000)} µs`;
}

/** Applies the message budget and keeps activations and lifelines consistent with it. */
function finish(basis: SequenceView["basis"], participants: SequenceParticipant[], messages: SequenceMessage[], limit: number, notes: string[], keepLast: boolean): SequenceView {
  const omitted = Math.max(0, messages.length - limit);
  const kept = omitted ? (keepLast ? messages.slice(-limit) : messages.slice(0, limit)) : messages;
  const shift = keepLast ? omitted : 0;
  const adjusted = kept.map(message => ({
    ...message,
    activeUntil: message.activeUntil === null ? null : Math.min(kept.length - 1, Math.max(0, message.activeUntil - shift)),
  }));
  const used = new Set(adjusted.flatMap(message => [message.from, message.to]));
  return { basis, participants: participants.filter(participant => used.has(participant.id)), messages: adjusted, omitted, notes };
}

export type StackOptions = { groupBy?: "file" | "function"; appOnly?: boolean; limit?: number };

/** Caller-to-callee arrows for the frames of one exception, ending where it was raised. */
export function stackSequence(exception: ExceptionRecord, options: StackOptions = {}): SequenceView {
  const { groupBy = "file", appOnly = false, limit = 60 } = options;
  const participants = new Map<string, SequenceParticipant>([["outside", {
    id: "outside", label: "Entry point", detail: "Whatever started the oldest captured frame. It is not part of the stack.", tone: "outside",
  }]]);
  const lifeline = (frame: Frame) => {
    const location = locationOf(frame);
    const key = groupBy === "function" ? `function:${location ?? ""}:${frame.function ?? ""}` : `file:${location ?? ""}`;
    const tone: SequenceTone = frame.in_app === true ? "app" : frame.in_app === false ? "external" : "unknown";
    const existing = participants.get(key);
    if (existing) {
      if (tone === "app") existing.tone = "app";
      return key;
    }
    participants.set(key, groupBy === "function"
      ? { id: key, label: frame.function || "Unknown function", detail: `${frame.function || "Unknown function"} in ${location ?? "an unknown location"}`, tone }
      : { id: key, label: location ? baseName(location) : "Unknown location", detail: location ?? "These frames have no path or module.", tone });
    return key;
  };

  const collapse = appOnly && exception.frames.some(frame => frame.in_app !== false);
  const visible = collapse ? exception.frames.filter((frame, index) => frame.in_app !== false || index === exception.frames.length - 1) : exception.frames;
  const messages: SequenceMessage[] = [];
  let caller = "outside";
  let previous: Frame | null = null;
  for (const frame of visible) {
    const callee = lifeline(frame);
    const hidden = frame.index - (previous ? previous.index + 1 : 0);
    const name = `${frame.function || "unknown"}()`;
    const where = `${locationOf(frame) ?? "an unknown location"}${frame.line ? `:${frame.line}` : ""}`;
    const context = hidden > 0
      ? ` ${plural(hidden, "frame")} outside the application are collapsed before it.`
      : previous ? ` Called from ${locationOf(previous) ?? "the previous frame"}${previous.line ? ` line ${previous.line}` : ""}.` : " This is the oldest captured frame.";
    messages.push({
      id: `frame:${frame.index}`, from: caller, to: callee,
      label: hidden > 0 ? `${plural(hidden, "hidden frame")}, then ${name}` : name,
      detail: `${frame.function || "Unknown function"} at ${where}.${context}${frame.after_async_boundary ? " Recorded after an async boundary, so it may have been scheduled rather than called directly." : ""}`,
      kind: hidden > 0 ? "gap" : frame.after_async_boundary ? "async" : "call",
      error: false, activeUntil: 0, durationMs: null, offsetMs: null, ref: { exception: exception.index, frame: frame.index },
    });
    caller = callee;
    previous = frame;
  }
  if (previous) {
    messages.push({
      id: "raise", from: caller, to: caller, label: `raises ${exception.type || "an exception"}`,
      detail: `${exception.type || "Exception"}${exception.value ? `: ${exception.value}` : ""}`,
      kind: "raise", error: true, activeUntil: null, durationMs: null, offsetMs: null, ref: { exception: exception.index, frame: previous.index },
    });
    // Every frame on the stack was still running when the exception was raised.
    for (const message of messages) if (message.activeUntil !== null) message.activeUntil = messages.length - 1;
  }

  const notes = ["Observed order at failure: each arrow is a call that was still in progress when the exception was raised, oldest caller first. Calls that had already returned are not shown, and a stack carries no timing."];
  if (exception.frames_omitted) notes.push(`${exception.frames_omitted === 1 ? "1 frame was" : `${exception.frames_omitted} frames were`} omitted by the provider or the import budget, so the chain may be incomplete.`);
  if (collapse && visible.length < exception.frames.length) notes.push(`${plural(exception.frames.length - visible.length, "frame")} outside the application are collapsed into dashed arrows.`);
  if (exception.frames.some(frame => frame.after_async_boundary)) notes.push("Dotted arrows cross an async boundary: the callee may have been scheduled by the caller rather than called directly.");
  if (!exception.frames.length) notes.push("This exception has no stack frames.");
  const view = finish("observed_stack", [...participants.values()], messages, limit, notes, true);
  if (view.omitted) view.notes.push(`${plural(view.omitted, "earlier arrow")} not drawn; the calls nearest the failure are kept.`);
  return view;
}

/** Spans of one trace in start order, from the parent span's service to the span's service. */
export function traceSequence(trace: Trace, traceId: string, options: { limit?: number } = {}): SequenceView {
  const { limit = 80 } = options;
  const notes = [
    "Traced order: each arrow is a span, ordered by start time and drawn from its parent span's service to its own service. Parent links come from the imported IDs, not from source code.",
    "Durations are elapsed wall time, not CPU time. Sibling spans that overlap may have run concurrently.",
    "Activation bars group descendants; their drawn height is not a time scale. Use the waterfall for timing.",
  ];
  const spans = trace.spans.filter(span => span.trace_id === traceId).sort((a, b) => {
    const left = BigInt(a.start_ns);
    const right = BigInt(b.start_ns);
    return left < right ? -1 : left > right ? 1 : a.span_id.localeCompare(b.span_id);
  });
  if (!spans.length) return { basis: "traced_spans", participants: [], messages: [], omitted: 0, notes };
  const origin = BigInt(spans[0].start_ns);
  const byId = new Map(spans.map(span => [span.span_id, span]));
  const rows = new Map(spans.map((span, index) => [span.span_id, index]));
  const children = new Map<string, string[]>();
  for (const span of spans) {
    if (span.parent_state === "present" && span.parent_id && byId.has(span.parent_id)) {
      children.set(span.parent_id, [...(children.get(span.parent_id) ?? []), span.span_id]);
    }
  }
  const lastRow = new Map<string, number>();
  const reach = (id: string, seen: Set<string>): number => {
    const known = lastRow.get(id);
    if (known !== undefined) return known;
    seen.add(id);
    let last = rows.get(id)!;
    for (const child of children.get(id) ?? []) if (!seen.has(child)) last = Math.max(last, reach(child, seen));
    lastRow.set(id, last);
    return last;
  };

  const services = new Map<string, SequenceParticipant>();
  const service = (name: string) => {
    const id = `service:${name}`;
    if (!services.has(id)) services.set(id, { id, label: name, detail: `Service ${name}, as reported by the span resource`, tone: "service" });
    return id;
  };
  let outside = false;
  const messages = spans.map((span): SequenceMessage => {
    const parent = span.parent_state === "present" && span.parent_id ? byId.get(span.parent_id) : undefined;
    let from = "outside";
    if (parent) from = service(parent.service);
    else outside = true;
    const to = service(span.service);
    const start = BigInt(span.start_ns);
    const durationMs = Number(BigInt(span.end_ns) - start) / 1e6;
    const offsetMs = Number(start - origin) / 1e6;
    const lineage = parent ? `Child of ${parent.name} in ${parent.service}.`
      : span.parent_state === "root" ? "Starts the trace."
        : span.parent_state === "cycle" ? "Its parent chain is cyclic, so its caller is unknown."
          : "Its parent span is not in this import.";
    return {
      id: `span:${span.span_id}`, from, to, label: span.name,
      detail: `${span.service}: ${span.name}. Starts ${formatDuration(offsetMs)} after the trace begins and lasts ${formatDuration(durationMs)}${span.status === "error" ? "; status error" : ""}. ${lineage}`,
      kind: "span", error: span.status === "error", activeUntil: reach(span.span_id, new Set()), durationMs, offsetMs, ref: { span: span.span_id },
    };
  });
  const participants = [
    ...(outside ? [{ id: "outside", label: "Outside this trace", detail: "The caller of a root span, or a parent span missing from this file.", tone: "outside" as const }] : []),
    ...services.values(),
  ];
  if (spans.length > limit) notes.push(`The first ${limit} spans by start time are shown; ${spans.length - limit} later spans are omitted.`);
  return finish("traced_spans", participants, messages, limit, notes, false);
}

// Mermaid text export. Names come from telemetry and repositories, so they lose characters that
// Mermaid treats as syntax. The page never renders this text as a diagram.
const mermaidText = (value: string) => value.replace(/[\r\n;#:"<>{}%]+/g, " ").replace(/\s+/g, " ").trim().slice(0, 80) || "unnamed";

export function mermaidSequence(view: SequenceView) {
  const aliases = new Map(view.participants.map((participant, index) => [participant.id, `P${index + 1}`]));
  const lines = ["sequenceDiagram"];
  for (const participant of view.participants) lines.push(`    participant ${aliases.get(participant.id)} as ${mermaidText(participant.label)}`);
  if (view.omitted) lines.push(`    %% ${view.omitted} arrows omitted`);
  for (const message of view.messages) {
    const from = aliases.get(message.from);
    const to = aliases.get(message.to);
    if (!from || !to) continue;
    if (message.kind === "raise") {
      lines.push(`    Note over ${to}: ${mermaidText(message.label)}`);
      continue;
    }
    const arrow = message.error ? "-x" : message.kind === "async" ? "-)" : message.kind === "gap" ? "-->>" : "->>";
    const duration = message.durationMs !== null ? ` (${formatDuration(message.durationMs)})` : "";
    lines.push(`    ${from}${arrow}${to}: ${mermaidText(message.label)}${duration}`);
  }
  return `${lines.join("\n")}\n`;
}
