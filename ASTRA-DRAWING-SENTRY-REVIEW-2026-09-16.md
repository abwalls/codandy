# Direct drawing, linked tickets and Sentry browse: review handoff

The whiteboard starting screen now renders an editable unsaved canvas. Save drawing and continue creates the persisted board using the drawn elements; leaving unsaved content uses the existing guard and JSON download remains available. Import moved under a disclosure. Delete clears old plan output/state before returning to the new drawing canvas.

TicketStore adds a source index and scoped history query, with no body or credential persistence. Source references are hashed; recommendations include repository/revision context. Additional changed drafts for a source need acknowledgement inside the same SQLite transaction that reserves the submission. Exact retries retain the existing receipt behavior. Inline links remain local receipt history, not refreshed provider status.

Sentry browsing reuses event transport for fixed cloud hosts, no redirects/proxies, a 2 MiB response limit and deadlines. Lists are at most 50 items; narrow fields are scrubbed before return. Cursor metadata is validated; provider pagination URLs are ignored. Issue results must match the requested project. Projects need org:read, issues/events event:read. No live credentials were used in QA.

A real integration-path bug was caught by browser QA: the old dev process retained stale proxy configuration. Restarting exposed a Windows hosted Worker startup hang. Portable dev now uses normal Vinext; Cloudflare remains enabled for build and managed Linux. Real localhost routing is verified. Initial dependency optimization can still make the first page compile slowly.

Validation: 307 backend tests, 47 API contracts, Ruff, TypeScript and changed-file ESLint passed. Personal storage hashes remained unchanged. Edge direct drawing/save/reopen/mobile, local ticket links, mocked additional-ticket confirmation and Sentry browse/pagination/selection passed. Live accounts, release commits, full provider foundation and richer whiteboard templates remain next work.
