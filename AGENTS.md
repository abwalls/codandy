# Code Atlas agent guide

## Product

Code Atlas turns an unfamiliar repository into an interactive, evidence-backed model of the software. The deterministic code graph is the source of truth. AI explains and investigates the graph but must not invent relationships or findings.

## Current state

- The React UI and sample banking report are functional.
- The FastAPI backend has bounded GitHub ingestion, syntax analysis for C#, TypeScript/TSX, JavaScript/JSX, Python and Go, atlas generation, in-memory jobs, SSE endpoints, and a source-text endpoint for the viewer, all with regression tests.
- React submits real jobs, streams progress, and displays atlas counts, searchable nodes, evidence, relationships, and the real source behind each node. Sample mode is a separate labeled path and keeps its placeholder sections until they are implemented.
- Native parsing runs in a disposable process with a hard timeout. Live GitHub analysis and local frontend proxy/SSE have been verified; see progress.md for details.
- Real analyses now include deterministic Architecture, Application flows, Developer guide, and Recommended changes sections derived from graph evidence. These are bounded static heuristics, not runtime traces, compiler semantics, profiling, or a security audit; keep their limitations visible.
- Opt-in local completed-report snapshots, recent-report reopening/removal, offline atlas imports, snapshot comparison, dependency impact, and five device-persisted color themes are implemented. Shared multi-user persistence/auth, Codex Q&A, hosted Python service and deeper semantic inference remain unfinished. Sample mode remains illustrative and labeled.
- Dependencies provides direct manifest/version evidence, supported npm/NuGet lockfile metadata, scoped usage candidates, and explicit public registry/OSV checks. Public observations are separate from atlas facts; an identified version does not establish runtime exposure. Unsupported or ambiguous constraints remain unknown. The green/navy preset is labeled Demo background.
- Dependency reviews can be filtered and exported with separate public observations. .NET project references feed Architecture and project-dependent impact inspection. Nearest central NuGet declarations are inspectable candidates only; MSBuild is never evaluated.
- Ask Atlas has contextual copy/export plus an opt-in local Codex App Server subscription adapter. Authentication stays in a dedicated ignored Codex profile; no token copying or API-key fallback. Loopback/header/origin checks guard local endpoints, which are not exposed by the hosted proxy. Model/effort choices are discovered; answers validate schema and citation IDs. Authenticated Plus-plan completion through the localhost frontend proxy is verified. Questions are independent; streaming/history and visual browser QA remain outstanding.

Read `PLAN.md` and `ARCHITECTURE.md` before changing product architecture.

## Immediate milestone

Implement a real end-to-end analysis for public GitHub repositories:

1. Validate and safely clone a public Git URL into an isolated temporary workspace.
2. Enforce repository size, file-count, depth, and timeout limits.
3. Detect projects and technologies from manifests and source extensions.
4. Extract basic files, declarations, imports, API routes, and tests for C# and TypeScript/React.
5. Emit a schema-validated `.codeatlas/atlas.json` with stable node IDs, relationships, source locations, evidence, and confidence.
6. Stream real job progress from FastAPI to React using Server-Sent Events.
7. Populate report sections from the returned atlas; show unsupported or not-detected states instead of fabricated content.

Do not add Codex-powered enrichment until deterministic ingestion and atlas generation work end to end.

## Security invariants

- Treat every analyzed repository as untrusted.
- Never run its builds, tests, package managers, scripts, binaries, MSBuild targets, hooks, or plugins during static analysis.
- Block local-network and credential-bearing Git URLs.
- Do not pass secrets, environment files, private keys, or common credential files to models or reports.
- Keep temporary workspaces isolated and disposable.
- Label relationships as resolved, inferred, or unresolved.
- Label security recommendations as potential risks unless a finding is actually verified.

## Stack

- Frontend: React 19, TypeScript, Vinext, Tailwind, Shadcn primitives.
- Backend: Python 3.12, FastAPI, Pydantic.
- Analysis: Tree-sitter grammars for C#, TypeScript/TSX, JavaScript/JSX, Python and Go, with later Roslyn and TypeScript Compiler API adapters.
- `tree-sitter` is pinned below 0.26. Release 0.26.0 corrupts process memory when a walk reads a node's `start_point`/`end_point` and then its `named_children`, which is exactly what the analyzer does for every declaration. `backend/tests/test_grammars.py` guards the verified range.
- Canonical artifact: `.codeatlas/atlas.json`.

## Commands

Frontend:

```powershell
pnpm install
pnpm exec tsc --noEmit
pnpm build
pnpm dev
```

Backend:

```powershell
Set-Location backend
uv sync --extra dev
uv run pytest -q
uv run ruff check .
uv run uvicorn app.main:app --reload --port 8000
```

Use `scripts\setup-windows.ps1` for first-time setup and `scripts\start-windows.ps1` to launch both services.

## Working rules

- Read progress.md when resuming and append a checkpoint after each completed slice and before stopping.
- Preserve the existing visual direction and responsive layouts.
- Reuse the existing UI primitives.
- Update `PLAN.md` when a milestone materially changes.
- Add focused tests for ingestion boundaries, parser behavior, schemas, and API contracts.
- Keep the frontend and Python atlas schemas synchronized.
- Do not commit `.env`, credentials, cloned repositories, generated workspaces, `.venv`, `node_modules`, or build output.
