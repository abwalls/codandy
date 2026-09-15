# Codandy agent guide

## Product

Codandy is pivoting to a debugging and investigation workspace: connect errors and performance evidence to source, preserve investigations, and prepare plans for developers and AI assistants. The current static analyzer remains the supporting foundation. Sentry and stack investigation are the immediate focus, followed by performance evidence and a single-user whiteboard.

Read PLAN.md, ROADMAP.md, ARCHITECTURE.md, docs/DEBUGGING-STRATEGY.md and the latest progress.md checkpoint before changing direction. Historical reviews and the supplied NEWPLAN.md do not override the current roadmap.

## Current state

- Implemented: bounded five-language static analysis, atlas/source/report views, dependency checks, retained reports, snapshot comparison, themes and a local Codex subscription connection. Current validation includes 221 backend tests and 28 frontend/API contracts, plus desktop/mobile Edge workflow QA. Tests must use the autouse isolated storage/provider fixture in backend/tests/conftest.py; never run them against personal reports or provider credentials.
- Implemented D1 slice: local Sentry REST event/stack imports, sanitized observation viewer/export, and a backend-held read-only Sentry Cloud event connector. Live credentials have not been configured or verified.
- Implemented: ZIP project upload, interactive static Architecture map, local saved cases/notes/status, candidate frame-to-snapshot matching, reviewed brief export and local investigation Q&A. Unknown or user-supplied revisions never upgrade to independently verified exact bindings.
- Planned, not implemented: project/issue browsing, independent runtime revision verification, trace/profile viewers, whiteboards, Codandy MCP and trusted live debugger control.
- Actual static relationship types: CONTAINS, IMPORTS, RESOLVES_TO, DEPENDS_ON, ROUTES_TO and CALLS. IDs are deterministic from kind/path/name; snapshot identity is required for runtime associations. No comprehensive call graph, coverage or per-function performance claim is supported.
- The hosted UI/sample remains separate from local Python analysis and subscription AI. Keep samples and unavailable features clearly labeled.

## Immediate milestone

**2026-09-14:** Andrew made the Whiteboard (PLAN.md D4, broadened) the next implementation track. Start with W0 in [docs/WHITEBOARD-PLAN.md](docs/WHITEBOARD-PLAN.md) and follow its milestones and safety rules. D1 remains open: the live Sentry test and project/issue browsing continue once Andrew's account is available.

D1 in PLAN.md: bounded event/stack contracts, redaction and TS/JS, Python and .NET fixtures; one read-only Sentry event flow; revision-aware frame/source binding; saved investigations; reviewed AI debugging brief export. Start with normalization and fixtures, then make the live connector functional. Do not start with numerical risk scores, broad telemetry ingestion, a debugger engine or empty sidebar pages.

Runtime observations, source bindings, AI hypotheses and user plans are distinct. A stack trace does not establish function timing or the precise null operand. No telemetry path can open arbitrary source files. No board arrow becomes a static graph edge automatically. Existing .codandy/atlas.json schema 0.2 remains unchanged for this pivot.

The old blanket debugging deferral is superseded. Running repository code remains prohibited inside static ingestion; future debugger/test execution requires a separately designed, explicitly trusted local execution boundary.

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
- Canonical artifact: `.codandy/atlas.json`.

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

- User identity requirement: use only the personal GitHub account `abwalls` for this project, never the former work account. Verify `gh api user` returns `abwalls` before GitHub mutations. The approved repository is `abwalls/codandy`; use `45399949+abwalls@users.noreply.github.com` for both author and committer. Never merge the old repository history. Stop if authentication or commit attribution differs.

- Read progress.md when resuming and append a checkpoint after each completed slice and before stopping.
- Preserve the existing visual direction and responsive layouts.
- Reuse the existing UI primitives.
- Update `PLAN.md` when a milestone materially changes.
- Add focused tests for ingestion boundaries, parser behavior, schemas, and API contracts.
- Keep the frontend and Python atlas schemas synchronized.
- Do not commit `.env`, credentials, cloned repositories, generated workspaces, `.venv`, `node_modules`, or build output.
