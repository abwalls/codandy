> Historical document, superseded by the root PLAN.md and ROADMAP.md. Capability claims and deferrals below are not current status.

# Codandy architecture

## Local subscription assistant

Opt-in `CODANDY_CODEX_ENABLED` starts an installed Codex App Server over private stdio. A dedicated ignored `CODANDY_CODEX_HOME` stores Codex-managed sign-in state; Codandy never reads or copies the normal Codex profile's auth tokens. Browser OAuth is initiated through `account/login/start`, and only an official auth.openai.com URL is returned. `account/read` must report ChatGPT authentication; no API-key fallback is offered.

The local `/api/analyses/assistant/*` routes require a loopback peer/host, a custom client header, and an approved local Origin when present. The hosted proxy does not forward them. This is a single-user local integration, not shared-server subscription pooling or hosted end-user authentication.

Model and reasoning choices come from `model/list` and are checked again on submission. Questions use retained backend atlas nodes, at most 24 nodes and 40 internal relationships in a 64 KB prompt. Source bodies and arbitrary client context are not accepted. Codex runs in an isolated empty context directory with read-only permissions, tools/features disabled, and no user-profile MCP/plugin configuration. Permission requests are refused. Responses are schema-validated and cited IDs must belong to the supplied excerpt; this does not prove every generated claim. Each question uses an ephemeral thread with a bounded response timeout.

## Source of truth

Every analysis produces a versioned `.codandy/atlas.json`. UI pages and AI tools query this artifact instead of relying on free-form model memory.

## Universal graph

Initial node types include repository, project, directory, file, namespace, class, interface, method, route, component, database entity, queue, and external service.

Initial edge types include `CONTAINS`, `IMPORTS`, `CALLS`, `IMPLEMENTS`, `INHERITS`, `DEPENDS_ON`, `ROUTES_TO`, `READS`, `WRITES`, `PUBLISHES`, `CONSUMES`, `RENDERS`, and `TESTS`.

Stable identities use deterministic names such as:

```text
method:csharp:Northstar.Auth.LoginHandler.Handle
route:http:POST:/api/auth/login
component:typescript:client/src/features/auth/LoginForm
```

## Pipeline

```text
Repository input
  -> safe ingestion
  -> project detection
  -> language analyzers
  -> universal code graph
  -> evidence rules
  -> AI enrichment
  -> atlas.json
  -> interactive report
```

## Analyzer boundary

The Python API coordinates a registry of analyzers. Tree-sitter provides broad syntax coverage for C#, TypeScript/TSX, JavaScript/JSX, Python and Go; grammars load lazily per repository. Deeper semantic analyzers run as separate adapters, including a future Roslyn CLI for .NET and TypeScript Compiler API worker for React/TypeScript.

The `tree-sitter` core is pinned below 0.26 because 0.26.0 corrupts memory during the point-then-children node walk the analyzer performs, segfaulting the parser process on ordinary sources.

The analyzer runs in a spawned disposable process. The parent
forwards progress over SSE, validates the returned artifact, and terminates the process
on deadline or failure. Native parser crashes are contained within that process.
This process executes Codandy's own static analyzer only, never repository tooling.

## Source viewer boundary

`atlas.json` stays a graph document and never embeds source bodies. So that evidence
remains readable after the disposable workspace is destroyed, the API captures the text of
indexed files while the clone still exists, within per-file and total byte budgets, and
serves it from `GET /analyses/{id}/source?path=...`.

Only paths the analyzer already indexed as file nodes are addressable, so the endpoint is a
map lookup with no request-time disk access, and secret-matched, binary and excluded paths
are unreachable. Retained text is evicted with its report, so a downloaded atlas carries
the graph while the viewer needs the live service.

## Frontend data boundary

React validates job events and artifacts with Zod contracts in lib/analysis-api.ts.
Real reports consume the backend schema directly; the illustrative banking atlas is a
separate sample model. EventSource reconnects using event IDs, with status polling to
recover missed terminal events and detect expired jobs or API restarts.

Local Vite development proxies /api/analyses to FastAPI on port 8000. Hosted builds
forward those routes to the HTTPS origin configured by CODANDY_API_URL. The Python
service needs separate hosting; the Sites Worker cannot run Git or native Python parsing.

## Future debugging boundary

Runtime observations remain separate from static facts and attach through stable node IDs. A debugging finding records affected nodes, severity, evidence, hypotheses, and recommended solutions without mutating the base atlas.


## Local report snapshots

Optional `CODANDY_REPORT_ROOT` stores completed job/atlas/source/event snapshots under generated job UUID filenames. Writes use a same-directory temporary file, flush/fsync and atomic replacement before publishing completion. Restart restores validated complete jobs; interrupted jobs are not resumed. Retention follows max_jobs with a 128 MB per-snapshot cap. Source endpoints remain map lookups after restoration, never arbitrary request-time file reads. A failed save fails the job explicitly.

This directory must be owned by one API process. It adds local durability only; distributed job coordination, authentication, shared storage, and hosted deployment are still future work. GET /api/analyses returns retained completed-report metadata plus whether local persistence is enabled.

## Dependency metadata boundary

Dependency nodes carry sanitized version attributes and optional lockfile evidence. No package manager runs. POST /api/analyses/{id}/dependencies?node_id=... looks up an existing dependency node only; clients cannot supply provider URLs or substitute package names. Explicit checks use bounded HTTPS requests to fixed public registry hosts and OSV. Live advisory/update observations stay separate from deterministic atlas facts and are labeled with timestamps, version basis, unknown/incomplete states and runtime limitations.
