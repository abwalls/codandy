"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { TicketLinks } from "@/components/ticket-links";
import { downloadText } from "@/lib/board-api";
import { integrationRequest, linearTeamsSchema, ticketReceiptSchema, ticketReviewSchema, type TicketReceipt, type TicketReview, type TicketSeed } from "@/lib/tickets-api";

export function CreateTicket({ seed }: { seed: TicketSeed }) {
  const [open, setOpen] = useState(false), [title, setTitle] = useState(seed.title), [description, setDescription] = useState(seed.description);
  const [teams, setTeams] = useState<{ id: string; name: string }[]>([]), [team, setTeam] = useState("");
  const [nextCursor, setNextCursor] = useState<string | null>(null), [teamPage, setTeamPage] = useState(0), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [projects, setProjects] = useState<{ id: string; name: string }[]>([]), [project, setProject] = useState("");
  const [projectCursor, setProjectCursor] = useState<string | null>(null), [projectPage, setProjectPage] = useState(0);
  function clearProjects() { setProjects([]); setProject(""); setProjectCursor(null); setProjectPage(0); }
  const [review, setReview] = useState<TicketReview | null>(null), [receipt, setReceipt] = useState<TicketReceipt | null>(null);
  const [checked, setChecked] = useState(false), [submission, setSubmission] = useState("");
  const [priority, setPriority] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  function invalidate() { setReview(null); setChecked(false); setReceipt(null); setSubmission(""); setAcknowledged(false); }
  async function action(fn: () => Promise<void>) { if (busy) return; setBusy(true); setError(""); try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : "Ticket action failed"); } finally { setBusy(false); } }
  async function loadTeams(after: string | null) {
    await action(async () => {
      const data = linearTeamsSchema.parse(await integrationRequest(`/linear/teams${after ? `?after=${encodeURIComponent(after)}` : ""}`));
      setTeams(data.items); setNextCursor(data.next_cursor); setTeamPage(after ? teamPage + 1 : 1); setTeam(""); clearProjects(); invalidate();
    });
  }
  async function loadProjects(after: string | null) {
    await action(async () => {
      const params = new URLSearchParams({ team_id: team });
      if (after) params.set("after", after);
      const data = linearTeamsSchema.parse(await integrationRequest(`/linear/projects?${params}`));
      setProjects(data.items); setProjectCursor(data.next_cursor); setProjectPage(after ? projectPage + 1 : 1); setProject(""); invalidate();
    });
  }
  const draft = { title, description, team_id: team, project_id: project || null, priority: priority === "" ? null : Number(priority), source_kind: seed.source_kind, source_id: seed.source_id };
  if (!open) return <div className="space-y-2"><Button variant="outline" onClick={() => setOpen(true)}>Prepare Linear ticket</Button>{seed.source_id && <TicketLinks source={seed} />}</div>;
  return <section aria-label="Prepare Linear ticket" className="space-y-3 rounded-xl border bg-card p-4 text-foreground">
    <h3 className="font-semibold">Review a Linear ticket</h3><p className="text-sm text-muted-foreground">Edit the draft, choose a team, then review exactly what will be sent. Creating a ticket shares its content with that Linear team. AI proposals still need verification.</p>
    <label className="block text-sm">Ticket title<Input disabled={busy} maxLength={250} value={title} onChange={e => { setTitle(e.target.value); invalidate(); }} /></label>
    <label className="block text-sm">Ticket description<Textarea disabled={busy} maxLength={16000} className="min-h-40" value={description} onChange={e => { setDescription(e.target.value); invalidate(); }} /></label>
    <div className="flex flex-wrap items-center gap-2"><Button variant="outline" disabled={busy} onClick={() => void loadTeams(null)}>Load Linear teams</Button>
      {nextCursor && <Button variant="outline" disabled={busy} onClick={() => void loadTeams(nextCursor)}>Next team page</Button>}
      {teamPage > 0 && <span className="text-xs text-muted-foreground">Team page {teamPage} · {teams.length} teams shown</span>}</div>
    <label className="block text-sm">Target team<select className="mt-1 block w-full rounded border bg-card p-2" disabled={busy} value={team} onChange={e => { setTeam(e.target.value); clearProjects(); invalidate(); }}><option value="">Select a team</option>{teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
    {nextCursor && <p className="text-sm">More teams are available. Loading another page clears the selected target and its review. Load Linear teams returns to the first page.</p>}
    <div className="space-y-2 rounded border p-3"><p className="text-sm font-medium">Optional project</p>
      <div className="flex flex-wrap items-center gap-2"><Button variant="outline" disabled={busy || !team} onClick={() => void loadProjects(null)}>Load team projects</Button>
        {projectCursor && <Button variant="outline" disabled={busy} onClick={() => void loadProjects(projectCursor)}>Next project page</Button>}
        {projectPage > 0 && <span className="text-xs text-muted-foreground">Project page {projectPage} · {projects.length} projects shown</span>}</div>
      <label className="block text-sm">Target project<select className="mt-1 block w-full rounded border bg-card p-2" disabled={busy || !team} value={project} onChange={e => { setProject(e.target.value); invalidate(); }}><option value="">No project</option>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
      <p className="text-xs text-muted-foreground">Only accessible, unarchived projects associated with the selected team are listed. Loading another page clears the project and review. Linear checks current permissions when creating the ticket.</p>
    </div>
    <label className="block text-sm">Ticket priority<select className="mt-1 block w-full rounded border bg-card p-2" disabled={busy} value={priority} onChange={e => { setPriority(e.target.value); invalidate(); }}><option value="">Use Linear default</option><option value="0">No priority</option><option value="1">Urgent</option><option value="2">High</option><option value="3">Medium</option><option value="4">Low</option></select></label>
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
