# Linear targeting review — 2026-09-17

Pagination and optional project targeting are implemented in the active working tree, not yet committed/published. This shares files with Claude's Unicode-name fix; preserve that fix and the independently added local analysis/history/change-review/symbol features.

## Behavior

- Explicit 50-item team pages; bounded opaque cursors travel as GraphQL variables, never interpolated query text or followed URLs.
- Optional projects load from the selected team's projects connection, excluding archived projects. Pages replace the current list, keeping memory bounded. First-page buttons reset paging; failures preserve current selection.
- Team changes discard project choices. Target/page changes discard review, consent and submission key. Drafts without a project retain the old payload shape.
- projectId is included in the exact reviewed payload and digest. Changing/removing it after review is rejected before any mutation. Existing durable uncertain-submission protection remains unchanged.
- Shared named-page validation rejects malformed pagination, repeated next cursor, empty continuation pages, duplicate/invalid IDs and non-string names. Names are scrubbed and clipped to 200 Python code points; frontend reuses Claude's matching schema.

## Validation

- 33 isolated ticket tests pass, including target digest/idempotency, local-only endpoints, cursor bounds, provider shape and project query scope.
- Ruff and changed frontend lint pass; 56 combined contract tests pass.
- Synthetic Edge checks pass team/project paging, encoded cursors, review reset, failures, optional project omission, team switch and mobile width. No live Linear call or ticket was made.
- Combined TypeScript reports a concurrent Symbols onShowSymbol prop mismatch in live-report.tsx. No production build/deployment claimed for this slice. Last successful deployment remains evidence/plan-comparison Sites v10, source cf9c921300ea6c8574b0d6115a25aca21b77b797.

## Review focus / limits

Check whether project target editing and paging invalidate every approval path. Project selection is a current listing, not durable verification of membership/access; Linear enforces permissions on issue creation. No labels, assignee or workflow-state targeting yet. No live account verification. Existing direct API requests can specify any valid project UUID, subject to provider authorization, just as team IDs could already be supplied directly.

Official API references checked: https://linear.app/developers/pagination and https://raw.githubusercontent.com/linear/linear/master/packages/sdk/src/schema.graphql (Team.projects and IssueCreateInput.projectId).


## Priority and final local checkpoint

Added explicit optional priority: use provider default (field omitted), No priority (0), Urgent (1), High (2), Medium (3), Low (4), matching the official IssueCreateInput schema. Backend rejects booleans, strings, fractions and out-of-range priorities. Exact reviews and digests include any selected priority, including zero; changes invalidate consent in both UI and backend.

39 ticket tests and Ruff pass. Combined backend run before the six priority cases passed 376 tests with one symlink-permission skip. Project/priority Edge checks and changed-file ESLint pass; combined TypeScript still has the concurrent onShowSymbol mismatch. The project contract suite passed 57 before adding the priority assertions; final priority contract run is recorded in progress.md. No live Linear writes, backend restart, commit or publication in this slice. The current running backend needs a restart to load the new project endpoint after coordinated changes are complete.

Read-only review observation for Claude's local-folder work: copy_file caches checked ancestor directories. If a checked directory is replaced by a junction/symlink between files, later files skip its link check, and shutil.copyfile(follow_symlinks=False) protects the leaf only, not ancestor resolution. The comment claiming a race cannot read outside the folder is stronger than the implementation. This is a code-inspection finding, not yet reproduced; add an ancestor-replacement fixture and consider handle-based source containment before describing the copy as race-safe. No changes were made to those files while coordination is pending.
