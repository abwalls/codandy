# Codandy debugging strategy

## Recommendation

Build an investigation workspace around errors and slow operations. Use Sentry as the first evidence provider, the existing static graph as source context, and a whiteboard as the place developers turn evidence into a debugging or implementation plan. The recurring unit of work should be a saved investigation, not a repository report or an ungrounded chat session.

This is a product hypothesis, not proof of an uncontested market. The first validation question is whether Codandy helps a developer complete a second real investigation more effectively than moving between Sentry and an IDE. A narrow, usable loop provides more evidence than adding numerous shallow integrations.

## Assessment of the supplied proposal

The supplied NEWPLAN.md argues for combining a static model with runtime observations and then prioritizing pre-merge change-risk analysis. Its evidence separation, reusable adapters and avoidance of a bespoke time-travel debugger are sound architectural directions. Its proposed ordering does not match the chosen Sentry/debugging focus, and several examples assume capabilities that the code does not currently implement.

| Proposal | Assessment and decision |
|---|---|
| Static graph plus separate runtime observations | Adopt. Preserve provenance and revision boundaries. |
| Sentry after test instrumentation, OTel and replay | Reorder. Sentry read-only retrieval and offline error import come first. |
| Change-risk score as the flagship | Defer. Evaluation and richer semantic/coverage evidence must precede numerical verdicts. |
| Full execution paths from static relationships | Narrow to candidate paths. Unobserved dispatch, middleware and distributed edges cannot be filled in by an LLM. |
| Exact null expression/value from an exception | Reject unless the captured runtime evidence establishes it. A null-reference exception alone does not identify the null operand. |
| Test coverage, precise targeted test counts and run times | Not supported by today's candidate test-file inventory. Require imported coverage/results and measured execution data. |
| Permanently stable node identities | Qualify. Current identities depend on kind/path/name; moves and renames can change them. Bind to snapshot + node, not node ID alone. |
| Existing READS/WRITES/PUBLISHES/TESTS relationships | Not present in the implemented relationship enum. These are possible future additions, not delivered assets. |
| Rename artifact to graph.json | Unnecessary churn. Keep .codandy/atlas.json and schema 0.2; add separate observation documents. |
| MCP interoperability | Adopt after the same investigation services work in the UI. |
| Whiteboarding | Add as a first-release workflow, with structured intent and evidence references. |
| Adoption percentages and claims that no competitor offers a feature | Exclude from positioning. The supplied figures were not established by this review, and exclusivity is not demonstrated. |

The proposal's market statistics and portfolio/interview commentary are not needed to choose an implementation path and should not be republished as substantiated product claims. The proposal remains a private local input in Downloads, not a new canonical public specification.

## Competitive boundary

Sentry's own Seer already combines errors, traces, logs, profiles and code context to investigate and address issues. Therefore "AI diagnoses Sentry errors" is not a differentiator by itself. Codandy should preserve source links back to Sentry, label any imported Seer conclusion as provider-generated, and avoid implying independence from the evidence it consumes. [Sentry: Seer](https://docs.sentry.io/product/ai-in-sentry/seer)

Sentry also provides an OAuth-based MCP service for coding assistants, with organization/project scoping. That makes a thin Sentry chat wrapper especially weak positioning. Codandy can instead offer an investigation artifact that combines provider evidence, a selected source revision, developer annotations, planning and verification, while remaining useful when only an offline stack is available. This is a recommended opportunity, not a claim that competitors lack all these features. [Sentry MCP](https://mcp.sentry.dev/)

Cursor, Visual Studio and other IDEs are useful interaction references: frame selection, a source pane, watch/state views and a clear current context. They should initially be destinations for a debugging brief rather than products Codandy tries to reproduce. A first release need not contain an editor, language server, debugger engine and terminal to provide value.

## First Sentry integration

### Authentication and scope

Use Sentry's supported read API from FastAPI. A local first version can accept a scoped organizational/internal-integration token through a protected local settings flow. Sentry recommends organizational tokens where possible; some endpoints have different authentication requirements, so tests must verify each selected endpoint rather than assume one token works everywhere. Multi-user distribution should later use the supported authorization flow with state/PKCE and installation-scoped storage. A ChatGPT subscription does not authenticate Sentry. [Sentry token guide](https://docs.sentry.io/api/guides/create-auth-token/) · [Sentry authentication](https://docs.sentry.io/api/auth/)

Request only the read permissions required by selected endpoints: event:read for issue/event reads, project:read for project discovery and org:read only where organization discovery requires it. Do not request event writes, administrative access or release mutation permissions for a viewer. Treat a DSN as ingestion configuration, not the default credential for fetching private issues. Exact endpoint scope checks belong in the connector contract. [Permissions and scopes](https://docs.sentry.io/api/permissions/)

Keep credentials backend-only and out of localStorage, Git, reports and prompts. First implementation should use session-only memory or an environment secret; persisted credentials need OS credential storage or an explicitly designed secret store. Expose connection status and disconnect without returning the token. Don't ask developers to paste credentials into AI chat.

### Data path

Start with project selection, issue listing, issue detail and a selected event. Sentry exposes an issue-event endpoint under `/api/0/organizations/{org}/issues/{issue}/events/{event}/`; event selectors include latest, oldest and recommended. Store the resolved event ID and retrieval time so a saved investigation does not silently become a different occurrence. REST response frames can include function, filename, line/column, context and optional variables, but these fields are not guaranteed. Normalize the response, including its exception entries, rather than treat issue summary text as an entire event. [Retrieve an issue event](https://docs.sentry.io/api/events/retrieve-an-issue-event/)

Use an explicit Cloud region selection. Sentry documents sentry.io and region-specific US/DE API domains. An arbitrary issue URL must be parsed into identifiers against the configured connection; it must not become a generic backend URL fetch. Self-hosted endpoints need a separate administrator-approved host policy and version compatibility testing. [Sentry API reference](https://docs.sentry.io/api/)

A read-only pull on user action is a reasonable local prototype. It is not a plan to poll all projects continuously. Sentry applies rate and concurrency limits per caller/endpoint and returns usage/reset headers; automatic retries must respect those limits. Prefer bounded caching and manual refresh initially. Webhooks become appropriate when a durable HTTPS receiver exists; their signature, lifecycle, deduplication and retry contract must be verified before that phase ships. This review did not establish the full webhook contract. [Rate limits](https://docs.sentry.io/api/ratelimits/)

### Privacy and input safety

Telemetry can carry personal data, credentials, user-controlled text and source snippets. Store an allowlisted, normalized representation by default. Exclude request bodies, cookies, authorization headers, raw user identities and frame locals initially. Bound message/breadcrumb text, redact known sensitive patterns and let the user preview what will be exported or submitted to an assistant. No automated scrubber guarantees all secrets are removed; explicit review and scope minimization remain necessary.

Treat stack paths, issue titles, exception messages, board text and log content as untrusted evidence, including possible prompt injection. Never execute embedded commands or fetch file/URL references automatically. A synthetic adversarial fixture corpus should include tokens in messages, malicious path prefixes, huge nested values and source-map URLs targeting local addresses. Import and live API retrieval must pass through the same normalization boundary.

## Correlating runtime evidence with source

There are four distinct things: a source snapshot, a runtime observation, a proposed association between them, and an interpretation of that evidence. Combining them into a single mutable graph would destroy the ability to explain why a conclusion was reached.

Use a binding record containing observation/frame identity, snapshot identity, candidate node IDs, mapping method, release/commit match status and limitations. Prefer known repository/service mapping, exact normalized path and line containment at a verified revision. A basename or function name alone is a candidate, especially in a monorepo. Overloads, anonymous functions, async state machines, transpilation and generated code need explicit ambiguity states.

A release string is not necessarily a commit. The same line number on main may point at unrelated code after deployment. Require known revision correspondence for an exact binding; otherwise allow a useful approximate source view with a prominent mismatch indicator. Keep provider symbolication/source-map error information. Missing original sources or .NET debug symbols is an evidence gap, not an invitation to infer an exact function.

The implemented `identity()` hashes kind/path/name into IDs. That is deterministic within its naming inputs, not immutable identity across renames. Every observation link therefore needs a snapshot reference. Existing captured source lookup is a useful boundary: viewer requests should continue to address a retained map, never open arbitrary telemetry-supplied paths.

An observed call stack represents the reported stack at capture time. It is not the entire request lifecycle, and exceptions can cross asynchronous boundaries or contain nested chains. Show the captured sequence separately from static candidate callers. Preserve unresolved frames, original order metadata and omissions rather than flattening the event into a fictional complete trace.

## Performance and live debugging are different capabilities

An exception stack does not provide elapsed time for each frame. Instrumented traces describe operations with timestamps and relationships; their spans are not necessarily one-to-one with language functions. The first performance viewer should expose the data's actual granularity, preserve missing parents/links and avoid summing overlapping work as if it were sequential. [OpenTelemetry traces](https://opentelemetry.io/docs/concepts/signals/traces/)

OpenTelemetry's code attributes evolved: the stable conventions use code.function.name, code.file.path and code.line.number, replacing earlier naming. A connector should normalize known variants, record the schema basis and retain unmapped spans. A friendly span name alone is insufficient proof of a function match. [OpenTelemetry code attribute migration](https://opentelemetry.io/docs/specs/semconv/non-normative/code-attrs-migration/)

Profiling is a separate adapter: sampled stack weight is not exact per-invocation latency, and not every profile measures CPU time. Sentry's continuous profiling introduces session sampling and lifecycle choices. Rather than assume all customers expose the same profile data through a stable API, first prove a supported format/account combination and retain links to the provider where retrieval is unavailable. [Sentry continuous profiling announcement](https://sentry.io/changelog/continuous-profiling-and-ui-profiling/)

For actual stepping and variable inspection, use a later Debug Adapter Protocol client or an IDE handoff. DAP defines a reusable debugger interface, but adapters advertise differing capabilities; launch and attach control real programs. This requires a trusted local workspace and explicit user action. Keep it outside the static analyzer and outside automatically executed assistant tools. A read-looking expression evaluation can itself have side effects. [Debug Adapter Protocol overview](https://microsoft.github.io/debug-adapter-protocol/overview)

## Whiteboard design

The first board should help developers turn an investigation into a plan, not become a generic collaborative design product. Give it freehand drawing and basic shapes, then make evidence cards the valuable addition: a frame, symbol, span or observation can be placed beside a hypothesis or proposed task. A drawn connection records user intent, not a discovered code relationship.

Excalidraw is the preferred spike because its editor is MIT-licensed and supports drawing tools, arrow bindings, undo/redo, image export and an open scene format. Its hosted application's collaboration and local-first behavior are separate from simply embedding the editor; Codandy must implement its own storage and lifecycle. [Excalidraw repository](https://github.com/excalidraw/excalidraw)

Retain board text, element IDs, explicit evidence references, assumptions, tasks and acceptance criteria alongside the scene. Export a selected PNG and a Markdown brief; support JSON round-trip. Excalidraw exposes export utilities, but rendering an image does not by itself produce reliable semantic context for an assistant. A useful text/evidence handoff should work before adding image-capable model requests. [Excalidraw export utilities](https://docs.excalidraw.com/docs/@excalidraw/excalidraw/api/utils/export)

tldraw is an alternative worth considering for richer custom tools, but its current production use requires an appropriate license/key; it is not a free drop-in commercial dependency under MIT. That makes it a deliberate product/licensing decision, not the default for this cost-conscious first release. [tldraw licensing](https://tldraw.dev/community/license)

Defer realtime collaboration, external embeds and automatic image understanding. Those add identity, asset hosting, synchronization and information-sharing decisions that are not needed to prove a single-user board-to-brief flow. Design autosave recovery, explicit export and keyboard-accessible editing before optional sharing.

## Implementation sequence and evaluation

Start by normalizing bounded events and stacks into persistent cases, then add one live read-only Sentry connector and a source-bound view. Introduce performance adapters and a basic whiteboard once that case model is reliable. Export the same evidence contract through MCP only after UI calls already exercise it. Add change-risk scoring and test selection later if investigation use demonstrates demand and suitable evidence becomes available.

Build a labeled corpus with TypeScript/JavaScript, Python and .NET cases: exact mapping, mixed/unknown release, duplicate filename, omitted frames, inner/async exceptions, missing symbolication and third-party-only stacks. Report mapping precision separately from coverage; declining an uncertain mapping is better than inflating coverage with an incorrect exact claim. Require all deliberately ambiguous cases to remain non-exact. Include retention, source eviction, redaction and malformed-provider tests.

Assess success through completed investigations: time to the relevant source, whether a developer can explain the next verification step, whether an exported brief retains its evidence, and whether the same developer returns for another case. Compare with the baseline Sentry-plus-IDE workflow. This is a proposed evaluation, not a measured improvement claim.

No live Sentry account, entitlement, endpoint permission or whiteboard package compatibility was tested during this planning review. Public documentation was checked on 2026-09-13/14; API/version support must be reconfirmed against the actual account during implementation. Market-wide uniqueness and the proposal's adoption statistics remain unverified. The next implementation is therefore a narrow connector-and-investigation slice, not a commitment to all proposed capabilities at once.

## Source inventory

Primary sources are linked next to the claims they support: Sentry authentication, token guide, scopes, event API, API regions, rate limits, Seer, MCP and profiling announcement; OpenTelemetry trace and code-attribute specifications; Microsoft's DAP overview; Excalidraw's repository/export documentation; and tldraw's license documentation. Mutable documentation was accessed during this review; package versions and endpoint behavior remain implementation-time checks.

Local inputs: C:/Users/andre/Downloads/NEWPLAN.md (proposed strategy, sections 1–11); Codandy's PLAN.md, ROADMAP.md, ARCHITECTURE.md, AGENTS.md and progress.md; backend/app/models.py and analyzer.py; current source/assistant/report boundaries. The supplied proposal is inspiration, not evidence that its examples or market claims are implemented or independently validated.


### Primary references

Documentation accessed during the September 13–14, 2026 review. Most pages are living documentation rather than dated research; no publication date is inferred from their crawl date.

| Publisher | Source | Used for |
|---|---|---|
| Sentry | [Seer](https://docs.sentry.io/product/ai-in-sentry/seer) | Existing AI investigation capability |
| Sentry | [MCP server](https://mcp.sentry.dev/) | Existing assistant integration and scoping |
| Sentry | [Token creation](https://docs.sentry.io/api/guides/create-auth-token/) | Local connector authentication |
| Sentry | [Authentication](https://docs.sentry.io/api/auth/) | Token/OAuth boundaries |
| Sentry | [Permissions](https://docs.sentry.io/api/permissions/) | Least-privilege read scopes |
| Sentry | [Issue event API](https://docs.sentry.io/api/events/retrieve-an-issue-event/) | Selected occurrence retrieval |
| Sentry | [API reference](https://docs.sentry.io/api/) | Regional endpoints |
| Sentry | [Rate limits](https://docs.sentry.io/api/ratelimits/) | Bounded request strategy |
| Sentry | [Continuous profiling](https://sentry.io/changelog/continuous-profiling-and-ui-profiling/) | Profiling lifecycle and sampling |
| OpenTelemetry | [Traces](https://opentelemetry.io/docs/concepts/signals/traces/) | Runtime observation semantics |
| OpenTelemetry | [Code attribute migration](https://opentelemetry.io/docs/specs/semconv/non-normative/code-attrs-migration/) | Attribute compatibility |
| Microsoft | [Debug Adapter Protocol](https://microsoft.github.io/debug-adapter-protocol/overview) | Future trusted debugger boundary |
| Excalidraw contributors | [Repository](https://github.com/excalidraw/excalidraw) and [export utilities](https://docs.excalidraw.com/docs/@excalidraw/excalidraw/api/utils/export) | Embedded whiteboard/export spike |
| tldraw | [License](https://tldraw.dev/community/license) | Alternative SDK production constraint |
