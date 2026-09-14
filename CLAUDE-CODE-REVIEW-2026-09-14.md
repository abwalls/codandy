# Codandy review handoff — 2026-09-14

Please review the current `abwalls/codandy` checkout and report concrete correctness, security, and product issues. Do not rewrite history or use the former work identity/account.

## Current product direction

Codandy is now a debugging and investigation workspace. The static repository atlas remains supporting evidence. The main product path is: import a Sentry event or stack, normalize and redact it, save an investigation, match frames to a retained source snapshot, prepare a reviewed AI brief, and inspect architecture/source evidence.

## Recently implemented

- Bounded ZIP project upload with path traversal, symlink, encrypted-entry, duplicate-path, size, count, depth, and timeout checks. Repository code is never executed during ingestion.
- Interactive Architecture map built from real atlas relationships, with folder/project views, search, focus, zoom, evidence drilldowns, inferred/resolved styling, unresolved counts, keyboard support, and a readable mobile layout.
- Local saved investigations with sanitized observations, notes, state, restart recovery, atomic writes, deletion, and explicit retention limits.
- Conservative Sentry/stack normalization for Sentry REST JSON, Python, JavaScript, and .NET stacks. Imported data is bounded, redacted, and provider-sensitive sections are withheld.
- Candidate frame-to-source matching against retained snapshots. Unknown or user-supplied revisions remain unverified; ambiguous and unavailable bindings stay visible.
- Reviewed debugging brief export and local Codex Q&A. Questions require a current review digest and may cite only included evidence. No live AI or Sentry account request was used in validation.
- Owner-private hosted preview: https://codandy.abwalls.chatgpt.site

## Validation already completed

- 221 backend tests and 28 frontend/API contract tests pass.
- Ruff, TypeScript, changed-file ESLint, and production build pass.
- Headless Edge QA passed ZIP upload through the Vite proxy, Architecture desktop/mobile behavior, keyboard focus, saved-case edit/reload, source matching/viewing, and reviewed brief preparation.
- Test storage is isolated by `backend/tests/conftest.py`; personal retained reports were recovered byte-for-byte after an earlier retention-test defect and are now protected from test runs.

## Review priorities

1. Inspect the existing Sentry connector and roadmap for the next narrow slice: explicit, bounded project/issue browsing with fixed backend-built URLs, opaque cursor pagination, response redaction, project filtering, and safe handling of 401/403/404/429/malformed responses. Do not add browser-side tokens or implicit organization crawling.
2. Audit ZIP central-directory preflight and extraction cleanup for parser edge cases. Preserve the rule that archives are untrusted and never executed.
3. Audit saved-case persistence, observation immutability, note redaction, source-binding ambiguity, and AI brief citation boundaries for accidental data leakage or fabricated certainty.
4. Review Architecture map claims: it must only visualize actual atlas relationships and must label inferred/unresolved edges; folder names must not become invented runtime architecture.
5. Check the local/hosted boundary. The hosted preview is UI-only; private Sentry credentials, local reports, local Codex subscription access, and the Python API stay on localhost.

## Important constraints

- Read `AGENTS.md`, `PLAN.md`, `ROADMAP.md`, `ARCHITECTURE.md`, `docs/DEBUGGING-STRATEGY.md`, and `progress.md` before changing architecture.
- Never run analyzed repository builds, tests, package managers, hooks, binaries, or plugins.
- Keep `tree-sitter` below 0.26.
- Do not add `.env`, credentials, reports, cloned repositories, node_modules, or build output to Git.
- GitHub identity is personal `abwalls`; approved author/committer is `45399949+abwalls@users.noreply.github.com`.

Please leave findings and suggested fixes in a new timestamped Markdown handoff file. Distinguish verified defects from roadmap suggestions, and include the commands/tests used for each finding.
