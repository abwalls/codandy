"use client";
import { useState } from "react";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { TicketLinks } from "@/components/ticket-links";
import { downloadText } from "@/lib/board-api";
import { integrationRequest, ticketReceiptSchema, ticketReviewSchema, type TicketReceipt, type TicketReview, type TicketSeed } from "@/lib/tickets-api";

export function CreateTicket({ seed }: { seed: TicketSeed }) {
  const [open, setOpen] = useState(false), [title, setTitle] = useState(seed.title), [description, setDescription] = useState(seed.description);
  const [teams, setTeams] = useState<{ id: string; name: string }[]>([]), [team, setTeam] = useState("");
  const [more, setMore] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [review, setReview] = useState<TicketReview | null>(null), [receipt, setReceipt] = useState<TicketReceipt | null>(null);
  const [checked, setChecked] = useState(false), [submission, setSubmission] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  function invalidate() { setReview(null); setChecked(false); setReceipt(null); setSubmission(""); setAcknowledged(false); }
  async function action(fn: () => Promise<void>) { if (busy) return; setBusy(true); setError(""); try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : "Ticket action failed"); } finally { setBusy(false); } }
  const draft = { title, description, team_id: team, source_kind: seed.source_kind, source_id: seed.source_id };
  if (!open) return <div className="space-y-2"><Button variant="outline" onClick={() => setOpen(true)}>Prepare Linear ticket</Button>{seed.source_id && <TicketLinks source={seed} />}</div>;
  return <section aria-label="Prepare Linear ticket" className="space-y-3 rounded-xl border bg-card p-4 text-foreground">
    <h3 className="font-semibold">Review a Linear ticket</h3><p className="text-sm text-muted-foreground">Edit the draft, choose a team, then review exactly what will be sent. Creating a ticket shares its content with that Linear team. AI proposals still need verification.</p>
    <label className="block text-sm">Ticket title<Input disabled={busy} maxLength={250} value={title} onChange={e => { setTitle(e.target.value); invalidate(); }} /></label>
    <label className="block text-sm">Ticket description<Textarea disabled={busy} maxLength={16000} className="min-h-40" value={description} onChange={e => { setDescription(e.target.value); invalidate(); }} /></label>
    <Button variant="outline" disabled={busy} onClick={() => void action(async () => { const data = z.object({ items: z.array(z.object({ id: z.string().uuid(), name: z.string() })), has_more: z.boolean() }).parse(await integrationRequest("/linear/teams")); setTeams(data.items); setMore(data.has_more); setTeam(""); invalidate(); })}>Load Linear teams</Button>
    <label className="block text-sm">Target team<select className="mt-1 block w-full rounded border bg-card p-2" disabled={busy} value={team} onChange={e => { setTeam(e.target.value); invalidate(); }}><option value="">Select a team</option>{teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
    {more && <p className="text-sm">Only the first 50 accessible teams are shown. Restrict the API key to your intended teams if the target is missing.</p>}
    <p className="text-xs text-muted-foreground">{title.length}/250 title characters · {description.length}/16,000 description characters. Shorten oversized drafts before review.</p>
    <Button disabled={busy || !team || !title.trim() || title.length > 250 || description.length > 16000} onClick={() => void action(async () => { setReview(ticketReviewSchema.parse(await integrationRequest("/tickets/review", draft))); setSubmission(crypto.randomUUID()); setChecked(false); setReceipt(null); setAcknowledged(false); })}>Review exact payload</Button>
    {review && <><p className="text-xs text-muted-foreground">Best-effort secret scrubbing applied. Check the entire text and team ID before sharing.</p><pre className="max-h-80 overflow-auto whitespace-pre-wrap break-all rounded border p-3 text-xs">{JSON.stringify(review.payload, null, 2)}</pre>
      <Button variant="outline" onClick={() => downloadText("linear-ticket.json", JSON.stringify(review.payload, null, 2), "application/json")}>Download reviewed payload</Button>
      <label className="flex items-start gap-2 text-sm"><input type="checkbox" disabled={busy || !!receipt} checked={checked} onChange={e => setChecked(e.target.checked)} />I reviewed this exact content and target and want to create the ticket in Linear.</label>
      {review.previous_submissions > 0 && <div className="space-y-2 rounded border p-3"><p className="text-sm">This source already has {review.previous_submissions} ticket submission(s). Check existing tickets before creating another.</p><TicketLinks source={seed} /><label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={acknowledged} disabled={busy} onChange={e => setAcknowledged(e.target.checked)} />I checked the existing submissions and intend to create an additional ticket.</label></div>}
      <Button disabled={busy || !checked || !!receipt || (review.previous_submissions > 0 && !acknowledged)} onClick={() => void action(async () => { setReceipt(ticketReceiptSchema.parse(await integrationRequest("/tickets", { ...draft, digest: review.digest, idempotency_key: submission, confirmed: true, acknowledge_existing: acknowledged }))); })}>{busy ? "Working…" : "Create ticket in Linear"}</Button></>}
    {receipt && <p role="status">Created <a className="underline" href={receipt.url} target="_blank" rel="noreferrer">{receipt.external_key}</a>. Its receipt is saved under Integrations.</p>}
    {error && <p role="alert" className="break-words text-sm text-destructive">{error}</p>}
    <p className="text-xs text-muted-foreground">If a submission times out, check Linear before starting another draft. Retrying the same reviewed content will not send it twice.</p>
    <Button variant="ghost" disabled={busy} onClick={() => setOpen(false)}>Close ticket editor</Button>
  </section>;
}
