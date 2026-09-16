"use client";
import { useState } from "react";
import Link from "next/link";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { ThemePicker } from "@/components/theme-picker";
import { CreateTicket } from "@/components/create-ticket";
import { integrationRequest, ticketReceiptSchema } from "@/lib/tickets-api";

const statusSchema = z.object({ configured: z.boolean(), persistent: z.boolean(), settings_hint: z.string() });
const historySchema = z.object({ items: z.array(z.object({ state: z.enum(["created", "uncertain"]), receipt: ticketReceiptSchema.nullable(), created_at: z.string() })) });
export function IntegrationsWorkspace() {
  const [status, setStatus] = useState<z.infer<typeof statusSchema> | null>(null), [verified, setVerified] = useState(false);
  const [history, setHistory] = useState<z.infer<typeof historySchema> | null>(null), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  async function action(fn: () => Promise<void>) { if (busy) return; setBusy(true); setError(""); try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : "Connection check failed"); } finally { setBusy(false); } }
  return <main className="min-h-svh bg-background p-4 text-foreground sm:p-6"><div className="mx-auto max-w-4xl space-y-6">
    <header className="flex flex-wrap items-center justify-between gap-4"><Link href="/">← Codandy</Link><Link href="/whiteboard">Whiteboard</Link><ThemePicker /></header>
    <h1 className="text-3xl font-semibold">Integrations</h1><p className="text-muted-foreground">Connect your local workspace to Linear and turn reviewed plans into tickets. Keys stay on the Python backend.</p>
    <section className="space-y-4 rounded-xl border bg-card p-5"><h2 className="text-xl font-semibold">Linear</h2><p className="text-sm">Add <code>CODANDY_LINEAR_API_KEY</code> to <code>backend/.env</code>, then restart the backend. Choose a personal key limited to the intended teams with permission to create issues. Your ChatGPT subscription does not grant access to Linear.</p>
      <a className="text-sm underline" href="https://linear.app/developers/graphql" target="_blank" rel="noreferrer">Linear connection documentation</a>
      <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy} onClick={() => void action(async () => { setVerified(false); setStatus(statusSchema.parse(await integrationRequest())); })}>Check local configuration</Button><Button disabled={busy || !status?.configured} onClick={() => void action(async () => { setVerified(false); const result = z.object({ verified: z.literal(true) }).parse(await integrationRequest("/linear/test", {})); setVerified(result.verified); })}>Test Linear connection</Button></div>
      {status && <p role="status" className="text-sm">{status.configured ? "API key configured" : "API key not configured"} · {verified ? "Connection verified just now" : "Connection not verified"} · {status.persistent ? "Ticket ledger enabled" : "Ticket creation disabled: ledger storage required"}</p>}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    </section>
    <CreateTicket seed={{ title: "", description: "", source_kind: "manual", source_id: "" }} />
    <section className="space-y-3 rounded-xl border bg-card p-5"><h2 className="font-semibold">Recent ticket submissions</h2><p className="text-sm text-muted-foreground">Local receipts and uncertain submissions. Ticket bodies are not saved in this ledger. An uncertain result needs checking in Linear; Codandy will not resend it automatically.</p><Button variant="outline" disabled={busy} onClick={() => void action(async () => { setHistory(historySchema.parse(await integrationRequest("/tickets"))); })}>Refresh receipts</Button>{history && !history.items.length && <p>No submissions yet.</p>}{history?.items.map((item, i) => <p key={i} className="break-words text-sm">{item.created_at} · {item.receipt ? <a href={item.receipt.url} target="_blank" rel="noreferrer" className="underline">{item.receipt.external_key}</a> : "Uncertain — check Linear before creating another ticket"}</p>)}</section>
    <p className="text-sm text-muted-foreground">Sentry event retrieval and OTLP file imports are available in <Link href="/debugging" className="underline">Errors & stacks</Link>. Jira, ClickUp and Datadog connections are still planned.</p>
  </div></main>;
}
