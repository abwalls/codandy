# Claude review findings: 2026-09-14

**From:** Claude (Opus 5), reviewer
**For:** Astra 6 and Andrew
**Responds to:** `CLAUDE-CODE-REVIEW-2026-09-14.md`
**Reviewed:** commit `21b3a59` compared against `dd6efa5`. Author and committer both show the approved `abwalls` no-reply identity.

> **Status update (same day):** Andrew asked me to fix findings 1–4, and they're fixed and verified. The changes are uncommitted and documented in `CLAUDE-FIXES-FOR-ASTRA-2026-09-14.md`. Minor items 5–7 are still open.

This review changed no code. Items 1–4 are **verified defects**; the command or test behind each is listed with it. Items 5–7 are minor. The roadmap suggestions are kept separate at the end.

---

## Verification rerun

| Check | Result |
|---|---|
| `pytest` (full backend) | **221 passed** |
| `ruff check .` | clean. The earlier I001 in `brief.py` is fixed |
| `pnpm test:contracts` | **28 passed** |
| `tsc --noEmit` | clean |
| ESLint on the changed frontend files | clean |
| Production build | succeeds |
| Personal storage hashes (`backend/.reports`, `backend/.investigations`) before and after pytest | unchanged. See finding 1 for why this passing today is not sufficient |

---

## Verified defects

### 1. The test suite can still delete personal reports: `backend/tests/test_archives.py:249`

`test_cancelled_queued_archive_removes_upload` builds its store as
`JobStore(workspace_limits(tmp_path))`. `workspace_limits()` constructs a new
`Settings(workspace_root=...)`. The autouse fixture in `conftest.py` patches only the
shared `app.main.settings` object, so this new instance still reads `backend/.env`.

**Evidence:**

- `Settings(workspace_root='x').report_root is not None` returned `True` when run from `backend/`.
- There are 2 personal reports on disk. `max_jobs` is 10.

**Consequence:**

- `JobStore.__init__` loads the personal snapshots.
- `ReportStorage.load()` deletes snapshot files beyond `max_jobs`.
- `create()` calls `storage.remove(oldest)` once the store holds `max_jobs` jobs.

Today the test only reads, because there are 2 reports. At 10 or more, each full test run
would delete a personal report. The hash check passed only because the count is low.

**Fix:**

- Pass `report_root=None` in `workspace_limits()` (and in any other test that constructs `Settings` for a store).
- Make the guard structural, so the next new test can't reopen the hole. During tests, disable dotenv loading with `monkeypatch.setitem(Settings.model_config, "env_file", None)`, and delete `CODANDY_*`/`CODE_ATLAS_*` storage and provider environment variables.
- Add a regression assertion that `Settings().report_root is None` inside the suite.

**Process note:** before `conftest.py` existed, test runs used personal storage. That
includes my own full pytest runs earlier on 2026-09-14 during ZIP intake work, so they
plausibly contributed to the retention incident Astra recovered from.

### 2. Source-mapped JS/TS frames never match source: `backend/app/debugging/bindings.py:16-31`

Direct calls to `runtime_path()`:

```
'webpack:///./src/App.tsx'        -> None
'webpack://my-app/./src/App.tsx'  -> None
'app:///src/App.tsx'              -> None
'./src/App.tsx'                   -> None
'src/App.tsx'                     -> 'src/App.tsx'
'http://localhost:3000/src/App.tsx' -> 'src/App.tsx'
```

Two causes:

- `app` and `webpack` are not in the scheme allowlist.
- `is_repository_relative()` rejects any `.` segment, so `./src/...` fails even after a
  successful parse.

Source-mapped browser frames usually take these forms. From general knowledge of Sentry
JS events; please confirm against a real processed event. So TS/React, the first target
audience in `PLAN.md`, gets `unmapped` for most frames. This fails safe (nothing is
fabricated), but it removes most of D1c's value for that audience. No fixture or
`test_bindings.py` case uses these forms. I grepped `backend/tests/fixtures/debugging`
and `test_bindings.py` for them.

**Fix:**

- Accept the `app` and `webpack` schemes, and drop webpack's namespace host.
- Strip leading `./` segments.
- For leading `../` or `~/`, strip the prefix but allow **suffix matching only**; never report `exact_path`.
- Keep `is_repository_relative()` as the final gate.
- Add fixtures modeled on a real source-mapped React event.

### 3. The analysis API is readable and writable through DNS rebinding: `backend/app/main.py`, `backend/app/routers/analyses.py`

Read-only probes against the running local backend:

```
GET /api/analyses        Host: 127.0.0.1:8000        -> 200
GET /api/analyses        Host: rebind.attacker.test  -> 200
GET /api/debugging/cases Host: rebind.attacker.test  -> 403   (local_only works)
```

`main.py` has no Host validation, and the analyses router has no equivalent of
`local_only`. After a DNS rebind, a malicious page becomes same-origin with
`127.0.0.1:8000`, so CORS no longer applies. It could then:

- list retained reports
- read atlases and **captured source**, including private code uploaded as ZIPs
- upload archives
- delete reports

This matters for the self-hosted, local-only plan too.

**Fix:**

- Add `TrustedHostMiddleware(allowed_hosts=["localhost", "127.0.0.1"])`. Make the allowlist a setting so a future separately secured backend can add its own host.
- Add a test asserting that a foreign `Host` gets rejected on `/api/analyses`, `/api/analyses/archive` and `/{id}/source`.

### 4. The Architecture map counts package and stdlib imports as "unresolved": `lib/architecture-map.ts:43-44`, legend in `components/architecture-map.tsx:43`

Script used: analyze a small repository with the real analyzer, then run `architectureMap()`.

```
imports: os, json, requests, svc.helper (resolved local), react, ../lib/core (resolved local)
folders view: links ['web->lib x1 inferred=1'] | 'unresolved references omitted' = 4
```

Every local import resolved. The four "unresolved references" are all stdlib or package
imports, and on a real repository that number is dominated by externals. It overstates
uncertainty and mislabels evidence, which is review priority 4.

**Fix:**

- Only imports that look local should count as unresolved local references (relative JS specifiers, Python relative or repository-rooted modules, Go module-prefixed paths).
- Report externals separately, e.g. "N package/standard-library imports not drawn".
- Note that an `IMPORTS` edge's own `resolution` doesn't separate the two cases: it is `unresolved` even when a `RESOLVES_TO` exists. The clean route is an import-node attribute such as `local_specifier: true`. `attributes` is free-form, so atlas stays `0.2`.

Everything else about the map held up. It draws only actual `RESOLVES_TO`/`DEPENDS_ON`
evidence, inferred links are dashed, package `DEPENDS_ON` edges are not drawn as project
links, and groups are described as physical source areas, not layers or services.

---

## Minor

5. **Uncited answers pass the citation check** (`backend/app/routers/cases.py:120-122`). The
   check rejects citations outside the packet, but an answer with **zero** citations is
   accepted, even though the instructions require citations for factual statements.
   Either reject it or mark it "uncited" in the UI.
6. **A shutdown-time submit failure can delete a stored report** (`backend/app/jobs.py:45-62`).
   Retention eviction, which includes `storage.remove()`, runs before `executor.submit()`.
   If the submit then fails during shutdown, the new job is rolled back but the evicted
   report is already gone. It's rare; evict only after a successful submit.
7. **Handoff documents are piling up in the repository root.** There are now four, and
   `ZIP-UPLOAD-NOTES-FOR-ASTRA.md` was committed with stale statements: "Nothing is
   committed", and open items 2 and 3 are now done. Suggest moving these to `docs/handoffs/`
   and marking superseded notes.

---

## Reviewed and sound: no action

- **ZIP preflight** (`check_archive_directory`).
  - End-of-central-directory parsing, the comment-reaches-end check, split/ZIP64 rejection, the 50,000-entry / 8 MiB budget, the physical directory walk and the forged-count check are all correct.
  - They agree with `zipfile`'s own record search.
  - Archives made by real tools were all accepted: `git archive` (204 files), PowerShell Compress-Archive/.NET (91), and Windows `tar.exe`/libarchive (91).
  - Shutdown submit handling and cancelled-future upload cleanup are correct.
- **Local/hosted boundary.**
  - The hosted app has one API route, `/api/analyses`.
  - All `/api/debugging/*` routes are behind `local_only`, including cases, source binding, brief and ask. It checks the client address, the `Host` header, `X-Codandy-Local` and an Origin allowlist; verified 403 above.
  - Not verified: the deployed Sites configuration itself.
- **Saved cases.**
  - `extra="forbid"` contracts.
  - A validator ties each binding to its own observation and frame.
  - Atomic, bounded writes; idempotent save.
  - Title and notes are redacted on edit.
  - No code path mutates the stored observation.
- **Bindings.** A revision never becomes `verified`, a mismatch is labelled, and more than 20 candidates becomes `unmapped` rather than silently promoting one.
- **Brief.** Content is framed as untrusted data, review is bound to a digest, citations must come from the packet, and output is capped at 60 KB with omission counts.

---

## Status against `ROADMAP.md`

| Gate | State |
|---|---|
| D1a imports and contracts | Done |
| D1b Sentry connection | Event retrieval done; **project/issue browsing and a live account test not started** |
| D1c binding and persistence | Done locally; independent revision verification pending; **JS path gap (finding 2)** |
| D1d live issue → source → brief | Brief and local Q&A done; **live gate open** |
| Architecture map | Supporting-tools work Andrew asked for; not a roadmap gate |
| D2–D4 (v1 scope) | Not started |

---

## Suggested next steps (roadmap, not defects)

1. **Fix findings 1–4 first.** They're small. Findings 1 and 3 protect Andrew's data and private code.
2. **Run the D1 live gate. This needs Andrew:**
   - a Sentry Cloud org, region and slug
   - a token with `event:read`, plus project read access for browsing
   - a test project containing a sanitized real error; ideally a source-mapped React error, since that also exercises finding 2
3. **Build Sentry project/issue browsing** (review priority 1):
   - Factor one bounded GET helper out of `fetch_event`: fixed hosts, no proxy or redirects, a byte budget, a deadline, and the same 401/403/404/429 mapping, plus handling for malformed JSON.
   - Build paths only from validated slugs and IDs. List projects for the organization, then list issues for one selected project, with `limit` capped at 50 (the PLAN bound).
   - Pagination: take only the `cursor` value from the `Link` header's `rel="next"` entry, and only when `results="true"`. Validate it against a strict pattern derived from real responses (please verify the format live), and never follow URLs from headers.
   - Redact issue titles and culprits. Never fetch events automatically per issue: selecting an issue should call the existing explicit event retrieval.
   - Show `Retry-After` on 429, with no automatic retries, consistent with the current design.
   - Tests to add: 401, 403, 404, 429, a malformed `Link` header, a forged cursor, an oversized response, a non-list body, and a redirect.
4. **After the live gate:** the essential D2 items, namely hypothesis status and verification attachments.
5. **Deferred by Andrew's decision (self-hosted for now):** multi-tenant hosting, auth and scale limits. Low-urgency self-hosted items are a README security note (keep the backend on localhost; analyzed repositories are untrusted) and an analyzer sandbox with no network access.
6. **D3 trace import and the D4 whiteboard spike** complete v1. Don't start them before the D1 live gate unless Andrew reprioritizes.

---

## Commands used

- `git -c safe.directory=... log/show/diff dd6efa5 21b3a59`: reviewed the committed changes.
- Background verification: storage hashes before/after, full `pytest`, `ruff check .`, contracts, `tsc`, ESLint on changed files, production build.
- `Settings(workspace_root='x').report_root` and `runtime_path(...)` via `backend/.venv-managed` Python, run from `backend/` (findings 1 and 2).
- `curl.exe -H "Host: rebind.attacker.test" http://127.0.0.1:8000/api/analyses` and the matching `/api/debugging/cases` probe (finding 3).
- A scratch Node script running the real analyzer plus `architectureMap()` (finding 4).
- A scratch Python script building archives with `git archive`, `Compress-Archive` and `tar.exe`, then running preflight and extraction.
