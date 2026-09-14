# ZIP upload intake — notes for Astra

**From:** Claude (Opus 5)
**Date:** 2026-09-14
**Subject:** Andrew asked for ZIP project uploads on the homescreen alongside GitHub URLs. It's implemented and tested. This note explains the design, the security properties to keep, and what is still open.

---

## Why I implemented this instead of reviewing it

Our usual split is still in place: you implement, I review. This time Andrew asked me
directly to add the feature and leave you a note. I kept the change narrow. The slice
doesn't touch the Sentry/debugging work you have in progress. The one thing I found there
is listed under [Open items](#open-items) and was **not** fixed.

**Nothing is committed.** Git refuses to run in this checkout from my session: the
repository is owned by `CodexSandboxOffline` and I'm running as `andre`, so git reports
"dubious ownership". I didn't change the global `safe.directory` config. Commits and
publishing are yours, under the `abwalls` identity rules in `AGENTS.md`.

---

## What the user sees

On the intake screen, below the GitHub form, there is an **"or"** divider and a dashed
dropzone labelled **"Upload a ZIP of your project"**. It accepts both click-to-browse
and drag-and-drop. The browser rejects non-`.zip`, empty, and over-100 MB files right
away. The backend repeats every one of these checks and is the authority.

- The progress screen's second step reads **"Extracting archive"** instead of "Cloning repository".
- For an uploaded archive, the live report header shows the archive name and
  "Uploaded ZIP archive · no Git revision".
- Recent reports show the archive name and "ZIP upload".
- The hint under the GitHub form changed from "ZIP and folder uploads coming later" to
  "folder uploads coming later".

---

## The flow

```
browser ──POST /api/analyses/archive?filename=x.zip  (raw body, Content-Type: application/zip)
   │
   ├─ router: content type → filename label → Content-Length cap → busy check
   ├─ receive_archive(): streams the body to .workspaces/upload-*.zip, counting bytes
   ├─ JobStore.create(ArchiveUpload(name, path))
   └─ worker thread JobStore.run():
        extract_archive() → TemporaryDirectory/repository   (phase "extracting")
        analyze_repository(root, url=<archive name>, ref=None)  (same spawned analyzer)
        atlas.repository = {source: "archive", name, ref: "upload", analyzed_at}
        collect_sources() → store result
        finally: unlink the upload file
```

After extraction, an upload goes through exactly the same analysis, source capture,
persistence and report path as a clone. The analyzer and its worker protocol are
**unchanged**. So is atlas schema `0.2`: `repository` was already a free-form
`dict[str, str]`, and adding `source`/`name` keys isn't a schema change.

**The body is raw, not multipart, on purpose.** `python-multipart` is not a dependency,
and a raw body needs no new dependency and no multipart parser. It also can't be sent by
a cross-site `<form>`, because `application/zip` is not a CORS "simple" content type.

---

## Security properties — preserve these

These are the load-bearing parts. Each one has a test.

1. **Uploads are never described in JSON.** `ArchiveUpload` is a frozen dataclass in
   `app/archives.py`. It is deliberately **not** part of `AnalysisCreate` or any Pydantic
   request model. If it ever became a JSON variant (for example `source.kind == "archive"`
   with a `path`), a client could name a server-side file for the worker to extract and
   then **delete**. The router constructs it only for a file it has just written.
   `test_upload_rejections_leave_nothing_behind` asserts that a JSON `kind: "archive"` gets a 422.
2. **Every member name is validated before anything is written.** Rejected names:
   - absolute paths and drive letters
   - `..`, empty, or `.` segments
   - control characters and `<>:"|?*` (the colon also blocks NTFS alternate data streams)
   - trailing dots or spaces
   - Windows reserved names (`con`, `nul`, `lpt1` …)

   One bad name fails the whole archive, and nothing is extracted. There is also a
   `resolve().is_relative_to(root)` check as defense in depth.
3. **Links and encrypted members are rejected.** A Unix symlink mode in `external_attr`
   is a link. Python's `zipfile` would write the link as a plain file anyway, but this
   mirrors `check_tree` rejecting links in clones.
4. **Both declared and actual sizes are limited.** The sum of declared sizes is checked
   against `max_repository_mb` before extraction, and the bytes actually written are
   counted during extraction. Declared sizes are attacker-controlled. File count and path
   depth use the same limits as clones, and `check_workspace()` runs again afterwards.
5. **Names are case-folded for duplicate and conflict detection.** Otherwise `src/App.py`
   and `src/app.py` would overwrite each other on Windows/macOS disks, and a file named
   `src` could conflict with a directory `src/`.
6. **Paths the analyzer would never index are never written to disk.** This covers
   `EXCLUDED_DIRS` (`.git`, `node_modules`, `bin`, `obj`, `dist`, …) and `SECRET_NAME`
   matches on both directories and files (`.env*`, keys, `*secret*`, `*credential*`).
   Two things follow. An uploaded `.env` never touches disk. And a zipped project that
   includes `node_modules` doesn't hit the 25 000-file limit for nothing. **If you change
   `EXCLUDED_DIRS` or `SECRET_NAME` in the analyzer, uploads follow automatically,
   because they import both.**
7. **An archive's Git metadata is never read.** `.git` isn't extracted, and `JobStore.run`
   skips the HEAD/ref reading for archives. That HEAD reading does
   `root / ".git" / head_ref` with `head_ref` taken from file contents. For a clone, Git
   wrote that file. For an upload it would be attacker-supplied, allowing a traversal read.
   So uploaded reports carry **no commit and no branch**, and source bindings will
   correctly report the revision as unknown.
8. **The upload limit is enforced on bytes received, not on `Content-Length`.** The header
   is only an early courtesy rejection; chunked uploads don't send it.
   `test_streamed_upload_limit_applies_without_content_length` covers this. The live smoke
   test also ran a real chunked upload.
9. **Cleanup covers every exit path.** A rejected, oversized, busy, non-zip or disconnected
   upload is unlinked in the router or in `receive_archive`. An accepted upload is unlinked
   in `JobStore.run`'s `finally` block, and extraction lives in a `TemporaryDirectory`.
   Tests assert that the workspace root is empty afterwards.
10. **The filename is a display label only.** `archive_label()` keeps the basename,
    replaces anything outside `[A-Za-z0-9 _.()+-]` with `_`, and caps the length. It never
    becomes a filesystem path; temp files use `mkstemp` names.

Two smaller details:

- If a GitHub "Download ZIP" archive (`repo-main/…`) has a single wrapper folder, it is
  unwrapped, so report paths match the repository layout.
- `__MACOSX/` resource forks are dropped. Without that, AppleDouble `._foo.py` files get
  parsed as Python, and every Finder-made zip ends up with two top-level entries.

---

## Frontend

- `components/codandy-workspace.tsx`
  - `Intake` gains `onUpload`, the dropzone, and client-side pre-checks.
  - `Analyzing` gains an `archive` prop that maps the `extracting` phase to step 2.
  - The submit logic was factored into one `start(label, isArchive, submit)` callback
    shared by `analyze` and `analyzeArchive`. The WebMCP `start_repository_analysis` tool
    still calls `analyze` and was **not** extended to archives.
  - Uploads use a 10-minute request timeout instead of `api()`'s default 15 seconds.
- `lib/analysis-api.ts` has two new exports:
  - `MAX_ARCHIVE_BYTES`, which mirrors the backend default and is used for UX only.
  - `repositoryName()`, which falls back from URL to archive name.
- `components/live-report.tsx` and `components/recent-reports.tsx` now show the archive
  name and label in place of the URL and commit. `components/investigation-source.tsx`
  already fell back to `repository.name`.
- `lib/atlas-comparison.ts`: an archive's identity is `archive:<lowercased name>`. Two
  uploads of `project.zip` can be compared with each other. An upload can't be compared
  with a GitHub snapshot or with a differently named archive. **This is a judgment call.**
  Archive names are weak identity: `repo-main.zip` and `repo-feature.zip` won't compare.
  If Andrew wants cross-name comparison, loosen it deliberately and keep the guard against
  unrelated repositories.
- `app/api/analyses/[[...path]]/route.ts` (hosted proxy):
  - `archive` is added to the allowlist.
  - Only `filename` is forwarded, never the whole query string. There's a contract test.
  - The body is **streamed** (`duplex: "half"`), not buffered, because Workers have a
    128 MB memory ceiling and uploads can be 100 MB.
  - Pre-checks: 405 for methods other than POST, 400 without a filename, 415 for a wrong
    content type, 413 for an oversized `Content-Length`.

**Adding an upload input means updating three places.** If you add another intake type
(folder upload is next per the hint copy): keep `repositoryName()`, `atlas-comparison`'s
`repositoryKey()`, and the `Analyzing` phase mapping in sync.

---

## Configuration

`Settings.max_upload_mb`, default **100**, range 1–1000. It limits the **compressed**
upload; the extracted size still uses `max_repository_mb` (250). I added
`CODANDY_MAX_UPLOAD_MB=100` to `backend/.env.example`, which keeps the "every Settings
field is present" property from the last review. If you change the default, also change
`MAX_ARCHIVE_BYTES` in `lib/analysis-api.ts` and in the proxy route. Both copies are
commented as mirrors.

---

## Files

**New:** `backend/app/archives.py`, `backend/tests/test_archives.py` (27 tests)

**Modified:**

| File | Change |
|---|---|
| `backend/app/jobs.py` | `busy()`; `create`/`run` accept `ArchiveUpload`; `extracting` phase; archive repository metadata; no Git read for archives; archive-specific failure text; upload unlink in `finally` |
| `backend/app/routers/analyses.py` | `POST /analyses/archive` |
| `backend/app/settings.py`, `backend/.env.example` | `max_upload_mb` |
| `app/api/analyses/[[...path]]/route.ts` | Archive allowlist, streamed body, pre-checks |
| `components/codandy-workspace.tsx` | Dropzone, upload submit, extracting step |
| `components/live-report.tsx`, `components/recent-reports.tsx` | Archive display |
| `lib/analysis-api.ts`, `lib/atlas-comparison.ts` | `MAX_ARCHIVE_BYTES`, `repositoryName()`, archive identity |
| `tests/analysis-api.test.mjs` | Proxy streaming and forwarding contract; archive naming and comparison (+2) |
| `progress.md` | Checkpoint |

---

## Verification

| Check | Result |
|---|---|
| `pytest` (full backend) | **218 passed**. A later one-line refactor in `receive_archive` (ruff ASYNC230) was re-verified with `test_archives`, `test_jobs` and `test_ingestion`: 65 passed |
| `ruff check` (changed backend files) | clean |
| `pnpm test:contracts` | **26 passed** (was 24) |
| `tsc --noEmit` | clean |
| ESLint (changed frontend files) | clean |
| Production build | succeeds |
| Live HTTP smoke — isolated uvicorn on :8001, scratch workspace/report roots | passes (details below) |

The live smoke used a 132 KB ZIP built from this repo's `lib/` and `components/` under a
`smoke-main/` wrapper, with an extra `node_modules/` entry and a `.env` file. Results:

- **Analysis:** 202 on submit, then complete. 89 files, 457 symbols, 946 relationships.
- **Report metadata:** `repository = {source: archive, name: smoke-main.zip, ref: upload}`.
- **Exclusions and source endpoint:** `node_modules` and `.env` were not indexed. The
  source endpoint served `lib/analysis-api.ts` and returned 404 for a traversal path.
- **Rejections:** a second upload while one was running got 429; a chunked upload with no
  Content-Length completed; `text/plain` got 415; a non-zip body got 422 with a string detail.
- **Cleanup:** workspace root empty afterwards.

**Not verified:**

- **Browser/visual QA.** The Chrome extension wasn't connected from my session, so
  drag-and-drop, the drag highlight, and the mobile layout of the dropzone haven't been
  looked at. What I did check is weaker: `http://localhost:5173/` returned 200, its
  server-rendered HTML contains the new dropzone copy and input label, and the old
  "ZIP and folder uploads coming later" text is gone.
- **Upload through the Vite dev proxy (`:5173` → `:8000`).** Andrew's backend on :8000
  was started **without `--reload`** and is still running the old code, so
  `/api/analyses/archive` returns 405 there until it's restarted. I didn't restart it.
  `http-proxy` streams bodies, so this should work, but it hasn't been run.
- **Hosted proxy against a real Worker.** Streaming is contract-tested in Node only.
  Cloudflare also caps request bodies by plan (100 MB on Free/Pro), which happens to
  equal our default.
- **Full-suite rerun after the ASYNC230 refactor.** The three suites that touch the
  change passed; the other ~150 tests don't import `archives.py`.

---

## Open items

1. **Pre-existing ruff failure, not mine:** `app/debugging/brief.py:3` has an I001 import
   order issue (`json` before `hashlib`). It's in your in-progress brief slice, so
   `ruff check .` on the whole backend is red until you fix it. It's auto-fixable.
2. **Central-directory memory.** `zipfile` loads the whole central directory when it opens
   an archive, before any of our limits run. A 100 MB upload made entirely of
   minimum-size entries could hold on the order of 2M `ZipInfo` objects in memory.
   That's acceptable for local single-user use; revisit it before multi-tenant hosting.
   A lower `max_upload_mb` or a cheap end-of-central-directory entry-count pre-check
   would close it.
3. **A cancelled future can leak one upload file.** If the API shuts down after
   `create()` submits a job but before the worker starts it,
   `executor.shutdown(cancel_futures=True)` means `run()` never executes, and
   `.workspaces/upload-*.zip` survives. The window is tiny; noting it for when shutdown
   handling gets attention.
4. **Folder upload** is still "coming later" per the copy. The extraction path in
   `archives.py` (validate names → select → bounded write) is the natural place to add a
   browser folder upload as a multi-file variant. **Ask Andrew first:** `PLAN.md` line 57
   frames private-code intake as validated bundle import first, then *trusted local-folder
   indexing*, and ZIP upload sits somewhere between those two.
5. **The `PLAN.md`/`ROADMAP.md` wording** wasn't changed. ZIP intake isn't a milestone
   change, but you may want to mention it where private-repository intake is discussed.

If you disagree with any of these calls, especially the raw-body transport or skipping
excluded paths at extraction, say so in your next checkpoint with your reasoning.
