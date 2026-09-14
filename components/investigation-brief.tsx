"use client";

import { useState } from "react";
import { z } from "zod";
import { Textarea } from "@/components/ui/textarea";
import { AssistantConnection } from "@/components/assistant-connection";
import { Button } from "@/components/ui/button";
import { debuggingRequest } from "@/lib/debugging-api";

const briefSchema = z.object({ case_id: z.string().uuid(), prompt: z.string(), review_digest: z.string(), included_frames: z.number(), omitted_frames: z.number() });

export function InvestigationBrief({ caseId }: { caseId: string }) {
  const [question, setQuestion] = useState("What does the evidence establish, what are the leading hypotheses, and what should I check next?");
  const [brief, setBrief] = useState<z.infer<typeof briefSchema> | null>(null);
  const [reviewed, setReviewed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function prepare() {
    setBusy(true); setMessage(""); setReviewed(false); setBrief(null);
    try { setBrief(briefSchema.parse(await debuggingRequest(`/cases/${caseId}/brief`))); }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : "Could not prepare the brief."); }
    finally { setBusy(false); }
  }
  function download() {
    if (!brief || !reviewed) return;
    const url = URL.createObjectURL(new Blob([brief.prompt], { type: "text/markdown;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url; link.download = `codandy-investigation-${caseId}.md`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <section className="space-y-3 rounded-xl border bg-card p-5"><h3 className="font-semibold">AI debugging brief</h3><p className="text-sm text-muted-foreground">Prepare a packet from the saved case: observed frames, candidate source references, notes and missing evidence. Save your edits first. Nothing is sent to an assistant automatically.</p><Button variant="outline" disabled={busy} onClick={prepare}>{busy ? "Preparing…" : brief ? "Refresh from saved case" : "Prepare brief"}</Button>
    {brief && <><p className="text-xs text-muted-foreground">{brief.included_frames} frames included · {brief.omitted_frames} omitted · snapshot of the saved case when prepared</p><TextareaPreview text={brief.prompt} /><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} />I reviewed this packet for sensitive information.</label><div className="flex flex-wrap gap-2"><Button disabled={!reviewed} onClick={download}>Download brief</Button><Button variant="outline" disabled={!reviewed} onClick={async () => { try { await navigator.clipboard.writeText(brief.prompt); setMessage("Brief copied."); } catch { setMessage("Clipboard unavailable. Download the brief instead."); } }}>Copy for an assistant</Button></div></>}
    {brief && reviewed && <div className="space-y-3"><label className="block text-sm">Question for Codandy<Textarea className="mt-2" maxLength={4000} value={question} onChange={e => setQuestion(e.target.value)} /></label><AssistantConnection key={brief.review_digest} question={question} scope={{ title: "Investigation" }} investigation={{ caseId, reviewDigest: brief.review_digest }} /></div>}
    {message && <p role="status" className="text-sm">{message}</p>}
  </section>;
}

function TextareaPreview({ text }: { text: string }) {
  return <pre tabIndex={0} aria-label="Review debugging brief" className="max-h-96 overflow-auto whitespace-pre-wrap break-all rounded-lg border p-3 text-xs">{text}</pre>;
}
