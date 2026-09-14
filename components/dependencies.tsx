"use client";

import { useMemo, useState } from "react";
import { api, dependencyCheckSchema, type AnalysisAtlas } from "@/lib/analysis-api";
import { dependencyUsage } from "@/lib/dependency-usage";
import { dependencyReport, matchesDependencyReview, type DependencyReview } from "@/lib/dependency-report";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AskButton } from "@/components/ask-atlas";

type Node = AnalysisAtlas["nodes"][number];
type Check = ReturnType<typeof dependencyCheckSchema.parse>;


const statusText: Record<Check["vulnerability_status"], string> = {
  unknown_version: "Exact version unavailable: vulnerability check not performed.",
  unavailable: "Advisory provider unavailable. Vulnerability status is unknown.",
  reported: "OSV reports advisories affecting the checked version. Runtime exposure is not verified.",
  no_matches: "No OSV matches returned for this version. This is not a clean security audit.",
  incomplete: "Provider results are incomplete. Vulnerability status remains uncertain.",
};

export function Dependencies({ atlas, jobId, onInspect }: { atlas: AnalysisAtlas; jobId: string | null; onInspect: (id: string) => void }) {
  const [search, setSearch] = useState("");
  const [ecosystem, setEcosystem] = useState("all");
  const [review, setReview] = useState<DependencyReview>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [limit, setLimit] = useState(50);
  const [checks, setChecks] = useState<Record<string, Check>>({});
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string | null>>({});
  const dependencies = useMemo(() => atlas.nodes.filter(node => node.kind === "dependency"), [atlas]);
  const filtered = dependencies.filter(node => (ecosystem === "all" || node.attributes.ecosystem === ecosystem) && matchesDependencyReview(checks[node.id], review) && `${node.label} ${node.path}`.toLowerCase().includes(search.toLowerCase()));
  const selected = dependencies.find(node => node.id === selectedId);
  const usage = useMemo(() => selected ? dependencyUsage(atlas, selected) : [], [atlas, selected]);
  const check = selected ? checks[selected.id] : null;
  const error = selected ? errors[selected.id] : null;
  const centralFile = selected?.attributes.central_version_file ? atlas.nodes.find(node => node.kind === "file" && node.path === selected.attributes.central_version_file) : null;
  function downloadReview() {
    const report = dependencyReport(atlas, checks, new Date().toISOString());
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url; link.download = "dependency-review.json"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function checkPublic(node: Node) {
    if (!jobId) return;
    setBusy(true); setErrors(current => ({ ...current, [node.id]: null }));
    try {
      const result = dependencyCheckSchema.parse(await api(`/${jobId}/dependencies?node_id=${encodeURIComponent(node.id)}`, { method: "POST", signal: AbortSignal.timeout(45000) }));
      if (result.node_id !== node.id) throw new Error("The provider returned a mismatched dependency result.");
      setChecks(current => ({ ...current, [node.id]: result }));
    } catch (cause) { setErrors(current => ({ ...current, [node.id]: cause instanceof Error ? cause.message : "Public dependency check failed." })); }
    finally { setBusy(false); }
  }
  return <div className="space-y-5">
    <p className="rounded-xl border border-cyan-300/15 p-4 text-sm leading-6 text-slate-400">Manifest declarations and supported lockfile evidence, not installed or running versions. Public checks send only the selected package name, ecosystem and identified version to its public registry and OSV. No packages are installed or executed. Update compatibility and vulnerability exposure require review.</p>
    <div className="flex flex-wrap gap-3"><Input aria-label="Search dependencies" placeholder="Search packages or manifests" value={search} onChange={event => { setSearch(event.target.value); setLimit(50); }} /><select aria-label="Package ecosystem" className="rounded-lg bg-card p-2" value={ecosystem} onChange={event => { setEcosystem(event.target.value); setLimit(50); }}><option value="all">All ecosystems</option>{["npm", "NuGet", "PyPI", "Go"].map(value => <option key={value}>{value}</option>)}</select></div>
    <p className="text-sm text-slate-400">{filtered.length} matching declarations in {new Set(dependencies.map(node => node.path)).size} manifests</p>
    <div className="flex flex-wrap items-center gap-3">
      <select aria-label="Dependency review status" className="rounded-lg bg-card p-2" value={review} onChange={event => { setReview(event.target.value as DependencyReview); setLimit(50); }}>
        <option value="all">All review states</option><option value="unchecked">Not checked</option><option value="updates">Updates available</option><option value="advisories">Advisories reported</option><option value="uncertain">Uncertain or incomplete checks</option>
      </select>
      <Button variant="outline" onClick={downloadReview}>Download dependency review</Button>
      <p className="text-xs text-slate-500">Exports all declarations and checks made in this report session, regardless of filters. Checks are not saved when you leave the report.</p>
    </div>
    <div className="grid items-start gap-5 xl:grid-cols-2"><div className="space-y-2">{filtered.slice(0, limit).map(node => <button key={node.id} aria-pressed={selected?.id === node.id} className={`block w-full min-w-0 rounded-xl border p-4 text-left ${selected?.id === node.id ? "border-cyan-300/40 bg-cyan-300/10" : "border-white/10 bg-card"}`} onClick={() => setSelectedId(node.id)}><span className="text-xs text-cyan-300">{node.attributes.ecosystem || "Reanalysis needed"} · {node.attributes.group || "dependency"}</span><strong className="mt-1 block break-all">{node.label}</strong><span className="mt-1 block text-sm text-slate-400">Declared: {node.attributes.declared_version || "unknown / unsupported"}</span><span className="block break-all text-xs text-slate-500">{node.path}</span><span className="mt-2 block text-xs text-cyan-200">{!checks[node.id] ? "Not checked" : checks[node.id].advisories.length ? `${checks[node.id].advisories.length} advisories reported` : checks[node.id].update_status === "newer_available" ? "Update available" : "Check recorded — inspect details"}</span></button>)}{!filtered.length && <p className="text-slate-400">No dependency declarations match. Supported manifests: package.json, .NET project files, Python project/requirements files and go.mod.</p>}{filtered.length > limit && <Button onClick={() => setLimit(limit + 50)}>Show more packages</Button>}</div>
      <aside className="order-first min-w-0 rounded-xl border border-white/10 bg-card p-5 xl:order-last">{selected ? <>
        <h3 className="break-all text-xl font-semibold">{selected.label}</h3>
        <div className="mt-3"><AskButton scope={{ title: `Dependency: ${selected.label}`, nodeIds: [selected.id, ...usage.slice(0, 15).map(node => node.id)], notes: JSON.stringify({ version_evidence: selected.attributes, public_check: check || "Not checked in this report session" }) }}>Ask about this dependency</AskButton></div>
        <p className="mt-3 text-sm text-slate-400">Identified version: {selected.attributes.checked_version || "unknown"} ({selected.attributes.version_basis || "unknown"})</p>
        {selected.attributes.version_note && <p className="mt-2 text-xs text-amber-200">{selected.attributes.version_note}</p>}
        {selected.attributes.lockfile && <p className="mt-2 break-all text-xs text-slate-400">Lockfile: {selected.attributes.lockfile}</p>}
        {selected.attributes.central_version_candidates && <div className="mt-3 rounded-lg border border-white/10 p-3 text-xs leading-5 text-slate-400">
          <p>Central version candidates: {selected.attributes.central_version_candidates}{selected.attributes.central_candidates_truncated ? " (partial list)" : ""}</p>
          <p className="mt-2">Declarations in the nearest Directory.Packages.props. Conditions, imports and overrides are not evaluated. These candidates are not used as an identified version for advisory checks.</p>
          {centralFile && <Button size="sm" variant="ghost" className="mt-2" onClick={() => onInspect(centralFile.id)}>Inspect central declarations</Button>}
        </div>}
        <Button className="mt-4" variant="outline" onClick={() => onInspect(selected.id)}>Inspect manifest evidence</Button>
        <h4 className="mt-6 font-semibold">Usage evidence ({usage.length})</h4>{usage.length > 100 && <p className="text-xs text-slate-500">Showing the first 100 import locations.</p>}<p className="mt-2 text-xs leading-5 text-slate-500">Import-name candidates within the owning project. Package-to-namespace mappings, aliases, transitive usage and runtime loading are not verified. No matches does not establish that a dependency is unused.</p>
        <div className="mt-2 max-h-64 overflow-auto">{usage.slice(0, 100).map(node => <button key={node.id} className="mt-2 block w-full break-all rounded-lg bg-white/5 p-3 text-left text-xs text-cyan-200" onClick={() => onInspect(node.id)}>{node.label} · {node.path}:{node.evidence[0]?.lines || ""}</button>)}</div>
        <Button className="mt-5" disabled={busy || !jobId || !selected.attributes.ecosystem} onClick={() => void checkPublic(selected)}>{busy ? "Checking public sources…" : "Check updates and advisories"}</Button>
        {!jobId && <p className="mt-2 text-xs text-slate-500">Public checks require a retained backend analysis. Imported snapshots show static evidence only.</p>}
        {error && <p role="alert" className="mt-3 text-sm text-amber-200">{error}</p>}
        {check && <div className="mt-5 space-y-3 text-sm text-slate-400"><p>Checked: {check.checked_at}</p><p>Registry version: {check.latest_version || "unavailable"}<br />{check.registry_basis}</p><p>{check.update_status === "newer_available" ? "A newer version is published. Compatibility and declared-range satisfaction have not been checked." : check.update_status === "same_version" ? "Checked version matches the registry version." : "Update ordering is unknown or the registry version is not newer."}</p><p className={check.vulnerability_status === "reported" ? "text-amber-200" : ""}>{statusText[check.vulnerability_status]}</p>{check.advisories.map(advisory => <a key={advisory.id} href={advisory.url} target="_blank" rel="noreferrer" className="block rounded-lg border border-white/10 p-3 text-cyan-200">{advisory.id}<span className="mt-1 block text-xs text-slate-400">{advisory.summary}</span></a>)}{check.advisories_truncated && <p>Only a partial advisory list is shown.</p>}</div>}
      </> : <p className="text-sm text-slate-400">Choose a dependency to inspect its version, usage evidence and public checks.</p>}</aside></div>
    <details className="rounded-xl border border-white/10 p-4 text-sm text-slate-400"><summary>Coverage limits</summary><p className="mt-3 leading-6">Direct manifest declarations only. npm package-lock.json and NuGet packages.lock.json provide version evidence when a single supported resolution is available. The nearest Directory.Packages.props supplies central version candidates, without evaluating MSBuild conditions, imports or overrides. pnpm/yarn/Python lockfiles, runtime inventories and a complete transitive dependency graph are not yet parsed. Version URLs, tags and credential-bearing sources are withheld. Advisories are separate, time-stamped observations and do not alter the deterministic atlas.</p></details>
  </div>;
}
