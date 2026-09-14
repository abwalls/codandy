# Codandy

Formerly Code Atlas. New configuration uses `CODANDY_*`; existing `CODE_ATLAS_*` settings remain supported during migration. The saved browser theme key is retained so your chosen color scheme survives the rename. Existing atlas JSON reports remain compatible; new analysis artifacts are written to `.codandy/atlas.json`.

Codandy builds an interactive, evidence-backed mental model of an unfamiliar repository. It combines deterministic code analysis with AI investigation so architectural claims, application flows, and explanations remain traceable to source.

## Product direction

Codandy is becoming an error-investigation and debugging workspace, starting with Sentry, source-bound call stacks, observed performance and whiteboards that produce AI-ready plans. This is the next roadmap, not a claim that those features are already implemented. The existing analyzer and local AI connection remain available.

See [PLAN.md](PLAN.md), [ROADMAP.md](ROADMAP.md) and the [research and strategy review](docs/DEBUGGING-STRATEGY.md). The active checkout is `C:\Users\andre\source\repos\codandy`; the older folder is an archive.

## Current foundation

- Responsive React 19 and TypeScript interface
- Repository URL and ZIP intake surfaces
- Visible analysis lifecycle
- Interactive sample banking atlas
- Deterministic graph node identities and source evidence
- Multi-language syntax indexing: C#, TypeScript/TSX, JavaScript/JSX, Python, Go
- Source viewer with evidence-range highlighting
- Context-aware “Ask Codandy” experience
- Python 3.12 FastAPI analysis backend
- Private deployable demo

The interface now analyzes public GitHub repositories through FastAPI, displays real streamed
progress, and opens an evidence-backed file/symbol index with atlas download and a source
viewer that shows the real code behind each node. Syntax indexing covers C#,
TypeScript/TSX, JavaScript/JSX, Python and Go. The banking sample remains available
separately and labels illustrative content. Real analyses support opt-in local report
persistence and independent questions through the local Codex subscription connection.
Sentry investigations, runtime performance views and whiteboards are the next roadmap,
not implemented features.

Native parsing runs in a disposable process with timeout and crash containment. Live GitHub
analysis, the frontend proxy, and browser interaction have been verified against real
TypeScript and Python repositories.

Read [progress.md](progress.md) when resuming development for the last completed work and next steps.

## Windows quick start

Open PowerShell in the project directory:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup-windows.ps1
.\scripts\start-windows.ps1
```

The setup script checks prerequisites, installs project dependencies, and verifies the backend.
The start script launches both services in the background and opens the browser. It uses the
workspace-local managed Python environment when available, falling back to backend/.venv.

## Frontend

Requirements: Node.js 22.13 or newer and pnpm.

```bash
pnpm install
pnpm dev
```

Build:

```bash
pnpm build
```

## Backend

Requirements: Python 3.12 or newer and uv.

```bash
cd backend
uv sync --extra dev
uv run uvicorn app.main:app --reload
```

Verify:

```bash
uv run pytest
uv run ruff check .
```

## Product direction

For this checkout's working managed environment, run backend checks from `backend` with
`.venv-managed/Scripts/python.exe -m pytest -q` and
`.venv-managed/Scripts/python.exe -m ruff check .`.
Run `corepack pnpm test:contracts` at the project root for frontend/Python contract tests.
The opt-in `backend/smoke.py` performs a live public GitHub clone through the API and verifies
atlas retrieval, SSE, and workspace cleanup; run it with the backend Python interpreter.

Local development forwards `/api/analyses` to `http://127.0.0.1:8000`. Hosted builds require
`CODANDY_API_URL` set to a separately hosted Python service's HTTPS origin. Until that
service is configured, hosted analysis returns an explicit unavailable message. Reports are kept in memory by default and expire on restart or retention eviction. Set `CODANDY_REPORT_ROOT=.reports` in `backend/.env` to retain completed reports and captured source across local API restarts. The intake **Recent reports** button reopens retained analyses.

The backend Dockerfile is an unverified draft with known dependency-install and executable-path defects; repairs are deferred. It is not currently deployable as documented. Hosted use also requires durable shared state, access control and operational limits: the current in-memory single-worker API cannot support multiple replicas.

Use **Download atlas** to save a report, then **Open saved atlas** on the intake screen to reopen it locally. Imports are limited to 20 MB and validated against the graph schema. Source text is not included, and imported snapshots cannot establish commit freshness. In a report, use **Snapshot comparison** to select a saved baseline from the same repository and schema version. The comparison reports graph metadata changes, not a source-code diff. Select source evidence to explore direct and transitive local importers under **Who depends on this file?**

Read [PLAN.md](PLAN.md) for milestones and [ARCHITECTURE.md](ARCHITECTURE.md) for the universal graph, analysis pipeline, and debugging-overlay boundary.

## Security boundary

Normal analysis is static and treats every repository as untrusted input. Codandy must not install repository dependencies, run builds, execute tests, invoke project scripts, or run repository binaries by default.


### Local completed-report retention

`CODANDY_REPORT_ROOT` enables local snapshots (one API process per directory). Each successful analysis writes a validated atlas, captured source and progress events atomically before reporting completion. Snapshots are capped at 128 MB each and retained up to `CODANDY_MAX_JOBS`; oldest reports are evicted when new jobs arrive. In-flight jobs are not resumed after a crash. Invalid snapshots are skipped. Source snapshots are plaintext: keep the storage directory private and out of source control. The default `.reports` directory is ignored by Git and container context.

This is local persistence, not a shared multi-replica datastore or access-control system. Do not expose the unauthenticated API as a multi-user service. Custom storage paths must also be excluded from source control.

### Color schemes

Use the header color picker to switch between Codandy Midnight (default), Demo background, Vol Orange, Violet Night and Graphite. The preference is saved on this device. Demo background and Vol Orange use publicly documented brand colors with supporting dark surfaces adapted to Codandy; these are visual presets, not affiliated products.

### Dependencies

Analyze a repository again, then open **Dependencies** in the report menu. Inspect npm, NuGet, Python and Go declarations, supported lockfile versions and import-name usage candidates. **Check updates and advisories** sends the selected package name/ecosystem/version to public registries and OSV; results are time-stamped and require network access. Registry updates are not compatibility recommendations, and advisory matches do not prove runtime exposure. Ranges without an identified version are not vulnerability-checked. See the in-app coverage limits for unsupported lockfile and transitive-resolution formats.

Filter packages by review state and use **Download dependency review** to save every declaration plus checks performed in the current report session as JSON. Search filters do not reduce the export. Public observations are not retained when leaving the report, and this review export is separate from the importable atlas artifact.

For .NET repositories, Architecture shows literal project-reference candidates; inspect a project to explore direct/transitive dependents. Dependencies also shows same-name central version candidates from the nearest `Directory.Packages.props`, with a link to source evidence. Conditions, imports and overrides are not evaluated, so central candidates do not become identified versions for advisory checks.

Click **Source files**, **Symbols**, **API routes** or **Tests** in Overview for a searchable detail list and source-inspection links. Sample mode contains only illustrative examples, not a full inventory behind its headline totals.

**Ask about this page** and contextual Ask buttons prepare questions with bounded graph evidence. Review, copy or download the prompt, or connect the optional local subscription assistant below. Nothing is sent until you choose an action.

### Use your ChatGPT plan locally

Install Codex, then set `CODANDY_CODEX_ENABLED=true` and `CODANDY_CODEX_EXECUTABLE` to the Codex executable in the backend's ignored `.env`. Start the backend from its directory. `CODANDY_CODEX_HOME` defaults to an isolated `.codex-codandy` folder; never commit it. This uses OpenAI's Codex App Server ChatGPT sign-in, not an API key or copied browser cookies.

Open a retained analysis, choose Ask Codandy, then **Connect ChatGPT → Continue sign-in with OpenAI**. Use the same ChatGPT account you normally use. Return and click **Check connection**. The app selects a default model/effort from the available catalog; you may change either. **Ask using my plan** consumes your account's Codex allowance. Subscription limits and model access still apply; this is not unlimited or guaranteed cheaper for every workload.

This connection is local-only. The hosted proxy does not expose it. Each question starts a fresh conversation and includes a bounded retained graph excerpt, without source bodies, comparison baselines or live advisory results. Generated answers remain AI explanations; citation IDs are validated but factual correctness needs review. Copied/exported questions remain available for sample/offline reports.


## Errors and Sentry events

Open `/debugging` locally (or choose **Errors & stacks**) to import a Python, JavaScript or .NET stack, or Sentry REST issue-event JSON. The local backend bounds and sanitizes input; the page displays ordered frames, exception chains, breadcrumbs, omissions and a reviewed JSON download. SDK ingestion payloads are deliberately unsupported. Observations remain in the page, not browser storage; downloaded observations are exports, not yet a reopenable investigation format.

For live reads, set `CODANDY_SENTRY_TOKEN` and `CODANDY_SENTRY_ORGANIZATION` in ignored `backend/.env`, optionally `CODANDY_SENTRY_HOST` (`sentry.io`, `us.sentry.io`, `de.sentry.io`), and restart the backend. Use a token with `event:read` and organization access, not a DSN. Enter the numeric issue ID and `latest`, `oldest`, `recommended` or a specific event ID. Each click performs one bounded GET; no redirects, automatic retries, source-map fetches or provider writes. See [Sentry issue-event API](https://docs.sentry.io/api/events/retrieve-an-issue-event/).

The hosted page describes this local workflow; it does not forward telemetry to a hosted API. Source binding, saved investigations, project/issue browsing and AI debugging briefs remain subsequent D1 work. Live access requires user configuration and has not been verified against a real account.
