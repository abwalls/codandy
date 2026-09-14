# Code Atlas delivery plan

## Product goal

Code Atlas turns an unfamiliar repository into an interactive, evidence-backed mental model. The deterministic code graph is the source of truth; AI investigates and explains that graph without inventing relationships.

## MVP experience

1. Connect a ChatGPT/Codex session.
2. Submit a public GitHub or Git URL, ZIP archive, or project folder.
3. Stream analysis progress while the repository is parsed statically.
4. Generate a versioned `atlas.json` tied to branch and commit.
5. Explore the executive summary, architecture, flows, codebase index, and developer guide.
6. Select any node to view source evidence and ask a scoped question.

## Architecture

- Frontend: React 19, TypeScript, responsive web/PWA interface.
- API: Python 3.12 with FastAPI and Pydantic.
- Analysis: analyzer registry with Tree-sitter parsing for C#, TypeScript/TSX, JavaScript/JSX, Python and Go, then native Roslyn and TypeScript analyzers.
- Graph: language-neutral nodes and typed relationships stored in `atlas.json`.
- Agent: Codex adapter behind an `AIProvider` interface, operating read-only against the repository workspace.
- Jobs: asynchronous analysis pipeline with Server-Sent Events for progress.

## Milestones

### M0 · Foundation (current)

- Responsive intake and report UI.
- Interactive sample atlas and node inspection.
- Shared atlas schema concepts.
- FastAPI application skeleton and job endpoints.
- Static-analysis-only security boundary.

### M1 · Real public-repository analysis (delivered)

- Clone public repositories into isolated temporary workspaces.
- Enforce size, file-count, depth, timeout, and allow/deny limits.
- Detect project types and languages from manifests.
- Index directories, files, imports, declarations, routes, and tests.
- Emit and validate `atlas.json`.
- Replace demo progress with SSE job events.

### M2 · Grounded report generation (partially delivered)

- Architecture evidence rules and confidence scoring.
- Important-flow discovery and reconstruction.
- Generated executive summary, conventions, and “where do I change?” guidance.
- Source viewer with stable symbol IDs and line evidence. **Done.**
- Recommended Changes report: performance opportunities, refactoring ideas, and potential security risks. Attach real source evidence, priority, effort, recommended approach, and verification steps to each finding. Distinguish unverified risks from confirmed vulnerabilities; never claim a clean security audit from an absence of findings.

### M3 · Codex integration

- ChatGPT-authenticated Codex session adapter.
- Read-only scoped investigation tools: symbols, callers, callees, implementations, routes, entities, and source.
- Node-scoped questions with cited evidence.
- Verify multi-tenant production policy before a hosted commercial release.

### M4 · Inputs and persistence

- ZIP and folder upload.
- Private GitHub authorization.
- Saved reports, commit freshness, and incremental re-analysis.

### M5 · Debugging overlay

- Accept issue descriptions, stack traces, logs, Sentry issues, and OpenTelemetry traces.
- Map runtime frames and spans onto stable atlas node IDs.
- Highlight affected report sections, probable root causes, evidence, and solution options.

## Security invariants

- Never execute uploaded repository code during normal analysis.
- Never run package installation, builds, tests, scripts, binaries, or project-defined tooling by default.
- Treat repositories as untrusted input and keep workspaces isolated and disposable.
- Keep Codex access read-only until a future user explicitly authorizes a code-changing workflow.
- Exclude secrets and sensitive file patterns from model context and generated reports.

## Next implementation slice

M1 is implemented and M2 is partially implemented. Bounded GitHub cloning, isolated
parsing for C#, TypeScript/TSX, JavaScript/JSX, Python and Go, validated atlas emission,
live SSE progress, deterministic grounded reports, and a source viewer are working and
browser-verified against real TypeScript and Python repositories. Native hangs and crashes
are contained in a disposable process. Verification includes 75 backend tests and 7
frontend/API contract tests.

Next steps, in order:

1. Deepen M2 inference. Architecture currently reports manifests and top-level folders
   rather than boundaries, layers, and external systems, and flows are bounded local
   traversals rather than reconstructed paths. Do not replace unsupported states with
   speculative findings.
2. Before hosted deployment, implement durable shared state, access control and operational limits. Dockerfile repair is explicitly deferred; its current build commands are not valid. Configure CODE_ATLAS_API_URL only after a working service exists.
3. Replace the sample report's remaining placeholder sections with real rendering, and
   consolidate the sample and live reports onto one navigation shell when the sample
   scope is explicitly expanded. The real report path already renders all four M2 sections.
4. Broaden language coverage further (Java, Rust, Ruby, PHP) and add semantic analyzers.

M4 partial: validated local atlas import/export and same-repository snapshot comparison are available, without retained source bodies or freshness checks. Opt-in single-process completed-report persistence and recent-report reopening are implemented; shared/server-scale persistence, repository uploads and private Git inputs remain unstarted. M3 has a working local subscription slice (below); M5 debugging overlay remains unstarted.

Review follow-up: dependency inventory is aggregated, cross-folder import cards now cite graph-backed paths, category labels and sample flow ordering are corrected. Backend verification: 81 tests; frontend contracts: 8 tests. Circular-import review cards and cited-node evidence validation are implemented.

See [progress.md](progress.md) for implementation checkpoints and local verification commands.

Report exploration: source inspector now includes direct/transitive local importers; Snapshot comparison shows indexed graph changes with explicit analyzer/behavior limitations.

Dependencies analyzer: direct package/version evidence, supported npm/NuGet lockfiles, scoped usage candidates, explicit registry update checks and OSV advisory lookups are implemented. Runtime inventories, other locks and full transitive resolution remain unsupported.

M2 architecture now includes literal .NET ProjectReference candidates between indexed manifests, with unresolved declarations and cited graph paths. MSBuild conditions, imports and reference metadata remain unevaluated.

Dependency follow-up: exportable review observations, review-state filtering, project-dependent impact traversal, and nearest Directory.Packages.props version candidates are delivered. Central candidates do not imply resolved versions.

Overview inventory drilldowns and contextual question drafting/export are available in the UI. The local M3 subscription adapter is described below; shared hosted AI integration remains unimplemented.

M3 local slice: an opt-in Codex App Server subscription adapter, OpenAI browser sign-in, discovered model/effort controls, retained-evidence questions, and schema/citation-ID validation are now implemented. Signed-in Plus-plan status and an authenticated answer with valid graph citations are verified through the localhost frontend proxy using Codex 0.154.0. Multi-turn history, streamed answers, source retrieval tools and shared hosted authentication remain future work.
