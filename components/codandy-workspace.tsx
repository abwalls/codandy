"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  BookOpen,
  Boxes,
  Braces,
  Bug,
  Check,
  ChevronRight,
  CircleDot,
  Code2,
  Database,
  FileCode2,
  Files,
  GitBranch,
  Layers3,
  LockKeyhole,
  Network,
  Play,
  Search,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
  Workflow,
  X,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { AtlasNode, demoAtlas } from "@/lib/atlas";
import { RecommendedChanges } from "@/components/recommended-changes";
import { RecentReports } from "@/components/recent-reports";
import { ThemePicker } from "@/components/theme-picker";
import { LiveReport } from "@/components/live-report";
import { OverviewDetails } from "@/components/overview-details";
import { type OverviewMetric } from "@/lib/overview-details";
import { AskCodandyProvider, AskButton, useAskCodandy } from "@/components/ask-codandy";
import { api, atlasSchema, jobSchema, type AnalysisAtlas, type AnalysisJob } from "@/lib/analysis-api";

type View = "intake" | "analyzing" | "report";
type Section = "overview" | "architecture" | "flows" | "codebase" | "guide" | "recommendations" | "debugging" | "dependencies";

const analysisSteps = [
  "Queued",
  "Cloning repository",
  "Detecting frameworks",
  "Indexing symbols",
  "Linking source relationships",
  "Generating evidence-backed reports",
  "Validating atlas",
  "Complete",
];

const navItems = [
  { id: "overview", label: "Overview", icon: BookOpen },
  { id: "architecture", label: "Architecture", icon: Network },
  { id: "flows", label: "Application flows", icon: Workflow },
  { id: "codebase", label: "Codebase", icon: FileCode2 },
  { id: "dependencies", label: "Dependencies", icon: Boxes },
  { id: "guide", label: "Developer guide", icon: TerminalSquare },
  { id: "recommendations", label: "Recommended changes", icon: Sparkles },
] as const;

const kindStyles: Record<AtlasNode["kind"], string> = {
  client: "border-cyan-400/30 bg-cyan-400/[0.08] text-cyan-100",
  route: "border-blue-400/30 bg-blue-400/[0.08] text-blue-100",
  handler: "border-violet-400/30 bg-violet-400/[0.08] text-violet-100",
  service: "border-amber-400/30 bg-amber-400/[0.08] text-amber-100",
  repository: "border-emerald-400/30 bg-emerald-400/[0.08] text-emerald-100",
  database: "border-rose-400/30 bg-rose-400/[0.08] text-rose-100",
};

function BrandMark() {
  return (
    <span className="relative grid size-9 place-items-center rounded-xl border border-cyan-300/30 bg-cyan-300/10 text-cyan-200 atlas-brand-glow">
      <Boxes className="size-[18px]" strokeWidth={1.8} />
      <span className="absolute -right-0.5 -top-0.5 size-2 rounded-full border border-[var(--surface-1)] bg-emerald-400" />
    </span>
  );
}

function Intake({ onAnalyze, onDemo, onImport, onReopen }: { onAnalyze: (value: string, ref?: string) => void; onDemo: () => void; onImport: (atlas: AnalysisAtlas) => void; onReopen: (atlas: AnalysisAtlas, job: AnalysisJob) => void }) {
  const [repo, setRepo] = useState("");
  const [ref, setRef] = useState("");
  const [importError, setImportError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const importInput = useRef<HTMLInputElement>(null);

  async function openAtlas(file: File) {
    setImportError(null);
    setImporting(true);
    try {
      if (file.size > 20 * 1024 * 1024) throw new Error("Atlas files must be 20 MB or smaller.");
      const parsed = atlasSchema.safeParse(JSON.parse(await file.text()));
      if (!parsed.success) throw new Error("This file is not a supported atlas or contains invalid graph references.");
      onImport(parsed.data);
    } catch (cause) {
      setImportError(cause instanceof SyntaxError ? "This file is not valid JSON." : cause instanceof Error ? cause.message : "Could not open the atlas.");
    } finally {
      setImporting(false);
      if (importInput.current) importInput.current.value = "";
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    onAnalyze(repo.trim(), ref.trim() || undefined);
  }

  return (
    <main className="atlas-grid min-h-svh bg-[var(--background)] text-slate-100">
      <header className="mx-auto flex w-full max-w-[1440px] items-center justify-between px-5 py-5 sm:px-8 lg:px-12">
        <div className="flex items-center gap-3">
          <BrandMark />
          <div>
            <div className="text-[15px] font-semibold tracking-[-0.02em]">Codandy</div>
            <div className="text-xs text-slate-500">Repository intelligence</div>
          </div>
        </div>
        <div className="flex items-center gap-2"><ThemePicker /><Button
          variant="outline"
          className="h-10 border-white/10 bg-white/[0.04] text-slate-200 hover:bg-white/[0.08] hover:text-white"
          onClick={() => window.alert("ChatGPT authentication is scaffolded for the next milestone.")}
        >
          <Sparkles className="text-cyan-300" />
          <span className="hidden sm:inline">Connect ChatGPT</span>
          <span className="sm:hidden">Connect</span>
        </Button></div>
      </header>

      <section className="mx-auto grid w-full max-w-[1180px] gap-8 px-5 pb-16 pt-[clamp(3rem,9vh,7rem)] lg:grid-cols-[minmax(0,1fr)_360px] lg:items-start lg:px-8">
        <div>
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/[0.06] px-3 py-1.5 text-xs font-medium text-cyan-200">
            <CircleDot className="size-3" /> Static analysis only · repository code is never executed
          </div>
          <h1 className="max-w-3xl text-balance text-[clamp(2.7rem,7vw,5.8rem)] font-semibold leading-[0.94] tracking-[-0.065em] text-white">
            See how the codebase <span className="atlas-text-glow text-cyan-200">actually works.</span>
          </h1>
          <p className="mt-6 max-w-2xl text-pretty text-lg leading-8 text-slate-400">
            Explore files, declarations, imports, and route candidates with evidence from a public GitHub repository.
          </p>

          <form onSubmit={submit} className="mt-10 max-w-2xl rounded-2xl border border-white/10 bg-[var(--surface-5)]/90 p-3 shadow-[0_24px_80px_rgba(0,0,0,.28)] backdrop-blur">
            <div className="flex flex-col gap-3 sm:flex-row">
              <div className="relative min-w-0 flex-1">
                <GitBranch className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-500" />
                <Input
                  aria-label="Public Git repository URL"
                  required
                  type="url"
                  value={repo}
                  onChange={(event) => setRepo(event.target.value)}
                  placeholder="https://github.com/org/repository"
                  className="h-12 border-white/10 bg-[var(--background)] pl-10 text-base text-slate-100 shadow-none placeholder:text-slate-600 focus-visible:border-cyan-300/40 focus-visible:ring-cyan-300/10"
                />
              </div>
              <Button type="submit" className="h-12 bg-cyan-300 px-5 font-semibold text-[var(--primary-foreground)] hover:bg-cyan-200">
                Analyze repository <ArrowRight />
              </Button>
            </div>
            <div className="mt-3 flex flex-col items-start justify-between gap-2 px-1 pb-1 sm:flex-row sm:items-center">
              <Input aria-label="Branch or tag (optional)" placeholder="Branch or tag (default branch if blank)" value={ref} onChange={event => setRef(event.target.value)} className="max-w-sm border-white/10" />
              <span className="text-xs text-slate-500">Public GitHub only · ZIP and folder uploads coming later</span>
            </div>
          </form>
          <RecentReports onOpen={onReopen} />
          <div className="mt-4 max-w-2xl space-y-2">
            <input ref={importInput} type="file" accept=".json,application/json" aria-label="Choose saved atlas" className="hidden" onChange={event => { const file = event.target.files?.[0]; if (file) void openAtlas(file); }} />
            <Button variant="outline" disabled={importing} onClick={() => importInput.current?.click()}>{importing ? "Opening atlas…" : "Open saved atlas"}</Button>
            <p className="text-xs leading-5 text-slate-500">Reopen a downloaded atlas.json on this device. Files stay in your browser; source text is not included in an atlas.</p>
            {importError && <p role="alert" className="text-sm text-amber-200">{importError}</p>}
          </div>
        </div>

        <button
          onClick={onDemo}
          className="group relative overflow-hidden rounded-2xl border border-white/10 bg-[var(--surface-4)] p-5 text-left shadow-[0_24px_80px_rgba(0,0,0,.22)] transition hover:-translate-y-1 hover:border-cyan-300/25"
        >
          <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-300/70 to-transparent" />
          <div className="flex items-start justify-between">
            <span className="grid size-11 place-items-center rounded-xl border border-white/10 bg-white/[0.04] text-cyan-200">
              <Play className="size-5 fill-current" />
            </span>
            <span className="rounded-full bg-emerald-400/10 px-2.5 py-1 text-xs font-medium text-emerald-300">Ready</span>
          </div>
          <div className="mt-9 text-xs font-semibold uppercase tracking-[0.13em] text-slate-500">Sample atlas</div>
          <h2 className="mt-2 text-xl font-semibold tracking-[-0.03em] text-white">Northstar Banking Platform</h2>
          <p className="mt-2 text-sm leading-6 text-slate-400">React, ASP.NET Core, CQRS, PostgreSQL, and event-driven workflows.</p>
          <div className="mt-6 flex items-center justify-between border-t border-white/[0.07] pt-4 text-sm text-slate-400">
            <span>1,942 symbols mapped</span>
            <ChevronRight className="size-4 transition group-hover:translate-x-1 group-hover:text-cyan-200" />
          </div>
        </button>
      </section>

      <footer className="mx-auto flex w-full max-w-[1180px] flex-wrap gap-x-6 gap-y-2 px-5 pb-8 text-xs text-slate-600 lg:px-8">
        <span className="inline-flex items-center gap-1.5"><ShieldCheck className="size-3.5" /> Read-only analysis</span>
        <span className="inline-flex items-center gap-1.5"><Code2 className="size-3.5" /> Evidence linked to source</span>
        <span className="inline-flex items-center gap-1.5"><LockKeyhole className="size-3.5" /> Private repository support planned</span>
      </footer>
    </main>
  );
}

function Analyzing({ source, job, error, connection, onExit }: { source: string; job: AnalysisJob | null; error: string | null; connection: string; onExit: () => void }) {
  const progress = job?.progress ?? 0;
  const activeStep = ["queued", "cloning", "detecting", "indexing", "linking", "reporting", "validating", "complete"].indexOf(job?.phase ?? "queued");

  return (
    <main className="atlas-grid grid min-h-svh place-items-center bg-[var(--background)] px-5 text-slate-100">
      <section className="w-full max-w-xl rounded-3xl border border-white/10 bg-[var(--surface-4)]/95 p-6 shadow-[0_28px_100px_rgba(0,0,0,.38)] sm:p-8">
        <div className="flex items-center gap-4">
          <BrandMark />
          <div className="min-w-0">
            <h1 className="text-xl font-semibold tracking-[-0.03em]">Building your atlas</h1>
            <p className="truncate text-sm text-slate-500">{source}</p>
          </div>
        </div>
        <Progress value={progress} className="mt-8 h-1.5 bg-white/[0.06] [&_[data-slot=progress-indicator]]:bg-cyan-300" />
        <p role="status" className="mt-3 text-sm text-cyan-200">{progress}% · {connection}</p>
        {error && <div role="alert" className="mt-4 rounded-xl border border-red-400/30 p-4 text-sm text-red-200">{error}</div>}
        {error && <Button onClick={onExit} className="mt-4">Back to repository input</Button>}
        <div className="mt-7 space-y-1">
          {analysisSteps.map((step, index) => {
            const complete = index < activeStep;
            const active = index === activeStep;
            return (
              <div key={step} className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm ${active ? "bg-cyan-300/[0.07] text-cyan-100" : "text-slate-500"}`}>
                <span className={`grid size-5 place-items-center rounded-full border ${complete ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-300" : active ? "animate-pulse border-cyan-300/40 bg-cyan-300/10 text-cyan-200" : "border-white/10"}`}>
                  {complete ? <Check className="size-3" /> : <span className="size-1 rounded-full bg-current" />}
                </span>
                {step}
              </div>
            );
          })}
        </div>
        <p className="mt-7 text-xs leading-5 text-slate-600">Source files are parsed statically. Build scripts, packages, and repository binaries are not executed.</p>
      </section>
    </main>
  );
}

function ReportSidebar({ section, onSection }: { section: Section; onSection: (section: Section) => void }) {
  return (
    <Sidebar collapsible="offcanvas" className="border-r border-white/[0.07] bg-[var(--sidebar)]">
      <SidebarHeader className="border-b border-white/[0.07] p-4">
        <div className="flex items-center gap-3 px-1">
          <BrandMark />
          <div>
            <div className="text-[15px] font-semibold text-slate-100">Codandy</div>
            <div className="text-xs text-slate-500">northstar/banking</div>
          </div>
        </div>
      </SidebarHeader>
      <SidebarContent className="px-2 py-3">
        <SidebarGroup>
          <SidebarGroupLabel className="px-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600">Report</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.id}>
                  <SidebarMenuButton
                    isActive={section === item.id}
                    onClick={() => onSection(item.id)}
                    className="h-9 text-slate-400 hover:bg-white/[0.05] hover:text-slate-100 data-[active=true]:bg-cyan-300/10 data-[active=true]:text-cyan-100"
                  >
                    <item.icon /> <span>{item.label}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarGroup className="mt-1">
          <SidebarGroupLabel className="px-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-600">Coming next</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton
                  isActive={section === "debugging"}
                  onClick={() => onSection("debugging")}
                  className="h-9 text-slate-400 hover:bg-white/[0.05] hover:text-slate-100 data-[active=true]:bg-amber-300/10 data-[active=true]:text-amber-100"
                >
                  <Bug /> <span>Debugging</span>
                  <span className="ml-auto rounded bg-white/[0.06] px-1.5 py-0.5 text-[10px] text-slate-500">Soon</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="border-t border-white/[0.07] p-4">
        <div className="rounded-xl border border-white/[0.07] bg-white/[0.025] p-3">
          <div className="flex items-center gap-2 text-xs text-slate-400"><GitBranch className="size-3.5" /> main · b7ac129</div>
          <div className="mt-2 text-xs text-slate-600">Analyzed Sep 12, 2026</div>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}

function ArchitectureMap({ selected, onSelect }: { selected: string | null; onSelect: (node: AtlasNode) => void }) {
  const flowNodes = demoAtlas.nodes.filter((node) => node.id !== "method:csharp:JwtTokenService.Generate");
  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-[var(--sidebar)] p-4 sm:p-6">
      <div className="atlas-map-grid absolute inset-0 opacity-40" />
      <div className="relative flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-slate-100">User authentication</h3>
          <p className="mt-1 text-sm text-slate-500">Observed request path across 5 symbols</p>
        </div>
        <span className="hidden rounded-full border border-emerald-300/20 bg-emerald-300/[0.07] px-2.5 py-1 text-xs text-emerald-300 sm:inline">97% confidence</span>
      </div>
      <div className="relative mt-7 flex flex-col items-center">
        {flowNodes.map((node, index) => (
          <div className="contents" key={node.id}>
            <button
              onClick={() => onSelect(node)}
              className={`group w-full max-w-lg rounded-xl border p-3.5 text-left shadow-[0_12px_34px_rgba(0,0,0,.16)] transition hover:-translate-y-0.5 hover:border-cyan-300/40 ${kindStyles[node.kind]} ${selected === node.id ? "ring-2 ring-cyan-300/30" : ""}`}
            >
              <div className="flex items-center gap-3">
                <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-black/15">
                  {node.kind === "database" ? <Database className="size-4" /> : node.kind === "client" ? <Code2 className="size-4" /> : <Braces className="size-4" />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold">{node.label}</span>
                  <span className="mt-0.5 block truncate font-mono text-[11px] opacity-55">{node.path}</span>
                </span>
                <ChevronRight className="size-4 opacity-30 transition group-hover:translate-x-0.5 group-hover:opacity-80" />
              </div>
            </button>
            {index < flowNodes.length - 1 && (
              <div className="flex h-9 flex-col items-center justify-center">
                <span className="h-5 w-px bg-gradient-to-b from-cyan-300/50 to-cyan-300/10" />
                <ChevronRight className="-mt-1 size-3 rotate-90 text-cyan-300/45" />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function NodeInspector({ node, onClose, onAsk }: { node: AtlasNode; onClose: () => void; onAsk: () => void }) {
  return (
    <aside className="fixed inset-y-0 right-0 z-40 hidden w-[370px] border-l border-white/[0.07] bg-[var(--surface-2)] shadow-[-24px_0_70px_rgba(0,0,0,.22)] xl:flex xl:flex-col">
      <div className="flex items-start justify-between border-b border-white/[0.07] p-5">
        <div className="min-w-0">
          <div className="text-xs font-semibold uppercase tracking-[0.12em] text-cyan-300">Selected node</div>
          <h2 className="mt-2 truncate text-lg font-semibold text-white">{node.label}</h2>
        </div>
        <Button aria-label="Close inspector" variant="ghost" size="icon-sm" onClick={onClose} className="text-slate-500 hover:bg-white/[0.06] hover:text-white"><X /></Button>
      </div>
      <div className="flex-1 overflow-y-auto p-5">
        <div className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium capitalize ${kindStyles[node.kind]}`}>{node.kind}</div>
        <p className="mt-5 text-[15px] leading-7 text-slate-300">{node.detail}</p>
        <div className="mt-6 rounded-xl border border-white/[0.07] bg-[var(--background)] p-4 font-mono text-xs leading-6 text-slate-400">
          <div className="text-cyan-200">{node.path}</div>
          <div>lines {node.lines}</div>
        </div>
        <dl className="mt-6 grid grid-cols-2 gap-3">
          <div className="rounded-xl border border-white/[0.07] p-3">
            <dt className="text-xs text-slate-600">Confidence</dt>
            <dd className="mt-1 text-lg font-semibold text-emerald-300">{node.confidence}%</dd>
          </div>
          <div className="rounded-xl border border-white/[0.07] p-3">
            <dt className="text-xs text-slate-600">Relationships</dt>
            <dd className="mt-1 text-lg font-semibold text-slate-200">{node.calls.length + node.calledBy.length}</dd>
          </div>
        </dl>
        <div className="mt-7">
          <h3 className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-600">Stable identity</h3>
          <code className="mt-2 block break-all text-xs leading-5 text-slate-500">{node.id}</code>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 border-t border-white/[0.07] p-4">
        <Button variant="outline" className="border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.07] hover:text-white"><Braces /> View code</Button>
        <Button onClick={onAsk} className="bg-cyan-300 text-[var(--primary-foreground)] hover:bg-cyan-200"><Sparkles /> Ask Codandy</Button>
      </div>
    </aside>
  );
}


function Overview({ selected, onSelect }: { selected: string | null; onSelect: (node: AtlasNode) => void }) {
  const [metric, setMetric] = useState<OverviewMetric | null>(null);
  const sampleRows = metric === "files" ? demoAtlas.nodes.filter((node, index, nodes) => nodes.findIndex(other => other.path === node.path) === index) : metric === "routes" ? demoAtlas.nodes.filter(node => node.kind === "route") : metric === "symbols" ? demoAtlas.nodes.filter(node => ["client", "handler", "service", "repository"].includes(node.kind)) : [];
  const stats = [
    [demoAtlas.counts.files, "Source files", Files, "files"],
    [demoAtlas.counts.symbols.toLocaleString(), "Symbols", Braces, "symbols"],
    [demoAtlas.counts.routes, "API routes", Zap, "routes"],
    [demoAtlas.counts.tests, "Tests", ShieldCheck, "tests"],
  ] as const;

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 pb-20 sm:p-6 lg:p-8">
      <section className="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-[linear-gradient(135deg,#0c1a2b_0%,#0a1725_55%,#0a2028_100%)] p-5 sm:p-7">
        <div className="absolute -right-20 -top-28 size-80 rounded-full bg-cyan-300/[0.05] blur-3xl" />
        <div className="relative flex flex-col justify-between gap-7 lg:flex-row lg:items-end">
          <div className="max-w-2xl">
            <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span className="rounded-md bg-white/[0.05] px-2 py-1 font-mono">main</span>
              <span>commit {demoAtlas.repository.commit}</span><span className="text-slate-700">•</span><span>{demoAtlas.repository.analyzedAt}</span>
            </div>
            <h1 className="text-2xl font-semibold tracking-[-0.04em] text-white sm:text-3xl">Northstar Banking Platform</h1>
            <p className="mt-3 text-base leading-7 text-slate-400">{demoAtlas.summary.description}</p>
          </div>
          <div className="min-w-[230px] rounded-xl border border-cyan-300/15 bg-[var(--background)]/50 p-4">
            <div className="text-xs text-slate-500">Primary architecture</div>
            <div className="mt-1 font-semibold text-cyan-100">{demoAtlas.summary.architecture}</div>
            <div className="mt-3 flex items-center gap-2 text-xs text-emerald-300"><Activity className="size-3.5" /> {demoAtlas.summary.confidence}% evidence confidence</div>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {stats.map(([value, label, Icon, key]) => (
          <button key={label} onClick={() => setMetric(key)} className="rounded-xl border border-white/[0.07] bg-[var(--card)] p-4 text-left hover:border-cyan-300/40 focus-visible:outline-2 focus-visible:outline-cyan-300 sm:p-5">
            <div className="flex items-center justify-between"><span className="text-2xl font-semibold tracking-[-0.04em] text-white">{value}</span><Icon className="size-4 text-slate-600" /></div>
            <div className="mt-1 text-sm text-slate-500">{label}</div>
            <span className="mt-2 block text-xs text-cyan-300">View details →</span>
          </button>
        ))}
      </section>

      <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_310px]">
        {metric && <OverviewDetails key={metric} metric={metric} sample total={demoAtlas.counts[metric]} rows={sampleRows} onClose={() => setMetric(null)} onInspect={id => { setMetric(null); const node = demoAtlas.nodes.find(node => node.id === id); if (node) onSelect(node); }} />}
        <ArchitectureMap selected={selected} onSelect={onSelect} />
        <div className="space-y-4">
          <div className="rounded-2xl border border-white/[0.08] bg-[var(--card)] p-5">
            <div className="flex items-center justify-between"><h3 className="font-semibold text-slate-100">Detected stack</h3><Layers3 className="size-4 text-slate-600" /></div>
            <div className="mt-4 flex flex-wrap gap-2">
              {demoAtlas.summary.technologies.map((tech) => <span key={tech} className="rounded-lg border border-white/[0.07] bg-white/[0.03] px-2.5 py-1.5 text-xs text-slate-400">{tech}</span>)}
            </div>
          </div>
          <div className="rounded-2xl border border-white/[0.08] bg-[var(--card)] p-5">
            <div className="flex items-center justify-between"><h3 className="font-semibold text-slate-100">Why Atlas thinks this</h3><Search className="size-4 text-slate-600" /></div>
            <ul className="mt-4 space-y-3 text-sm leading-5 text-slate-400">
              {["38 IRequest implementations", "Controllers dispatch through IMediator", "Feature-based command/query folders", "Domain does not reference infrastructure"].map((item) => (
                <li key={item} className="flex gap-2.5"><Check className="mt-0.5 size-3.5 shrink-0 text-emerald-300" /> {item}</li>
              ))}
            </ul>
            <button className="mt-5 inline-flex items-center gap-1 text-sm font-medium text-cyan-300 hover:text-cyan-200">View all evidence <ChevronRight className="size-3.5" /></button>
          </div>
        </div>
      </section>
    </div>
  );
}

function SampleSection({ section, onSelect }: { section: "architecture" | "flows" | "codebase" | "guide"; onSelect: (node: AtlasNode) => void }) {
  const title: Record<typeof section, string> = {
    architecture: "System architecture",
    flows: "Application flows",
    codebase: "Codebase index",
    guide: "Developer guide",
  };
  const description: Record<typeof section, string> = {
    architecture: "The sample atlas maps the illustrative banking platform into a React client, ASP.NET Core API, application handlers, infrastructure services, and PostgreSQL.",
    flows: "A representative authentication request path through the sample system. The evidence and confidence values belong to the illustrative atlas.",
    codebase: "Browse the representative symbols included in the sample atlas and open any one for its illustrative source location.",
    guide: "Sample change paths show where a developer might begin investigating common changes in this illustrative repository.",
  };
  const nodes = demoAtlas.nodes;
  return <div className="mx-auto max-w-6xl space-y-6 p-4 pb-20 sm:p-6 lg:p-8">
    <header className="rounded-2xl border border-amber-300/15 bg-amber-300/[0.04] p-5 sm:p-7">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-amber-300">Sample report · illustrative data</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-white">{title[section]}</h1>
      <p className="mt-3 max-w-3xl text-base leading-7 text-slate-400">{description[section]}</p>
    </header>
    {section === "architecture" && <div className="grid gap-4 md:grid-cols-2">
      {["Client", "API boundary", "Application layer", "Infrastructure", "Data store"].map((layer, index) => <article key={layer} className="rounded-2xl border border-white/[0.08] bg-[var(--card)] p-5"><div className="text-xs uppercase tracking-wider text-cyan-300">Layer {index + 1}</div><h2 className="mt-2 text-lg font-semibold text-white">{layer}</h2><p className="mt-2 text-sm leading-6 text-slate-400">{["LoginForm and the browser-facing interaction.", "HTTP route handling and request validation.", "LoginHandler coordinates authentication work.", "Repositories and token services adapt infrastructure concerns.", "PostgreSQL identity data used by the repository."][index]}</p></article>)}
    </div>}
    {section === "flows" && <article className="rounded-2xl border border-white/[0.08] bg-[var(--card)] p-5 sm:p-6"><div className="flex flex-wrap items-center gap-2 text-xs text-slate-500"><span className="rounded-full bg-cyan-300/10 px-2.5 py-1 text-cyan-200">Observed in sample graph</span><span>97% illustrative confidence</span></div><h2 className="mt-4 text-xl font-semibold text-white">User authentication</h2><div className="mt-5 grid gap-3 md:grid-cols-3">{nodes.map((node) => <button key={node.id} onClick={() => onSelect(node)} className="rounded-xl border border-white/[0.08] bg-[var(--background)] p-4 text-left transition hover:border-cyan-300/30"><div className="text-xs uppercase text-cyan-300">{node.kind}</div><div className="mt-2 break-words text-sm font-medium text-slate-200">{node.label}</div><div className="mt-2 text-xs text-slate-500">Flow participant</div></button>)}</div><p className="mt-5 text-sm leading-6 text-slate-500">These participants belong to a branching sample graph. Their positions do not imply execution order.</p></article>}
    {section === "codebase" && <div className="grid gap-3 sm:grid-cols-2">{nodes.map(node => <button key={node.id} onClick={() => onSelect(node)} className="rounded-xl border border-white/[0.08] bg-[var(--card)] p-4 text-left hover:border-cyan-300/30"><div className={`inline-flex rounded-full border px-2 py-1 text-[11px] uppercase ${kindStyles[node.kind]}`}>{node.kind}</div><h2 className="mt-3 break-words font-semibold text-white">{node.label}</h2><p className="mt-1 break-all text-xs text-slate-500">{node.path}{node.lines ? `:${node.lines}` : ""}</p><p className="mt-3 text-sm leading-6 text-slate-400">{node.detail}</p></button>)}</div>}
    {section === "guide" && <div className="grid gap-4 md:grid-cols-2">{[
      ["Change authentication behavior", "Start at LoginForm, then inspect the login route and LoginHandler before changing token or user lookup behavior."],
      ["Change identity persistence", "Begin with UserRepository.GetByEmail and follow its PostgreSQL evidence before changing data access."],
      ["Add an API endpoint", "Start at the API route evidence, then trace the handler and service boundary shown in the sample flow."],
      ["Trace a source decision", "Select any node to inspect its illustrative path, line range, confidence, and stable identity."],
    ].map(([heading, body]) => <article key={heading} className="rounded-2xl border border-white/[0.08] bg-[var(--card)] p-5"><h2 className="font-semibold text-white">{heading}</h2><p className="mt-3 text-sm leading-6 text-slate-400">{body}</p></article>)}</div>}
  </div>;
}

function PlaceholderSection({ section }: { section: Section }) {
  if (section === "debugging") {
    return (
      <div className="mx-auto grid min-h-[calc(100svh-72px)] max-w-3xl place-items-center p-6 text-center">
        <div>
          <span className="mx-auto grid size-14 place-items-center rounded-2xl border border-amber-300/20 bg-amber-300/[0.07] text-amber-200"><Bug /></span>
          <div className="mt-5 text-xs font-semibold uppercase tracking-[0.13em] text-amber-300">Phase two</div>
          <h1 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-white">Trace a bug through the atlas</h1>
          <p className="mx-auto mt-4 max-w-xl text-base leading-7 text-slate-400">Describe an issue, paste a stack trace, or attach logs. Atlas will investigate affected paths and overlay likely root causes directly onto the report.</p>
          <Button disabled className="mt-7 bg-amber-300 text-[#171005]">Start investigation</Button>
        </div>
      </div>
    );
  }
  const labels: Record<string, [string, string]> = {
    architecture: ["System architecture", "Explore projects, boundaries, dependencies, and external systems."],
    flows: ["Application flows", "Follow request, event, and background-work paths through the codebase."],
    codebase: ["Codebase index", "Search directories, symbols, endpoints, entities, and tests."],
    guide: ["Developer guide", "Learn conventions and find where to make common changes."],
  };
  const [title, description] = labels[section] ?? labels.architecture;
  return (
    <div className="mx-auto max-w-6xl p-5 sm:p-8">
      <div className="rounded-2xl border border-white/[0.08] bg-[var(--card)] p-6 sm:p-8">
        <div className="text-xs font-semibold uppercase tracking-[0.12em] text-cyan-300">Foundation preview</div>
        <h1 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-white">{title}</h1>
        <p className="mt-3 text-base text-slate-400">{description}</p>
        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {["Grounded explanations", "Direct source links", "Contextual AI questions"].map((item) => <div key={item} className="rounded-xl border border-white/[0.07] bg-[var(--background)] p-4 text-sm text-slate-400"><Check className="mb-3 size-4 text-emerald-300" />{item}</div>)}
        </div>
      </div>
    </div>
  );
}

function Report({ onExit }: { onExit: () => void }) {
  return <AskCodandyProvider contextFor={scope => ({ sample: true, warning: "Illustrative banking sample, not analyzed repository evidence.", scope: scope.title, notes: scope.notes, repository: demoAtlas.repository, nodes: scope.nodeIds ? demoAtlas.nodes.filter(node => scope.nodeIds!.includes(node.id)) : demoAtlas.nodes, relationships: demoAtlas.relationships })}><SampleReportContent onExit={onExit} /></AskCodandyProvider>;
}

function SampleReportContent({ onExit }: { onExit: () => void }) {
  const [section, setSection] = useState<Section>("overview");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const ask = useAskCodandy();
  const selectedNode = useMemo(() => demoAtlas.nodes.find((node) => node.id === selectedId) ?? null, [selectedId]);

  return (
    <SidebarProvider className="bg-[var(--background)] text-slate-100">
      <ReportSidebar section={section} onSection={setSection} />
      <SidebarInset className={`min-w-0 bg-[var(--background)] transition-[margin] ${selectedNode ? "xl:mr-[370px]" : ""}`}>
        <header className="sticky top-0 z-30 flex min-h-[64px] flex-wrap items-center justify-between gap-2 py-2 border-b border-white/[0.07] bg-[var(--background)]/90 px-3 backdrop-blur-xl sm:px-5">
          <div className="flex min-w-0 items-center gap-2">
            <SidebarTrigger className="text-slate-400 hover:bg-white/[0.06] hover:text-white" />
            <div className="mx-1 h-5 w-px bg-white/[0.08]" />
            <div className="min-w-0">
              <div className="truncate text-sm font-medium text-slate-200">northstar/banking-platform</div>
              <div className="text-xs text-amber-300">Sample report · illustrative data</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <ThemePicker />
            <Button variant="ghost" size="sm" onClick={onExit} className="text-slate-500 hover:bg-white/[0.05] hover:text-white">New analysis</Button>
            <AskButton scope={{ title: `Sample ${section}` }}>Ask about this page</AskButton>
          </div>
        </header>
        {section === "overview" ? (
          <Overview selected={selectedId} onSelect={(node) => setSelectedId(node.id)} />
        ) : section === "recommendations" ? (
          <RecommendedChanges />
        ) : section === "dependencies" ? (
          <section className="m-5 rounded-xl border border-white/10 bg-card p-6"><h1 className="text-2xl font-semibold">Dependencies</h1><p className="mt-3 text-sm leading-6 text-slate-400">The illustrative banking atlas does not include package manifests or version evidence. Analyze a real repository to inspect npm, NuGet, Python and Go declarations, usage candidates, updates and reported advisories.</p><Button className="mt-5" onClick={onExit}>Analyze a repository</Button></section>
        ) : section === "debugging" ? (
          <PlaceholderSection section={section} />
        ) : (
          <SampleSection section={section} onSelect={(node) => setSelectedId(node.id)} />
        )}
      </SidebarInset>
      {selectedNode && <NodeInspector node={selectedNode} onClose={() => setSelectedId(null)} onAsk={() => ask?.({ title: `Sample node: ${selectedNode.label}`, nodeIds: [selectedNode.id, ...selectedNode.calls, ...selectedNode.calledBy] })} />}
    </SidebarProvider>
  );
}

export function CodandyWorkspace() {
  const [view, setView] = useState<View>("intake");
  const [source, setSource] = useState("");
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [atlas, setAtlas] = useState<AnalysisAtlas | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connection, setConnection] = useState("Submitting repository");
  const busy = useRef(false);

  const analyze = useCallback(async (value: string, ref?: string) => {
    if (busy.current) throw new Error("An analysis is already running");
    busy.current = true;
    setSource(value); setAtlas(null); setJob(null); setError(null);
    setConnection("Submitting repository"); setView("analyzing");
    try {
      const created = jobSchema.parse(await api("", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source: { url: value, ref } }) }));
      setJob(created);
      return { status: "started", jobId: created.id };
    } catch (cause) {
      busy.current = false;
      setError(cause instanceof Error ? cause.message : "Could not reach the analysis service.");
      setConnection("Submission failed");
      return { status: "failed" };
    }
  }, []);

  const jobId = job?.id;
  useEffect(() => {
    if (!jobId || view !== "analyzing") return;
    const controller = new AbortController();
    const events = new EventSource(`/api/analyses/${jobId}/events`);
    let stopped = false;
    let completing = false;
    let checking = false;
    let failures = 0;
    const fail = (message: string) => {
      if (stopped) return;
      stopped = true; events.close(); busy.current = false;
      setError(message); setConnection("Analysis stopped");
    };
    const accept = async (snapshot: AnalysisJob) => {
      if (stopped || completing || snapshot.id !== jobId) return;
      setJob(current => current && current.progress > snapshot.progress && snapshot.status !== "failed" ? current : snapshot);
      if (snapshot.status === "failed") { fail(snapshot.error || "Analysis failed"); return; }
      if (snapshot.status === "complete") {
        completing = true; events.close(); setConnection("Loading validated report");
        try {
          const result = atlasSchema.parse(await api(`/${jobId}/atlas`, { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]) }));
          if (!stopped) { setAtlas(result); setView("report"); busy.current = false; }
        } catch (cause) { fail(cause instanceof Error ? cause.message : "Could not load the atlas"); }
      }
    };
    events.onopen = () => { if (!stopped) setConnection("Receiving live progress"); };
    events.addEventListener("progress", event => {
      try { void accept(jobSchema.parse(JSON.parse((event as MessageEvent).data))); }
      catch { fail("The analysis service returned invalid progress data."); }
    });
    const checkStatus = async () => {
      if (stopped || completing || checking) return;
      checking = true;
      try {
        const snapshot = jobSchema.parse(await api(`/${jobId}`, { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]) }));
        failures = 0; await accept(snapshot);
      } catch (cause) {
        if (++failures >= 3) fail(cause instanceof Error ? cause.message : "Lost connection to the analysis service");
      } finally { checking = false; }
    };
    events.onerror = () => {
      if (!stopped && !completing) { setConnection("Reconnecting to progress…"); void checkStatus(); }
    };
    // Status checks recover a missed terminal event and detect expired jobs/API restarts.
    const timer = window.setInterval(() => void checkStatus(), 5000);
    void checkStatus();
    return () => { stopped = true; events.close(); controller.abort(); window.clearInterval(timer); };
  }, [jobId, view]);

  useEffect(() => {
    const context = document.modelContext;
    if (!context?.registerTool) return;
    const lifecycle = new AbortController();

    void Promise.resolve(
      context.registerTool(
        {
          name: "start_repository_analysis",
          title: "Analyze repository",
          description: "Start the visible Codandy analysis flow for a public Git repository URL.",
          inputSchema: {
            type: "object",
            properties: {
              repositoryUrl: { type: "string", format: "uri" },
            },
            required: ["repositoryUrl"],
            additionalProperties: false,
          },
          annotations: { readOnlyHint: false, untrustedContentHint: true },
          async execute(input) {
            const value = input as { repositoryUrl?: unknown };
            if (typeof value.repositoryUrl !== "string" || !value.repositoryUrl.startsWith("https://")) {
              throw new Error("repositoryUrl must be a valid HTTPS URL");
            }
            return analyze(value.repositoryUrl);
          },
        },
        { signal: lifecycle.signal },
      ),
    ).catch(() => undefined);

    return () => lifecycle.abort();
  }, [analyze]);

  const exit = () => { setView("intake"); setJob(null); setError(null); };
  if (view === "analyzing") return <Analyzing source={source} job={job} error={error} connection={connection} onExit={exit} />;
  if (view === "report") return atlas ? <LiveReport atlas={atlas} jobId={jobId ?? null} onExit={exit} /> : <Report onExit={exit} />;
  return <Intake onAnalyze={(value, ref) => { void analyze(value, ref); }} onDemo={() => { setAtlas(null); setView("report"); }} onImport={result => { setJob(null); setAtlas(result); setView("report"); }} onReopen={(result, savedJob) => { setJob(savedJob); setAtlas(result); setView("report"); }} />;
}
