"use client";

import { useCallback, useEffect, useState } from "react";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { debuggingRequest, observationSchema, type Observation } from "@/lib/debugging-api";

const caseSchema = z.object({ schema_version: z.literal("case-0.1"), id: z.string().uuid(),
  title: z.string(), state: z.enum(["open", "resolved", "archived"]), created_at: z.string(),
  updated_at: z.string(), notes: z.string(), observation: observationSchema });
const listSchema = z.object({ persistent: z.boolean(), unreadable: z.number(), limit: z.number(),
  cases: z.array(caseSchema.omit({ schema_version: true, notes: true, observation: true }).extend({ provider: z.string() })) });

export function InvestigationCases({ observation, onOpen, disabled }: {
  observation: Observation | null; onOpen: (observation: Observation, caseId: string | null) => void; disabled: boolean;
}) {
  const [listing, setListing] = useState<z.infer<typeof listSchema> | null>(null);
  const [selected, setSelected] = useState<z.infer<typeof caseSchema> | null>(null);
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [state, setState] = useState<"open" | "resolved" | "archived">("open");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const active = selected?.observation.id === observation?.id ? selected : null;
  const dirty = !!active && (title !== active.title || notes !== active.notes || state !== active.state);
  const refresh = useCallback(async () => setListing(listSchema.parse(await debuggingRequest("/cases"))), []);
  useEffect(() => {
    const abort = new AbortController();
    debuggingRequest("/cases", { signal: abort.signal }).then(raw => {
      if (!abort.signal.aborted) setListing(listSchema.parse(raw));
    }).catch(cause => { if (!abort.signal.aborted) setError(cause.message); });
    return () => abort.abort();
  }, []);
  function select(value: z.infer<typeof caseSchema>) {
    setSelected(value); setTitle(value.title); setNotes(value.notes); setState(value.state); onOpen(value.observation, value.id);
  }
  async function run(task: () => Promise<void>) {
    setBusy(true); setError(""); setNotice("");
    try { await task(); await refresh(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Investigation request failed."); }
    finally { setBusy(false); }
  }
  const locked = busy || disabled;
  return <section className="space-y-3 rounded-xl border bg-card p-4" aria-label="Saved investigations">
    <h2 className="font-semibold">Investigations</h2>
    <p className="text-xs text-muted-foreground">{listing?.persistent ? "Saved on this computer, independently of repository reports." : "Local investigation storage"}</p>
    {listing && !listing.persistent && <p className="text-xs text-amber-500">Storage is in memory only. Cases will be lost when the backend restarts.</p>}
    {!!listing?.unreadable && <p role="status" className="text-xs text-amber-500">{listing.unreadable} stored file(s) could not be loaded. Files were preserved.</p>}
    {observation && !active && <Button disabled={locked} onClick={() => run(async () => {
      select(caseSchema.parse(await debuggingRequest("/cases", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ observation_id: observation.id }) })));
      setNotice("Investigation saved with sanitized evidence.");
    })}>Save investigation</Button>}
    {active && <div className="space-y-3 border-t pt-3">
      <label className="block text-sm">Case title<Input value={title} maxLength={200} disabled={locked} onChange={e => setTitle(e.target.value)} /></label>
      <label className="block text-sm">Status<select className="mt-1 w-full rounded-md border bg-background p-2" value={state} disabled={locked} onChange={e => setState(e.target.value as typeof state)}><option value="open">Open</option><option value="resolved">Resolved</option><option value="archived">Archived</option></select></label>
      <label className="block text-sm">Investigation notes<Textarea className="mt-1 h-32" value={notes} maxLength={20000} disabled={locked} onChange={e => setNotes(e.target.value)} placeholder="Hypotheses, missing evidence and next steps…" /></label>
      <p className="text-xs text-muted-foreground">Notes are your annotations, not verified findings. Common secrets are scrubbed when you save. {dirty ? "Unsaved changes." : "Saved."}</p>
      <Button disabled={locked || !dirty || !title.trim()} onClick={() => run(async () => {
        select(caseSchema.parse(await debuggingRequest(`/cases/${active.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title, state, notes }) })));
        setNotice("Changes saved. Review the scrubbed notes.");
      })}>Save changes</Button>
      <Button className="ml-2" variant="outline" disabled={locked} onClick={() => {
        if (!window.confirm("Delete this saved investigation from this computer? The open evidence will remain visible.")) return;
        run(async () => { await debuggingRequest(`/cases/${active.id}`, { method: "DELETE" }); setSelected(null); onOpen(active.observation, null); setNotice("Investigation deleted."); });
      }}>Delete</Button>
    </div>}
    {error && <p role="alert" className="break-words text-sm text-destructive">{error}</p>}
    {notice && <p role="status" className="text-sm">{notice}</p>}
    <div className="max-h-64 space-y-2 overflow-auto">
      {listing?.cases.map(item => <Button key={item.id} variant={active?.id === item.id ? "secondary" : "ghost"} className="h-auto w-full justify-start whitespace-normal text-left" disabled={locked} onClick={() => {
        if (dirty && !window.confirm("Discard unsaved notes and open this investigation?")) return;
        run(async () => select(caseSchema.parse(await debuggingRequest(`/cases/${item.id}`))));
      }}><span><span className="block break-words">{item.title}</span><span className="text-xs text-muted-foreground">{item.state} · {new Date(item.updated_at).toLocaleDateString()}</span></span></Button>)}
      {listing && !listing.cases.length && <p className="text-sm text-muted-foreground">No saved investigations yet.</p>}
    </div>
  </section>;
}
