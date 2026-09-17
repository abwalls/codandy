"use client";
import { useState } from "react";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { debuggingRequest, sentryProjectsSchema as projectsSchema, sentryIssuesSchema as issuesSchema } from "@/lib/debugging-api";

export function SentryBrowser({ disabled, onSelect }: { disabled: boolean; onSelect: (id: string) => void }) {
  const [projects, setProjects] = useState<z.infer<typeof projectsSchema> | null>(null), [issues, setIssues] = useState<z.infer<typeof issuesSchema> | null>(null);
  const [project, setProject] = useState(""), [search, setSearch] = useState("is:unresolved"), [projectSearch, setProjectSearch] = useState("");
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  async function action(fn: () => Promise<void>) { if (busy || disabled) return; setBusy(true); setError(""); try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : "Sentry browse failed"); } finally { setBusy(false); } }
  function loadProjects(cursor = "") { void action(async () => { setProject(""); setIssues(null); setProjects(null); setProjects(projectsSchema.parse(await debuggingRequest(`/sentry/projects?${new URLSearchParams({ query: projectSearch, cursor })}`))); }); }
  function loadIssues(cursor = "") { void action(async () => { setIssues(null); setIssues(issuesSchema.parse(await debuggingRequest(`/sentry/issues?${new URLSearchParams({ project, query: search, cursor })}`))); }); }
  return <details className="space-y-3 rounded-lg border p-3"><summary className="cursor-pointer font-medium">Browse projects and issues</summary>
    <p className="text-xs text-muted-foreground">Each click reads one page from Sentry. Project browsing needs org:read; issue/event reads need event:read. No background polling.</p>
    <label className="block text-sm">Find Sentry projects<Input maxLength={300} disabled={busy || disabled} value={projectSearch} onChange={e => { setProjectSearch(e.target.value); setProjects(null); setProject(""); setIssues(null); }} /></label>
    <Button variant="outline" disabled={busy || disabled} onClick={() => loadProjects()}>Load projects</Button>
    {projects && <><label className="block text-sm">Sentry project<select aria-label="Sentry project" className="mt-1 block w-full rounded border bg-card p-2" value={project} disabled={busy || disabled} onChange={e => { setProject(e.target.value); setIssues(null); }}><option value="">Select a project</option>{projects.items.map(item => <option key={item.id} value={item.id}>{item.name || item.slug || item.id}</option>)}</select></label>{!projects.items.length && <p className="text-sm">No projects on this page.</p>}{projects.next_cursor && <Button variant="outline" disabled={busy || disabled} onClick={() => loadProjects(projects.next_cursor!)}>Next projects page</Button>}{projects.notes.map(note => <p className="text-xs text-muted-foreground" key={note}>{note}</p>)}</>}
    {project && <><label className="block text-sm">Sentry issue query<Input maxLength={300} disabled={busy || disabled} value={search} onChange={e => { setSearch(e.target.value); setIssues(null); }} /></label><Button variant="outline" disabled={busy || disabled} onClick={() => loadIssues()}>Search issues</Button></>}
    {issues && <><div className="max-h-80 space-y-2 overflow-auto">{issues.items.map(item => <button key={item.id} className="block w-full break-words rounded border p-3 text-left text-sm hover:bg-muted" disabled={busy || disabled} onClick={() => onSelect(item.id)}><span className="block font-medium">{item.title || `Issue ${item.id}`}</span><span className="block text-xs text-muted-foreground">{item.status} Â· {item.culprit}</span><span className="text-xs underline">Select issue {item.id}</span></button>)}{!issues.items.length && <p className="text-sm">No issues match on this page.</p>}</div>{issues.next_cursor && <Button variant="outline" disabled={busy || disabled} onClick={() => loadIssues(issues.next_cursor!)}>Next issues page</Button>}{issues.notes.map(note => <p className="text-xs text-muted-foreground" key={note}>{note}</p>)}<p className="text-xs">Selecting an issue fills its ID below. Use Fetch event to inspect its stack.</p></>}
    {busy && <p role="status" className="text-sm">Reading Sentryâ€¦</p>}{error && <p role="alert" className="break-words text-sm text-destructive">{error}</p>}
  </details>;
}
