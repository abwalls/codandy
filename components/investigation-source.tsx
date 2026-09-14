"use client";

import { useEffect, useState } from "react";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SourceView } from "@/components/source-view";
import { api, recentReportsSchema } from "@/lib/analysis-api";
import { debuggingRequest } from "@/lib/debugging-api";

const bindingSchema = z.object({ exception_index: z.number(), frame_index: z.number(),
  snapshot_id: z.string().uuid(), status: z.enum(["exact", "candidate", "ambiguous", "unmapped"]),
  method: z.string(), revision: z.enum(["verified", "unknown", "mismatch"]), limitations: z.array(z.string()),
  candidates: z.array(z.object({ path: z.string(), line: z.number().nullable(), node_ids: z.array(z.string()) })) });
const savedBindings = z.object({ snapshot_id: z.string().uuid().nullable(), snapshot_repository: z.record(z.string()),
  runtime_commit: z.string().nullable(), path_prefix: z.string(), bindings: z.array(bindingSchema) });

export function InvestigationSource({ caseId }: { caseId: string }) {
  const [reports, setReports] = useState<z.infer<typeof recentReportsSchema>["reports"]>([]);
  const [snapshot, setSnapshot] = useState("");
  const [commit, setCommit] = useState("");
  const [prefix, setPrefix] = useState("");
  const [saved, setSaved] = useState<z.infer<typeof savedBindings> | null>(null);
  const [selected, setSelected] = useState<{ path: string; line: number | null } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    const abort = new AbortController();
    Promise.all([api("", { signal: abort.signal }), debuggingRequest(`/cases/${caseId}`, { signal: abort.signal })]).then(([rawReports, rawCase]) => {
      if (abort.signal.aborted) return;
      setReports(recentReportsSchema.parse(rawReports).reports);
      const data = savedBindings.parse(rawCase); setSaved(data); setSnapshot(data.snapshot_id || ""); setCommit(data.runtime_commit || ""); setPrefix(data.path_prefix);
    }).catch(cause => { if (!abort.signal.aborted) setError(cause.message); });
    return () => abort.abort();
  }, [caseId]);
  const expired = saved?.snapshot_id && !reports.some(report => report.id === saved.snapshot_id);
  async function bind() {
    setBusy(true); setError(""); setSelected(null);
    try {
      const data = savedBindings.parse(await debuggingRequest(`/cases/${caseId}/source-binding`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ snapshot_id: snapshot, runtime_commit: commit.trim() || null, path_prefix: prefix.trim() }) }));
      setSaved(data);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Source matching failed."); }
    finally { setBusy(false); }
  }
  return <section className="space-y-4 rounded-xl border bg-card p-5" aria-label="Stack source matching">
    <div><h3 className="font-semibold">Stack & source</h3><p className="mt-2 text-sm text-muted-foreground">Choose an analyzed repository snapshot. Matches are source candidates, not proof of the failing code revision.</p></div>
    <label className="block text-sm">Repository snapshot<select className="mt-1 w-full rounded-md border bg-background p-2" value={snapshot} disabled={busy} onChange={e => setSnapshot(e.target.value)}><option value="">Select a retained report</option>{reports.map(report => <option key={report.id} value={report.id}>{report.repository.url || report.repository.name || report.id} · {(report.repository.commit || "revision unknown").slice(0, 12)} · {new Date(report.created_at).toLocaleString()}</option>)}</select></label>
    <details><summary className="cursor-pointer text-sm">Runtime revision and path mapping (optional)</summary><div className="mt-3 grid gap-3 sm:grid-cols-2"><label className="text-sm">Reported runtime commit<Input value={commit} disabled={busy} onChange={e => setCommit(e.target.value)} placeholder="Full Git commit SHA" /></label><label className="text-sm">Deployment path prefix<Input value={prefix} disabled={busy} maxLength={500} onChange={e => setPrefix(e.target.value)} placeholder="/srv/my-service" /></label></div><p className="mt-2 text-xs text-muted-foreground">A matching user-supplied SHA is not independent verification. The prefix is removed before comparing captured file paths.</p></details>
    <Button disabled={busy || !snapshot || (!!commit.trim() && !/^(?:[a-fA-F0-9]{40}|[a-fA-F0-9]{64})$/.test(commit.trim()))} onClick={bind}>{busy ? "Matching…" : "Match and save source references"}</Button>
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    {expired && <p role="status" className="text-sm text-amber-500">The pinned snapshot is no longer retained. Mappings remain saved, but source may be unavailable. Analyze the repository again and select a new snapshot.</p>}
    {!!saved?.bindings.length && <><p className="text-xs text-muted-foreground">Saved snapshot {saved.snapshot_id} · {saved.snapshot_repository.commit || "revision unknown"}</p><div className="max-h-80 space-y-2 overflow-auto">{saved.bindings.map(binding => <div key={`${binding.exception_index}:${binding.frame_index}`} className="rounded-lg border p-3"><p className="text-sm">Exception {binding.exception_index + 1}, frame {binding.frame_index + 1} · {binding.status} · revision {binding.revision}</p><div className="mt-2 flex flex-wrap gap-2">{binding.candidates.map(candidate => <Button key={candidate.path} variant="outline" className="h-auto whitespace-normal break-all text-left text-xs" onClick={() => setSelected(candidate)}>{candidate.path}{candidate.line ? `:${candidate.line}` : ""}</Button>)}</div><details className="mt-2 text-xs text-muted-foreground"><summary className="cursor-pointer">Matching evidence: {binding.method.replaceAll("_", " ")}</summary><ul>{binding.limitations.map(note => <li key={note}>{note}</li>)}</ul></details></div>)}</div></>}
    {selected && saved?.snapshot_id && <SourceView key={`${saved.snapshot_id}:${selected.path}:${selected.line}`} jobId={saved.snapshot_id} path={selected.path} lines={selected.line ? `${selected.line}-${selected.line}` : undefined} />}
  </section>;
}
