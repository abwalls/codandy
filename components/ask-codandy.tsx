"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { suggestedQuestions, questionPrompt, type AskScope } from "@/lib/ask-context";
import { AssistantConnection } from "@/components/assistant-connection";

const AskContext = createContext<((scope: AskScope) => void) | null>(null);
export function useAskCodandy() { return useContext(AskContext); }
export function AskButton({ scope, children = "Ask Codandy" }: { scope: AskScope; children?: ReactNode }) {
  const open = useContext(AskContext);
  if (!open) return null;
  return <Button variant="outline" size="sm" onClick={() => open(scope)}>{children}</Button>;
}

function QuestionDraft({ scope, context, jobId }: { scope: AskScope; context: unknown; jobId?: string | null }) {
  const [question, setQuestion] = useState(scope.question || "");
  const [status, setStatus] = useState("");
  const prompt = questionPrompt(question, context);
  async function copy() {
    try { await navigator.clipboard.writeText(prompt); setStatus("Question and evidence copied. Paste them into your AI assistant."); }
    catch { setStatus("Clipboard access unavailable. Select the prepared prompt below or download it."); }
  }
  function download() {
    const url = URL.createObjectURL(new Blob([prompt], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url; link.download = "codandy-question.txt"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <div className="space-y-4 px-4 pb-6">
    <p className="rounded-lg border border-cyan-300/20 p-3 text-sm text-slate-400">{jobId ? "Ask through your local ChatGPT/Codex connection, or copy a question with evidence to another assistant." : "This sample or offline snapshot supports question copy/export. Open a retained backend analysis to use the local AI connection."} Nothing is sent until you choose an action.</p>
    <p className="break-words text-sm text-cyan-300">Context: {scope.title}</p>
    <div className="flex flex-wrap gap-2">{suggestedQuestions(scope.title).map(text => <button key={text} className="rounded-lg border border-white/10 p-2 text-left text-xs text-slate-300 hover:border-cyan-300/40" onClick={() => { setQuestion(text); setStatus(""); }}>{text}</button>)}</div>
    <label className="block text-sm">Your question<textarea autoFocus aria-label="Your Codandy question" maxLength={4000} rows={4} className="mt-2 block w-full rounded-lg border border-white/15 bg-card p-3" value={question} onChange={event => { setQuestion(event.target.value); setStatus(""); }} /></label>
    {jobId && <AssistantConnection jobId={jobId} question={question} scope={scope} />}
    <div className="flex flex-wrap gap-2"><Button disabled={!question.trim()} onClick={() => void copy()}>Copy question + evidence</Button><Button disabled={!question.trim()} variant="outline" onClick={download}>Download question</Button></div>
    <p role="status" className="text-sm text-cyan-300">{status}</p>
    <details><summary className="cursor-pointer text-sm">Review included evidence</summary><textarea aria-label="Prepared question and evidence" readOnly rows={16} value={prompt} className="mt-3 w-full rounded-lg border border-white/10 bg-card p-3 font-mono text-xs" /></details>
    <p className="text-xs text-slate-400">Only the displayed excerpt is included. Review it before sharing. Answers from another assistant are not verified Codandy findings.</p>
  </div>;
}

export function AskCodandyProvider({ children, contextFor, jobId }: { children: ReactNode; contextFor: (scope: AskScope) => unknown; jobId?: string | null }) {
  const [request, setRequest] = useState<{ scope: AskScope; context: unknown } | null>(null);
  return <AskContext.Provider value={scope => setRequest({ scope, context: contextFor(scope) })}>{children}
    <Sheet open={!!request} onOpenChange={open => { if (!open) setRequest(null); }}><SheetContent className="w-[min(600px,95vw)] overflow-y-auto bg-background text-foreground sm:max-w-[600px]">
      <SheetHeader><SheetTitle>Ask Codandy</SheetTitle><SheetDescription>Draft a question scoped to this page or selected evidence.</SheetDescription></SheetHeader>
      {request && <QuestionDraft scope={request.scope} context={request.context} jobId={jobId} />}
    </SheetContent></Sheet>
  </AskContext.Provider>;
}
