"use client";

import { useEffect, useState } from "react";
import { ZodError } from "zod";
import { Braces, Database, Loader2, Network } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ArchitectureMap } from "@/components/architecture-map";
import { DataContractsView, DataModelView, DiagramNotice } from "@/components/data-model-diagrams";
import { api, type AnalysisAtlas } from "@/lib/analysis-api";
import { structureSchema, type StructureDocument } from "@/lib/structure-api";

type Load =
  | { status: "unavailable" }
  | { status: "loading" }
  | { status: "ready"; structure: StructureDocument }
  | { status: "error"; message: string };

const VIEWS = [
  { id: "dependencies", label: "Dependencies", icon: Network },
  { id: "data", label: "Data model", icon: Database },
  { id: "contracts", label: "Data contracts", icon: Braces },
] as const;

/** Switches between the dependency map and diagrams built from declared data models. */
export function ArchitectureHub({ atlas, jobId, onInspect }: { atlas: AnalysisAtlas; jobId: string | null; onInspect: (id: string) => void }) {
  const [view, setView] = useState<(typeof VIEWS)[number]["id"]>("dependencies");
  // The caller remounts this component per report, so the opening state is derived here.
  const [load, setLoad] = useState<Load>(jobId ? { status: "loading" } : { status: "unavailable" });

  useEffect(() => {
    if (!jobId) return;
    const controller = new AbortController();
    void (async () => {
      try {
        const structure = structureSchema.parse(await api(`/${jobId}/structure`, { signal: controller.signal }));
        if (!controller.signal.aborted) setLoad({ status: "ready", structure });
      } catch (cause) {
        if (controller.signal.aborted) return;
        setLoad({ status: "error", message: cause instanceof ZodError
          ? "The diagram data did not match the format this page expects. Run the analysis again to rebuild it."
          : cause instanceof Error ? cause.message : "Diagrams could not be loaded." });
      }
    })();
    return () => controller.abort();
  }, [jobId]);

  const counts = load.status === "ready" ? { data: load.structure.entities.length, contracts: load.structure.types.length } : null;
  return <div className="space-y-4">
    <div role="group" aria-label="Architecture diagram" className="flex flex-wrap gap-2">
      {VIEWS.map(item => {
        const count = item.id === "data" ? counts?.data : item.id === "contracts" ? counts?.contracts : undefined;
        return <Button key={item.id} variant={view === item.id ? "secondary" : "outline"} aria-pressed={view === item.id} onClick={() => setView(item.id)}>
          <item.icon />{item.label}{count !== undefined && <span className="rounded-full bg-white/10 px-2 text-xs text-slate-300">{count}</span>}
        </Button>;
      })}
    </div>
    {view === "dependencies" ? <ArchitectureMap atlas={atlas} onInspect={onInspect} />
      : load.status === "ready" ? (view === "data"
        ? <DataModelView structure={load.structure} atlas={atlas} onInspect={onInspect} />
        : <DataContractsView structure={load.structure} atlas={atlas} onInspect={onInspect} />)
        : <DiagramNotice icon={view === "data" ? Database : Braces} title={view === "data" ? "Data model" : "Data contracts"}>
          {load.status === "loading" ? <span className="flex items-center gap-2"><Loader2 className="size-4 animate-spin" />Loading declared data models…</span>
            : load.status === "error" ? load.message
              : "These diagrams need the local analysis service. Reopen this report from Recent reports, or run the analysis again."}
        </DiagramNotice>}
  </div>;
}
