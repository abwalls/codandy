import type { PlanOutputs } from "./board-api";

type Plan = PlanOutputs["structured_plan"];
const taskFields = ["title", "description", "depends_on", "acceptance_criteria", "verification", "proposed_paths"] as const;
const planFields = ["title", "objective", "in_scope", "out_of_scope", "decisions", "risks", "open_questions"] as const;
// Contracts have a fixed field shape; array order is intentional and preserved.
const equal = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
export function compareBoardPlans(before: Plan, after: Plan) {
  const old = new Map(before.tasks.map(task => [task.id, task]));
  const next = new Map(after.tasks.map(task => [task.id, task]));
  if (old.size !== before.tasks.length || next.size !== after.tasks.length) throw new Error("Plans with duplicate task IDs cannot be compared reliably.");
  const added = after.tasks.filter(task => !old.has(task.id));
  const removed = before.tasks.filter(task => !next.has(task.id));
  const changed = after.tasks.flatMap(task => { const previous = old.get(task.id); if (!previous) return []; const fields = taskFields.filter(field => !equal(previous[field], task[field])); return fields.length ? [{ id: task.id, before: previous, after: task, fields }] : []; });
  const sections = planFields.filter(field => !equal(before[field], after[field]));
  const reordered = !equal(before.tasks.filter(t => next.has(t.id)).map(t => t.id), after.tasks.filter(t => old.has(t.id)).map(t => t.id));
  return { added, removed, changed, sections, reordered, unchanged: after.tasks.length - added.length - changed.length };
}
