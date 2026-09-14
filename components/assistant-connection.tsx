"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { assistantApi, connectionSchema, answerSchema, loginSchema } from "@/lib/assistant-api";
import type { AskScope } from "@/lib/ask-context";

export function AssistantConnection({ jobId, question, scope }: { jobId: string; question: string; scope: AskScope }) {
  const [connection, setConnection] = useState<ReturnType<typeof connectionSchema.parse> | null>(null);
  const [model, setModel] = useState("");
  const [effort, setEffort] = useState("");
  const [loginUrl, setLoginUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reply, setReply] = useState<{ question: string; result: ReturnType<typeof answerSchema.parse> } | null>(null);
  async function refresh() {
    setBusy(true); setError("");
    try {
      const value = connectionSchema.parse(await assistantApi("status"));
      setConnection(value);
      const selected = value.models.find(item => item.id === model) || value.models.find(item => item.default) || value.models[0];
      setModel(selected?.id || ""); setEffort(selected?.efforts.includes(effort) ? effort : selected?.default_effort || "");
      if (value.connected) setLoginUrl("");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Connection failed."); }
    finally { setBusy(false); }
  }
  async function login() {
    setBusy(true); setError("");
    try {
      const result = loginSchema.parse(await assistantApi("login", {}));
      const url = new URL(result.url);
      if (url.origin !== "https://auth.openai.com") throw new Error("Unsupported sign-in address.");
      setLoginUrl(url.href);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Sign-in failed."); }
    finally { setBusy(false); }
  }
  async function ask() {
    setBusy(true); setError(""); setReply(null);
    try {
      const result = answerSchema.parse(await assistantApi("ask", { analysis_id: jobId, question, title: scope.title.slice(0, 250), node_ids: [...new Set(scope.nodeIds || [])].slice(0, 100), model, effort }));
      setReply({ question, result });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "The assistant could not answer."); }
    finally { setBusy(false); }
  }
  const selected = connection?.models.find(item => item.id === model);
  return <section className="space-y-3 rounded-xl border border-cyan-300/20 p-4">
    <h3 className="font-medium">ChatGPT subscription connection</h3>
    <p className="text-xs leading-5 text-slate-400">Runs through Codex on this computer. Sign in with your ChatGPT account; requests consume your Codex allowance. No API-key fallback. Higher reasoning effort can take longer and use more allowance.</p>
    <div className="flex flex-wrap gap-2"><Button size="sm" variant="outline" disabled={busy} onClick={() => void refresh()}>{busy ? "Working…" : "Check connection"}</Button>{!connection?.connected && <Button size="sm" disabled={busy} onClick={() => void login()}>Connect ChatGPT</Button>}</div>
    {loginUrl && <p className="text-sm"><a href={loginUrl} target="_blank" rel="noreferrer" className="text-cyan-300 underline">Continue sign-in with OpenAI</a><span className="mt-2 block text-slate-400">After signing in, return here and click Check connection.</span></p>}
    {connection?.connected && <><p className="text-sm text-cyan-300">Connected · {connection.plan || "ChatGPT"}</p><div className="flex flex-wrap gap-3">
      <label className="text-xs">Model<select aria-label="AI model" disabled={busy} value={model} onChange={event => { const value = connection.models.find(item => item.id === event.target.value); setModel(event.target.value); setEffort(value?.default_effort || ""); }} className="mt-1 block max-w-full rounded-lg bg-card p-2">{connection.models.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label className="text-xs">Reasoning effort<select aria-label="Reasoning effort" disabled={busy} value={effort} onChange={event => setEffort(event.target.value)} className="mt-1 block rounded-lg bg-card p-2">{selected?.efforts.map(value => <option key={value}>{value}</option>)}</select></label>
    </div><Button disabled={busy || !question.trim() || !model || !effort} onClick={() => void ask()}>Ask using my plan</Button><p className="text-xs text-slate-400">Sends your question and up to 24 retained graph nodes to Codex. Source bodies, draft notes, live advisory results and comparison baselines are not sent. Each question starts a fresh conversation.</p></>}
    {error && <p role="alert" className="text-sm text-amber-200">{error}</p>}
    {reply && <div aria-live="polite" className="space-y-3 border-t border-white/10 pt-3"><p className="text-sm font-medium">{reply.question}</p><p className="whitespace-pre-wrap text-sm leading-6">{reply.result.answer}</p><details><summary className="text-xs">Cited node IDs ({reply.result.citations.length})</summary><ul className="mt-2 space-y-1 text-xs text-cyan-300">{reply.result.citations.map(id => <li key={id} className="break-all">{id}</li>)}</ul></details><p className="text-xs text-slate-400">AI explanation. Citation IDs are checked against the supplied context; factual correctness still needs review.</p></div>}
  </section>;
}
