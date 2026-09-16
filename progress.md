# Codandy progress

## 2026-09-12 - Handoff audit and M2 continuation

- Reviewed HANDOFF-2026-09-12.md. Its language registry, source viewer, clone race fix, tree-sitter `<0.26` safety pin, UTF-8 contract pipe, and source endpoint protections are present in the workspace.
- Verification: 75 backend tests passed with `--basetemp=.pytest-tmp`; 7 frontend/API contract tests passed; TypeScript, changed-file ESLint, and production build passed.
- Real report path now renders Architecture, Application flows, Developer guide, and Recommended changes from atlas `report` evidence. Report graph checks, filters, evidence cards, route/module paths, approach and verification details are covered by tests and schema validation.
- A live smoke retry was blocked by current GitHub network access (`Git operation failed`); local report fixtures produced schema 0.2 with generated architecture/flows/guide and an honest no-match recommendation state. No source or report data is fabricated.
- Sample report placeholders remain intentionally separate per the handoff’s recorded user decision. Hosted Python deployment, mobile QA, deeper semantic inference, Codex Q&A, persistence, and debugging overlay remain next work.

Update this log after each completed implementation slice and before stopping. Read it together with PLAN.md when resuming.

## 2026-09-12 - Resumed: real UI and process isolation

- Implemented a spawned, disposable analyzer process with enforced deadline, termination, and sanitized crash handling. JobStore now uses this boundary. Native parsing cannot take down or indefinitely block the API worker.
- Verified 41 backend tests, including real process extraction and injected hangs/crashes; Ruff passed after import cleanup.
- Implementing real intake submission, SSE progress/recovery, validated frontend artifact schema, evidence index, and atlas download. Sample reports remain a separate explicit path.

## 2026-09-12 - Real data flow verified

- React submits public GitHub URL plus optional ref, shows actual SSE progress, reconnects with status recovery, and loads the schema-validated atlas. Removed simulated completion and disabled unsupported uploads.
- Added real overview, searchable/paginated node index, source evidence, labeled relationships, and atlas download. Architecture, flows, guide, recommendations, and AI have explicit unavailable states. Sample mode retains a visible illustrative-data label.
- Added Zod frontend artifact/job contracts and executable cross-language tests against Python-generated output. Added hosted API forwarding with an explicit missing-backend state and local Vite proxy to port 8000.
- Live GitHub smoke passed against microsoft/TypeScript-React-Starter at commit 19c71f2c6a2b874b1b2bb28a8526b19185b8eece: 24 files, 15 symbols, 2 candidate test files, 77 relationships, Node.js/React/TypeScript. Confirmed atlas retrieval, terminal SSE, and workspace cleanup.
- Repeated the live flow through http://localhost:5173/api/analyses: completion and Last-Event-ID replay passed; backend/.workspaces was empty afterward.
- Browser preview/interaction QA is unavailable: CUA reports no available browser. HTTP rendering returned 200; TypeScript and production build passed. This does not establish visual/browser-interaction verification.
- Updated the Windows launcher to use the working managed environment when present.

## 2026-09-12 - UI integration stopping checkpoint

- Final verification: 41 backend tests passed; Ruff passed; 5 frontend/Python/proxy contract tests passed; TypeScript passed; production build passed, including the hosted API route. Direct ESLint check of changed TS/TSX files passed. The pnpm ESLint wrapper intermittently failed to locate its executable, so the installed ESLint JS entrypoint was used successfully.
- Updated PLAN.md, ARCHITECTURE.md, AGENTS.md, and README.md for the connected data flow, process boundary, local setup, hosted API requirement, and remaining work.
- No hosted publication was made: the Python backend currently runs locally, and no hosted backend endpoint has been configured for the connected experience. The existing hosted sample remains unchanged.
- Resume with browser QA when available, then a hosted Python service and CODANDY_API_URL wiring if remote access is wanted. Broader parser fixtures/project association and grounded M2 rules follow. No AI enrichment has been added.
- Commands: from root run `corepack pnpm test:contracts`, `corepack pnpm exec tsc --noEmit`, and `corepack pnpm build`; from backend run `.venv-managed/Scripts/python.exe -m pytest -q`, `.venv-managed/Scripts/python.exe -m ruff check .`, and opt-in `.venv-managed/Scripts/python.exe smoke.py` (requires GitHub network access).
- During server teardown, Vite logs revealed clone-local tsconfig files triggered frontend reloads. Excluded backend/workspaces/tool directories from Vite watching and TypeScript scanning. Temporary smoke-test directories were cleaned up and test servers stopped.

## 2026-09-12 - Starting checkpoint

- Reviewed PLAN.md, ARCHITECTURE.md, ingestion, analyzer, jobs, API routes, tests, and frontend atlas usage.
- Existing backend implements bounded GitHub cloning, C#/TypeScript Tree-sitter extraction, in-memory jobs, atlas validation, and SSE. These exceed the scaffold-only status in the existing documentation.
- Existing tests cover ingestion and health only. React still consumes demoAtlas and simulated progress; its sample schema differs from the backend artifact.
- This session: verify and harden deterministic backend behavior with parser, schema, and job/API contract tests before frontend integration.
- Workspace has no Git metadata; changes cannot be compared to a prior commit here.

## 2026-09-12 - Parser regression coverage

- Added mixed C#/TSX extraction, exclusions, node-budget, graph-validation, and stable-ID tests.
- Fixed duplicate same-line import/route identities and made these identities independent of line numbers; readable labels remain separate from identity ordinals.
- Initial verification: 34 tests passed. Found that Tree-sitter ignores progress callbacks with byte input; callback-input parsing crashes the installed Windows native parser. Retained byte parsing and an explicit post-parse deadline check. Hard parser timeout isolation remains unfinished and is a priority before treating ingestion as production-ready.
- Existing .venv references a missing system Python. Created ignored backend/.venv-managed with workspace-local managed Python; use its Scripts/python.exe for checks this session.

## 2026-09-12 - Job/API coverage completed; stopping checkpoint

- Added end-to-end local-fixture tests through FastAPI for queued-to-complete transitions, artifact round-trip, branch/commit metadata, SSE progress and Last-Event-ID replay, error sanitization, workspace-context exit, unavailable results, busy rejection, and bounded report retention.
- Added the managed virtual environment to Git and Ruff exclusions. Cleaned up existing lint failures in backend imports and context-manager formatting.
- Updated PLAN.md, README.md, and AGENTS.md to reflect the actual implementation and require future progress checkpoints.
- Final verification from backend/: `.venv-managed/Scripts/python.exe -m pytest -q` -> **38 passed**; `.venv-managed/Scripts/python.exe -m ruff check .` -> **all checks passed**. Two third-party TestClient deprecation warnings remain.
- Tests mock the network clone; no live GitHub clone or browser integration was verified. Frontend code and schemas were not changed in this slice.
- Resume with native analyzer process isolation and timeout/crash regression tests, then a live public GitHub smoke test, then synchronized frontend artifact types and real API/SSE/report integration. Keep unsupported results explicit and samples labeled; do not add AI enrichment yet.
- Local setup note: standard backend/.venv is still broken because its original Python path is missing. The separate .venv-managed environment is working; avoid relying on the standard launch script until the environment is repaired or recreated.

## 2026-09-12 - Browser QA availability check

- User requested browser QA. Started the frontend and working managed-Python backend; frontend http://localhost:5173/ returned 200 and backend http://127.0.0.1:8000/health returned ok.
- Browser QA remains blocked by the session's browser connection, not by service startup: CUA inventory returned no browsers, and opening Chrome returned "Browser is not available: chrome".
- Left both services running for manual review. No browser interactions or visual checks were claimed. Resume browser QA when a browser connection is available.

## 2026-09-12 - Chrome browser QA completed

- Chrome extension connected successfully; Edge was not exposed in the browser inventory.
- Browser-tested real GitHub submission and observed live cloning progress followed by the correct Microsoft TypeScript React starter report (24 files, 15 symbols, 2 test candidates).
- Verified codebase pagination, search resetting pagination, source evidence with line ranges, relationship navigation, and explicit unavailable recommendations.
- Verified rejection of a localhost repository URL, recovery to intake, sample report labeling, and return from sample to intake.
- Inspected the desktop evidence-view screenshot: content and controls were readable with no visible overlap.
- No defects found in these checks. Mobile layout, download completion, and forced connection-loss recovery were not tested in this pass. Both services remain running; Chrome was left on intake.

## 2026-09-12 - M2 report implementation started

- User requested sustained implementation during the usage window. Active goal: replace Architecture, Application flows, Developer guide, and Recommended changes placeholders with deterministic graph-grounded reports.
- Extended artifact to schema 0.2 with node attributes, local import resolution, declared dependencies/tasks, project membership, route-handler/local-call candidates, and graph-validated report items. Frontend still accepts older 0.1 artifacts and asks for reanalysis for missing reports.
- Added deterministic structure/guide/flow report rules and recommendation rules for long declarations, high local import counts, eval syntax, and raw HTML JSX. All recommendations remain inferred review opportunities with evidence, approach, and verification; no exploitability or performance claims.
- Added report cards, category/search filters, static path links, source navigation, recommendation details, and honest no-match states in the real UI.
- Focused new backend report tests: 10 passed. Existing baseline suite passed before the new route tests exposed/fixed zero-argument call extraction and inline-handler scope. Final combined checks and browser QA are next.

## 2026-09-12 - Encoding fix, language coverage, source viewer (latest)

Scope agreed with the user: fix the failing contract suite, broaden language coverage, add
the source viewer. Leave the sample report's placeholder tabs/screens in place until they
are implemented, and leave the M5 debugging overlay alone. The two report UIs were left
separate because the consolidation was explicitly declined.

- Fixed the red contract suite. `reporting.py` builds module-dependency titles with a
  non-ASCII arrow, and the cross-language test piped the atlas JSON through Python's
  Windows ANSI stdout. Fixed at the pipe with `PYTHONIOENCODING=utf-8` rather than by
  removing the arrow, because any repository path or identifier can be non-ASCII. Locked
  with an assertion that the arrow survives the round trip.
- Broadened syntax indexing from C#/TypeScript to C#, TypeScript/TSX, JavaScript/JSX,
  Python and Go. Grammars now load lazily from a suffix registry. Added Python
  class/function/decorator handling with Flask/FastAPI decorator routes linked to the
  decorated function, Go struct/interface/alias resolution from the type body plus
  mux/gin route registration, and JavaScript parity with TypeScript. Added manifest
  support for `pyproject.toml`, `requirements.txt` and `go.mod` (names only, never
  versions or markers), plus Express/Vue/Angular/Svelte, FastAPI/Django/Flask and
  Gin/Echo/Chi detection. Local import resolution now covers relative JS/TS specifiers,
  relative and repository-rooted Python modules, and Go package directories under the
  declared module path.
- Fixed a latent gap in the existing TypeScript path: class members are `method_definition`,
  which was absent from `DECLARATIONS`, so **no TypeScript or JavaScript class method was
  ever indexed**. The live TypeScript smoke repo went from 77 to 133 relationships after
  the fix.
- Added the source viewer. `atlas.json` deliberately still carries no source bodies; the
  API captures indexed file text while the clone exists, within per-file (128 KB) and total
  (4 MB) budgets, and serves `GET /analyses/{id}/source?path=...`. Only paths already
  indexed as file nodes are addressable, so the endpoint is a map lookup with no
  request-time disk access. Retained text is evicted with its report. The React viewer
  renders line numbers, highlights the evidence range with context, and offers whole-file
  view; repository text is rendered as text children only, never markup.
- Fixed a pre-existing race in `check_workspace`. It runs every 50 ms while Git is still
  writing, and Git's lock and temporary files vanish between the walk and the `stat`,
  raising `FileNotFoundError` and surfacing as the generic "Analysis failed" message. Live
  analysis was intermittently failing because of this.
- Found and contained a memory-corruption bug in `tree-sitter` 0.26.0: reading a node's
  `start_point`/`end_point` and then its `named_children` corrupts process memory and
  segfaults. The analyzer does exactly that for every declaration, so this affected the
  pre-existing C#/TypeScript path too and was only hidden by small test repositories. It
  reproduced at ~45% on a real Python repository and 100% on one 404-line file. Pinned
  `tree-sitter>=0.25,<0.26` with the rationale recorded in `pyproject.toml`, and added
  `tests/test_grammars.py` to assert the verified range and walk every registered grammar.
  The disposable-process boundary did its job: the API survived and reported a dead worker.
- Verification: 75 backend tests pass; Ruff clean; 7 frontend/API contract tests pass;
  TypeScript clean; production build succeeds; ESLint clean on changed files. Live smoke
  against microsoft/TypeScript-React-Starter passes and now also asserts source retrieval
  and traversal rejection. Browser QA against pallets/itsdangerous: 50 files, 144 symbols,
  98 Python methods, 46 resolved local imports, and the source viewer showing real Python
  with the evidence range highlighted and the whole-file toggle working.
- Not done: mobile/responsive QA of the source viewer, hosted deployment, and deeper M2
  inference. The sample report's placeholder sections remain untouched by request.
- Commands: from root `corepack pnpm test:contracts`, `corepack pnpm exec tsc --noEmit`,
  `corepack pnpm build`; from backend `.venv-managed/Scripts/python.exe -m pytest -q`,
  `.venv-managed/Scripts/python.exe -m ruff check .`, opt-in
  `.venv-managed/Scripts/python.exe smoke.py`. Note: pytest needs
  `--basetemp=.pytest-tmp` on this machine because
  `%LOCALAPPDATA%\Temp\pytest-of-andre` is a stale directory the account can no longer
  read or write; clearing it needs an elevated shell.

## 2026-09-12 - Continued v1 completion

- Started a new tracked goal for remaining v1 work after reviewing the Claude handoff.
- Audited the handoff implementation: language registry, source viewer, clone race fix, tree-sitter safety pin, UTF-8 contract handling, source endpoint protections, and documented test claims match the workspace.
- Deepened Architecture reports with inferred path boundaries (API, client, domain, application, infrastructure, persistence, and related conventional folders) and observed manifest dependency entries. Each item is explicitly observed or inferred with limitations.
- Completed the sample report's Architecture, Application flows, Codebase, and Developer guide views using the labeled demo atlas. Sample content remains visibly illustrative; debugging stays deferred.
- Verification after these changes: 75 backend tests passed with `--basetemp=.pytest-tmp`; 7 frontend/API contract tests passed; TypeScript, ESLint, and production build passed.
- Live GitHub smoke is currently unavailable because this environment cannot reach GitHub; no failure was hidden. Hosted Python deployment, persistence, Codex Q&A, debugging overlay, mobile QA, and additional language families remain separate work.
- Added `backend/Dockerfile`, `.dockerignore`, and complete production limit examples to make the hosted Python service deployable on a container platform. Deployment, origin configuration, authentication, persistence, and operational monitoring still require an external hosting decision.


## 2026-09-12 - Opus review follow-up and report exploration

- Read AGENTS, review notes, roadmap, plan and architecture before edits. Confirmed review findings 2-5; fixed dependency-card flooding, missing labels, optional sample line rendering and misleading sequential sample-flow numbering. Narrowed SampleSection props and title/description maps to its four supported sections. Retained debugging and the legacy placeholder branch; Dockerfile remains deferred.
- Aggregated dependency declarations into one bounded inventory card with full counts and up to 100 inspectable nodes. Added cross-folder import cards backed by IMPORTS/RESOLVES_TO edges, with explicit inference limitations and per-folder metrics.
- Added validated local atlas import on intake (20 MB cap, malformed JSON/schema errors, no upload). Saved reports are labeled snapshots without source text or freshness verification.
- Moved source evidence above the node list on narrow layouts, added return navigation from evidence to its report section, and keyed source retrieval by job as well as path.
- Corrected README and PLAN deployment claims: Dockerfile is a known-broken deferred draft; shared persistence/access controls are prerequisites for hosted use. This supersedes the earlier deployable-container claim.
- Checkpoint verification: 77 backend tests pass, 7 frontend/API contracts pass, TypeScript passes, focused Ruff passes. Added aggregation/bounding and cross-folder evidence regression cases. Browser inventory exposes no connected browsers/apps, so responsive visual QA remains unverified.
- Tests used fresh backend/.pytest-tmp-review-* directories rather than the previously inaccessible .pytest-tmp. Final cleanup/build verification follows.


## 2026-09-12 - Graph integrity and circular-import review

- Tightened Python and TypeScript validation: report evidence must match evidence on its cited nodes. Added rejection tests for invented source evidence.
- Added iterative strongly connected component analysis of resolved local imports. Recommended changes now includes bounded circular-import cards with actual graph steps, counts, review approach and verification. These explicitly do not prove runtime failures; type-only/conditional imports are not distinguished.
- Verified 81 backend tests, including self-import/acyclic boundaries, a 5,001-node graph without recursion, and schema-valid cycle reports. Frontend contracts now include 8 cases. Fixed Ruff import ordering after the cycle change.
- Live GitHub smoke passed with escalated host network access (sandbox Git failed): 24 files, 15 symbols, 133 relationships, commit 19c71f2c, source retrieval and workspace cleanup verified. This smoke preceded the cycle rule; later cycle changes were fixture-tested.
- Remaining: browser/mobile interaction QA (no browser surfaces exposed), durable server persistence, auth/Codex Q&A, repository upload inputs, hosted service, and deferred Docker/debugging work. No hosted deployment attempted: Python service and its persistence/access-control prerequisites are not provisioned.
- Final checkpoint: 81 backend tests and 8 frontend contracts passed; TypeScript, ESLint, Ruff and production build passed. Removed all four fresh pytest scratch directories created in this session. Pre-existing inaccessible scratch directories were left untouched. Changes are local and have not been pushed to GitHub.


## 2026-09-12 - Published review fixes and continued exploration features

- Published the previous verified review/report slice to GitHub main as 0330ba5.
- Added Snapshot comparison to the real-report menu. Users select a validated saved baseline from the same repository/schema, see added/removed/changed nodes and relationship-record counts, filter changes, and inspect current evidence. Baseline selection survives navigating to evidence and back. Comparison reports indexed metadata changes, not source or behavioral equivalence; analyzer coverage and renames are explicit limitations.
- Added Who depends on this file to the source inspector. It follows reverse local-import paths, distinguishes direct and transitive importers, avoids cycles, and offers paginated inspectable results. Unknown aliases, runtime behavior and Go package-directory imports remain outside this file-level view.
- Verification: 11 frontend/API tests pass, including comparison identity/order handling, edits/removals, and reverse-import cycle handling. TypeScript and focused ESLint pass. Backend unchanged since its 81-test checkpoint. Build and publication follow below.


## 2026-09-13 - Local completed-report retention

- Published snapshot comparison and dependency impact to GitHub main as d402d92 after successful build, TypeScript, ESLint and 11 frontend contracts.
- Added opt-in CODANDY_REPORT_ROOT local persistence. Complete atlas/source/event snapshots are validated and written via fsynced temporary file plus atomic replace, capped at 128 MB each. Startup restores valid completed snapshots and applies max_jobs retention; incomplete jobs are not resumed. Single process per directory only.
- Added GET /api/analyses recent-report metadata and intake Recent reports/reopen flow. Reopened jobs preserve source access. In-memory behavior remains the default.
- Added restart/source/SSE integration, corruption/path mismatch, retention, atomic-failure preservation and recent-report schema coverage. Backend suite: 86 passed. No Dockerfile edits; .reports is excluded from Git/container context. Browser QA remains unavailable.
- Next: final frontend contracts/build, scratch cleanup and publication. Shared persistence/access controls, repository uploads, Codex and debugging remain unfinished.
- Final retention checks: 86 backend tests, 12 frontend contracts, TypeScript, ESLint, Ruff and production build pass. Removed all three new pytest directories for this slice.


## 2026-09-13 - User-selectable brand color schemes

- Published opt-in local retention and recent-report reopening as ca4327d.
- User requested Forbright and Tennessee themes with the current scheme preserved as default. Added Codandy Midnight (default), Forbright, Vol Orange, Violet Night and Graphite. Shared theme picker appears in intake, sample report and live report; next-themes persists the device preference using codandy-theme and sets data-theme before paint. Picker hydrates with a stable default value.
- Converted hardcoded report backgrounds to shared surface variables while retaining default shades. Brand accents, gradients, focus rings, panels and sidebar adapt consistently; status/risk colors remain semantic.
- Forbright primary references verified from https://maintenance.forbrightbank.com/ public inline CSS: navy #18272d, green #41ac3a, supporting green #33812d. Theme adapts dark supporting surfaces for legibility; it does not claim bank affiliation or reproduce a full proprietary brand guide. UT official palette: https://brand.utk.edu/standards/colors/ orange #ff8200, white and Smokey #4b4b4b, with darker supporting surfaces for this app.
- Initial build, TypeScript and focused ESLint passed. Contrast spot-check prompted darkening the Forbright card surface to improve small green labels. Final checks and publication follow. Browser visual QA remains unavailable in this session.
- Final theme checks: TypeScript, changed-file ESLint, all 12 frontend/API tests and production build pass. No browser QA claim is made. The backend remains at its previously verified 86-test checkpoint.


## 2026-09-13 - Retained-report removal and final publication checkpoint

- Published the five-theme picker as cde0966. Original Codandy Midnight remains default; Forbright, Vol Orange, Violet Night and Graphite preferences persist per device.
- Added confirmed removal in Recent reports and DELETE /api/analyses/{id}, including hosted proxy forwarding. Active jobs return 409. Snapshot deletion precedes in-memory removal, and storage failures return a sanitized error without reporting success.
- Verified removal clears captured sources and survives API restart; active-job refusal and proxy method/body behavior are covered. 87 backend tests and 13 frontend/API tests pass; TypeScript, Ruff and focused ESLint pass. Production build and scratch cleanup follow.
- Next substantive work: browser interaction/theme/mobile QA when a browser is connected; deeper parser coverage and import/flow precision; repository upload inputs; AI provider adapter and grounded Q&A. Multi-user hosted deployment remains blocked on access control/shared state and the explicitly deferred Dockerfile. Local snapshots do not solve distributed state.
- Final removal checkpoint: production build passed and the new pytest scratch directory was removed. Ready to publish; no browser QA or hosted deployment was performed.


## 2026-09-13 - Dependency analyzer, versions and public advisories

- User requested a dedicated Dependencies menu for third-party packages, versions, usage, updates and vulnerabilities. Added it to live and sample navigation; sample mode requests a real analysis rather than inventing package metadata.
- Enriched dependency nodes with ecosystem, sanitized numeric declared constraints, identified version and basis. Supports npm dependency/dev/peer/optional groups; NuGet inline/child versions; Python requirements/PEP 621/Poetry version metadata; and Go block/single-line requirements. npm package-lock and NuGet packages.lock supply lockfile versions where supported. Version URLs, credentials, variable expressions and unsupported tags are not retained.
- Dependencies offers ecosystem/search filters, manifest and scoped import-name evidence, and explicit per-package public checks. Public lookups use fixed npm/PyPI/NuGet/Go hosts plus OSV, disable redirects/environment proxies, cap responses at 4 MB and bound concurrent checks. NuGet base address is discovered from the official service index and still host-allowlisted.
- Results separate public registry versions, update ordering and OSV advisory matches, with timestamps and links. Unknown/ranged versions skip OSV rather than claim a clean result. Declared/locked versions are not running-version proof; no installs, compatibility checks or exploitability claims are made. Partial advisory pages are marked incomplete.
- Added package/version redaction, lockfile evidence, multiple ecosystems, unknown versions, provider outage, pagination, endpoint node ownership, proxy query whitelist, advisory-link validation and usage-scope regression cases. Before final edge-case tests: 102 backend tests and 16 frontend contracts pass; TypeScript and Ruff pass.
- Live host-network checks succeeded for npm lodash 4.17.20, NuGet Newtonsoft.Json 12.0.1, PyPI requests 2.19.1 and Go golang.org/x/text v0.3.0: registry metadata and OSV advisories returned for all four. Sandbox-only network checks correctly returned unavailable. Browser QA remains unverified.
- Remaining coverage limits: pnpm/yarn/Python locks, central NuGet version management, a complete transitive package graph and verified namespace-to-package binding. Existing atlases need reanalysis for the new metadata. Public checks require a retained backend job; imported snapshots retain only static metadata.

## 2026-09-13 - Resume checkpoint: Demo background and dependency correctness

- Resumed the unpublished dependency analyzer slice. Renamed the visible Forbright option to Demo background, preserving its stored theme ID so existing preferences keep working.
- Fixed conflicting manifest versions, unbalanced constraints, npm partial ranges, NuGet minimum-version semantics, and Go require parsing. Go replacement/exclusion directives now withhold an identified version with a visible explanation. NuGet lock evidence with unsupported target-framework versions no longer silently chooses a remaining version.
- Version semantics checked against https://learn.microsoft.com/en-us/nuget/concepts/package-versioning and https://go.dev/doc/modules/gomod-ref.
- Checkpoint: 113 backend tests, Ruff, 16 frontend/API tests, TypeScript and focused ESLint pass. Dependency production build passed; rebuilding after the display-label/note edits. Browser inventory remains empty, so visual QA is outstanding.
- Next slice: make dependency findings easier to export and review, preserving the separation between static inventory and public observations.
- Production rebuild passed after the Demo background rename and version-note UI. Publishing this checkpoint before starting export/review work.

## 2026-09-13 - Dependency review export and triage

- Published the analyzer/theme checkpoint as 7c38a13 to GitHub main.
- Added review-state filters and package-row check indicators, plus a JSON download containing all static declarations and separately timestamped public checks from this report session. Unchecked declarations stay distinct from unavailable/incomplete checks. Filters do not silently omit exported inventory.
- Fixed async lookup errors appearing against a different selected package. Selection now exposes aria-pressed state. Public check results remain session-local; the download makes them retainable without changing the canonical atlas.
- Verification: 17 frontend/API tests, TypeScript and focused ESLint pass. Backend remains at the 113-test checkpoint; no backend changes in this slice. Production build follows.
- Production build passed; removed the scratch directories created for dependency tests. Next: improve static .NET project-to-project architecture evidence.

## 2026-09-13 - .NET project-reference architecture

- Published dependency review/export as c9c6020 to GitHub main.
- Added ProjectReference declaration nodes, indexed-manifest path matching, inferred project dependency edges, and Architecture cards with matched/unresolved counts and inspectable evidence. IDs are independent of unrelated project additions. Third-party package totals exclude project-to-project references.
- Dynamic, external, missing and secret-excluded targets stay unresolved without copying their raw expressions into atlas labels. Conditions, MSBuild imports and reference-output metadata remain unevaluated; links do not assert build inclusion or runtime assembly use. Source reference: https://learn.microsoft.com/en-us/visualstudio/msbuild/common-msbuild-project-items.
- Backend verification: 120 tests and Ruff pass, covering path boundaries, XML namespaces, conditional candidates, stable IDs and schema-grounded report steps. Frontend contract fixture now includes real .NET reference evidence; final checks follow.
- Final checks: 17 frontend/API tests, TypeScript, focused ESLint and production build pass. Next slice: project-dependent impact inspection using these graph edges.

## 2026-09-13 - Project impact inspection

- Published static project-reference architecture as 0eebf90.
- Selecting a project now shows its direct and transitive candidate dependent projects in the source inspector. Traversal excludes unresolved links and package dependencies, terminates on cycles, and retains the existing file-import impact view for file nodes.
- Verification: 18 frontend/API tests, TypeScript, focused ESLint and production build pass. Backend remains at 120 passing tests. Next: bounded static central NuGet declaration metadata.

## 2026-09-13 - Central NuGet evidence and handoff checkpoint

- Published project impact inspection as 346419d.
- Added bounded/cached parsing of the nearest indexed Directory.Packages.props. Same-name PackageVersion Include/Update entries become separately labeled central version candidates with source evidence and an inspect action. Multiple candidates remain visible (capped at eight); unsafe values and DTD/entity declarations are withheld. Imports and conditions are not executed or evaluated, and candidates never silently become advisory-check versions.
- Central candidates are included separately in dependency review downloads. Version behavior reference: https://learn.microsoft.com/en-us/nuget/consume-packages/central-package-management.
- Backend: 125 tests and Ruff pass, including nearest-file selection, child Version metadata, conditional alternatives, invalid XML and unsafe-value withholding. Frontend/export checks follow.
- Remaining priorities: connected-browser interaction/mobile/theme QA; additional lockfile formats and transitive inventory; deeper parser/flow inference; ZIP/folder input; grounded AI provider integration. Hosted shared state/auth and the deferred Dockerfile remain unfinished. Reanalyze older reports to obtain the added dependency and .NET reference metadata.
- Final checkpoint: 125 backend tests, 18 frontend/API tests, Ruff, TypeScript, changed-component ESLint and production build pass. Scratch directories from these slices were removed. Browser surfaces remain unavailable; no visual QA or hosted deployment is claimed. Publishing all completed slices to GitHub main.

## 2026-09-13 - Overview drilldowns and contextual questions

- Started from 8a69274. User requested clickable Source files, Symbols, API routes and Tests cards, plus more AI question entry points. No account quota readout is available to confirm remaining Astra usage.
- Both sample and real overview cards now open searchable, paginated detail sheets with source-inspection actions and explicit route/test coverage limits. The sample lists only supplied examples and identifies its headline counts as illustrative; no missing sample tests or inventory are fabricated.
- Added a shared Ask Codandy question composer on report pages, inventory drilldowns, report findings, selected source nodes, dependencies and loaded snapshot comparisons. Drafts include scoped graph evidence and reviewable context, suggested questions, clipboard copy and text download. Source bodies are not included; excerpt limits and omitted evidence are disclosed.
- Removed sample canned AI answers. Live in-app model responses remain unimplemented: no provider is configured and no Codex executable was discoverable on PATH. Asked user which connection to target; until selected/configured the composer explicitly prepares questions for another assistant and never sends data automatically.
- Verification: 20 frontend/API tests, TypeScript, changed-file ESLint and production build pass. Backend unchanged from its 125-test checkpoint. Browser inventory is empty, so interaction/mobile visual QA remains outstanding.
- Stop/resume: finalize publication of this UI slice. Next required AI work is provider selection/configuration and a bounded backend adapter with validated citations; do not claim question export is an integrated model conversation.

## 2026-09-13 - Local ChatGPT subscription connection

- User selected account/subscription access instead of API billing. Verified official Codex App Server auth and model-list documentation: https://learn.chatgpt.com/docs/app-server and https://learn.chatgpt.com/docs/auth. This supports a local Codex client; do not present website login as general hosted API entitlement.
- Found the installed Codex 0.154.0 executable outside PATH and generated its protocol schemas into ignored .tools for compatibility inspection. Added a bounded stdio bridge using an isolated ignored auth profile. Tokens remain managed by Codex; existing auth files are never read/copied. Browser login, connection status, discovered models/efforts, and schema-validated answer requests are implemented. API-key fallback is disabled.
- Local routes reject non-loopback peers/hosts, unapproved browser origins and missing custom headers. Hosted proxy refuses these routes. Questions accept only retained analysis IDs and validated node selections, rebuilding a bounded graph context server-side. No source bodies or arbitrary client context is forwarded. Tools/plugins/browser/shell features are disabled; permission requests are refused, and threads are ephemeral/read-only.
- UI now exposes Connect ChatGPT, official sign-in link, Check connection, model/effort choices and Ask using my plan. Every question is independent. Responses show the submitted question and cited IDs; IDs are checked, not the factual truth of every claim.
- Configured this machine through ignored backend/.env, and verified the real installed runtime handshake returns connected=false. Restarted the previously stale backend (which lacked even recent-report endpoints) with updated code; existing memory-only reports require reanalysis. Verified signed-out status directly on port 8000 and through the live frontend proxy on port 5173.
- Validation: 131 backend tests, 23 frontend/API tests, Ruff, TypeScript, changed-file ESLint and production build pass. No authenticated model completion or visual browser QA is claimed. User must complete OpenAI sign-in; remaining work is the first live answer smoke check, then streamed/multi-turn answers and richer evidence retrieval.

### Authenticated completion checkpoint

- User completed OpenAI sign-in; the isolated local connection reports Plus. Model discovery returns account-accessible choices and defaults. A real answer to the user's Symbols question succeeded through localhost:5173, using the default model/effort and three valid retained graph citations.
- Fixed installed-runtime compatibility: Codex 0.154.0 accepts readOnly/networkAccess=false but rejects the newer restricted-access object. Kept tools disabled, approvals refused, and the working directory isolated. Ephemeral threads have no rollout to archive; dispose of their process after each question instead. Added a focused protocol/cleanup regression test (seven assistant tests pass).
- Preserved the user's current completed report and all 161 captured source files into ignored backend/.reports before restarting. Enabled local report persistence in ignored backend/.env. The backend is running the fixed code on port 8000, with the report restored; frontend remains on port 5173. No credentials or local snapshots are included in publication.
- Stop/resume: local subscription Q&A is functional and live-tested. Previous full validation passed (131 backend / 23 frontend tests plus build); the new regression adds one backend test. Visual browser QA remains unavailable. Next useful slices are streamed answers, multi-turn history, and richer bounded context with inspectable citations.


## 2026-09-13 - Fresh-history repository preparation

- Preserved a verified source-only backup and copied all 170 tracked files into a new independent repository. Application code is unchanged; this progress entry is the only content addition. No original Git objects, local credentials, reports or generated files were copied.
- Publish the fresh root commit to abwalls/codandy using only the verified GitHub no-reply identity. Keep abwalls/codandy intact until the user reviews the new repository and explicitly authorizes final deletion.
- Next: verify the published root commit and source parity, then review old-commit availability and final repository naming with the user. Do not merge or push old history into this repository.

## 2026-09-13 - Codandy rename

- Renamed product branding, PWA metadata, frontend/backend packages, workspace and assistant components, repository URLs, generated review labels, artifact directory and configuration names to Codandy/codandy. The graph schema and analysis behavior remain unchanged. Legacy environment variables and local assistant headers remain accepted; the browser theme storage key remains stable to retain user preferences.
- Working only from the fresh personal-account history. GitHub repository target: abwalls/codandy. Intended active local checkout: C:/Users/andre/source/repos/codandy. The old local folder is a backup; never merge or publish its Git history.
- Fresh-clone validation uncovered the Vite helper in ignored build/ was absent from published source. Included the existing helper and its MIT license under scripts/ and updated the import, making clean-clone builds reproducible.
- Validation: 134 backend tests, 23 frontend/API tests, TypeScript, ESLint, Ruff and production build pass. New settings tests verify legacy environment/.env compatibility and precedence of new names. Remaining final checks: local service restart with retained reports/auth, repository publication and hosted preview rename.

### Codandy local runtime checkpoint

- Published the tested rename to the public personal repository https://github.com/abwalls/codandy. Active clean checkout moved to C:/Users/andre/source/repos/codandy; the original code-atlas directory remains only as an archive/tool cache. Never merge its old Git history.
- Created the new backend environment and recreated Windows pnpm links after the move. Backend and frontend now run from the Codandy folder on ports 8000 and 5173. Verified frontend HTTP 200/Codandy title, two retained reports through the frontend proxy, and connected Plus-plan AI status with the new local header.
- Dedicated local Codex sign-in and report snapshots were preserved in ignored directories. Runtime uses CODANDY_* settings. The managed Python interpreter and uv are now installed inside Codandy; the running app no longer depends on the archived project directory.
- Renamed the existing owner-private Sites preview title/slug to Codandy. Public GitHub publication is complete; the hosted sample/frontend remains separate from the local Python/AI services. Final private preview deployment follows this checkpoint.

### Final publication checkpoint

- Private preview deployment succeeded at https://codandy.abwalls.chatgpt.site. Public source is https://github.com/abwalls/codandy. The hosted frontend/sample remains separate from local Python analysis and subscription AI.
- Verified the backend after moving its interpreter: codandy-api health and connected Plus status through localhost:5173. The clean history uses only the personal no-reply identity; no former-company matches were found in tracked content.


## 2026-09-13 - Debugging-first strategy and roadmap

- Reviewed the private Downloads/NEWPLAN.md proposal, current schemas/analyzer and official Sentry, OpenTelemetry, DAP, Excalidraw and tldraw documentation. Published a cited research artifact at docs/DEBUGGING-STRATEGY.md; did not republish the private proposal or its unverified market statistics.
- Replaced PLAN.md and ROADMAP.md with Sentry/stack investigation as D1, performance evidence and a first-release whiteboard as follow-on gates, and later MCP/DAP/change verification. Updated ARCHITECTURE.md and AGENTS.md to separate current capabilities from planned records and to supersede the old debugging deferral. Historical plans are labeled under docs/archive/.
- Important corrections: actual graph has six relationship types, IDs depend on kind/path/name, static tests are not coverage, and exception stacks do not establish function durations or precise null values. Keep atlas 0.2 unchanged; runtime observations, mappings, hypotheses and board plans are separate.
- This slice changes documentation only. No Sentry credential was requested/read, no live Sentry API connection was tested, and no runtime feature was implemented or redeployed. Previous application checks remain the baseline; document links, diff and personal-account history are checked for this publication.
- Next implementation: D1 normalization/redaction/contracts and synthetic TS/JS, Python/.NET fixtures, then one read-only live Sentry event-to-source flow with persistence and reviewed AI export. Sentry deployment/account selection remains open; default design is local-first with Cloud support and account-free imports.
- Directory: all active work is in C:/Users/andre/source/repos/codandy. This conversation still has the archived code-atlas directory as its configured workspace; open Codandy in the client for future sessions. Do not rename/merge the archive or restore its old Git history.


### 2026-09-14 - Strategy publication checkpoint

- Resumed the interrupted planning slice, verified the saved drafts and completed the reference inventory. Corrected stale README claims that local AI/persistence were unavailable. Checked local document links, code fences, former-company references and documentation-only diff scope.
- Planning deliverables are ready for personal-account publication. No runtime code, dependencies, credentials or deployment configuration changed; no application test/build rerun or Sentry live-integration claim is made for this documentation-only slice.
- Implementation starts with PLAN.md D1a (sanitized event/stack contracts and fixtures), then D1b/D1c (read-only Sentry connection and revision-aware source binding). Account/region remains an implementation-time choice; import fixtures do not depend on it.


### 2026-09-14 - Sentry implementation resumed

- Reviewed Claude's untracked normalization/contracts and two synthetic fixtures. No connector, API, UI or tests were present. Preserved that foundation; fixing parsing/redaction and adding a local read-only event/import flow. Live credentials have not been supplied or tested.


### 2026-09-14 - Sentry import and read-only UI slice

- Preserved Claude's normalizers/contracts and fixed pre-redaction stack clipping, JS cause-frame merging, partial-ID chain inference, quoted secret assignments and short bearer tokens. Reject duplicate JSON keys; restrict provider IDs; retain visible budgets/omissions.
- Added loopback/header/origin-guarded import/status/retrieval API, backend-held SecretStr Sentry settings, fixed Cloud hosts, no proxy/redirects, 2 MiB response cap, bounded read deadline and one explicit GET per click. Added Errors & stacks page, navigation, source-context/breadcrumb inspection and reviewed sanitized download. No raw telemetry is persisted or sent to AI.
- Initial validation: 168 backend tests and 23 existing frontend contracts passed; added a Python-to-TypeScript debugging contract and extra transport regressions for final checks. D1 source binding, case persistence, issue browsing and AI brief work remain open. No live account configured/verified.


### 2026-09-14 - Sentry validation and handoff checkpoint

- Full backend suite passed 168 tests; the final expanded debugging suite passed all 37 (three additional transport tests). All 24 frontend contracts, TypeScript, changed-file ESLint/Ruff and production build passed. Cross-language test validates actual Python-normalized Sentry data with the frontend schema.
- Restarted only Codandy's backend (wrapper PID 4188), preserving report storage. Verified HTTP 200 on http://localhost:5173/debugging and a synthetic JSON import through the frontend proxy returning two sanitized exception records. Sentry status correctly reports not configured. No live provider request was made.
- Browser automation returned no available browser surfaces; visual interaction QA remains unverified. The local frontend stays running for user testing. Hosted UI remains a local-workflow entry point, not a hosted telemetry connector.
- Next: configure a user-owned event:read token in ignored backend/.env to validate a real event; then project/issue selection, revision-aware source binding and durable cases. Do not mark D1 complete or claim live verification. Current slice is ready for personal-account GitHub and owner-private Sites publication.


### 2026-09-14 - Sentry slice published

- Published implementation commit 574eae4 to abwalls/codandy; author and committer both use the approved abwalls GitHub no-reply identity. Tracked source contains no former-company text.
- Owner-private Sites version 4 deployed successfully from that implementation commit at https://codandy.abwalls.chatgpt.site (deployment appgdep_6aa81c86f45481919956df6956561f38). Local testing entry: http://localhost:5173/debugging; backend remains running on 8000. This final log-only checkpoint does not change the deployed runtime.
- Sentry credentials and a real account verification remain outstanding; all delivered provider tests use synthetic responses. Continue with the remaining D1 items listed above.


### 2026-09-14 - Investigation persistence started

- Resumed from dd6efa5. Adding local saved cases with independent sanitized evidence, bounded storage, atomic writes, notes/status and explicit deletion. Imports retain at most 20 normalized observations awaiting Save; raw telemetry is not retained. No Sentry account is needed for this slice.


### 2026-09-14 - Saved-case tests passed; source matching started

- Saved cases now support save/reopen, scrubbed notes/title edits, open/resolved/archived status and explicit delete. 43 focused debugging/persistence tests passed, including restart recovery, pending-observation eviction and atomic-write failure. TypeScript passed.
- Adding persisted frame-to-snapshot candidates next. Matching uses only indexed file paths, preserves ambiguity and treats user-supplied runtime commits as unverified; mismatches remain visible. No exact match is claimed without independent revision evidence.


### 2026-09-14 - Source matching and reviewed AI briefs

- Added persisted frame candidates against retained snapshots, deployment-prefix matching, duplicate-path ambiguity, runtime-commit mismatch labels and captured-source viewing. 54 focused persistence/import/binding tests passed. Unknown revisions never become exact bindings.
- Added a bounded debugging brief with observation/frame citation IDs, clearly labeled user notes, explicit omissions and no source-body expansion. Added local Codex Q&A using the reviewed packet digest: stale reviews and citations outside the packet are rejected. Model tools remain disabled and each question uses an ephemeral thread. Validation for this slice is in progress; no live AI or Sentry request has been made.


### 2026-09-14 - ZIP project upload intake (Claude, at Andrew's request)

- Added `POST /api/analyses/archive` (raw `application/zip` body, streamed with a byte cap, new `CODANDY_MAX_UPLOAD_MB=100`) and a homescreen ZIP dropzone next to the GitHub form. Extraction in `backend/app/archives.py` validates every member name before writing, rejects links/encrypted members, bounds declared and actual bytes, file count, depth and case-folded conflicts, unwraps a single wrapper folder, and never writes `EXCLUDED_DIRS`/`SECRET_NAME` paths. Uploads reuse the spawned analyzer, source capture and persistence; atlas stays 0.2 with `repository = {source: archive, name, ref: upload}` and no commit (archive Git metadata is never read). `ArchiveUpload` is intentionally not a JSON request model.
- Verification: 218 backend tests (27 new archive tests), 26 frontend/API contracts, TypeScript, changed-file ESLint and Ruff, production build, and a live isolated-uvicorn smoke (content-length and chunked uploads, busy/415/422 rejections, exclusions, source traversal 404, clean workspace). Whole-backend `ruff check .` still reports the pre-existing I001 in `app/debugging/brief.py`.
- Not verified: browser/visual QA (Chrome extension unavailable), upload through the Vite proxy (running :8000 backend has no `--reload` and was not restarted), hosted Worker streaming. Nothing committed: git reports dubious ownership for this session's user. Full design notes and open items: ZIP-UPLOAD-NOTES-FOR-ASTRA.md.


### 2026-09-14 - Architecture visualization and ZIP handoff review

- User steered continued feature work toward Architecture diagrams; reviewed Claude's ZIP-upload handoff and preserved its changes. Adding an interactive static dependency map with folder/project views, search, focus, zoom, evidence drilldowns and explicit inferred/unresolved limits. No architectural service/layer claims are inferred from folder names.
- ZIP follow-ups identified: bound central-directory metadata before ZipFile allocation and remove queued uploads if their future is cancelled. Existing source traversal, excluded paths and archive-no-revision rules remain required.


### 2026-09-14 - Architecture, ZIP and investigation validation

- Interactive Architecture map now shows real project references and joined IMPORTS/RESOLVES_TO evidence, including Go directory targets. Added search/depth/focus/zoom, source drilldown, contextual Ask, resolved/inferred legend and explicit view budgets. Refined mobile to readable connected cards after screenshot review.
- Preserved Claude's ZIP intake and added metadata preflight before ZipInfo allocation, forged-directory-count checks and cancelled-queue cleanup. Directory bounds are 50,000 entries / 8 MiB; split/ZIP64 directories are explicitly unsupported.
- 221 backend tests and 28 frontend contracts passed. Headless Edge QA passed actual ZIP upload through Vite, Architecture desktop/mobile and keyboard focus, case save/edit/reload, source matching/viewing, and reviewed brief preparation with no page errors. Provider calls were simulated, not live. Synthetic QA cases/reports were removed.
- Found and fixed an existing test-isolation defect: TestClient lifespans were loading personal report persistence from backend/.env. The retention test replaced the local report list. Recovered the two original 161-file reports byte-for-byte from the preserved archive copy (IDs 4f347663-b46c-4223-aab0-57ac34e49497 and 8f9966e8-92e5-4ce4-bb72-66e3161954cb); quarantined known synthetic reports under ignored .tools. New autouse fixture redirects all app test storage and disables provider connections. Verify real report hashes remain unchanged after tests. Backend restarted to load recovered reports (wrapper PID 39840). No repository history was restored or merged.
- Next: finish publication/build checkpoint, then continue Sentry project/issue browsing and the remaining roadmap. D1 live account validation remains open.


### 2026-09-14 - Review findings 1–4 fixed (Claude, at Andrew's request)

- Tests: conftest now disables backend/.env and CODANDY_*/CODE_ATLAS_* variables for every Settings() instance (the retention hole was a fresh Settings() inside a test); regression test failed before the fix and passes after. API: new AllowedHosts middleware returns 403 for unapproved Host headers (DNS rebinding); CODANDY_ALLOWED_HOSTS defaults to localhost/127.0.0.1/::1; smoke.py uses base_url localhost. Bindings: webpack://, webpack-internal://, app:/// and ./ frame paths now bind; ../ and ~/ are suffix-only. Analyzer marks import nodes with local_import; the Architecture map counts only local imports as unresolved and labels older atlases honestly.
- Verification: 241 backend tests, 29 contracts, ruff, tsc, changed-file ESLint and build passed; personal report/investigation hashes unchanged across pytest; live isolated-uvicorn host probe returned 200 for local names and 403 for a rebound name on GET/POST/DELETE. Not verified: browser QA of the new legend, real Sentry path forms, and the running :8000 backend (not restarted). Nothing committed. Details: CLAUDE-FIXES-FOR-ASTRA-2026-09-14.md; findings 5–7 remain open.
- Browser QA (Claude in Chrome): homescreen and saved-atlas Overview screenshots verified; Architecture legend verified by DOM query, but its screenshots stalled twice (needs Edge headless recheck). QA showed `@/` path aliases mislabelled as packages, so JS/TS `@/` imports are now `local_import` (241 tests, 29 contracts, ruff still pass; storage hashes unchanged). Roadmap: the map draws 0 links for Codandy itself because tsconfig aliases and the backend/ Python package root are unresolved.
- Follow-up at Andrew's request: the analyzer now reads tsconfig/jsconfig paths and baseUrl as data (JSONC, relative extends only, repository-contained targets, unique-candidate rule, inferred links) and resolves absolute Python imports from the nearest pyproject.toml/setup.py/setup.cfg/requirements.txt root (including src/) before the repository root. A Codandy sample went from 0 to 3 folder-level map connections (258 resolved imports: 176 via the @/* alias, 74 via backend/; no local imports left unresolved). 243 backend tests, 29 contracts and ruff pass; personal storage hashes unchanged. Browser view of the populated map not verified.
- Committed the review fixes and alias work as 6485448 on branch claude/review-fixes-and-import-aliases (abwalls author and committer, not pushed).


### 2026-09-14 - Whiteboard planning (Claude, at Andrew's request)

- Andrew's decisions: the Whiteboard is the next track; repository link is optional; the AI provider is the local Codex subscription; outputs are Markdown plan.md and ticket.md, a printable report page, and a GitHub issue draft (copy only in v1). Drafted docs/WHITEBOARD-PLAN.md with milestones W0–W6 and updated the D4 entries in PLAN.md and ROADMAP.md.
- Verified for the plan: Excalidraw 0.18.1 is MIT with a React ^19 peer and is client-only; vinext's dynamic shim supports ssr: false; fonts default to the esm.run CDN and must be self-hosted; restore, export and skeleton APIs exist (skeleton is beta); Codex app-server turn/start accepts text, image and localImage with a per-turn outputSchema, but image limits and model support are undocumented, so W0 must probe them. No code written; nothing committed for planning.


### 2026-09-14 — Whiteboard implementation started

- Reviewed Claude's WHITEBOARD-PLAN and preserved its review-fix branch plus uncommitted AGENTS/progress edits. Whiteboard is the active track; the earlier staged Sentry-browser script was never applied.
- Added Excalidraw canvas, self-hosted fonts, local board storage with revision conflicts/atomic writes, deterministic scrubbed review packets, optional snapshot context, interpretation/plan stages through the existing Codex bridge, source-element citation validation, task dependency validation, saved plan versions and Markdown/ticket/print/issue-draft outputs.
- Enhanced the plan with exact first-slice boundaries: text-only interpretation, explicit user corrections, proposed paths only, combined artifact limits, stale review/result rejection, and no claim of fully completed W0–W5.
- Initial focused validation: 19 board/assistant tests passed; full validation and browser QA are in progress. No live model requests have been made.


### 2026-09-14 — Whiteboard validation and live AI

- Full backend suite passed: 255 tests. Personal report/case SHA-256 hashes were unchanged. TypeScript, lint and production build passed; the existing 29 frontend contracts passed, with a new Python/TypeScript board contract check added for final validation.
- Headless Edge: create, labeled rectangle drawing, geometry/label presence in the review packet, autosave, JSON export, reopen with notes, and mobile no-overflow checks passed. Corrected the test to drag on the canvas rather than the properties panel. Synthetic test boards were deleted.
- Font QA caught the package's CDN fallback: its runtime URLs include `fonts/`, so assets must live in `public/excalidraw-assets/fonts/`. Fixed the copy path; repeated labeled drawing produced zero external requests and zero page errors. The canvas remains lazy-loaded; the largest emitted lazy library chunk is about 1.82 MB uncompressed, and the observed build phases totaled about 21 seconds (no exact prior bundle-size baseline was captured).
- Live subscription smoke used only a synthetic Task API board: `gpt-6-astra` completed both interpretation and plan stages; schema/citation checks and plan/ticket export passed. The synthetic board was deleted. No personal repository or board content was sent by this test.
- Restarted the backend to load whiteboards and Claude's fixes (wrapper 36820, worker 17372). Whiteboard functionality is local at http://localhost:5173/whiteboard. Final checks/publication follow this checkpoint.


### 2026-09-15 - Visual atlas V0–V2 (Claude implements, Astra reviews)

- At Andrew's request, committed Astra's verified Whiteboard work on main as 460a9d3 (255 backend tests and 30 contracts beforehand). Visuals continue on branch claude/visual-atlas under docs/VISUALIZATION-PLAN.md, with milestones V0–V7, honesty and accessibility rules, library decisions and Astra's review protocol.
- V0: the analyzer and ZIP intake now skip __pycache__, .pytest_cache, .mypy_cache and .ruff_cache. New lib/architecture-layout.ts provides a deterministic layered layout (depth-first back edges, longest-path layers, virtual waypoints, barycenter sweeps, Tarjan cycles, isolated row) and a layer-ordered dependency matrix where back edges always fall below the diagonal. architectureMap accepts expanded folders.
- V1/V2: the Architecture map replaces the 10-group ring with Layered and Matrix views (40/60-group budgets, 12 on mobile), folder split and collapse, a cycle notice and a matrix cell evidence panel. No new dependencies.
- Verification: 256 backend tests, ruff, 34 contracts (4 new), tsc, changed-file ESLint and build passed; personal report, case and board hashes unchanged. On Codandy's atlas: sensible layers and no cycles; 40/60-group layouts take 4/16 ms. DOM-level browser QA passed for layered, focus, split, matrix and cell evidence, with no console errors. Not verified: pixel screenshots, because the Chrome tab was hidden and paint was paused (not an app defect), other themes, and a real repository with folder-level cycles. Handoff: CLAUDE-VISUALS-2026-09-15.md.


### 2026-09-15 - Data model and contract diagrams, AD0-AD2 (Claude implements, Astra reviews)

- **Plans on main (not pushed):**
  - Committed the integrations plan (c4c6782) and the architecture diagrams plan (8d334c5).
  - Implementation continues on branch claude/architecture-diagrams, stacked on claude/visual-atlas with main merged in.
- **Backend:**
  - New `backend/app/structure/` builds `structure-0.1` in the analysis worker after the atlas.
  - Data models come from Prisma, SQL DDL (path-ordered CREATE/ALTER/DROP), SQLAlchemy and Django. Data contracts come from Pydantic, dataclasses, TypedDicts and TypeScript interfaces and object aliases.
  - Only atlas file nodes are read, as text.
  - Budgets: 2,000 entities, 5,000 types and 300 fields each. Diagrams get 85% of the analysis deadline, and any failure becomes a limitation, not a failed report.
  - The result is written to `.codandy/structure.json`, persisted in snapshots (optional, so older reports still load) and served at `GET /api/analyses/{id}/structure`. The hosted proxy allows the path.
- **Frontend:**
  - `lib/structure-api.ts` is the zod mirror of the contract.
  - `lib/structure-diagram.ts` builds the ERD and contract views and the Mermaid `erDiagram`/`classDiagram` export with sanitized identifiers.
  - `lib/architecture-layout.ts` factors out `orderLayers`, with V1/V2 output unchanged, and adds a left-to-right record layout.
  - The Architecture tab now switches between Dependencies, Data model and Data contracts:
    - crow's-foot ends
    - schema and folder selectors
    - search, focus and Keys only
    - stubs for undeclared or elsewhere types
    - evidence buttons
    - Ask scopes
    - mobile lists
- **Verification:**
  - 267 backend tests (11 new), ruff, 40 contracts (6 new), tsc, changed-file ESLint and build all pass.
  - Personal report, case and board hashes are unchanged.
  - On a source copy of Codandy: 88 contract types and 92 links in 0.33 s; no database schemas, as expected.
- **Not verified:** browser rendering and interaction of the new views (the running :8000 backend was not restarted, so it lacks the endpoint), other themes, and large real schemas. Handoff: CLAUDE-HANDOFF-2026-09-15.md.


### 2026-09-15 — Resume, diagram review and offline trace import

- Resumed on claude/architecture-diagrams at 50ab730. Claude committed the prior whiteboard implementation and added visual/ERD/contract code; ticket providers and monitoring integrations were plans only. Reviewed both handoffs and integration/diagram plans.
- Fixed verified annotation-token leakage and generic-parameter false links (both new regressions failed before fixes). Added an atlas checkpoint so optional diagram timeout/crash preserves completed analysis. 17 focused structure/worker tests passed; review details in ASTRA-DIAGRAMS-CR-2026-09-15.md.
- Added the first offline M2 slice: local OTLP JSON import (2 MiB, 1,000 spans), exact nanosecond strings, duplicate-ID validation, parent/missing/cycle labels, attribute allowlist/redaction, and a filterable waterfall/selected-span view in Errors & stacks. Reviewed sanitized export and explicit ephemeral retention. Ten focused backend tests and TypeScript/ESLint checks passed. No provider credentials, network receiver or external writes were introduced.
- Plan refinements distinguish offline import from provider foundation dependencies, proposed architecture patterns from detected evidence, and ticket drafts from actual writes. Full regression, browser review, whiteboard recheck and publication remain in progress.

### 2026-09-15 — Regression and browser verification complete

- Passed 280 backend tests and 41 frontend/API contracts, Ruff, TypeScript, changed-file ESLint, diff checks and production build. Backend saved report/case/board hashes did not change. Existing dependency deprecation and large-bundle warnings remain non-blocking.
- Edge QA passed ERD rendering in all five themes, keyboard selection, desktop/mobile data contracts, OTLP import/filter/selection/redaction/reviewed export, and whiteboard drawing/label/notes autosave/reopen/export. Whiteboard loaded without external asset requests. Synthetic QA reports and boards were removed by ID/title-scoped cleanup.
- Updated the roadmap and agent guide to replace stale W0-not-started status. Review handoffs: ASTRA-DIAGRAMS-CR-2026-09-15.md and ASTRA-INTEGRATIONS-M2-2026-09-15.md.
- Next boundary: provider foundation and reviewed Linear ticket creation, plus observed sequence views. Jira, ClickUp, Datadog, live OTLP collection, image-based whiteboard interpretation and autonomous implementation are not complete. Publication follows this validated checkpoint.

### 2026-09-15 — Published and stopping checkpoint

- Reviewed changes fast-forwarded into main and pushed to abwalls/codandy. Both new commits use abwalls and the approved GitHub noreply address. Active checkout is C:/Users/andre/source/repos/codandy; the code-atlas directory is an archive, not the working repo.
- Private Sites v6 successfully deployed at https://codandy.abwalls.chatgpt.site from a9662f971b410b1889f9b9375bda43a0f6434034. Access remains owner-only. Hosted UI does not connect to the local Python/Codex services; use http://localhost:5173 for whiteboard and trace workflows. The browser-handoff tool is unavailable in this session; deployment succeeded independently.
- Backend and frontend remain running for local testing. Next work starts with docs/INTEGRATIONS-PLAN.md I0/T0/T1 (provider foundation and reviewed Linear ticket creation) and observed sequence visualization; see the two Astra review handoffs for boundaries and validation. This final documentation-only checkpoint follows the published application source.


### 2026-09-15 - Review of Astra's slice and observed sequence diagrams (Claude implements, Astra reviews)

- **Review of 0ae34af** (Astra's diagram fixes and offline OTLP import):
  - Re-ran on main: 280 backend tests, ruff and 41 contracts pass, and personal report, case and board hashes are unchanged.
  - Read the traces normalizer, route, trace API, viewer, worker checkpoint, redacted `clip` and TypeScript generic shadowing. No defects found; suggestions are in CLAUDE-SEQUENCES-2026-09-15.md.
- **Worker efficiency:** the worker sent and validated the full atlas twice (checkpoint and result). It now sends `atlas` once, then a separate `structure` message. Timeout, crash, error or invalid diagrams after the checkpoint still return the atlas with the unavailable-diagrams limitation.
- **AD3 observed part** (branch `claude/observed-sequences`):
  - `lib/sequence-diagram.ts` builds stack sequences (caller to callee, per file or function lifelines, collapsed library frames, async boundaries, raise marker, 60-arrow budget keeping the calls nearest the failure) and trace sequences (service lifelines, parent-to-child in start order, activations to the last descendant, outside lifeline for root, missing and cyclic parents, 80-span budget), plus Mermaid `sequenceDiagram` export with sanitized labels.
  - `components/sequence-diagram.tsx` renders keyboard-selectable arrows with a detail panel and notes.
  - Errors & stacks gains a Frames/Sequence toggle per exception, and the trace viewer gains Waterfall/Sequence. `hooks/use-clipboard.ts` is shared with the data model views.
- **Verification:**
  - 44 contract tests (3 new, including normalized Sentry evidence), tsc, changed-file ESLint and build pass.
  - In a first full backend run the worker crash test timed out at its 2 s limit while the production build ran concurrently. It passed three isolated reruns and the final full run recorded in the handoff.
  - Headless Edge over DevTools against the running dev server: a pasted JavaScript stack rendered 5 lifelines and 6 arrows; the function grouping, keyboard selection and Frames toggle worked. The OTLP file rendered 5 spans across 4 services with activations, missing-parent detail and the Waterfall toggle. At 390 px the page stays 390 px wide and the diagram scrolls inside its container. No console errors.
- **Not verified:** light themes, very large traces near 1,000 spans, and Sentry events with mixed in-app frames in the browser (covered by contract tests only). Handoff: CLAUDE-SEQUENCES-2026-09-15.md.

### 2026-09-15 — Resume: sequence review and Linear ticket workflow

- Resumed on claude/observed-sequences with a clean checkout. Reviewed Claude's worker and observed sequence changes. A new regression reproduced a library-frame filtering defect: the raise marker pointed at an application caller when the real failing frame was hidden. Preserve the final captured frame when collapsing libraries. Trace sequence notes now distinguish activation grouping from time-scaled bars.
- Implementing a local-only Linear slice: backend-only key, fixed-host bounded GraphQL, explicit connection/team reads, exact scrubbed payload review, and durable SQLite submission reservations/receipts. A failed/uncertain write is never automatically resent. Added Integrations UI and whiteboard plan entry point; live provider validation is not yet performed. Tests and browser QA are in progress.

### 2026-09-15 — Linear workflow validated

- Fixed the reproduced observed-stack attribution bug; final library frame remains visible when other library frames collapse. Added trace activation-scale clarification.
- Implemented local Linear ticket review/create from Integrations, recommendations and current whiteboard exports. Durable pre-send reservations prevent automatic duplicate sends after timeout/restart. Ledger excludes ticket bodies/credentials. Full provider platform and inline source receipt links remain unfinished.
- Full backend suite: 291 passed; personal storage hashes unchanged. Follow-up ticket suite: 17 passed including six added transport-boundary cases. Frontend/API contracts: 46 passed. Ruff, TypeScript, changed-file ESLint and production build passed. Mocked Edge desktop/mobile flow passed, with screenshots inspected. No live Linear writes were made.
- Restarted local backend for the new endpoints. Review and continuation details: ASTRA-LINEAR-REVIEW-2026-09-15.md. Publishing the validated changes next; account-backed testing remains pending.

### 2026-09-15 — Linear slice published; resume here

- Main pushed to abwalls/codandy; application commit 15ef3661e0b9aa78cf64e1d2a4aa138a21ad5043 uses only the approved personal noreply identity. Claude's observed-sequence work is included. Private Sites v7 deployed successfully at https://codandy.abwalls.chatgpt.site with owner-only access unchanged.
- Backend health is OK and local UI remains running. Start testing at http://localhost:5173/integrations. Linear is not configured on this backend yet; set CODANDY_LINEAR_API_KEY in backend/.env and restart, then use the explicit connection test. Never create a live ticket without reviewing its target and contents. Hosted preview cannot access local provider services.
- Next implementation: source-item receipt links/duplicate warnings, fuller Linear targets, then shared provider foundations and Sentry project/issue browsing. Live account validation is a separate user-configured gate. Review notes: ASTRA-LINEAR-REVIEW-2026-09-15.md. This documentation-only checkpoint follows the deployed application source.
