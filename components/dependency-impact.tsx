"use client";

import { useMemo, useState } from "react";
import type { AnalysisAtlas } from "@/lib/analysis-api";
import { dependencyImpact } from "@/lib/dependency-impact";
import { Button } from "@/components/ui/button";

export function DependencyImpact({ atlas, path, kind = "file", onInspect }: { atlas: AnalysisAtlas; path: string; kind?: "file" | "project"; onInspect: (id: string) => void }) {
  const impact = useMemo(() => dependencyImpact(atlas, path, kind), [atlas, path, kind]);
  const [limit, setLimit] = useState(10);
  return <section className="mt-5 border-t border-white/10 pt-4">
    <h4 className="font-medium">Who depends on this {kind}?</h4>
    <p className="mt-2 text-xs leading-5 text-slate-500">{impact.length} candidate {kind === "project" ? "dependent projects. Declared project-reference paths only; conditions, imports and build inclusion are not evaluated." : "importing files. Local path resolution only; dynamic imports, aliases and package-directory dependencies may be absent."} This does not predict runtime impact.</p>
    {!impact.length && <p className="mt-2 text-sm text-slate-400">No supported incoming {kind === "project" ? "project references" : "file-import paths"} detected.</p>}
    {impact.slice(0, limit).map(entry => <button key={entry.node.id} className="mt-2 block w-full break-all rounded-lg bg-white/5 p-3 text-left text-xs text-slate-300 hover:text-cyan-200" onClick={() => onInspect(entry.node.id)}>{entry.node.path}<span className="mt-1 block text-cyan-300">{entry.distance === 1 ? kind === "project" ? "Direct project reference" : "Direct importer" : `${entry.distance} ${kind === "project" ? "project" : "import"} links away`}</span></button>)}
    {impact.length > limit && <Button variant="ghost" size="sm" className="mt-2" onClick={() => setLimit(limit + 20)}>Show more dependents</Button>}
  </section>;
}
