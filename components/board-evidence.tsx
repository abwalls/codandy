"use client";
import { useState } from "react";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { boardRequest, type Board } from "@/lib/board-api";

export function BoardEvidence({ board, disabled, mutate }: { board: Board; disabled: boolean; mutate: (path: string, method: string, value?: unknown) => void }) {
  const [kind, setKind] = useState<"source" | "case">("case");
  const [query, setQuery] = useState(""); const [items, setItems] = useState<{id: string; title: string}[]>([]);
  const [selected, setSelected] = useState(""); const [total, setTotal] = useState<number | null>(null); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  async function search() { setBusy(true); setError(""); setSelected(""); try { const params = new URLSearchParams({kind, query}); if (board.snapshot_id) params.set("snapshot_id", board.snapshot_id); const result=z.object({items:z.array(z.object({id:z.string(),title:z.string()})),total:z.number()}).parse(await boardRequest(`/${board.id}/evidence-options?${params}`)); setItems(result.items); setTotal(result.total); } catch(e) { setError(e instanceof Error ? e.message : "Evidence search failed"); } finally {setBusy(false);} }
  return <section className="space-y-3 rounded-xl border bg-card p-4" aria-label="Captured evidence">
    <h2 className="font-semibold">Evidence for this plan</h2><p className="text-xs text-muted-foreground">Pin a scrubbed summary from a saved investigation or source snapshot. Copies stay with this board and its saved plans even if the original is deleted. Removing a card affects future requests; delete the board to remove its saved copies. No source bodies are included.</p>
    {board.evidence_cards.map(card => <article key={card.id} id={`evidence-${card.id}`} className="space-y-2 rounded-lg border p-3"><h3 className="text-sm font-semibold">{card.title}</h3><p className="text-xs text-muted-foreground">{card.basis}</p><p className="text-xs">Captured {new Date(card.captured_at).toLocaleString()} · {card.kind}</p><details><summary className="cursor-pointer text-sm">Read captured summary</summary><pre className="mt-2 whitespace-pre-wrap break-words text-xs">{card.text}</pre><p className="mt-2 break-all text-xs">Source: {card.source_id} · revision: {card.source_revision} · snapshot: {card.snapshot_id || "none"}</p><p className="break-all text-xs">Evidence ID: {card.id}</p></details><Button size="sm" variant="ghost" disabled={disabled || busy} onClick={() => mutate(`/${board.id}/evidence/${card.id}?revision=${board.revision}`, "DELETE")}>Remove evidence card</Button></article>)}
    <details><summary className="cursor-pointer text-sm">Pin evidence ({board.evidence_cards.length}/10)</summary><div className="mt-3 space-y-3">
      <label className="block text-sm">Evidence type<select className="mt-1 w-full rounded border bg-card p-2" value={kind} disabled={busy || disabled} onChange={e=>{setKind(e.target.value as "source" | "case");setItems([]);setSelected("");setTotal(null);}}><option value="case">Saved investigation</option><option value="source">Linked repository source</option></select></label>
      {kind === "source" && !board.snapshot_id && <p className="text-xs">Choose and save a repository snapshot above before searching source items.</p>}
      <label className="block text-sm">Find evidence<Input maxLength={200} value={query} disabled={busy || disabled} onChange={e=>setQuery(e.target.value)} placeholder="Filter by title, symbol or path" /></label>
      <Button variant="outline" disabled={busy || disabled || (kind === "source" && !board.snapshot_id)} onClick={()=>void search()}>Search saved evidence</Button>
      {total !== null && <p className="text-xs">Showing {items.length} of {total}. Refine your search when results exceed 50.</p>}
      {!!items.length && <><label className="block text-sm">Evidence item<select aria-label="Evidence item" className="mt-1 w-full rounded border bg-card p-2" disabled={busy || disabled} value={selected} onChange={e=>setSelected(e.target.value)}><option value="">Choose an item</option>{items.map(item=><option key={item.id} value={item.id}>{item.title}</option>)}</select></label><Button disabled={busy || disabled || !selected || board.evidence_cards.length>=10} onClick={()=>mutate(`/${board.id}/evidence`,"POST",{revision:board.revision,kind,source_id:selected,snapshot_id:kind === "source" ? board.snapshot_id : null})}>Pin selected evidence</Button></>}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    </div></details>
  </section>;
}
