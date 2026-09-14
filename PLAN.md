# Codandy product and delivery plan

## Direction

Codandy is becoming a debugging and investigation workspace: bring an error or slow operation, connect it to the relevant source, investigate with evidence, sketch a plan, and hand a reviewable debugging brief to an AI assistant or IDE.

The primary workflow is **Connect → Investigate → Understand → Plan → Verify**. Repository analysis supports that workflow. Sentry integration and stack investigation are the immediate priority; generic repository reports and pre-merge risk scoring are no longer the headline roadmap.

This plan supersedes the previous milestone ordering and debugging deferral. It does not claim the new features exist. See [ROADMAP.md](ROADMAP.md) for delivery gates, [ARCHITECTURE.md](ARCHITECTURE.md) for boundaries, and [the strategy review](docs/DEBUGGING-STRATEGY.md) for research and assessment of the supplied proposal. The prior plan and status report are retained under docs/archive/ as historical records.

## Current baseline

Implemented: bounded static GitHub analysis across five language families; file/symbol/source inspection; partial route and local-call inference; dependency inventory and checks; graph-based reports; local report persistence; snapshot comparisons; themes; and independent, evidence-scoped questions through a local Codex subscription connection. The current implementation also supports bounded ZIP project uploads, an interactive Architecture dependency map, local saved investigations, conservative frame/source candidates and reviewed debugging briefs with local Codex Q&A. Current validation: 221 backend tests, 28 frontend contracts and desktop/mobile headless Edge workflow checks; see progress.md for build and publication checkpoints.

Not implemented: Sentry project/issue browsing, independently verified runtime revision binding, trace/profile analysis, live debugger control, whiteboards, private Git provider authentication, trusted local-folder indexing and a Codandy MCP server. The read-only Sentry event connector is implemented but still awaits a real authorized account test. The hosted frontend remains separate from local Python analysis and subscription AI.

## Initial audience and product promise

Start with a developer investigating an exception in a TypeScript/React or Python service, with C#/.NET stack support included in the first release gate. Sentry Cloud is the provisional first connector target; confirm account/region before a live integration test. A bounded JSON or pasted-stack import must work without a Sentry account. Other languages remain explicitly unsupported by the stack parser until tested, even when the static analyzer supports them.

Promise: a developer can locate the evidence behind an incident, see what is missing, preserve an investigation, and prepare a useful next action. Do not promise automatic root cause, a replacement IDE, production telemetry collection, or a verified fix without verification evidence.

## Navigation and core interaction

| Area | Purpose | Delivery |
|---|---|---|
| Investigations | Saved cases, imported errors, recent work and next actions | First landing area when functional |
| Errors | Sentry issue list and selected event, filtered by project/environment/release | First connector slice |
| Stack & Source | Ordered exception frames, source pane, binding status and related code | First investigation slice |
| Performance | Observed spans and imported profiles with explicit measurement basis | After exception workflow |
| Whiteboard | Free drawing, evidence cards and structured debugging plans | First usable board in v1 |
| Codebase | Existing overview, symbols, architecture, dependencies and snapshots | Retained supporting tools |
| Integrations | Sentry connection, project/repository mappings and AI status | First connector slice |

Use one investigation ID across these views. Ask Codandy receives the selected case context, not whichever global report happened to be open. A planned area should not look implemented: add a navigation item only when it opens a useful view, or label its unavailable state clearly.

## D1 — Sentry-to-source investigation: immediate work

Deliver a narrow vertical slice with fixtures first, then a real read-only connection.

1. Add versioned observation, stack frame, source-binding and investigation contracts in Python and TypeScript. Keep atlas 0.2 unchanged. Add a synthetic, non-sensitive fixture corpus and validation of size, depth, frame count and truncation.
2. Implement one normalization path for a supported Sentry REST event JSON and a pasted stack. Preserve exception chains and provider frame ordering; record how each adapter interprets it. Keep SDK payload formats distinct from REST response formats.
3. Add the read-only Sentry adapter: local connection status, project selection, bounded issue listing, issue detail and explicit event retrieval. Use a backend-held, scoped token; never a DSN as the read credential. No browser localStorage tokens, no credentials in reports or assistant prompts.
4. Bind frames against a selected, pinned repository snapshot using configured path mappings and file/line evidence. Represent exact, candidate, ambiguous and unmapped results. A release label is not automatically a Git SHA; unknown or mismatched revisions remain visible.
5. Build Errors → Stack & Source → Save investigation. Opening a frame must use captured/indexed source, never an arbitrary filesystem path from telemetry. Offer Open in Sentry even when binding fails.
6. Persist sanitized cases independently of expiring analysis jobs. Retain a referenced snapshot explicitly or show that its source has expired. Refreshing an issue creates another observation, not an overwrite of prior evidence.
7. Connect Ask Codandy and export a debugging brief: observations, relevant source references, hypotheses, missing evidence and verification steps. Explicit review precedes AI submission; existing graph-only requests are not silently expanded to include telemetry.

**Done when:** a real authorized Sentry event can be opened, mapped where evidence allows, saved/reopened after restart, and exported with correct citations. Fixtures cover TS/JS, Python and .NET; missing source maps, duplicate filenames, async/inner exceptions, unavailable source, revision mismatch, bad credentials, 403/404, 429, malformed responses and cancellation. No injected secrets survive into saved cases or AI exports in the test corpus. Fixtures alone do not qualify as a live integration.

**Initial engineering bounds (tunable, not provider limits):** 2 MiB per imported event/stack payload, JSON depth 32, 200 frames across a case import, 20 exception records, 200 breadcrumbs, a bounded 50-issue list page, at most three provider GET attempts with deadline/backoff, and a visible result for every omitted/truncated section. Reject decompression expansion above the byte budget. Never crawl an entire organization implicitly.

## D2 — Investigation quality and source access

Add evidence-pinned follow-ups, hypothesis status (proposed/contradicted/supported), explicit verification attachments and redaction preview. Prioritize source mapping precision over mapping every frame. Prepare signed fixtures with known source revisions for evaluation; track exact-binding precision, mapping coverage and ambiguous/unmapped rates separately.

Private repositories are a material adoption dependency: allow imported validated atlas/source bundles first; design trusted local-folder indexing next, with explicit folder selection and all static-analysis exclusions retained. Do not obtain private source by reusing a Sentry token. Git provider OAuth and remote private cloning are later, separately authorized connectors.

## D3 — Performance investigation

Start with a bounded imported OTLP JSON trace, then evaluate a supported Sentry trace API on the target account. Render a waterfall with gaps, concurrency and links. Bind spans only where code attributes or explicit service/repository mappings support it. Missing telemetry means unavailable, not zero.

Add one profile format through an isolated adapter after a compatibility spike. Distinguish span wall time from sampled stack weight and from CPU time. Show units, window, sampling and included population. Compute quantiles only from a suitable event set with sample count disclosed. Never manufacture per-function time from an exception stack or source size. Cross-release comparisons require comparable windows, environments and measurement definitions.

**Done when:** a seeded slow-operation fixture exposes the expected measured bottleneck, overlapping spans are not double-counted, missing parents remain visible, and the UI describes every metric's provenance. Live provider profile access is a separate capability gate; a product UI screenshot is not an API contract.

## D4 — Whiteboard and AI planning

Adopt an embedded Excalidraw spike: freehand, shapes, text, arrows, undo/redo and pan/zoom. Keep a structured board document separate from its rendered image. Add evidence cards pinned to an investigation, frame, node or span; distinguish observed evidence, user annotations, hypotheses and proposed work.

Store boards locally with autosave, explicit delete and lossless JSON export/import. Export selected content as PNG plus a Markdown debugging brief and machine-readable references. A plan brief contains objective, evidence, assumptions, ordered tasks and acceptance criteria. AI-proposed changes to a board require review; drawn arrows never become code-graph relationships automatically.

**Done when:** a board survives reload, can be exported/reimported, and generates a useful brief without an image-capable model. Bound attachments/scene size; sanitize links and imported markup; do not render untrusted SVG/HTML or auto-fetch remote images. Keyboard-accessible text/evidence editing and a usable small-screen fallback are release requirements. Realtime collaboration, public sharing and image interpretation are later.

## D5 — Agent and IDE interoperability

Expose a small read-only Codandy MCP surface backed by the same validated services: get investigation, get evidence, find symbol, get related code, export brief. Returned content retains provenance and uncertainty. Do not attach a broad Sentry MCP server to the current tool-disabled Codex bridge without a separate permission design. Direct provider API ingestion and agent-facing MCP serve different roles.

Start IDE integration with reviewed file/line links or exported tasks. A later Debug Adapter Protocol proof of concept must use an explicitly selected trusted local project and adapter. Breakpoints, stepping, variable inspection and evaluation are separate from artifact analysis. No launch, attach, test execution or expression evaluation in the untrusted repository analyzer.

## D6 — Optional change verification and team workflows

After investigation usage is demonstrated, add diff-to-symbol mapping, suggested relevant tests and imported coverage/results. Calibrate any impact/risk rubric before presenting numerical risk scores. Static test filenames are not coverage; a migration filename does not prove irreversibility. PR comments, issue mutations and generated fixes require explicit write scope and review.

Webhooks, multi-user storage/auth, hosted workers, multiple providers and collaboration follow measured demand. Before webhooks, design a public HTTPS receiver with signature verification, deduplication, installation lifecycle and durable jobs. Do not expose the localhost assistant to receive external callbacks.

## v1 release boundary

v1 includes D1, the essential persistence/evidence improvements in D2, a bounded trace/performance viewer from D3 and a single-user board/brief flow from D4. It does not require native debugger control, full MCP orchestration, an APM backend, replay recording, calibrated risk scoring or a multi-tenant SaaS. These are independent later gates.

Measure time to locate relevant source and produce a reviewable next step on a labeled incident corpus; successful save/reopen/export; binding errors; unwanted sensitive-data exposure; and whether developers return for a second case. Targets are proposed validation gates, not current performance claims. Set numerical latency/quality budgets from the first representative corpus rather than inventing market statistics.

## First implementation handoff

Next coding slice: D1 contracts, redaction/normalization and TS/Python/.NET fixtures, followed immediately by one read-only Sentry event request and its UI. Suggested modules: backend/app/debugging/{models,normalize,redaction,binding,store}.py; backend/app/integrations/sentry.py; backend/app/routers/investigations.py; lib/investigation-api.ts; components/investigations/. These are proposed paths, not existing modules.

Keep work scoped to this path until the first live issue-to-source flow is demonstrable. Do not begin by adding risk scores, a debugger engine, broad log ingestion or an empty set of sidebar pages.


### D1 implementation checkpoint — 2026-09-14

Normalization contracts and synthetic fixtures now support Sentry REST events plus Python, JS and .NET stacks. `/debugging` adds a local import/inspection/redaction-review/export flow and backend-only Sentry Cloud configuration with explicit event retrieval. One GET per request is deliberate (manual retry, bounded deadline), below the three-attempt maximum. No live credential test has occurred. Project/issue browsing, revision-aware bindings, durable investigations and reviewed AI briefs are still pending; D1 is not complete.
