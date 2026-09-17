"use client";
import { useState } from "react";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { integrationRequest, ticketReceiptSchema, type TicketSeed } from "@/lib/tickets-api";

const schema = z.object({ items: z.array(z.object({ state: z.enum(["created", "uncertain"]), receipt: ticketReceiptSchema.nullable(), created_at: z.string() })) });
export function TicketLinks({ source }: { source: Pick<TicketSeed, "source_kind" | "source_id"> }) {
  const [history, setHistory] = useState<z.infer<typeof schema> | null>(null), [busy, setBusy] = useState(false), [error, setError] = useState("");
  return <div className="space-y-2 text-sm"><Button variant="ghost" size="sm" disabled={busy} onClick={async () => {
    setBusy(true); setError("");
    try { setHistory(schema.parse(await integrationRequest("/tickets/links", { source_kind: source.source_kind, source_id: source.source_id }))); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not read ticket links"); }
    finally { setBusy(false); }
  }}>{busy ? "Reading links…" : "Show linked tickets"}</Button>
    {history && <div className="space-y-2 rounded border p-3"><p className="text-xs text-muted-foreground">Saved locally for this source. This does not refresh the provider issue status.</p>{!history.items.length && <p>No linked submissions yet.</p>}{history.items.map((item, index) => <p className="break-words" key={index}>{item.receipt ? <a className="underline" href={item.receipt.url} target="_blank" rel="noreferrer">{item.receipt.external_key}</a> : "Uncertain submission — check Linear before creating another ticket"}<span className="ml-2 text-xs text-muted-foreground">{item.created_at}</span></p>)}{history.items.length === 50 && <p className="text-xs">Showing the most recent 50 submissions for this source.</p>}</div>}
    {error && <p role="alert" className="text-destructive">{error}</p>}
  </div>;
}
