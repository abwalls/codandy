"use client";

import Link from "next/link";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { InvestigationBrief } from "@/components/investigation-brief";
import { InvestigationSource } from "@/components/investigation-source";
import { InvestigationCases } from "@/components/investigation-cases";
import { ThemePicker } from "@/components/theme-picker";
import { debuggingRequest, observationSchema, sentryStatusSchema, type Observation } from "@/lib/debugging-api";

export function DebuggingWorkspace() {
  const [caseId, setCaseId] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [issue, setIssue] = useState("");
  const [event, setEvent] = useState("latest");
  const [status, setStatus] = useState("Checking local Sentry configuration…");
  const [observation, setObservation] = useState<Observation | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reviewed, setReviewed] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => {
    const abort = new AbortController();
    debuggingRequest("/sentry/status", { signal: abort.signal }).then(raw => {
      const data = sentryStatusSchema.parse(raw);
      setStatus(data.configured ? `Configured for ${data.organization} on ${data.host}. Fetch an event to verify access.` : "Sentry is not configured. Stack and JSON imports are ready on the local backend.");
    }).catch(cause => { if (!abort.signal.aborted) setStatus(cause.message); });
    return () => { abort.abort(); controller.current?.abort(); };
  }, []);

  async function run(path: string, body?: string, media?: string) {
    if (busy) return;
    setBusy(true); setError(""); setReviewed(false); setObservation(null); setCaseId(null);
    const abort = new AbortController(); controller.current = abort;
    try {
      if (body && new TextEncoder().encode(body).length > 2 * 1024 * 1024) throw new Error("Imports must be 2 MiB or smaller.");
      const result = observationSchema.parse(await debuggingRequest(path, { method: "POST", body,
        headers: media ? { "Content-Type": media } : {}, signal: abort.signal }));
      if (!abort.signal.aborted) { setObservation(result); setText(""); }
    } catch (cause) {
      setError(abort.signal.aborted ? "Request cancelled. No result was retained." : cause instanceof Error ? cause.message : "Import failed.");
    } finally { controller.current = null; setBusy(false); }
  }

  function download() {
    if (!observation || !reviewed) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(observation, null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = `codandy-observation-${observation.id}.json`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <main className="atlas-grid min-h-svh bg-[var(--background)] p-5 text-foreground sm:p-8">
    <header className="mx-auto mb-8 flex max-w-6xl flex-wrap items-center justify-between gap-4"><Link href="/" className="font-semibold">← Codandy</Link><ThemePicker /></header>
    <div className="mx-auto grid max-w-6xl gap-7 lg:grid-cols-[320px_minmax(0,1fr)]">
      <aside className="space-y-6">
        <InvestigationCases observation={observation} disabled={busy} onOpen={(value, id) => { setCaseId(id); setObservation(value); setReviewed(false); setError(""); }} />
        <div><h1 className="text-2xl font-semibold">Errors & stacks</h1><p className="mt-2 text-sm text-muted-foreground">Inspect a Sentry event or a Python, JavaScript or .NET stack. No repository execution is required.</p></div>
        <section className="space-y-3 rounded-xl border bg-card p-4"><h2 className="font-semibold">Read from Sentry</h2><p role="status" className="text-sm text-muted-foreground">{status}</p>
          <label className="block text-sm">Issue ID<Input value={issue} disabled={busy} onChange={e => setIssue(e.target.value)} placeholder="Numeric issue ID" /></label>
          <label className="block text-sm">Event<Input value={event} disabled={busy} onChange={e => setEvent(e.target.value)} placeholder="latest or event ID" /></label>
          <Button disabled={busy || !/^\d{1,32}$/.test(issue) || !/^(latest|oldest|recommended|[a-fA-F0-9]{32})$/.test(event)} onClick={() => run(`/sentry/issues/${issue}/events/${event}`)}>Fetch event</Button>
          <details className="text-sm"><summary className="cursor-pointer">Connection setup</summary><p className="mt-2">Set CODANDY_SENTRY_TOKEN and CODANDY_SENTRY_ORGANIZATION in backend/.env, then restart the backend. Use a Sentry token with event:read access. CODANDY_SENTRY_HOST selects sentry.io, us.sentry.io or de.sentry.io. The token stays on your backend.</p></details>
        </section>
        <section className="space-y-3 rounded-xl border bg-card p-4"><h2 className="font-semibold">Import evidence</h2>
          <label className="block text-sm">Stack or Sentry REST event JSON<Textarea value={text} disabled={busy} onChange={e => setText(e.target.value)} className="mt-2 h-48 resize-y font-mono text-xs" placeholder="Paste a traceback, stack, or REST event JSON…" /></label>
          <Button disabled={busy || !text.trim()} onClick={() => run("/imports", text, text.trimStart().startsWith("{") ? "application/json" : "text/plain")}>Inspect evidence</Button>
          <label className="block text-sm">Or choose a JSON / text file<Input type="file" accept=".json,.txt,.log" disabled={busy} onChange={async e => {
            const file = e.target.files?.[0]; e.target.value = ""; if (!file) return;
            if (file.size > 2 * 1024 * 1024) { setError("Imports must be 2 MiB or smaller."); return; }
            try { const content = await file.text(); await run("/imports", content, content.trimStart().startsWith("{") ? "application/json" : "text/plain"); }
            catch { setError("Could not read this file."); }
          }} /></label>
          <p className="text-xs text-muted-foreground">2 MiB maximum. Evidence is sent to your local backend for scrubbing. Save an investigation to retain sanitized evidence on this computer. No automatic AI submission.</p>
        </section>
      </aside>
      <section className="min-w-0 space-y-5" aria-label="Observation">
        {busy && <div role="status" className="flex items-center gap-3">Reading evidence…<Button variant="outline" onClick={() => controller.current?.abort()}>Cancel</Button></div>}
        {error && <p role="alert" className="break-words rounded-xl border border-destructive p-4">{error}</p>}
        {!observation && !busy && <div className="rounded-xl border bg-card p-8"><h2 className="text-xl font-semibold">Start with the failure</h2><p className="mt-3 text-muted-foreground">Import an event to see its exception chain, ordered frames, breadcrumbs and missing evidence.</p><p className="mt-3 text-sm text-muted-foreground">Save a case to preserve evidence and notes. Match saved cases to a repository snapshot to inspect candidate source files. A stack alone does not establish function timing or the exact cause of a null reference.</p></div>}
        {observation && <>
          <div className="rounded-xl border bg-card p-5"><p className="text-sm text-muted-foreground">{observation.source.provider} · {observation.source.format}</p><h2 className="mt-2 break-words text-xl font-semibold">{observation.title || "Imported observation"}</h2><p className="mt-2 break-words text-sm">{observation.environment || "Environment unknown"} · {observation.release || "Revision unknown"}</p><Button className="mt-3" variant="outline" onClick={() => { setObservation(null); setCaseId(null); setReviewed(false); }}>Clear evidence</Button></div>
          {caseId && <><InvestigationBrief key={`brief:${caseId}`} caseId={caseId} /><InvestigationSource key={caseId} caseId={caseId} /></>}
          {observation.exceptions.map(exception => <section key={exception.index} className="rounded-xl border bg-card p-5"><h3 className="break-words font-semibold">{exception.type || "Exception"}: {exception.value}</h3><p className="my-3 text-xs text-muted-foreground">Caller → callee · {exception.frames_omitted} omitted frames{exception.relation_to_next ? ` · followed by ${exception.relation_to_next.replaceAll("_", " ")}` : ""}</p>
            {!exception.frames.length && <p>No stack frames provided.</p>}
            <ol className="space-y-2">{exception.frames.map(frame => <li key={frame.index} className="rounded-lg border p-3"><details><summary className="cursor-pointer break-all font-mono text-sm">{frame.function || "Unknown function"} — {frame.path || frame.abs_path || "Path unavailable"}{frame.line ? `:${frame.line}` : ""}{frame.column !== null ? `:${frame.column}` : ""}</summary><p className="my-2 text-xs text-muted-foreground">{frame.in_app === null ? "Application ownership unknown" : frame.in_app ? "Application frame" : "External frame"}{frame.after_async_boundary ? " · async boundary" : ""} · Source revision unverified</p>{frame.context.length ? <pre className="overflow-auto text-xs">{frame.context.map(line => `${line.line}  ${line.text}`).join("\n")}</pre> : <p className="text-sm text-muted-foreground">No source context supplied.</p>}</details></li>)}</ol>
          </section>)}
          <details className="rounded-xl border bg-card p-5"><summary className="cursor-pointer font-semibold">Breadcrumbs ({observation.breadcrumbs.length})</summary><ol className="mt-3 space-y-2 text-sm">{observation.breadcrumbs.map((crumb, i) => <li key={i} className="break-words">{crumb.timestamp} {crumb.category}: {crumb.message || "No message"}</li>)}</ol></details>
          <section className="space-y-3 rounded-xl border bg-card p-5"><h3 className="font-semibold">Review before sharing</h3><p className="text-sm text-muted-foreground">Scrubbing is best-effort. Review the full sanitized result before downloading or sharing with an assistant.</p><ul className="list-disc space-y-1 pl-5 text-sm">{[...observation.limitations, ...observation.truncations.map(t => `${t.section}: retained ${t.retained} of ${t.original}. ${t.reason}`), ...observation.redactions.map(r => `${r.section}: ${r.count} ${r.kind} redaction(s)`), ...observation.withheld.map(w => `Withheld: ${w}`)].map((note, i) => <li key={i}>{note}</li>)}</ul><details><summary className="cursor-pointer text-sm">Full sanitized result and provider interpretation</summary><pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap break-all text-xs">{JSON.stringify(observation, null, 2)}</pre></details><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} />I reviewed the sanitized evidence.</label><Button disabled={!reviewed} onClick={download}>Download observation</Button></section>
        </>}
      </section>
    </div>
  </main>;
}
