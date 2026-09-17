"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export function BoardQuestions({ questions, disabled, onApply }: { questions: string[]; disabled: boolean; onApply: (text: string) => void }) {
  const [answers, setAnswers] = useState<Record<number, string>>({});
  if (!questions.length) return <p className="text-sm text-muted-foreground">No clarifying questions were returned. Review the interpretation and correct anything it misunderstood.</p>;
  const text = questions.flatMap((q, i) => answers[i]?.trim() ? [`Question: ${q}\nUser answer: ${answers[i].trim()}`] : []).join("\n\n");
  return <div className="space-y-3">{questions.map((question, i) => <label key={i} className="block text-sm">{question}<Textarea disabled={disabled} maxLength={2000} value={answers[i] || ""} onChange={e => setAnswers({ ...answers, [i]: e.target.value })} placeholder="Clarify what you intended to draw..." className="mt-1" /></label>)}<Button variant="outline" disabled={disabled || !text} onClick={() => onApply(text)}>Apply answers to requirements</Button><p className="text-xs text-muted-foreground">Answers become your saved requirements. Review and interpret the updated drawing again before planning.</p></div>;
}
