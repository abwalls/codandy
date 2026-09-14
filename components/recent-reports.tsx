"use client";

import { useState } from "react";
import { api, atlasSchema, jobSchema, recentReportsSchema, type AnalysisAtlas, type AnalysisJob } from "@/lib/analysis-api";
import { Button } from "@/components/ui/button";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";

export function RecentReports({ onOpen }: { onOpen: (atlas: AnalysisAtlas, job: AnalysisJob) => void }) {
  const [history, setHistory] = useState<ReturnType<typeof recentReportsSchema.parse> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);
  async function remove(id: string) {
    setBusy(true); setError(null);
    try {
      await api(`/${id}`, { method: "DELETE" });
      setHistory(current => current ? { ...current, reports: current.reports.filter(report => report.id !== id) } : current);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not remove this report."); }
    finally { setBusy(false); setRemoving(null); }
  }
  async function refresh() {
    setBusy(true); setError(null);
    try { setHistory(recentReportsSchema.parse(await api("", { signal: AbortSignal.timeout(10000) }))); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load recent reports."); }
    finally { setBusy(false); }
  }
  async function open(id: string) {
    setBusy(true); setError(null);
    try {
      const [atlas, job] = await Promise.all([
        api(`/${id}/atlas`, { signal: AbortSignal.timeout(15000) }),
        api(`/${id}`, { signal: AbortSignal.timeout(10000) }),
      ]);
      onOpen(atlasSchema.parse(atlas), jobSchema.parse(job));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "This report is no longer available."); }
    finally { setBusy(false); }
  }
  return <section className="mt-5 max-w-2xl space-y-3">
    <Button variant="outline" disabled={busy} onClick={() => void refresh()}>{busy ? "Loading reports…" : history ? "Refresh recent reports" : "Recent reports"}</Button>
    {error && <p role="alert" className="text-sm text-amber-200">{error}</p>}
    <AlertDialog open={removing !== null} onOpenChange={value => { if (!value && !busy) setRemoving(null); }}>
      <AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Remove this report?</AlertDialogTitle><AlertDialogDescription>The retained atlas and captured source will be removed from this backend. Downloaded atlas files on your device will remain. You can analyze the repository again later.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel disabled={busy}>Keep report</AlertDialogCancel><AlertDialogAction disabled={busy} onClick={event => { event.preventDefault(); if (removing) void remove(removing); }}>Remove report</AlertDialogAction></AlertDialogFooter></AlertDialogContent>
    </AlertDialog>
    {history && <>
      <p className="text-xs leading-5 text-slate-500">{history.persistent ? "Completed reports are saved on this backend, up to its retention limit." : "Reports are kept in backend memory and expire on restart or retention eviction."}</p>
      {!history.reports.length && <p className="text-sm text-slate-400">No completed reports retained yet.</p>}
      {history.reports.map(report => <div key={report.id} className="flex min-w-0 items-center gap-2 rounded-xl border border-white/10 bg-[var(--surface-4)] p-3"><button disabled={busy} className="min-w-0 flex-1 p-1 text-left disabled:opacity-50" onClick={() => void open(report.id)}><span className="block break-all text-sm text-cyan-200">{report.repository.url || report.repository.name}</span><span className="mt-1 block text-xs text-slate-500">{report.repository.commit?.slice(0, 12) || (report.repository.source === "archive" ? "ZIP upload" : "Unknown commit")} · {report.created_at}</span></button><Button variant="ghost" size="sm" disabled={busy} onClick={() => setRemoving(report.id)}>Remove</Button></div>)}
    </>}
  </section>;
}
