"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ThemePicker } from "@/components/theme-picker";
import { boardRequest, boardSchema, downloadText, reviewSchema, type Board, type Review } from "@/lib/board-api";
import { api, recentReportsSchema } from "@/lib/analysis-api";
import { assistantApi, connectionSchema } from "@/lib/assistant-api";

const Canvas = dynamic(async () => {
  (window as unknown as { EXCALIDRAW_ASSET_PATH: string }).EXCALIDRAW_ASSET_PATH = "/excalidraw-assets/";
  return import("@/components/board-canvas");
}, { ssr: false, loading: () => <p className="p-10">Loading drawing tools…</p> });
type Connection = z.infer<typeof connectionSchema>;

export function WhiteboardWorkspace() {
  const [boards, setBoards] = useState<{ id: string; title: string; revision: number }[]>([]);
  const [board, setBoard] = useState<Board | null>(null);
  const [scene, setScene] = useState<Board["scene"]["elements"]>([]);
  const [title, setTitle] = useState(""); const [notes, setNotes] = useState(""); const [snapshot, setSnapshot] = useState("");
  const [reports, setReports] = useState<{ id: string; label: string }[]>([]);
  const [dirty, setDirty] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const [review, setReview] = useState<Review | null>(null); const [checked, setChecked] = useState(false);
  const [connection, setConnection] = useState<Connection | null>(null); const [model, setModel] = useState(""); const [effort, setEffort] = useState("");
  const [loginUrl, setLoginUrl] = useState(""); const [highlight, setHighlight] = useState<string[]>([]);
  const [outputs, setOutputs] = useState<{ plan: string; ticket: string; stale: boolean } | null>(null);
  const [canvasKey, setCanvasKey] = useState(0); const [savedMessage, setSavedMessage] = useState("");
  const revision = useRef(0); const serial = useRef(0); const saving = useRef(false); const sceneJSON = useRef("[]");
  const refresh = useCallback(async () => { const result = z.object({ items: z.array(z.object({ id: z.string(), title: z.string(), revision: z.number() })), unreadable: z.number(), persistent: z.boolean() }).parse(await boardRequest()); setBoards(result.items); if (!result.persistent) setSavedMessage("Memory only: enable board storage to keep boards after restart"); if (result.unreadable) setError(`${result.unreadable} saved boards could not be read; their files were preserved.`); }, []);
  useEffect(() => { Promise.resolve().then(refresh).catch(e => setError(e.message)); api("").then(raw => { setReports(recentReportsSchema.parse(raw).reports.map(r => ({ id: r.id, label: r.repository.name || r.repository.url || r.id }))); }).catch(() => {}); }, [refresh]);
  useEffect(() => { const warn = (event: BeforeUnloadEvent) => { if (dirty) { event.preventDefault(); event.returnValue = ""; } }; window.addEventListener("beforeunload", warn); return () => window.removeEventListener("beforeunload", warn); }, [dirty]);
  function changed() { serial.current++; setDirty(true); setReview(null); setChecked(false); setOutputs(null); }
  function load(value: Board) { setBoard(value); revision.current = value.revision; setScene(value.scene.elements); sceneJSON.current = JSON.stringify(value.scene.elements); setTitle(value.title); setNotes(value.notes); setSnapshot(value.snapshot_id || ""); setDirty(false); setReview(null); setChecked(false); setOutputs(null); setHighlight([]); setCanvasKey(k => k + 1); }
  async function action(fn: () => Promise<void>) { if (busy || saving.current) return; setBusy(true); setError(""); try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : "Whiteboard action failed"); } finally { setBusy(false); } }
  function canLeave() { return !dirty || window.confirm("This board has unsaved edits. Export the draft to keep them, or discard and continue?"); }
  async function save() {
    if (!board || saving.current || busy || !dirty) return;
    saving.current = true; const version = serial.current;
    try { const result = boardSchema.parse(await boardRequest(`/${board.id}`, "PUT", { title, notes, scene: { elements: scene }, snapshot_id: snapshot || null, revision: revision.current })); revision.current = result.revision; setBoard(result); setSavedMessage(`Saved revision ${result.revision}`); if (version === serial.current) setDirty(false); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : "Save failed"); }
    finally { saving.current = false; }
  }
  // Debounced autosave. Failed saves remain dirty and available as a draft download.
  const saveRef = useRef(save); useEffect(() => { saveRef.current = save; });
  useEffect(() => { if (!dirty || busy || error) return; const timer = setTimeout(() => void saveRef.current(), 1500); return () => clearTimeout(timer); }, [dirty, scene, title, notes, snapshot, busy, error, board?.revision]);
  async function prepare(stage: "interpret" | "plan") { if (!board) return; setReview(reviewSchema.parse(await boardRequest(`/${board.id}/review?stage=${stage}`))); setChecked(false); }
  async function connect() { const value = connectionSchema.parse(await assistantApi("status")); setConnection(value); const selected = value.models.find(m => m.default) || value.models[0]; setModel(selected?.id || ""); setEffort(selected?.default_effort || ""); }
  async function generate() { if (!board || !review || !checked || dirty) return; const result = boardSchema.parse(await boardRequest(`/${board.id}/generate`, "POST", { stage: review.stage, digest: review.digest, model, effort })); setBoard(result); setReview(null); setChecked(false); }
  const selectedModel = connection?.models.find(m => m.id === model);
  const latestInterpretation = board?.artifacts.findLast(a => a.stage === "interpret");
  const planArtifacts = board?.artifacts.filter(a => a.stage === "plan") || [];
  const draft = { title, notes, scene: { elements: scene }, snapshot_id: snapshot || null };
  return <main className="min-h-svh bg-background p-4 text-foreground sm:p-6">
    <header className="mb-5 flex flex-wrap items-center justify-between gap-3 print:hidden"><div className="flex items-center gap-5"><Link href="/" className="font-semibold">← Codandy</Link><h1 className="text-xl font-semibold">Whiteboard</h1><Link href="/debugging" className="text-sm text-muted-foreground">Errors & stacks</Link></div><ThemePicker /></header>
    <div className="grid gap-5 xl:grid-cols-[210px_minmax(0,1fr)_340px] print:block">
      <aside className="space-y-4 print:hidden"><Button disabled={busy} onClick={() => void action(async () => { if (!canLeave()) return; load(boardSchema.parse(await boardRequest("", "POST", {}))); await refresh(); })}>New board</Button>
        <label className="block text-sm">Import board JSON<Input type="file" accept=".json,.excalidraw" disabled={busy} onChange={e => { const file = e.target.files?.[0]; e.target.value = ""; if (!file) return; void action(async () => { if (!canLeave()) return; if (file.size > 4 * 1024 * 1024) throw new Error("Imports must be 4 MiB or smaller"); const raw = JSON.parse(await file.text()); if (raw.files && Object.keys(raw.files).length) throw new Error("Image files are unsupported; remove them before importing"); const imported = { title: raw.title || file.name.slice(0, 200), notes: raw.notes || "", scene: raw.scene || { elements: raw.elements }, snapshot_id: null }; load(boardSchema.parse(await boardRequest("", "POST", imported))); await refresh(); }); }} /></label>
        <nav className="max-h-80 space-y-1 overflow-auto">{boards.map(item => <button key={item.id} disabled={busy} className={`block w-full break-words rounded-lg p-2 text-left text-sm ${board?.id === item.id ? "bg-accent" : "hover:bg-muted"}`} onClick={() => void action(async () => { if (canLeave()) load(boardSchema.parse(await boardRequest(`/${item.id}`))); })}>{item.title}</button>)}</nav>
        <p className="text-xs text-muted-foreground">Boards stay on this computer. Label shapes and arrows so an assistant can understand your intent. Images and web embeds are unsupported.</p>
      </aside>
      <section className="min-w-0 space-y-3 print:hidden">{!board ? <div className="rounded-xl border bg-card p-10"><h2 className="text-2xl font-semibold">Sketch a change. Make a plan.</h2><p className="mt-3 text-muted-foreground">Create a board, draw labeled components, then review the interpretation before generating an implementation plan and ticket.</p></div> : <>
        <div className="flex flex-wrap items-center gap-2"><Input aria-label="Board title" maxLength={200} value={title} disabled={busy} className="min-w-40 flex-1" onChange={e => { setTitle(e.target.value); changed(); }} /><Button variant="outline" disabled={busy || !dirty} onClick={() => void save()}>Save</Button><span role="status" className="text-xs">{dirty ? "Unsaved edits" : savedMessage || `Saved revision ${board.revision}`}</span></div>
        <Canvas key={canvasKey} elements={board.scene.elements} disabled={busy} highlight={highlight} onChange={elements => { const json = JSON.stringify(elements); if (json !== sceneJSON.current) { sceneJSON.current = json; setScene(elements); changed(); } }} />
        <div className="flex flex-wrap gap-2"><Button variant="outline" onClick={() => downloadText(`${title || "board"}.json`, JSON.stringify({ schema_version: "board-0.1", ...draft }, null, 2), "application/json")}>Export draft JSON</Button><Button variant="outline" disabled={busy} onClick={() => void action(async () => { if (!window.confirm(`Delete “${board.title}” and all its saved plans? This cannot be undone.`)) return; await boardRequest(`/${board.id}?revision=${board.revision}`, "DELETE"); setBoard(null); setDirty(false); await refresh(); })}>Delete board</Button></div>
        <label className="block text-sm">Optional repository snapshot<select className="mt-1 block w-full rounded-lg border bg-card p-2" value={snapshot} disabled={busy} onChange={e => { setSnapshot(e.target.value); changed(); }}><option value="">Blank-slate design</option>{snapshot && !reports.some(r => r.id === snapshot) && <option value={snapshot}>Linked snapshot (availability checked before AI)</option>}{reports.map(r => <option value={r.id} key={r.id}>{r.label}</option>)}</select></label>
        <label className="block text-sm">Requirements, answers and corrections<Textarea className="mt-1 min-h-32" maxLength={8000} disabled={busy} value={notes} onChange={e => { setNotes(e.target.value); changed(); }} placeholder="Explain your goal, answer the assistant's questions, and correct anything it misunderstood." /></label>
      </>}</section>
      <aside className="min-w-0 space-y-4 print:hidden">
        {error && <p role="alert" className="break-words rounded-xl border border-destructive p-3 text-sm">{error}</p>}
        {board && <><section className="space-y-3 rounded-xl border bg-card p-4"><h2 className="font-semibold">Understand → clarify → plan</h2><p className="text-xs text-muted-foreground">Each step sends only the packet you review. AI results are proposals. Requests use your local Codex subscription allowance.</p><div className="flex flex-wrap gap-2"><Button disabled={busy || dirty} onClick={() => void action(() => prepare("interpret"))}>Review interpretation packet</Button><Button variant="outline" disabled={busy || dirty || !board.artifacts.some(a => a.stage === "interpret" && a.revision === board.revision)} onClick={() => void action(() => prepare("plan"))}>Review plan packet</Button></div>
          {review && <><details open><summary className="text-sm">Exact packet · revision {review.revision}</summary><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-all text-xs">{review.text}</pre></details><label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={checked} onChange={e => setChecked(e.target.checked)} />I reviewed this packet and want to send it to Codex.</label><Button variant="outline" disabled={busy} onClick={() => void action(connect)}>Check AI connection</Button>{!connection?.connected && <Button variant="outline" disabled={busy} onClick={() => void action(async () => { const raw = z.object({ url: z.string() }).parse(await assistantApi("login", {})); const url = new URL(raw.url); if (url.protocol !== "https:" || url.hostname !== "auth.openai.com") throw new Error("Unsupported sign-in URL"); setLoginUrl(url.href); })}>Connect ChatGPT</Button>}{loginUrl && <a className="block text-sm underline" href={loginUrl} target="_blank" rel="noreferrer">Continue sign-in, then check connection</a>}{connection?.connected && <><label className="block text-xs">Model<select className="mt-1 w-full rounded border bg-card p-2" value={model} onChange={e => { setModel(e.target.value); setEffort(connection.models.find(m => m.id === e.target.value)?.default_effort || ""); }}>{connection.models.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label><label className="block text-xs">Reasoning effort<select className="mt-1 w-full rounded border bg-card p-2" value={effort} onChange={e => setEffort(e.target.value)}>{selectedModel?.efforts.map(v => <option key={v}>{v}</option>)}</select></label><Button disabled={busy || !checked || dirty || !model || !effort} onClick={() => void action(generate)}>{busy ? "Working…" : `Generate ${review.stage === "plan" ? "plan" : "interpretation"}`}</Button></>}</>}
        </section>
        {latestInterpretation?.interpretation && <section className="space-y-3 rounded-xl border bg-card p-4"><h2 className="font-semibold">AI interpretation {dirty || latestInterpretation.revision !== board.revision ? "(stale)" : ""}</h2><p className="whitespace-pre-wrap text-sm">{latestInterpretation.interpretation.summary}</p>{latestInterpretation.interpretation.findings.map((f, i) => <button key={i} className="block w-full rounded border p-2 text-left text-sm" onClick={() => setHighlight(f.element_ids)}><span className="text-xs text-muted-foreground">{f.basis} · </span>{f.text}</button>)}<h3 className="text-sm font-semibold">Questions to answer</h3><ol className="list-decimal space-y-2 pl-5 text-sm">{latestInterpretation.interpretation.questions.map((q, i) => <li key={i}>{q}</li>)}</ol><p className="text-xs">Add answers and corrections below the canvas, save, and interpret again.</p><details><summary className="text-sm">Assumptions</summary>{latestInterpretation.interpretation.assumptions.map((a, i) => <p key={i} className="mt-2 text-sm">{a}</p>)}</details></section>}
        {planArtifacts.length > 0 && <section className="space-y-2 rounded-xl border bg-card p-4"><h2 className="font-semibold">Saved plans</h2>{[...planArtifacts].reverse().map(a => <Button key={a.id} className="h-auto w-full whitespace-normal" variant="outline" disabled={busy} onClick={() => void action(async () => { setOutputs(z.object({ plan: z.string(), ticket: z.string(), stale: z.boolean() }).parse(await boardRequest(`/${board.id}/outputs/${a.id}`))); })}>{a.plan?.title} · r{a.revision}{dirty || a.revision !== board.revision ? " · stale" : ""}</Button>)}</section>}</>}
      </aside>
    </div>
    {outputs && <section className="mx-auto mt-6 max-w-5xl rounded-xl border bg-card p-6 print:border-0"><div className="mb-4 flex flex-wrap gap-2 print:hidden"><Button onClick={() => downloadText("plan.md", outputs.plan)}>Download plan.md</Button><Button onClick={() => downloadText("ticket.md", outputs.ticket)}>Download ticket.md</Button><Button variant="outline" onClick={() => void action(async () => { await navigator.clipboard.writeText(outputs.ticket); setSavedMessage("Issue draft copied"); })}>Copy GitHub issue draft</Button><Button variant="outline" onClick={() => window.print()}>Print / Save PDF</Button></div>{outputs.stale && <p className="mb-4 font-semibold">Stale plan: the board has changed.</p>}<pre className="whitespace-pre-wrap break-words font-sans text-sm leading-6">{outputs.ticket}</pre></section>}
  </main>;
}
