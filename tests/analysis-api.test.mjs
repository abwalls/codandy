import { observationSchema } from "../lib/debugging-api.ts";
import { dependencyUsage } from "../lib/dependency-usage.ts";
import { connectionSchema, loginSchema, assistantApi } from "../lib/assistant-api.ts";
import { overviewNodes } from "../lib/overview-details.ts";
import { buildAskContext, questionPrompt, suggestedQuestions } from "../lib/ask-context.ts";
import { dependencyReport, matchesDependencyReview } from "../lib/dependency-report.ts";
import { dependencyImpact } from "../lib/dependency-impact.ts";
import { compareAtlases } from "../lib/atlas-comparison.ts";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { test } from "node:test";
import { atlasSchema, jobSchema, sourceFileSchema, recentReportsSchema, dependencyCheckSchema, api } from "../lib/analysis-api.ts";
import { GET, POST, DELETE } from "../app/api/analyses/[[...path]]/route.ts";

const python = process.env.CODANDY_TEST_PYTHON || resolve("backend",
  existsSync("backend/.venv-managed") ? ".venv-managed" : ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const generated = spawnSync(python, ["-c", `
import tempfile
from pathlib import Path
from app.analyzer import analyze_repository
from app.settings import Settings
with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    (root / 'index.ts').write_text('import "react"; import "./other"; export function run() {}')
    (root / 'other.ts').write_text('export const value = 1;')
    (root / 'Api.csproj').write_text('<Project><ProjectReference Include="Domain.csproj" /></Project>')
    (root / 'Domain.csproj').write_text('<Project />')
    print(analyze_repository(root, 'https://github.com/org/repo.git', None,
                             Settings(), lambda *_: None).model_dump_json())
`], {
  cwd: resolve("backend"),
  encoding: "utf8",
  // Atlas content is UTF-8 (report titles, and any non-ASCII repository path or
  // identifier). Without this, Python encodes stdout/stderr with the Windows
  // ANSI codepage and dies on the first non-ASCII character.
  env: { ...process.env, PYTHONIOENCODING: "utf-8" },
});
assert.equal(generated.status, 0, generated.stderr);
const fixture = JSON.parse(generated.stdout);

test("frontend accepts a real Python-generated atlas", () => {
  const atlas = atlasSchema.parse(fixture);
  assert.equal(atlas.counts.symbols, 1);
  assert.equal(atlas.relationships.find(edge => edge.type === "IMPORTS").resolution, "unresolved");
  assert.ok(atlas.report.architecture.items.some(item => item.category === "project_dependency" && item.steps.length > 0));
});
test("invalid graph and schema versions are rejected", () => {
  assert.equal(atlasSchema.safeParse({ ...fixture, schema_version: "future" }).success, false);
  assert.equal(atlasSchema.safeParse({ ...fixture, nodes: [...fixture.nodes, fixture.nodes[0]] }).success, false);
  assert.equal(atlasSchema.safeParse({ ...fixture, nodes: [] }).success, false);
});
test("report evidence and flow steps must come from the backend graph", () => {
  assert.equal(fixture.schema_version, "0.2");
  assert.equal(fixture.report.architecture.status, "generated");
  assert.equal(fixture.report.flows.items[0].category, "module_dependency");
  // Guards the UTF-8 stdout pipe above: this title carries a non-ASCII arrow.
  assert.match(fixture.report.flows.items[0].title, /→/);
  const broken = structuredClone(fixture);
  broken.report.flows.items[0].steps[0].type = "CALLS";
  assert.equal(atlasSchema.safeParse(broken).success, false);
  const missing = structuredClone(fixture);
  missing.report.architecture.items[0].node_ids = ["invented"];
  assert.equal(atlasSchema.safeParse(missing).success, false);
});
test("progress rejects invalid statuses and percentages", () => {
  const job = { id: "00000000-0000-4000-8000-000000000000", status: "complete", phase: "complete", progress: 100, error: null, created_at: "2026-09-12" };
  assert.equal(jobSchema.safeParse(job).success, true);
  assert.equal(jobSchema.safeParse({ ...job, progress: 101 }).success, false);
  assert.equal(jobSchema.safeParse({ ...job, status: "invented" }).success, false);
});
test("API errors expose useful validation and unavailable states", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => Response.json({ detail: [{ msg: "invalid" }] }, { status: 422 });
    await assert.rejects(api(""), /public HTTPS/);
    globalThis.fetch = async () => Response.json({ detail: "Atlas is not ready" }, { status: 409 });
    await assert.rejects(api("/id/atlas"), /Atlas is not ready/);
    globalThis.fetch = async () => new Response("unavailable", { status: 503 });
    await assert.rejects(api(""), /backend is running/);
  } finally { globalThis.fetch = original; }
});

test("hosted proxy reports missing configuration and forwards SSE replay", async () => {
  const original = globalThis.fetch;
  const configured = process.env.CODANDY_API_URL;
  try {
    delete process.env.CODANDY_API_URL;
    assert.equal((await GET(new Request("https://atlas.test/api/analyses"))).status, 503);
    process.env.CODANDY_API_URL = "https://api.atlas.test";
    assert.equal((await GET(new Request("https://atlas.test/api/analyses/other"))).status, 404);
    globalThis.fetch = async (url, init) => {
      assert.equal(url.origin, "https://api.atlas.test");
      assert.equal(init.headers.get("Last-Event-ID"), "2");
      return new Response('id: 3\nevent: progress\ndata: {}\n\n', { headers: { "Content-Type": "text/event-stream" } });
    };
    const response = await GET(new Request("https://atlas.test/api/analyses/00000000-0000-4000-8000-000000000000/events", { headers: { "Last-Event-ID": "2" } }));
    assert.equal(response.headers.get("Content-Type"), "text/event-stream");
    assert.match(await response.text(), /^id: 3/);
    globalThis.fetch = async (_url, init) => {
      assert.equal(init.method, "POST");
      assert.equal(init.body, '{"source":{}}');
      return Response.json({ detail: "busy" }, { status: 429, headers: { "Retry-After": "5" } });
    };
    const busy = await POST(new Request("https://atlas.test/api/analyses", { method: "POST", body: '{"source":{}}' }));
    assert.equal(busy.status, 429);
    assert.equal(busy.headers.get("Retry-After"), "5");
  } finally {
    globalThis.fetch = original;
    if (configured === undefined) delete process.env.CODANDY_API_URL;
    else process.env.CODANDY_API_URL = configured;
  }
});

test("source payloads round-trip and the proxy forwards only the path parameter", async () => {
  const original = globalThis.fetch;
  const configured = process.env.CODANDY_API_URL;
  const id = "00000000-0000-4000-8000-000000000000";
  const payload = { path: "src/App.tsx", text: "const a = 1;\n", lines: 1, truncated: false };
  assert.deepEqual(sourceFileSchema.parse(payload), payload);
  assert.equal(sourceFileSchema.safeParse({ ...payload, lines: -1 }).success, false);
  assert.equal(sourceFileSchema.safeParse({ ...payload, truncated: "no" }).success, false);
  try {
    process.env.CODANDY_API_URL = "https://api.atlas.test";
    globalThis.fetch = async (url) => {
      assert.equal(url.pathname, `/api/analyses/${id}/source`);
      // Exactly one forwarded parameter: never the caller's whole query string.
      assert.deepEqual([...url.searchParams], [["path", "src/App.tsx"]]);
      return Response.json(payload);
    };
    const response = await GET(new Request(
      `https://atlas.test/api/analyses/${id}/source?path=src%2FApp.tsx&token=leak`));
    assert.equal(response.status, 200);
    assert.deepEqual(sourceFileSchema.parse(await response.json()), payload);
    const missing = await GET(new Request(`https://atlas.test/api/analyses/${id}/source`));
    assert.equal(missing.status, 400);
  } finally {
    globalThis.fetch = original;
    if (configured === undefined) delete process.env.CODANDY_API_URL;
    else process.env.CODANDY_API_URL = configured;
  }
});


test("saved atlas rejects evidence outside the report item cited nodes", () => {
  const altered = structuredClone(fixture);
  altered.report.architecture.items[0].evidence[0].path = "invented.ts";
  assert.equal(atlasSchema.safeParse(altered).success, false);
});


test("snapshot comparison ignores ordering and rejects unrelated repositories", () => {
  const reordered = structuredClone(fixture);
  reordered.nodes.reverse(); reordered.relationships.reverse();
  reordered.nodes.forEach(node => node.evidence.reverse());
  assert.equal(compareAtlases(fixture, reordered).changes.length, 0);
  reordered.repository.url = "https://github.com/somewhere/else.git";
  assert.throws(() => compareAtlases(fixture, reordered), /same repository/);
  reordered.repository.url = fixture.repository.url;
  reordered.schema_version = "0.1";
  assert.throws(() => compareAtlases(fixture, reordered), /schema versions/);
});

test("snapshot comparison reports node edits and relationship changes", () => {
  const changed = structuredClone(fixture);
  const removed = changed.nodes.pop();
  changed.nodes[0].detail += " new metadata";
  changed.nodes.push({ ...removed, id: removed.id + ":new" });
  changed.relationships = changed.relationships.filter(edge => edge.source !== removed.id && edge.target !== removed.id);
  const result = compareAtlases(fixture, changed);
  assert.deepEqual(result.changes.map(change => change.status).sort(), ["added", "changed", "removed"]);
  assert.equal(result.unchangedNodes, fixture.nodes.length - 2);
  assert.ok(result.removedRelationships > 0);
});


test("dependency impact follows incoming import paths without revisiting cycles", () => {
  const graph = structuredClone(fixture);
  const target = graph.nodes.find(node => node.kind === "file" && node.path === "other.ts");
  const source = graph.nodes.find(node => node.kind === "file" && node.path === "index.ts");
  assert.deepEqual(dependencyImpact(graph, "other.ts").map(item => [item.node.path, item.distance]), [["index.ts", 1]]);
  graph.relationships.push({ source: target.id, target: "cycle-import", type: "IMPORTS" });
  graph.relationships.push({ source: "cycle-import", target: source.id, type: "RESOLVES_TO", resolution: "inferred" });
  assert.equal(dependencyImpact(graph, "other.ts").length, 1);
  assert.deepEqual(dependencyImpact(graph, "missing.ts"), []);
});


test("recent report contract validates IDs and persistence status", () => {
  const history = { persistent: true, reports: [{ id: "00000000-0000-4000-8000-000000000000", repository: fixture.repository, created_at: "2026-09-13" }] };
  assert.equal(recentReportsSchema.parse(history).reports.length, 1);
  history.reports[0].id = "../escape";
  assert.equal(recentReportsSchema.safeParse(history).success, false);
});


test("hosted proxy forwards report removal without a body", async () => {
  const oldFetch = globalThis.fetch;
  const oldOrigin = process.env.CODANDY_API_URL;
  process.env.CODANDY_API_URL = "https://backend.example.com";
  try {
    globalThis.fetch = async (url, init) => {
      assert.equal(init.method, "DELETE");
      assert.equal(init.body, undefined);
      return Response.json({ deleted: "00000000-0000-4000-8000-000000000000" });
    };
    const response = await DELETE(new Request("https://atlas.example.com/api/analyses/00000000-0000-4000-8000-000000000000", { method: "DELETE" }));
    assert.equal(response.status, 200);
  } finally {
    globalThis.fetch = oldFetch;
    if (oldOrigin === undefined) delete process.env.CODANDY_API_URL;
    else process.env.CODANDY_API_URL = oldOrigin;
  }
});


test("dependency public-check contract rejects unsafe advisory links", () => {
  const result = { node_id: "dependency:example", checked_at: "2026-09-13", version: "1.0.0", version_basis: "declared", latest_version: "2.0.0", registry_status: "checked", registry_basis: "npm latest tag", update_status: "newer_available", vulnerability_status: "reported", advisories: [{ id: "GHSA-example", summary: "Example", url: "https://osv.dev/vulnerability/GHSA-example" }], advisories_truncated: false };
  assert.equal(dependencyCheckSchema.safeParse(result).success, true);
  result.advisories[0].url = "javascript:alert(1)";
  assert.equal(dependencyCheckSchema.safeParse(result).success, false);
});

test("hosted dependency checks forward only the node ID", async () => {
  const oldFetch = globalThis.fetch;
  const oldOrigin = process.env.CODANDY_API_URL;
  process.env.CODANDY_API_URL = "https://backend.example.com";
  try {
    globalThis.fetch = async (url, init) => {
      assert.equal(new URL(url).search, "?node_id=dependency%3Aexample");
      assert.equal(init.method, "POST");
      return Response.json({});
    };
    const response = await POST(new Request("https://atlas.example.com/api/analyses/00000000-0000-4000-8000-000000000000/dependencies?node_id=dependency%3Aexample&url=http://localhost/", { method: "POST" }));
    assert.equal(response.status, 200);
  } finally {
    globalThis.fetch = oldFetch;
    if (oldOrigin === undefined) delete process.env.CODANDY_API_URL;
    else process.env.CODANDY_API_URL = oldOrigin;
  }
});


test("dependency usage stays inside the owning project", () => {
  const graph = structuredClone(fixture);
  const source = graph.nodes.find(node => node.kind === "file" && node.path === "index.ts");
  const imported = graph.nodes.find(node => node.kind === "import" && node.label === "react");
  const dependency = { ...source, id: "dep:react", kind: "dependency", label: "react", attributes: { ecosystem: "npm" } };
  graph.nodes.push(dependency, { ...source, id: "project:root", kind: "project" });
  graph.relationships.push({ source: "project:root", target: dependency.id, type: "DEPENDS_ON" }, { source: "project:root", target: source.id, type: "CONTAINS" });
  assert.deepEqual(dependencyUsage(graph, dependency).map(node => node.id), [imported.id]);
  graph.nodes.push({ ...imported, id: "import:other-project", path: "other-project/index.ts" });
  assert.deepEqual(dependencyUsage(graph, dependency).map(node => node.id), [imported.id]);
});

test("subscription connection discovers model effort capabilities and rejects foreign login URLs", () => {
  const connection = connectionSchema.parse({ connected: true, plan: "pro", models: [{ id: "test", name: "Test", default: true, default_effort: "low", efforts: ["low", "high"] }] });
  assert.deepEqual(connection.models[0].efforts, ["low", "high"]);
  assert.equal(loginSchema.safeParse({ url: "https://attacker.example/" }).success, false);
  assert.equal(loginSchema.safeParse({ url: "https://auth.openai.com/oauth/authorize" }).success, true);
});

test("assistant requests use the local client header and surface connection errors", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async (url, init) => {
      assert.equal(url, "/api/analyses/assistant/status");
      assert.equal(init.headers["X-Codandy-Local"], "1");
      return Response.json({ detail: "Local connection disabled" }, { status: 503 });
    };
    await assert.rejects(() => assistantApi("status"), /Local connection disabled/);
  } finally { globalThis.fetch = original; }
});

test("hosted proxy does not expose local subscription endpoints", async () => {
  const previous = process.env.CODANDY_API_URL;
  process.env.CODANDY_API_URL = "https://backend.example.com";
  try {
    const response = await GET(new Request("https://atlas.example.com/api/analyses/assistant/status"));
    assert.equal(response.status, 404);
  } finally {
    if (previous === undefined) delete process.env.CODANDY_API_URL;
    else process.env.CODANDY_API_URL = previous;
  }
});

test("overview drilldowns separate files, symbols, routes and test candidates", () => {
  const graph = structuredClone(fixture);
  const base = graph.nodes.find(node => node.kind === "file");
  graph.nodes.push(...["route", "test", "handler", "dependency", "import"].map(kind => ({ ...base, id: `metric:${kind}`, kind })));
  assert.equal(overviewNodes(graph, "files").length, fixture.counts.files);
  assert.deepEqual(overviewNodes(graph, "routes").map(node => node.id), ["metric:route"]);
  assert.deepEqual(overviewNodes(graph, "tests").map(node => node.id), ["metric:test"]);
  assert.equal(overviewNodes(graph, "symbols").length, fixture.counts.symbols + 1);
  assert.equal(overviewNodes(graph, "symbols").some(node => node.kind === "dependency"), false);
});

test("AI drafts stay inside their selected evidence scope and disclose omissions", () => {
  const graph = structuredClone(fixture);
  const first = graph.nodes[0];
  graph.nodes.push(...Array.from({ length: 30 }, (_, index) => ({ ...first, id: `context:${index}` })));
  const ids = ["context:29", ...graph.nodes.map(node => node.id), "missing"];
  const context = buildAskContext(graph, { title: "Codebase", nodeIds: ids });
  assert.equal(context.nodes[0].id, "context:29");
  assert.equal(context.nodes.length, 24);
  assert.ok(context.omitted_nodes > 0);
  assert.equal(buildAskContext(graph, { title: "Empty selection", nodeIds: [] }).nodes.length, 0);
  const single = buildAskContext(graph, { title: "Selected node", nodeIds: [first.id] });
  assert.deepEqual(single.nodes.map(node => node.id), [first.id]);
  assert.ok(single.relationships.every(edge => edge.source === first.id && edge.target === first.id));
  assert.match(questionPrompt("  Explain this  ", single), /Question: Explain this/);
  assert.match(questionPrompt("Explain", single), /untrusted data/);
  assert.ok(suggestedQuestions("API routes").some(question => question.includes("unresolved")));
});

test("dependency review keeps unchecked inventory distinct from public observations", () => {
  const graph = structuredClone(fixture);
  const base = graph.nodes.find(node => node.kind === "file");
  graph.nodes.push({ ...base, id: "dependency:checked", kind: "dependency", label: "example", attributes: { ecosystem: "npm", checked_version: "1.0.0" } },
    { ...base, id: "dependency:unchecked", kind: "dependency", label: "unknown", attributes: { central_version_candidates: "1.0.0", central_version_file: "Directory.Packages.props" } });
  const check = dependencyCheckSchema.parse({ node_id: "dependency:checked", checked_at: "2026-09-13", version: "1.0.0", version_basis: "declared", latest_version: null, registry_status: "unavailable", registry_basis: "", update_status: "unknown", vulnerability_status: "unavailable", advisories: [], advisories_truncated: false });
  const report = dependencyReport(graph, { [check.node_id]: check, unrelated: { ...check, node_id: "unrelated" } }, "2026-09-13T00:00:00Z");
  assert.equal(report.inventory.find(item => item.node_id === "dependency:unchecked").identified_version, null);
  assert.equal(report.inventory.find(item => item.node_id === "dependency:unchecked").central_version_candidates, "1.0.0");
  assert.deepEqual(report.public_checks, [check]);
  assert.equal(report.exported_at, "2026-09-13T00:00:00Z");
  assert.equal(matchesDependencyReview(undefined, "unchecked"), true);
  assert.equal(matchesDependencyReview(undefined, "uncertain"), false);
  assert.equal(matchesDependencyReview(check, "uncertain"), true);
  assert.equal(matchesDependencyReview(check, "advisories"), false);
  assert.equal(matchesDependencyReview({ ...check, registry_status: "checked", update_status: "same_version", vulnerability_status: "no_matches", advisories_truncated: true }, "uncertain"), true);
  assert.equal(dependencyReport(graph, { "dependency:checked": { ...check, node_id: "unrelated" } }, "now").public_checks.length, 0);
});

test("project impact follows project edges, skips unresolved links and terminates on cycles", () => {
  const graph = structuredClone(fixture);
  const base = graph.nodes.find(node => node.kind === "project");
  graph.nodes.push(...["a", "b", "c", "d"].map(name => ({ ...base, id: `project:${name}`, path: `${name}.csproj` })));
  graph.relationships.push(...[["b", "a"], ["c", "b"], ["a", "c"]].map(([source, target]) => ({ source: `project:${source}`, target: `project:${target}`, type: "DEPENDS_ON", resolution: "inferred" })),
    { source: "project:d", target: "project:a", type: "DEPENDS_ON", resolution: "unresolved" });
  assert.deepEqual(dependencyImpact(graph, "a.csproj", "project").map(entry => [entry.node.id, entry.distance]), [["project:b", 1], ["project:c", 2]]);
  assert.deepEqual(dependencyImpact(graph, "missing.csproj", "project"), []);
  assert.equal(dependencyImpact(fixture, "Domain.csproj", "project")[0].node.path, "Api.csproj");
});

test("debugging observation contract accepts normalized Python Sentry evidence", () => {
  const result = spawnSync(python, ["-c", `
from pathlib import Path
from app.debugging.sentry_event import normalize_sentry_event_bytes
print(normalize_sentry_event_bytes(Path('tests/fixtures/debugging/sentry_python_chained.json').read_bytes()).model_dump_json())
`], { cwd: resolve("backend"), encoding: "utf8", env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
  assert.equal(result.status, 0, result.stderr);
  const observation = observationSchema.parse(JSON.parse(result.stdout));
  assert.equal(observation.exceptions[0].relation_to_next, "direct_cause");
  assert.ok(!JSON.stringify(observation).includes("hunter2"));
  assert.equal(observationSchema.safeParse({ ...observation, schema_version: "0.2" }).success, false);
});
