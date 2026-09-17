# Codandy product and delivery plan

## Direction

Codandy is becoming a debugging and investigation workspace: bring an error or slow operation, connect it to the relevant source, investigate with evidence, sketch a plan, and hand a reviewable debugging brief to an AI assistant or IDE.

The primary workflow is **Connect → Investigate → Understand → Plan → Verify**. Repository analysis supports that workflow. Sentry integration and stack investigation are the immediate priority; generic repository reports and pre-merge risk scoring are no longer the headline roadmap.

This plan supersedes the previous milestone ordering and debugging deferral. It does not claim the new features exist. See [ROADMAP.md](ROADMAP.md) for delivery gates, [ARCHITECTURE.md](ARCHITECTURE.md) for boundaries, and [the strategy review](docs/DEBUGGING-STRATEGY.md) for research and assessment of the supplied proposal. The prior plan and status report are retained under docs/archive/ as historical records.

## Current baseline

Implemented: bounded static GitHub analysis across five language families; file/symbol/source inspection; partial route and local-call inference; dependency inventory and checks; graph-based reports; local report persistence; snapshot comparisons; themes; and independent, evidence-scoped questions through a local Codex subscription connection. The current implementation also supports bounded ZIP project uploads, an interactive Architecture dependency map, local saved investigations, conservative frame/source candidates and reviewed debugging briefs with local Codex Q&A. Current validation: 221 backend tests, 28 frontend contracts and desktop/mobile headless Edge workflow checks; see progress.md for build and publication checkpoints.

Not implemented: Sentry project/issue browsing, independently verified runtime revision binding, profile analysis, live debugger control, private Git provider authentication, trusted local-folder indexing and a Codandy MCP server. The read-only Sentry event connector is implemented but still awaits a real authorized account test. The hosted frontend remains separate from local Python analysis and subscription AI.

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

**2026-09-14 update:** Andrew made the Whiteboard the next implementation track and broadened its scope. A user draws a system, for example a cloud architecture. The AI interprets the drawing, asks clarifying questions, and produces an agent-ready `plan.md` plus a human-readable ticket, report page and GitHub issue draft. Boards can optionally link to a retained repository snapshot, and the local Codex subscription connection remains the AI provider. The detailed plan, with milestones W0–W6, is in [docs/WHITEBOARD-PLAN.md](docs/WHITEBOARD-PLAN.md). The D1 Sentry live gate stays open and proceeds when an account is available.

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


### Whiteboard delivery checkpoint — 2026-09-14

The first usable whiteboard loop is implemented at `/whiteboard`: local drawing/CRUD/autosave, revision conflicts, reviewed text interpretation, user corrections, reviewed structured plans, saved plan versions, optional retained snapshot context, Markdown/ticket downloads, printable text and issue-draft copy. A live synthetic interpretation and plan both succeeded using the existing local Codex subscription connection. The longer W0–W5 gates are not wholly complete; see the implementation review in docs/WHITEBOARD-PLAN.md for the exact boundaries and remaining work.


### Integrations plan — 2026-09-15

[docs/INTEGRATIONS-PLAN.md](docs/INTEGRATIONS-PLAN.md) plans three groups of connectors:

- **Monitoring:** finishing the Sentry connector, OpenTelemetry trace import and a local receiver, and Datadog errors and spans.
- **Ticketing:** Linear, ClickUp and Jira Cloud.
- **Supporting:** GitHub private repositories, CI test and coverage evidence, and IDE links.

It extends D1b/D1d, D3 and D6 on these terms: monitoring is read-only; credentials stay on the backend; every ticket write is reviewed and explicitly confirmed, and the AI can only draft; no webhooks. Astra implements it slice by slice and Claude reviews each slice. Decisions still waiting on Andrew are listed in §10 of that plan.


### Architecture diagrams plan — 2026-09-15

[docs/ARCHITECTURE-DIAGRAMS-PLAN.md](docs/ARCHITECTURE-DIAGRAMS-PLAN.md) goes beyond import relationships. It adds data-model ERDs, class and data-contract diagrams, sequence diagrams (static source order, observed stacks and traced spans, plus a static-versus-traced comparison), an endpoint-to-data map, API contract, deployment, messaging and frontend maps, and small illustrations across the app.

New facts come from static extractors and live in a separate `structure-0.1` document, so atlas schema 0.2 stays unchanged. Declared schemas and manifests are labelled as declared, not deployed. Secret values are never kept. It supersedes V3/V4 in the visualization plan. The implementer and remaining decisions are listed in §11.


### Data model and contract diagrams checkpoint — 2026-09-15

On branch `claude/architecture-diagrams`, awaiting Astra's review, the analysis worker now also builds `.codandy/structure.json` (`structure-0.1`) from indexed files, and the Architecture tab gains Data model and Data contracts views beside the dependency map.

- **Data model (ERDs):** Prisma, SQL DDL, SQLAlchemy and Django declarations.
- **Data contracts:** Pydantic models, dataclasses, TypedDicts, TypeScript interfaces and object type aliases.

Extraction is static and bounded. It has its own share of the analysis time budget and is withheld with a visible limitation rather than failing the report. Reports saved earlier still open; their diagrams need a new analysis. Status by milestone is in §13 of the diagrams plan.

### 2026-09-15 ticketing delivery update

The first local Linear creation workflow is implemented from Recommended changes, whiteboard plan exports and Integrations. Exact scrubbed payload review and explicit confirmation precede each external write. A durable submission ledger prevents automatic duplicate retries, including after restart. Offline fixtures and browser mocks validate the workflow; live account validation remains open. See docs/INTEGRATIONS-PLAN.md for unfinished shared-provider, pagination and source-link criteria. Observed stack/trace sequence views are reviewed, with a fix preserving the true final captured frame when library frames are collapsed.

### 2026-09-16 delivered slices

Whiteboard starts with a real unsaved drawing canvas; saving creates the local board and opens the existing AI planning workflow. Import is secondary. Source-linked ticket receipts are available on saved boards and recommendation cards; a different ticket draft for the same source requires explicit acknowledgement. Recommendation linkage is scoped to repository/revision.

Sentry project and issue browsing is implemented with at most 50 results per click, safe cursor pagination, scrubbed narrow fields, and explicit issue selection before event retrieval. Projects need org:read and issue/event reads need event:read. Live account testing and release-commit verification remain open. No status changes or other Sentry writes are added.

### 2026-09-16 — Whiteboard planning delivery

Structured task cards now expose dependencies, acceptance criteria, verification and proposed paths. Each task can be prepared as an individually reviewed Linear ticket, with receipt identity scoped to board/plan/task; no automatic issue dependency links are claimed. Coding-assistant handoffs and the exact reviewed drawing context are downloadable. A reading guide discloses freehand, unlabeled, dangling and omitted elements; group context is retained as user design. Visual image interpretation, evidence cards, live provider validation and automatic implementation remain open.

### 2026-09-17 — Reviewed visual whiteboard interpretation delivered

The local whiteboard can now render a sanitized drawing preview and submit the exact reviewed PNG plus text context to the connected Codex model. Image consent is separate, review digests bind image/revision/context, and changes invalidate approval. Visual findings have explicit visual_inference provenance and require supplied element citations. The assistant asks about ambiguous handwriting, shapes, relationships and requirements. Inline answers become saved user requirements; reinterpret the updated revision before generating a plan.

PNG input is bounded to 2 MiB, 2,048 pixels per side and supported RGB/RGBA formats, with CRC/expanded-byte validation and ancillary metadata stripping. Temporary local image files are removed after completion or failure; image bodies are not stored in board artifacts. Typed text is scrubbed before rendering; handwriting still requires user inspection. Tools remain disabled and there is no remote URL or client-supplied file path input.

Validation: 322 backend tests, 49 frontend/API contracts, Ruff, TypeScript, changed-file lint and production build pass. Mocked and live synthetic Edge workflows pass image consent, interpretation questions, inline answers and mobile layout. Two small live synthetic requests used the connected default GPT-6-Astra/low model; no personal board or provider ticket was shared. The visible freehand test asked whether the unknown shape meant an arrow/component, its endpoints and the API's responsibility. Other account/model combinations remain unverified. Source/case evidence cards, plan comparison and external-image imports remain future work.
