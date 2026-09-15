import { architectureMap } from "../lib/architecture-map.ts";
import { dependencyMatrix, edgePath, layeredLayout, recordEdgePath, recordLayout } from "../lib/architecture-layout.ts";
import { structureSchema } from "../lib/structure-api.ts";
import { contractAreas, contractsView, erdView, mermaidClassDiagram, mermaidErDiagram } from "../lib/structure-diagram.ts";
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
import { atlasSchema, jobSchema, sourceFileSchema, recentReportsSchema, dependencyCheckSchema, api, repositoryName } from "../lib/analysis-api.ts";
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

test("hosted proxy streams ZIP uploads and forwards only the file name", async () => {
  const oldFetch = globalThis.fetch;
  const oldOrigin = process.env.CODANDY_API_URL;
  process.env.CODANDY_API_URL = "https://backend.example.com";
  const bytes = new Uint8Array([0x50, 0x4b, 0x03, 0x04, 1, 2, 3]);
  const upload = (query, type = "application/zip", method = "POST") => POST(new Request(
    `https://atlas.example.com/api/analyses/archive${query}`, { method, headers: { "Content-Type": type }, body: bytes }));
  try {
    globalThis.fetch = async (url, init) => {
      assert.equal(url.pathname, "/api/analyses/archive");
      assert.deepEqual([...url.searchParams], [["filename", "project.zip"]]);
      assert.equal(init.headers.get("Content-Type"), "application/zip");
      assert.deepEqual(new Uint8Array(await new Response(init.body).arrayBuffer()), bytes);
      return Response.json({ detail: "busy" }, { status: 429, headers: { "Retry-After": "5" } });
    };
    const busy = await upload("?filename=project.zip&token=leak");
    assert.equal(busy.status, 429);
    assert.equal(busy.headers.get("Retry-After"), "5");
    globalThis.fetch = async () => assert.fail("Rejected uploads must not reach the backend");
    assert.equal((await upload("")).status, 400);
    assert.equal((await upload("?filename=project.zip", "text/plain")).status, 415);
  } finally {
    globalThis.fetch = oldFetch;
    if (oldOrigin === undefined) delete process.env.CODANDY_API_URL;
    else process.env.CODANDY_API_URL = oldOrigin;
  }
});

test("uploaded archives display by name and compare only with the same archive name", () => {
  const upload = name => ({ ...structuredClone(fixture), repository: { source: "archive", name, ref: "upload", analyzed_at: "2026-09-14" } });
  assert.equal(repositoryName(upload("project.zip").repository), "project.zip");
  assert.equal(repositoryName(fixture.repository), "org/repo");
  assert.equal(compareAtlases(upload("project.zip"), upload("Project.zip")).changes.length, 0);
  assert.throws(() => compareAtlases(upload("project.zip"), upload("other.zip")), /same repository/);
  assert.throws(() => compareAtlases(fixture, upload("project.zip")), /same repository/);
});

test("architecture map uses resolved import targets without inventing relationships", () => {
  const node = (id, kind, path, attributes = {}) => ({ id, kind, path, label: id, detail: "", confidence: 80, evidence: [], attributes });
  const edge = (source, target, type, resolution) => ({ source, target, type, resolution, confidence: 80, evidence: [] });
  // `missing` is the undrawn import's local_import value; undefined models an older atlas.
  const sample = missing => ({ nodes: [node("a", "file", "web/app.ts"), node("b", "file", "lib/core.ts"),
    node("i", "import", "web/app.ts", missing === undefined ? {} : { local_import: true }),
    node("missing", "import", "web/app.ts", missing === undefined ? {} : { local_import: missing })],
    relationships: [edge("a", "i", "IMPORTS", "unresolved"), edge("i", "b", "RESOLVES_TO", "inferred"), edge("a", "missing", "IMPORTS", "unresolved")] });
  const legacy = architectureMap(sample(), "folders");
  assert.equal(legacy.links.length, 1);
  assert.equal(legacy.links[0].source, "web");
  assert.equal(legacy.links[0].target, "lib");
  assert.equal(legacy.links[0].inferred, 1);
  // Without the analyzer's classification a package cannot be told from a failed local import.
  assert.deepEqual([legacy.classified, legacy.unresolved, legacy.external], [false, 0, 1]);
  const legacySample = sample();
  assert.deepEqual(architectureMap({ ...legacySample, nodes: [...legacySample.nodes].reverse(), relationships: [...legacySample.relationships].reverse() }, "folders"), legacy);
  const local = architectureMap(sample(true), "folders");
  assert.deepEqual([local.classified, local.unresolved, local.external], [true, 1, 0]);
  const external = architectureMap(sample(false), "folders");
  assert.deepEqual([external.classified, external.unresolved, external.external], [true, 0, 1]);
  assert.equal(architectureMap(sample(), "projects").links.length, 0);
});

test("analyzer marks package imports so the architecture map does not call them unresolved", () => {
  const imported = label => fixture.nodes.find(node => node.kind === "import" && node.label === label);
  assert.equal(imported("react").attributes.local_import, false);
  assert.equal(imported("./other").attributes.local_import, true);
  const graph = architectureMap(fixture, "folders");
  assert.deepEqual([graph.classified, graph.unresolved, graph.external], [true, 0, 1]);
});

test("architecture project map shows only actual project references", () => {
  const graph = architectureMap(fixture, "projects");
  assert.equal(graph.groups.length, 2);
  assert.equal(graph.links.length, 1);
  assert.ok(graph.links.every(link => link.nodeIds.every(id => fixture.nodes.some(node => node.id === id && node.kind === "project"))));
});


test("whiteboard Python storage and frontend contracts agree", async () => {
  const { boardSchema, reviewSchema } = await import("../lib/board-api.ts");
  const result = spawnSync(python, ["-c", "import json; from app.boards import BoardStore, Draft, packet; board = BoardStore(None).create(Draft(title='Contract board')); print(json.dumps({'board': board.model_dump(mode='json'), 'review': packet(board, 'interpret')}))"], { cwd: resolve("backend"), encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  const data = JSON.parse(result.stdout);
  assert.equal(boardSchema.parse(data.board).title, "Contract board");
  assert.equal(reviewSchema.parse(data.review).revision, 1);
  assert.equal(boardSchema.safeParse({ ...data.board, schema_version: "future" }).success, false);
});

const layoutGroup = id => ({ id, label: id, nodeIds: [id], internal: 0 });
const layoutLink = (source, target, count = 1) => ({ source, target, count, inferred: count, nodeIds: [] });
const layoutGroups = ["app", "components", "ui", "lib", "island"].map(layoutGroup);
const layoutLinks = [layoutLink("app", "components", 2), layoutLink("components", "ui", 35), layoutLink("components", "lib", 28), layoutLink("ui", "lib", 57)];

test("layered layout puts importers above their dependencies, deterministically", () => {
  const layout = layeredLayout(layoutGroups, layoutLinks);
  const layerOf = id => layout.nodes.find(node => node.id === id).layer;
  assert.deepEqual(["app", "components", "ui", "lib"].map(layerOf), [0, 1, 2, 3]);
  assert.equal(layout.nodes.find(node => node.id === "island").isolated, true);
  assert.notEqual(layout.isolatedTop, null);
  assert.deepEqual(layout.cycles, []);
  assert.ok(layout.edges.every(edge => !edge.back));
  // components -> lib spans two layers, so it routes through one virtual waypoint between the boxes.
  const long = layout.edges.find(edge => edge.link.source === "components" && edge.link.target === "lib");
  assert.equal(long.points.length, 3);
  assert.match(edgePath(long), /^M [\d.]+ [\d.]+ C .+ C .+$/);
  assert.ok(layout.nodes.every(node => node.x >= 0 && node.x + node.width <= layout.width && node.y + node.height <= layout.height));
  assert.deepEqual(layeredLayout(layoutGroups, layoutLinks), layout);
  const reversed = layeredLayout([...layoutGroups].reverse(), [...layoutLinks].reverse());
  assert.deepEqual(["app", "components", "ui", "lib"].map(id => reversed.nodes.find(node => node.id === id).layer), [0, 1, 2, 3]);
});

test("layered layout draws import cycles as back edges instead of hiding them", () => {
  const layout = layeredLayout(layoutGroups, [...layoutLinks, layoutLink("lib", "components", 3)]);
  assert.deepEqual(layout.cycles, [["components", "ui", "lib"]]);
  assert.deepEqual(layout.edges.filter(edge => edge.back).map(edge => [edge.link.source, edge.link.target]), [["lib", "components"]]);
  assert.ok(layout.edges.filter(edge => edge.link.source !== "app").every(edge => edge.cyclic));
  assert.equal(layout.edges.find(edge => edge.link.source === "app").cyclic, false);
  // Back edges bulge to the right, so the canvas reserves room for them.
  assert.ok(layout.width > layeredLayout(layoutGroups, layoutLinks).width);
});

test("dependency matrix keeps forward dependencies above the diagonal and cycles below it", () => {
  const clean = dependencyMatrix(layoutGroups, layoutLinks);
  assert.deepEqual(clean.order, ["app", "components", "ui", "lib", "island"]);
  assert.ok(clean.cells.every(cell => !cell.below && cell.row < cell.column));
  assert.equal(clean.max, 57);
  const cyclic = dependencyMatrix(layoutGroups, [...layoutLinks, layoutLink("lib", "components", 3)]);
  assert.deepEqual(cyclic.cells.filter(cell => cell.below).map(cell => [cell.source, cell.target]), [["lib", "components"]]);
  assert.deepEqual(cyclic.cycles, [["components", "ui", "lib"]]);
});

test("architecture map splits an expanded folder into its subfolders", () => {
  const node = (id, kind, path, attributes = {}) => ({ id, kind, path, label: id, detail: "", confidence: 80, evidence: [], attributes });
  const edge = (source, target, type) => ({ source, target, type, resolution: type === "IMPORTS" ? "unresolved" : "inferred", confidence: 80, evidence: [] });
  const sample = {
    nodes: [node("a", "file", "components/a.tsx"), node("b", "file", "components/ui/button.tsx"), node("u", "file", "lib/utils.ts"),
      node("ia", "import", "components/a.tsx", { local_import: true }), node("ib", "import", "components/ui/button.tsx", { local_import: true })],
    relationships: [edge("a", "ia", "IMPORTS"), edge("ia", "b", "RESOLVES_TO"), edge("b", "ib", "IMPORTS"), edge("ib", "u", "RESOLVES_TO")],
  };
  const collapsed = architectureMap(sample, "folders", 1);
  assert.deepEqual(collapsed.groups.map(group => group.id).sort(), ["components", "lib"]);
  assert.deepEqual(collapsed.links.map(link => [link.source, link.target, link.count]), [["components", "lib", 1]]);
  assert.equal(collapsed.groups.find(group => group.id === "components").internal, 1);
  const expanded = architectureMap(sample, "folders", 1, new Set(["components"]));
  assert.deepEqual(expanded.groups.map(group => group.id).sort(), ["components", "components/ui", "lib"]);
  assert.deepEqual(expanded.links.map(link => [link.source, link.target]).sort(), [["components", "components/ui"], ["components/ui", "lib"]]);
});

const structureGenerated = spawnSync(python, ["-c", `
import tempfile
from pathlib import Path
from app.analyzer import analyze_repository
from app.settings import Settings
from app.structure.extract import extract_structure
files = {
    'db/schema.sql': 'CREATE TABLE users (id int PRIMARY KEY, email text NOT NULL UNIQUE);\\nCREATE TABLE orders (id int PRIMARY KEY, user_id int NOT NULL REFERENCES users(id), parent_id int REFERENCES orders(id));\\nCREATE TABLE reviews (id int PRIMARY KEY, author_id int REFERENCES accounts(id));\\nCREATE TABLE \`x"; click\` (id int);\\nCREATE TABLE settings (key text);\\n',
    'api/models.py': 'from pydantic import BaseModel\\n\\nclass Base(BaseModel):\\n    id: int\\n\\nclass Money(Base):\\n    amount: str\\n\\nclass Order(Base):\\n    total: Money\\n    note: str | None = None\\n',
    'api/extra/refund.py': 'from pydantic import BaseModel\\n\\nclass Refund(BaseModel):\\n    amount: Money\\n',
    'web/types.ts': 'export type Customer = { id: string; orders: OrderSummary[] };\\nexport interface OrderSummary { id: string; customer: Customer }\\n',
}
with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding='utf-8')
    settings = Settings()
    atlas = analyze_repository(root, 'https://github.com/org/repo.git', None, settings, lambda *_: None)
    print(extract_structure(root, atlas, settings).model_dump_json())
`], { cwd: resolve("backend"), encoding: "utf8", env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
assert.equal(structureGenerated.status, 0, structureGenerated.stderr);
const structureFixture = JSON.parse(structureGenerated.stdout);
const sqlSource = document => document.sources.find(source => source.kind === "sql");
const tableId = (document, table) => document.entities.find(entity => entity.table === table).id;

test("frontend accepts a Python-generated structure document and rejects dangling references", () => {
  const structure = structureSchema.parse(structureFixture);
  assert.deepEqual(structure.entities.map(entity => entity.table).sort(), ["orders", "reviews", "settings", "users", 'x"; click']);
  assert.equal(structureSchema.safeParse({ ...structureFixture, schema_version: "structure-9" }).success, false);
  const dangling = structuredClone(structureFixture);
  const resolved = dangling.entity_links.find(link => link.resolution === "resolved");
  resolved.target.entity = "entity:missing";
  assert.equal(structureSchema.safeParse(dangling).success, false);
  const stray = structuredClone(structureFixture);
  stray.type_links[0].target = "type:missing";
  assert.equal(structureSchema.safeParse(stray).success, false);
});

test("ERD view puts referenced tables left of the tables that reference them", () => {
  const structure = structureSchema.parse(structureFixture);
  const source = sqlSource(structure);
  const view = erdView(structure, source.id);
  const stub = view.records.find(record => record.stub);
  assert.deepEqual([stub.title, stub.refId], ["accounts", null]);
  const records = view.records.map(record => ({ id: record.id, rows: record.rows.length }));
  const layout = recordLayout(records, view.links);
  const x = id => layout.records.find(record => record.id === id).x;
  assert.ok(x(tableId(structure, "users")) < x(tableId(structure, "orders")));
  assert.ok(x(stub.id) < x(tableId(structure, "reviews")));
  assert.equal(layout.edges.find(edge => edge.self).link.source, tableId(structure, "orders"));
  const user = view.links.find(link => link.source === tableId(structure, "users"));
  assert.deepEqual([user.start, user.end], [{ cardinality: "one", optional: false }, { cardinality: "many", optional: true }]);
  assert.equal(view.records.find(record => record.id === tableId(structure, "orders")).rows[user.targetRow].name, "user_id");
  assert.ok(layout.records.every(record => record.x >= 0 && record.y >= 0 && record.x + record.width <= layout.width && record.y + record.height <= layout.height));
  assert.deepEqual(recordLayout(records, view.links), layout);
  const focused = erdView(structure, source.id, { focus: tableId(structure, "users") });
  assert.deepEqual(focused.records.map(record => record.title).sort(), ["orders", "users"]);
  const keys = erdView(structure, source.id, { keysOnly: true }).records.find(record => record.title === "users");
  assert.deepEqual([keys.rows.map(row => row.name), keys.hiddenRows], [["id"], 1]);
});

test("record layout routes cycles right to left and long links through waypoints", () => {
  const records = ["a", "b", "c", "d"].map(id => ({ id, rows: 2 }));
  const link = (source, target) => ({ id: `${source}-${target}`, source, target });
  const layout = recordLayout(records, [link("a", "b"), link("b", "c"), link("a", "c"), link("c", "a")]);
  const at = id => layout.records.find(record => record.id === id);
  assert.deepEqual(layout.cycles, [["a", "b", "c"]]);
  const back = layout.edges.find(edge => edge.back);
  assert.deepEqual([back.link.id, back.points[0].x, back.points[1].x], ["c-a", at("c").x, at("a").x + at("a").width]);
  assert.equal(layout.edges.find(edge => edge.link.id === "a-c").points.length, 4);
  assert.equal(at("d").isolated, true);
  assert.notEqual(layout.isolatedTop, null);
  assert.match(recordEdgePath(back), /^M [\d.]+ [\d.]+ C /);
});

test("Mermaid exports use safe identifiers and follow declared cardinality", () => {
  const structure = structureSchema.parse(structureFixture);
  const source = sqlSource(structure);
  const text = mermaidErDiagram(structure.entities.filter(entity => entity.source_id === source.id), structure.entity_links.filter(link => link.source_id === source.id));
  assert.match(text, /^erDiagram\n/);
  assert.match(text, /\n {4}users \|\|--o\{ orders : "user_id"\n/);
  assert.match(text, /\n {4}orders \|o--o\{ orders : "parent_id"\n/);
  assert.match(text, /\n {4}%% not drawn: reviews references accounts \(unresolved\)\n/);
  assert.match(text, /\n {4}x_click \{\n {8}int id\n/);
  assert.match(text, /\n {8}text email UK\n/);
  assert.equal(text.includes('";'), false);
  const classes = mermaidClassDiagram(structure.types, structure.type_links);
  assert.match(classes, /\n {4}Base <\|-- Money\n/);
  assert.match(classes, /\n {4}Order --> Money : total\n/);
  assert.match(classes, /\n {4}Refund \.\.> Money : amount\n/);
  assert.match(classes, /\n {8}str_None note\n/);
});

test("contract view narrows to a folder and keeps types it references elsewhere visible", () => {
  const structure = structureSchema.parse(structureFixture);
  assert.deepEqual(contractAreas(structure).map(area => [area.id, area.count]), [["api", 3], ["web", 2], ["api/extra", 1]]);
  const models = contractsView(structure, { area: "api" });
  assert.deepEqual(models.records.map(record => record.title).sort(), ["Base", "Money", "Order"]);
  const order = models.records.find(record => record.title === "Order");
  const total = models.links.find(link => link.source === order.id && link.kind === "field");
  assert.equal(order.rows[total.sourceRow].name, "total");
  assert.equal(contractsView(structure, { area: "api", inheritance: false }).links.some(link => link.kind === "extends"), false);
  const extra = contractsView(structure, { area: "api/extra" });
  assert.deepEqual(extra.records.map(record => [record.title, record.stub]), [["Refund", false], ["Money", true]]);
  assert.equal(extra.links[0].dashed, true);
  const customer = structure.types.find(type => type.name === "Customer").id;
  assert.deepEqual(contractsView(structure, { focus: customer }).records.map(record => record.title).sort(), ["Customer", "OrderSummary"]);
});

test("hosted proxy forwards structure requests without the caller's query string", async () => {
  const oldFetch = globalThis.fetch;
  const oldOrigin = process.env.CODANDY_API_URL;
  const id = "00000000-0000-4000-8000-000000000000";
  process.env.CODANDY_API_URL = "https://backend.example.com";
  try {
    globalThis.fetch = async url => {
      assert.equal(url.pathname, `/api/analyses/${id}/structure`);
      assert.equal(url.search, "");
      return Response.json(structureFixture);
    };
    const response = await GET(new Request(`https://atlas.example.com/api/analyses/${id}/structure?token=leak`));
    assert.equal(response.status, 200);
    assert.equal(structureSchema.safeParse(await response.json()).success, true);
  } finally {
    globalThis.fetch = oldFetch;
    if (oldOrigin === undefined) delete process.env.CODANDY_API_URL;
    else process.env.CODANDY_API_URL = oldOrigin;
  }
});


test("OTLP trace contract preserves nanosecond offsets and independent trace parents", async () => {
  const { traceSchema, traceRows } = await import("../lib/trace-api.ts");
  const result = spawnSync(python, ["-c", "import json; from tests.test_traces import fixture; from app.debugging.traces import normalize_trace_bytes; print(normalize_trace_bytes(json.dumps(fixture()).encode()).model_dump_json())"], { cwd: resolve("backend"), encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  const trace = traceSchema.parse(JSON.parse(result.stdout));
  const rows = traceRows(trace, "a".repeat(32));
  assert.equal(rows[1].offsetMs, 0.000001);
  assert.equal(rows[1].depth, 1);
  assert.equal(rows[1].span.status, "error");
  assert.deepEqual(traceRows(trace, "b".repeat(32)), []);
});

const stackFrame = (index, fn, path, line, inApp = true, asyncBoundary = false) => ({ index, provider_index: index, function: fn, module: null, path, abs_path: null, line, column: null, in_app: inApp, after_async_boundary: asyncBoundary, context: [] });
const stackException = { index: 0, type: "TypeError", value: "Cannot read properties of undefined", module: null, relation_to_next: null, provider_exception_id: null, provider_parent_id: null, handled: false, frames_omitted: 3, frames: [
  stackFrame(0, "handle", "node_modules/express/router.js", 10, false),
  stackFrame(1, "dispatch", "node_modules/express/layer.js", 20, false),
  stackFrame(2, "checkout", "src/routes/orders.ts", 30),
  stackFrame(3, "loadCart", "src/routes/orders.ts", 44),
  stackFrame(4, "fetchPrices", "src/services/pricing.ts", 12, true, true),
] };

test("stack sequence follows observed caller-to-callee order and ends at the raise", async () => {
  const { mermaidSequence, stackSequence } = await import("../lib/sequence-diagram.ts");
  const all = stackSequence(stackException);
  assert.deepEqual(all.participants.map(item => item.label), ["Entry point", "router.js", "layer.js", "orders.ts", "pricing.ts"]);
  assert.deepEqual(all.messages.map(item => [item.kind, item.label]), [["call", "handle()"], ["call", "dispatch()"], ["call", "checkout()"], ["call", "loadCart()"], ["async", "fetchPrices()"], ["raise", "raises TypeError"]]);
  assert.equal(all.messages[3].from, all.messages[3].to);
  assert.ok(all.messages.filter(item => item.kind !== "raise").every(item => item.activeUntil === all.messages.length - 1));
  assert.ok(all.notes.some(note => note.includes("3 frames were omitted")));
  const app = stackSequence(stackException, { appOnly: true });
  assert.deepEqual([app.messages[0].kind, app.messages[0].label], ["gap", "2 hidden frames, then checkout()"]);
  assert.equal(app.participants.some(item => item.label === "router.js"), false);
  assert.equal(stackSequence(stackException, { groupBy: "function" }).participants.length, 6);
  const trimmed = stackSequence(stackException, { limit: 3 });
  assert.deepEqual([trimmed.messages.length, trimmed.omitted, trimmed.messages.map(item => item.activeUntil)], [3, 3, [2, 2, null]]);
  const text = mermaidSequence(all);
  assert.match(text, /^sequenceDiagram\n {4}participant P1 as Entry point\n/);
  assert.match(text, /\n {4}P4->>P4: loadCart\(\)\n/);
  assert.match(text, /\n {4}P4-\)P5: fetchPrices\(\)\n/);
  assert.match(text, /\n {4}Note over P5: raises TypeError\n/);
  const hostile = mermaidSequence(stackSequence({ ...stackException, frames: [stackFrame(0, 'run"; click', "src/a;#<b>{c}.ts", 1)] }));
  // Arrows such as ->> legitimately contain ">", so check the characters labels must lose.
  assert.equal(/[;#<{}"]/.test(hostile), false);
  assert.equal(hostile.includes("b>"), false);
});

test("stack sequence accepts normalized Python Sentry evidence", async () => {
  const { stackSequence } = await import("../lib/sequence-diagram.ts");
  const result = spawnSync(python, ["-c", `
from pathlib import Path
from app.debugging.sentry_event import normalize_sentry_event_bytes
print(normalize_sentry_event_bytes(Path('tests/fixtures/debugging/sentry_python_chained.json').read_bytes()).model_dump_json())
`], { cwd: resolve("backend"), encoding: "utf8", env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
  assert.equal(result.status, 0, result.stderr);
  const observation = observationSchema.parse(JSON.parse(result.stdout));
  assert.ok(observation.exceptions.length > 1);
  for (const exception of observation.exceptions) {
    const view = stackSequence(exception);
    const ids = new Set(view.participants.map(item => item.id));
    assert.ok(view.messages.every(item => ids.has(item.from) && ids.has(item.to)));
    assert.equal(view.messages.filter(item => item.kind === "raise").length, exception.frames.length ? 1 : 0);
  }
});

test("trace sequence draws parent services to child services in start order", async () => {
  const { mermaidSequence, traceSequence } = await import("../lib/sequence-diagram.ts");
  const span = (id, parent, service, name, start, end, extra = {}) => ({ trace_id: "c".repeat(32), span_id: id.repeat(16), parent_id: parent ? parent.repeat(16) : null, name, service, start_ns: String(start), end_ns: String(end), status: "unset", parent_state: parent ? "present" : "root", attributes: {}, ...extra });
  const trace = { schema_version: "trace-0.1", omitted_spans: 0, withheld_attributes: 0, redactions: [], limitations: [], spans: [
    span("1", null, "web", "GET /checkout", 1_000_000, 90_000_000),
    span("2", "1", "api", "POST /orders", 2_000_000, 80_000_000),
    span("3", "2", "api", "validate cart", 3_000_000, 4_000_000),
    span("4", "2", "db", "INSERT orders", 5_000_000, 70_000_000, { status: "error" }),
    span("5", "9", "worker", "send email", 6_000_000, 7_000_000, { parent_state: "missing" }),
  ] };
  const id = "c".repeat(32);
  const view = traceSequence(trace, id);
  assert.deepEqual(view.participants.map(item => item.label), ["Outside this trace", "web", "api", "db", "worker"]);
  assert.deepEqual(view.messages.map(item => [item.from, item.to, item.label]), [["outside", "service:web", "GET /checkout"], ["service:web", "service:api", "POST /orders"], ["service:api", "service:api", "validate cart"], ["service:api", "service:db", "INSERT orders"], ["outside", "service:worker", "send email"]]);
  assert.deepEqual(view.messages.map(item => item.activeUntil), [3, 3, 2, 3, 4]);
  assert.deepEqual([view.messages[3].error, view.messages[1].durationMs, view.messages[4].offsetMs], [true, 78, 5]);
  assert.match(view.messages[4].detail, /parent span is not in this import/);
  assert.match(mermaidSequence(view), /\n {4}P3-xP4: INSERT orders \(65\.0 ms\)\n/);
  const limited = traceSequence(trace, id, { limit: 2 });
  assert.deepEqual([limited.omitted, limited.messages.map(item => item.activeUntil), limited.participants.map(item => item.label)], [3, [1, 1], ["Outside this trace", "web", "api"]]);
  assert.deepEqual(traceSequence(trace, "d".repeat(32)).messages, []);
});
