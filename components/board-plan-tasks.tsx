"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { CreateTicket } from "@/components/create-ticket";
import { downloadText, type PlanOutputs } from "@/lib/board-api";

export function BoardPlanTasks({ boardId, outputs, stale }: { boardId: string; outputs: PlanOutputs; stale: boolean }) {
  const [message, setMessage] = useState("");
  const handoff = `# Coding assistant handoff\n\nThis is an AI-proposed design, not verified source architecture. Inspect the target repository before editing. Ask about open questions, preserve task dependencies, and verify acceptance criteria. Do not create external tickets or deploy without explicit authorization.\n\n${outputs.plan}`;
  return <section className="my-5 space-y-4" aria-label="Implementation tasks">
    <h2 className="text-xl font-semibold">Implementation tasks</h2>
    <p className="text-sm text-muted-foreground">Review these proposals before assigning work. Dependencies below refer to this plan; they are not automatically created as Linear links.</p>
    <div className="flex flex-wrap gap-2 print:hidden"><Button variant="outline" onClick={() => downloadText("assistant-handoff.md", handoff)}>Download assistant handoff</Button><Button variant="outline" onClick={async () => { try { await navigator.clipboard.writeText(handoff); setMessage("Assistant handoff copied"); } catch { setMessage("Copy failed. Download the handoff instead."); } }}>Copy assistant handoff</Button><span role="status" className="text-sm">{message}</span></div>
    {stale && <p role="status">This plan is stale. Generate a current plan before preparing new tickets.</p>}
    {outputs.structured_plan.tasks.map(task => {
      const description = [`AI-proposed task from board ${boardId}, revision ${outputs.revision}.`, `Plan: ${outputs.structured_plan.title}`, `Task: ${task.id}`, "", task.description, "", `Depends on: ${task.depends_on.join(", ") || "none"}`, "", "Acceptance criteria:", ...task.acceptance_criteria.map(v => `- [ ] ${v}`), "", "Verification:", ...task.verification.map(v => `- ${v}`), "", "Proposed paths (existence unverified):", ...task.proposed_paths.map(v => `- ${v}`)].join("\n");
      return <article key={task.id} className="space-y-3 rounded-xl border p-4">
        <h3 className="font-semibold">{task.id}: {task.title}</h3><p className="whitespace-pre-wrap text-sm">{task.description}</p><p className="text-xs text-muted-foreground">Depends on: {task.depends_on.join(", ") || "none"}</p>
        <h4 className="text-sm font-semibold">Acceptance criteria</h4><ul className="list-disc space-y-1 pl-5 text-sm">{task.acceptance_criteria.map((v,i) => <li key={i}>{v}</li>)}</ul>
        <h4 className="text-sm font-semibold">Verification</h4><ul className="list-disc space-y-1 pl-5 text-sm">{task.verification.map((v,i) => <li key={i}>{v}</li>)}</ul>
        {task.proposed_paths.length > 0 && <details><summary className="text-sm">Proposed paths (existence unverified)</summary>{task.proposed_paths.map((v,i) => <p key={i} className="break-all text-xs">{v}</p>)}</details>}
        {!stale && <div className="print:hidden"><CreateTicket key={`${outputs.artifact_id}:${task.id}`} seed={{ title: task.title, description, source_kind: "board", source_id: JSON.stringify([boardId, outputs.artifact_id, task.id]) }} /></div>}
      </article>;
    })}
  </section>;
}
