"use client";

import { useEffect, useMemo, useState } from "react";
import { FileCode2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, sourceFileSchema, type AnalysisSourceFile } from "@/lib/analysis-api";

// Lines around the evidence range, and hard caps so a large file or a whole-file
// declaration cannot render an unbounded number of DOM rows.
const CONTEXT_LINES = 4;
const WINDOW_LIMIT = 240;
const FILE_LIMIT = 2000;

type State =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; file: AnalysisSourceFile }
  | { status: "error"; message: string };

/** Parses the analyzer's "start-end" evidence range. */
export function parseLineRange(lines: string | null | undefined): [number, number] | null {
  if (!lines) return null;
  const match = /^(\d{1,9})-(\d{1,9})$/.exec(lines);
  if (!match) return null;
  const start = Number(match[1]);
  const end = Number(match[2]);
  return start > 0 && end >= start ? [start, end] : null;
}

export function SourceView({ jobId, path, lines }: { jobId: string | null; path: string; lines?: string | null }) {
  // The caller remounts this component per path, so the opening state is derived
  // rather than assigned from inside the effect.
  const [state, setState] = useState<State>(
    jobId && path ? { status: "loading" } : { status: "idle" });
  const [whole, setWhole] = useState(false);

  useEffect(() => {
    if (!jobId || !path) return;
    const controller = new AbortController();
    void (async () => {
      try {
        const file = sourceFileSchema.parse(await api(
          `/${jobId}/source?path=${encodeURIComponent(path)}`, { signal: controller.signal }));
        if (!controller.signal.aborted) setState({ status: "ready", file });
      } catch (cause) {
        if (controller.signal.aborted) return;
        setState({ status: "error", message: cause instanceof Error ? cause.message
          : "Source text could not be loaded." });
      }
    })();
    return () => controller.abort();
  }, [jobId, path]);

  const file = state.status === "ready" ? state.file : null;
  // Repository text is untrusted: it is rendered as text children only, never as markup.
  const rows = useMemo(() => {
    if (!file) return [];
    const all = file.text.split(/\r?\n/);
    if (all.length && all[all.length - 1] === "") all.pop();
    const range = parseLineRange(lines);
    if (whole || !range) {
      return all.slice(0, FILE_LIMIT).map((text, index) => ({ number: index + 1, text, marked: false }));
    }
    const from = Math.max(1, range[0] - CONTEXT_LINES);
    const to = Math.min(all.length, Math.min(range[1] + CONTEXT_LINES, from + WINDOW_LIMIT - 1));
    return all.slice(from - 1, to).map((text, index) => ({
      number: from + index, text, marked: from + index >= range[0] && from + index <= range[1],
    }));
  }, [file, lines, whole]);

  if (state.status === "idle") return null;
  if (state.status === "loading") {
    return <p className="mt-4 flex items-center gap-2 text-sm text-slate-500">
      <Loader2 className="size-3.5 animate-spin" /> Loading source…</p>;
  }
  if (state.status === "error") {
    return <p className="mt-4 rounded-lg border border-white/10 bg-[var(--background)] p-3 text-sm text-slate-400">{state.message}</p>;
  }

  const range = parseLineRange(lines);
  const hidden = file && !whole && rows.length < Math.min(file.lines, FILE_LIMIT);
  return <div className="mt-4 min-w-0">
    <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
      <FileCode2 className="size-3.5 shrink-0" />
      <span className="min-w-0 break-all font-medium text-slate-300">{path}</span>
      {range && <span className="text-cyan-300">lines {range[0]}–{range[1]}</span>}
      <span>· {file?.lines} captured lines</span>
    </div>
    <div className="overflow-x-auto rounded-lg border border-white/10 bg-[var(--background)]">
      <pre className="min-w-fit py-2 text-[12px] leading-5"><code>
        {rows.map(row => <span key={row.number}
          className={`flex ${row.marked ? "bg-cyan-300/[0.09]" : ""}`}>
          <span className="sticky left-0 select-none border-r border-white/[0.06] bg-[var(--background)] px-2 text-right text-slate-600"
            style={{ minWidth: "3.5rem" }}>{row.number}</span>
          <span className={`whitespace-pre px-3 ${row.marked ? "text-slate-100" : "text-slate-400"}`}>{row.text || " "}</span>
        </span>)}
      </code></pre>
    </div>
    <div className="mt-2 flex flex-wrap items-center gap-3">
      {(hidden || whole) && range && <Button variant="ghost" size="sm" className="text-cyan-200"
        onClick={() => setWhole(!whole)}>{whole ? "Show evidence range" : "Show whole file"}</Button>}
      {file?.truncated && <span className="text-xs text-amber-300">
        Captured text was truncated at the viewer byte limit.</span>}
      {rows.length >= FILE_LIMIT && <span className="text-xs text-amber-300">
        Showing the first {FILE_LIMIT} lines.</span>}
    </div>
  </div>;
}
