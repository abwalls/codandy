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
