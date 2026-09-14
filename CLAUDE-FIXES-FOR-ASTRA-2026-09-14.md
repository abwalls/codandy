# Fixes for review findings 1–4: notes for Astra

**From:** Claude (Opus 5)
**Date:** 2026-09-14
**Context:** Andrew agreed with findings 1–4 in `CLAUDE-REVIEW-FINDINGS-2026-09-14.md` and asked me to fix them. All four are fixed and verified. **Nothing is committed**; commits and publishing are yours, under the `abwalls` identity rules. Andrew is setting up a Sentry account for the live D1 test.

Findings 5–7 (uncited answers accepted, eviction before a failed submit, handoff-document sprawl) are **not** addressed. They are still open for you.

---

## 1. Tests can no longer reach personal reports

**Problem:** `conftest.py` patched only the shared `app.main.settings` object. Any
`Settings()` created inside a test still read `backend/.env`. One of those was
`JobStore(workspace_limits(...))` in `test_cancelled_queued_archive_removes_upload`, so the
test loaded personal reports and would have evicted one once there were 10 or more.

**Fix — structural, in `backend/tests/conftest.py`, applied to every test:**

- `monkeypatch.setitem(Settings.model_config, "env_file", None)`: no `Settings()` instance reads `backend/.env` during tests.
- Every `CODANDY_*` and `CODE_ATLAS_*` environment variable is removed for the duration of each test.
- The existing shared-object overrides are kept.
- `workspace_limits()` in `test_archives.py` also passes `report_root=None` explicitly.

**Proof it holds:** new test
`test_settings.py::test_new_settings_in_tests_cannot_inherit_personal_storage_or_credentials`.
I ran it **before** the conftest change and it failed (`'.reports' is None`); after the
change it passes. The two existing `_env_file=`-based settings tests still pass, because
an explicit `_env_file` overrides the patched default.

**Still true:** `Settings().investigation_root` defaults to the relative path
`.investigations`, and that isn't environment-derived. Tests must keep passing explicit
roots to `CaseStore`; all existing tests do.

## 2. DNS-rebinding protection for the whole API

**Problem:** `/api/analyses/*` accepted any `Host` header. A rebinding page could read
reports and captured source (including ZIP-uploaded code), upload archives, and delete
reports.

**Fix:**

- New `backend/app/hosts.py` is a pure ASGI middleware, `AllowedHosts`, added last in `main.py` so it runs before CORS and every route.
- It returns **403** with a JSON `detail`, matching `local_only` and the existing `test_assistant.py` expectation.
- It deliberately isn't `BaseHTTPMiddleware`, so SSE streaming is unaffected.
- `host_name()` accepts only DNS-name, IPv4 or bracketed-IPv6 Host values with an optional port. It rejects `user@host`, paths, empty values and malformed brackets before calling `urlsplit`.
- New setting `allowed_hosts`, default `["localhost", "127.0.0.1", "::1"]`. It's read per request (a callable), so tests can patch it. Documented in `backend/.env.example` as `CODANDY_ALLOWED_HOSTS`.
- Tests add `testserver` (TestClient's default Host) in conftest only.
- `backend/smoke.py` now uses `TestClient(app, base_url="http://localhost")`; otherwise the opt-in live smoke would get 403.

**Verification:**

- New `backend/tests/test_hosts.py` covers header parsing (9 cases) and route-level rejection for GET list, archive POST, source GET and DELETE, plus acceptance of `127.0.0.1:8000` and `[::1]:8000`.
- Live check against an isolated uvicorn on :8001 using scratch storage, with `curl.exe`:
  - `localhost` and `127.0.0.1` returned 200.
  - `rebind.attacker.test` returned 403 for GET `/api/analyses`, POST `/archive` and DELETE `/{id}`.
  - `/api/debugging/cases` still returned 403.

**Deployment impact:**

- Anything reaching the backend under another name now needs that name added to `CODANDY_ALLOWED_HOSTS`. That includes a hosted proxy's `CODANDY_API_URL` host, a LAN IP when uvicorn runs with `--host 0.0.0.0`, and container health checks that use a service name. Otherwise it gets 403.
- The Vite dev proxy uses `changeOrigin` with target `127.0.0.1:8000`, so local development is unaffected.
- The README doesn't mention this setting yet; worth one line next to the setup notes.

## 3. Source-mapped JS/TS frames now match

**Problem:** `runtime_path()` returned `None` for `webpack://…/./src/App.tsx`, `app:///src/App.tsx` and `./src/App.tsx`, so React frames were always `unmapped`.

**Fix in `backend/app/debugging/bindings.py`:** new `path_hint(value) -> (path, anchored) | None`.

- **Schemes:** `http`, `https`, `file`, `webpack`, `webpack-internal` and `app` are accepted. URL hosts and webpack namespaces are dropped.
- **Anchored paths:** leading `./` segments are stripped, and the result counts as anchored. That's the same assumption URL paths already made, so `exact_path` is allowed.
- **Suffix-only paths:** leading `../` or `~/` segments are stripped, but the result is **not anchored**. Such paths only feed suffix scoring, never `exact_path`, and the binding gets a limitation note: "relative to an unknown base".
- **Final gate unchanged:** `is_repository_relative()` still decides. Interior `..`, colons and control characters are still rejected.
- **`runtime_path()`** is now a wrapper returning anchored paths only. `test_unsafe_runtime_paths_never_bind` is unchanged and still passes. The path-prefix mapping still uses anchored paths only.
- **Verified:** the JS stack parser keeps these locations as written in `frame.path` (probed with `normalize_stack_text`).

**Tests in `test_bindings.py`:**

- Five bundler/rewritten forms bind as `exact_path` candidates with the correct line.
- `../` and `webpack://ns/../` forms produce `path_suffix` with visible ambiguity, never an exact match.
- `path_hint` rejects unlisted schemes such as `chrome-extension://`, and interior traversal.

**Follow-ups, not done:**

- **Confirm with a real event.** Check the path forms against a real processed Sentry React event once Andrew's account exists. I based the forms on general knowledge of Sentry/webpack output.
- **Monorepo mapping.** Webpack's `./` is relative to the bundler context, which in a monorepo can be a package folder (`packages/web`). Today's `path_prefix` can only *strip* a runtime prefix, not *add* a repository subfolder, so those frames still fall back to suffix or basename candidates. A "repository subfolder" mapping would close that.

## 4. The Architecture map no longer calls package imports "unresolved"

**Problem:** every import without a drawn target (`react`, `os`, `requests`) was counted as an "unresolved reference".

**Fix — the analyzer now classifies imports** (`backend/app/analyzer.py`, in the import resolution loop). Every import node gets the boolean attribute `local_import`:

| Language | `true` when… | Otherwise `false` |
|---|---|---|
| JS/TS | the specifier starts with `.`, **or** with `@/` (a conventional path alias; npm scopes are always `@scope/name`, so `@/` can't be a package). Aliases still aren't resolved | packages |
| Python | the import is relative, **or** the top-level package exists at the repository root (`head.py`, `head/__init__.py`, or a root directory named `head`) | stdlib, installed packages, **and `src/`-layout packages (known limitation)** |
| Go | the path is under the nearest `go.mod` module path | stdlib, third-party modules |
| C# and other languages | never (no local import resolution exists) | `using` namespaces |

**Schema note:** atlas stays `0.2`. `attributes` was already a free-form `str | int | bool` map on both sides. There's no new edge or node kind.

**Frontend changes:**

- `lib/architecture-map.ts` now returns `unresolved` (local imports without a resolved target), `external` (other undrawn imports) and `classified` (whether the atlas carries the attribute at all).
- `components/architecture-map.tsx`, legend wording:
  - **New atlases:** "N unresolved local imports · M package, standard-library or namespace imports not drawn".
  - **Atlases analyzed before this change:** "M imports without a resolved local target not drawn (reanalyze to separate packages from unresolved local imports)". It doesn't guess.
  - **Projects view:** "N unresolved project references omitted".

**Verification:**

- `test_analyzer.py::test_imports_are_classified_as_local_or_external` covers TS, Python (relative, absolute local, missing local, stdlib, package), Go (stdlib and module) and C# `using`.
- Contract tests cover legacy, local and external classification with order independence. They also cover the real Python-generated fixture: `react` → false, `./other` → true, so `unresolved` is 0 and `external` is 1.
- End-to-end script (real analyzer plus `architectureMap()`) on the repository from the finding: unresolved went from **4 to 0**; the four stdlib/package imports now count as external.

**Side effects to know about:**

- **Snapshot comparison noise.** Comparing a snapshot analyzed before this change with one analyzed after shows import nodes as "changed", because the attribute is new. This is the same kind of noise as any analyzer improvement, e.g. the earlier `method_definition` fix.
- **Retained reports.** Andrew's two retained reports predate the attribute and will show the legacy wording until they're reanalyzed.

---

## Files changed

**New:** `backend/app/hosts.py`, `backend/tests/test_hosts.py`, `CLAUDE-FIXES-FOR-ASTRA-2026-09-14.md` (this file)

**Modified:**

| File | Change |
|---|---|
| `backend/tests/conftest.py` | No dotenv or `CODANDY_*` environment variables for any `Settings()`; `testserver` allowed in tests |
| `backend/tests/test_settings.py` | Isolation regression test |
| `backend/tests/test_archives.py` | `workspace_limits()` passes `report_root=None` |
| `backend/app/settings.py`, `backend/.env.example` | `allowed_hosts` / `CODANDY_ALLOWED_HOSTS` |
| `backend/app/main.py` | Registers `AllowedHosts` |
| `backend/smoke.py` | `TestClient` uses `base_url="http://localhost"` |
| `backend/app/debugging/bindings.py` | `path_hint()`, bundler schemes, suffix-only unknown bases |
| `backend/tests/test_bindings.py` | +8 tests |
| `backend/app/analyzer.py` | `local_import` attribute on import nodes; tsconfig/jsconfig path aliases (`jsonc_loads`); Python project-root resolution; limitation text |
| `backend/tests/test_analyzer.py` | Import classification, tsconfig alias, and Python project-root tests |
| `lib/architecture-map.ts`, `components/architecture-map.tsx` | Local/external/legacy counts and wording |
| `tests/analysis-api.test.mjs` | Architecture test rewritten; new fixture-based classification test |
| `progress.md` | Checkpoint |
| `CLAUDE-REVIEW-FINDINGS-2026-09-14.md` | Status line pointing here |

---

## Verification

| Check | Result |
|---|---|
| `pytest` (full backend) | **243 passed**: was 221; 241 after findings 1–4; 2 more from the alias and package-root follow-up |
| `ruff check .` | clean |
| Personal storage SHA-256 (`backend/.reports`, `backend/.investigations`) before/after pytest | **unchanged** |
| `pnpm test:contracts` | **29 passed** (was 28) |
| `tsc --noEmit` | clean |
| ESLint (changed frontend files) | clean |
| Production build | succeeds |
| Live host-guard probe (isolated :8001) | passes, as described above |

**Browser QA (Claude in Chrome, local dev server at :5173):**

- **Homescreen:** screenshot verified. The ZIP dropzone, "or" divider and updated copy all render, with no console errors.
- **Opening a saved atlas:** used an atlas generated by the updated analyzer from a copy of this repository's `lib/`, `components/`, `app/` and `backend/app/`. Opening it is browser-only, so no personal reports were touched. Overview screenshot verified: 168 files, 703 symbols, 1,904 relationships.
- **Architecture legend (checked by DOM query):** it rendered from the new code as "5/5 groups · 0 connections outside view · 74 unresolved local imports · 501 package, standard-library…". That count was captured before the `@/` alias rule existed.
- **The QA run caught a mislabel:** 176 `@/…` alias imports were being called "package" imports. I added the `@/` rule, recounted, and got **250 unresolved local imports** (176 aliases plus 74 Python `app.*`) and **325 external** (react, radix-ui, lucide-react, pathlib, …).
- **Architecture screenshots timed out twice** with "renderer may be frozen or unresponsive". DOM queries still worked, so this may just be a screenshot/compositor stall on a background tab. I didn't investigate further. **Please run your headless Edge check on this atlas's Architecture view** to rule out a slow SVG paint on large atlases.

**Follow-up (Andrew asked for it): import aliases and Python package roots now resolve**

QA showed the map drew **0 connections for Codandy itself**. Its TypeScript imports through the `@/*` alias in `tsconfig.json`, and its Python package root is `backend/`, not the repository root. Both now resolve in `backend/app/analyzer.py`, and both treat configuration as data only.

- **tsconfig/jsconfig path aliases**
  - **Reading.** `tsconfig*.json` and `jsconfig*.json` files are captured during the file walk, after the existing size and secret-name filters, with a 256 KB cap and no NUL bytes allowed. `jsonc_loads()` parses them: a string-aware reader that allows comments and trailing commas. Nothing in them is evaluated, and TypeScript never runs.
  - **Which config.** The nearest `tsconfig.json` above the importing file applies; failing that, the nearest `jsconfig.json`.
  - **`extends`.** Relative `extends` is followed, whether a string or an array, up to a depth of 8 and with cycle protection. Package extends such as `@tsconfig/…` are ignored, because they'd need installed packages.
  - **`paths` matching.** An exact pattern wins; otherwise the longest wildcard prefix. Only single-`*` patterns are supported. Targets resolve from the effective `baseUrl`, or from the config that defines `paths` if there's no `baseUrl`. At most 20 targets are tried, and any target that escapes the repository is dropped.
  - **Bare specifiers** fall back to `baseUrl` and link only when a file exists there.
  - **Unique-candidate rule.** The first target with any indexed candidate decides, and ambiguity stays unresolved.
  - **Links** are `resolution="inferred"` with confidence 80. The evidence reason names the tsconfig/jsconfig alias and says bundler aliases aren't evaluated.
  - **`local_import`** is true for a matched `paths` alias (even when unresolved), any `@/` specifier, or a `baseUrl` resolution.
- **Python project roots**
  - Any directory holding `pyproject.toml`, `setup.py`, `setup.cfg` or `requirements.txt` is a root.
  - Absolute imports try enclosing roots nearest first (each root's `src/` before the root itself, when that folder exists), then the repository root. The first root that holds the module decides.
  - This replaces the accidental match on a root-level `app/` folder described above.
- **Limitation text** (`BASE_LIMITATIONS`) is updated. Bundler aliases (webpack/Vite `resolve.alias`), package.json `exports`/`imports`, project references, build tags and installed-package resolution are still not evaluated.

**New tests:**

- `test_tsconfig_path_aliases_resolve_as_data_only` covers comments and trailing commas, relative `extends`, exact versus wildcard patterns, a bare `baseUrl` import, nested-config precedence, ambiguity, a missing target, an attempt to escape the repository, and an `extends` cycle.
- `test_python_absolute_imports_resolve_from_the_enclosing_project_root` checks that the `backend/pyproject.toml` root wins over a same-named root `app/`. It also covers imports from a tests folder, a `setup.cfg` project with a `src/` layout, and an installed module staying non-local.

**Real-repository check.** I analyzed a copy of `lib/`, `components/`, `app/`, `hooks/` and `backend/app/`, together with the real `package.json`, `tsconfig.json` and `backend/pyproject.toml`:

- **Resolved imports:** 258 in total. 176 go through the `@/*` alias, and 74 are Python imports resolved via `backend/`.
- **Unresolved:** **0** local imports left.
- **Map at folder depth 1:** 3 connections (components → lib ×85, app → components ×3, components → hooks ×1). At depth 2 there are 6. Before this change: 0.

**Side effects:**

- **Snapshot comparisons.** There are more `RESOLVES_TO` edges, so comparisons against earlier atlases will show added relationships.
- **Dependency impact** now includes files that import through aliases.
- **Retained reports** need re-analysis to benefit.

**Not verified:**

- **Architecture view screenshot.** It stalled twice, as described above. The legend text was checked by DOM query only.
- **Real Sentry event path forms.** They await Andrew's account.
- **Andrew's running :8000 backend.** It was **not restarted**, so it still runs the old code (no host guard, no `local_import`). Restart it to pick up the fixes.
