"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { boardRequest, planOutputsSchema, type Board, type PlanOutputs } from "@/lib/board-api";
import { compareBoardPlans } from "@/lib/board-plan-comparison";

export function BoardPlanComparison({ board, current }: { board: Board; current: PlanOutputs }) {
  const alternatives = board.artifacts.filter(a => a.stage === "plan" && a.id !== current.artifact_id);
  const [selected, setSelected] = useState(""); const [baseline, setBaseline] = useState<PlanOutputs | null>(null);
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  if (!alternatives.length) return null;
  let diff: ReturnType<typeof compareBoardPlans> | null = null;
  let comparisonError = "";
  if (baseline) { try { diff = compareBoardPlans(baseline.structured_plan, current.structured_plan); } catch(e) { comparisonError = e instanceof Error ? e.message : "Comparison unavailable"; } }
  async function compare() { setBusy(true); setError(""); setBaseline(null); try { setBaseline(planOutputsSchema.parse(await boardRequest(`/${board.id}/outputs/${selected}`))); } catch(e) {setError(e instanceof Error ? e.message : "Plan version unavailable");} finally {setBusy(false);} }
  return <section className="my-5 space-y-3 rounded-xl border p-4 print:hidden" aria-label="Compare plan versions">
    <h2 className="font-semibold">Compare plan versions</h2><p className="text-xs text-muted-foreground">Matches tasks by their IDs. Renamed IDs appear as removed/added; this compares proposals, not repository changes or completed work.</p>
    <label className="block text-sm">Compare against<select aria-label="Compare against" disabled={busy} className="mt-1 w-full rounded border bg-card p-2" value={selected} onChange={e=>{setSelected(e.target.value);setBaseline(null);setError("");}}><option value="">Choose a saved plan</option>{alternatives.map(a=><option key={a.id} value={a.id}>{a.plan?.title} · board revision {a.revision} · {a.id.slice(0,8)}</option>)}</select></label><Button variant="outline" disabled={busy || !selected} onClick={()=>void compare()}>{busy ? "Comparing..." : "Compare with displayed plan"}</Button>
    {(error || comparisonError) && <p role="alert" className="text-sm text-destructive">{error || comparisonError}</p>}
    {diff && baseline && <div className="space-y-3 text-sm"><p>Revision {baseline.revision} → {current.revision}: {diff.added.length} added, {diff.removed.length} removed, {diff.changed.length} changed, {diff.unchanged} unchanged tasks.</p>{diff.reordered && <p>The order of shared task IDs changed.</p>}
      {diff.added.map(t=><p key={`add:${t.id}`} className="rounded border p-2">Added: {t.id} — {t.title}</p>)}{diff.removed.map(t=><p key={`remove:${t.id}`} className="rounded border p-2">Removed: {t.id} — {t.title}</p>)}
      {diff.changed.map(t=><details key={t.id} className="rounded border p-3"><summary className="cursor-pointer">Changed: {t.id} — {t.after.title} ({t.fields.map(f=>f.replaceAll("_"," ")).join(", ")})</summary>{t.fields.map(field=><div key={field} className="mt-3"><h3 className="font-semibold">{field.replaceAll("_"," ")}</h3><div className="mt-1 grid gap-2 sm:grid-cols-2"><div><p className="text-xs text-muted-foreground">Earlier plan</p><pre className="whitespace-pre-wrap break-words text-xs">{JSON.stringify(t.before[field],null,2)}</pre></div><div><p className="text-xs text-muted-foreground">Displayed plan</p><pre className="whitespace-pre-wrap break-words text-xs">{JSON.stringify(t.after[field],null,2)}</pre></div></div></div>)}</details>)}
      {diff.sections.map(field=><details key={field} className="rounded border p-3"><summary className="cursor-pointer">Changed plan section: {field.replaceAll("_"," ")}</summary><p className="mt-2 text-xs text-muted-foreground">Earlier plan</p><pre className="whitespace-pre-wrap break-words text-xs">{JSON.stringify(baseline.structured_plan[field],null,2)}</pre><p className="mt-2 text-xs text-muted-foreground">Displayed plan</p><pre className="whitespace-pre-wrap break-words text-xs">{JSON.stringify(current.structured_plan[field],null,2)}</pre></details>)}
      {!diff.added.length && !diff.removed.length && !diff.changed.length && !diff.sections.length && !diff.reordered && <p>No structured plan changes.</p>}
    </div>}
  </section>;
}
