# Offline OTLP import: review handoff

Implemented the credential-free portion of M2. Errors & stacks now accepts OTLP JSON files and displays a filterable waterfall with selected span details and reviewed sanitized export. Input is ephemeral; reload clears it. Timing represents elapsed wall time, not CPU time.

Review backend/app/debugging/traces.py, the trace import route, lib/trace-api.ts and components/trace-viewer.tsx. Limits: 2 MiB JSON, depth 32, 1,000 retained spans. IDs and timestamp ordering are validated; duplicate span IDs within a trace are rejected. Nanoseconds remain strings until relative BigInt subtraction. Missing and cyclic parent chains are labeled. Resource and span attributes use a narrow allowlist, with text redaction before display/export. Events, links, arbitrary attributes, SQL text and status messages are omitted.

Validation: 280 backend tests, 41 frontend/API contracts, Ruff, TypeScript, changed-file ESLint and production build passed. Headless Edge verified import, service/name and error filtering, span selection, scrubbing, export review gate and mobile layout. ERD QA covered all five themes and keyboard selection; contracts and whiteboard passed desktop/mobile checks. Personal report/case/board hashes were unchanged by the backend suite.

Remaining: no OTLP receiver, protobuf decoding, source binding, persistence, AI submission, Datadog connection or ticket-provider calls. I0 and reviewed ticket creation are still separate work. Consider larger multi-service fixtures before extending the timeline to sequence diagrams. Build retains the existing large-chunk warning; backend tests report dependency deprecation warnings.
