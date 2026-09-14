"use client";

import { Gauge, GitBranch, ShieldAlert, Lightbulb } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const categories = [
  { id: "performance", label: "Performance", icon: Gauge, tone: "text-cyan-200", description: "Reduce unnecessary work and investigate bottlenecks." },
  { id: "refactoring", label: "Refactoring", icon: GitBranch, tone: "text-violet-200", description: "Simplify responsibilities and make changes easier to test." },
  { id: "security", label: "Security", icon: ShieldAlert, tone: "text-amber-200", description: "Review potential risks and validate safeguards." },
] as const;

type Recommendation = {
  id: string;
  category: typeof categories[number]["id"];
  title: string;
  priority: "High" | "Medium";
  effort: string;
  path: string;
  concern: string;
  action: string;
  verification: string;
};

// Illustrative fixtures only. These are not findings from an analyzed repository.
const recommendations: Recommendation[] = [
  {
    id: "PERF-001", category: "performance", title: "Review the user lookup query",
    priority: "Medium", effort: "Small",
    path: "src/Infrastructure/Users/UserRepository.cs",
    concern: "A login lookup may retrieve more fields than authentication needs. At scale, unnecessary data access could increase latency.",
    action: "Inspect the query and project only required fields. Consider a no-tracking query if the returned entity is never updated in this flow.",
    verification: "Capture the generated SQL and compare query plans and latency under representative load. Confirm indexes and preserve required authentication data.",
  },
  {
    id: "REF-001", category: "refactoring", title: "Separate token construction from login orchestration",
    priority: "Medium", effort: "Moderate",
    path: "src/Application/Auth/Login/LoginHandler.cs",
    concern: "If token construction or claim mapping is duplicated in request handlers, authentication changes become harder to test consistently.",
    action: "Keep LoginHandler focused on orchestration. Consolidate duplicated token construction behind the existing token-service interface.",
    verification: "First verify duplication exists. Preserve token claims, expiry behavior, and error handling with focused regression tests.",
  },
  {
    id: "SEC-001", category: "security", title: "Verify login abuse protection",
    priority: "High", effort: "Moderate",
    path: "src/Api/Auth/AuthController.cs",
    concern: "An authentication endpoint without effective abuse controls could be exposed to repeated password attempts. Protection may already exist at the gateway.",
    action: "Inspect endpoint, middleware, and gateway configuration for rate limiting and account-level protections. Avoid revealing whether an account exists in failure responses.",
    verification: "Review deployment controls and test policy enforcement in an authorized test environment. This is a potential risk to investigate, not a confirmed vulnerability.",
  },
];

function RecommendationCard({ item }: { item: Recommendation }) {
  const category = categories.find((value) => value.id === item.category)!;
  return (
    <article className="overflow-hidden rounded-2xl border border-white/[0.08] bg-[var(--card)]">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.07] px-5 py-4">
        <span className={`inline-flex items-center gap-2 text-sm font-medium ${category.tone}`}><category.icon className="size-4" />{category.label}</span>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className={`rounded-full border px-2.5 py-1 ${item.priority === "High" ? "border-amber-300/20 bg-amber-300/10 text-amber-200" : "border-cyan-300/20 bg-cyan-300/10 text-cyan-200"}`}>{item.priority} priority</span>
          <span className="rounded-full border border-white/10 px-2.5 py-1 text-slate-400">{item.effort} effort</span>
        </div>
      </div>
      <div className="space-y-5 p-5 sm:p-6">
        <div>
          <p className="font-mono text-xs text-slate-500">{item.id} · Illustrative recommendation</p>
          <h2 className="mt-2 text-xl font-semibold tracking-tight text-white">{item.title}</h2>
          <p className="mt-3 text-base leading-7 text-slate-400">{item.concern}</p>
        </div>
        <div className="rounded-xl border border-white/[0.07] bg-[var(--background)] p-4">
          <p className="text-sm text-slate-400">Suggested inspection point · sample path</p>
          <code className="mt-2 block break-all text-sm text-cyan-200">{item.path}</code>
        </div>
        <div className="grid gap-5 lg:grid-cols-2">
          <div><h3 className="text-sm font-semibold text-slate-200">Recommended approach</h3><p className="mt-2 text-base leading-7 text-slate-400">{item.action}</p></div>
          <div><h3 className="text-sm font-semibold text-slate-200">How to verify</h3><p className="mt-2 text-base leading-7 text-slate-400">{item.verification}</p></div>
        </div>
      </div>
    </article>
  );
}

export function RecommendedChanges() {
  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 pb-20 sm:p-6 lg:p-8">
      <header>
        <p className="text-sm font-medium text-cyan-300">Code quality review</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-white">Recommended changes</h1>
        <p className="mt-3 max-w-3xl text-base leading-7 text-slate-400">Performance improvements, refactoring opportunities, and potential security risks, with a suggested approach and verification steps.</p>
      </header>
      <div role="note" className="flex gap-3 rounded-xl border border-amber-300/20 bg-amber-300/[0.06] p-4 text-sm leading-6 text-amber-100">
        <Lightbulb className="mt-1 size-4 shrink-0" />
        <p><strong>Sample recommendations.</strong> These illustrate the planned review experience. No repository scan or vulnerability assessment has been performed. Priorities, effort estimates, and paths are examples; no code changes are applied.</p>
      </div>
      <Tabs defaultValue="all" className="gap-5">
        <TabsList aria-label="Recommendation categories" className="grid h-auto! w-full grid-cols-2 gap-1 bg-[var(--surface-6)] p-1 sm:flex sm:w-fit">
          <TabsTrigger value="all" className="min-h-10 px-4">All changes · {recommendations.length}</TabsTrigger>
          {categories.map((category) => <TabsTrigger key={category.id} value={category.id} className="min-h-10 px-4"><category.icon />{category.label}</TabsTrigger>)}
        </TabsList>
        <TabsContent value="all" className="space-y-5">{recommendations.map((item) => <RecommendationCard key={item.id} item={item} />)}</TabsContent>
        {categories.map((category) => (
          <TabsContent key={category.id} value={category.id} className="space-y-5">
            <p className="text-base text-slate-400">{category.description}</p>
            {recommendations.filter((item) => item.category === category.id).map((item) => <RecommendationCard key={item.id} item={item} />)}
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
