# Integrations plan: monitoring, ticketing and source connectors

**Status:** draft for implementation.
**Written:** 2026-09-15 by Claude, at Andrew's request.
**Implementer:** Astra 6. **Reviewer:** Claude, one review per slice (see §11).

**Relationship to existing plans:**
- Extends PLAN.md **D1b/D1d** (Sentry), **D3** (traces and performance) and **D6** (ticket writes, CI evidence).
- **D5** (Codandy MCP server) is referenced here but stays in PLAN.md.
- Respects Andrew's self-hosted decision: local-first, single user, no public receivers.
- Keeps every security invariant in AGENTS.md.

---

## 1. Goals

1. **Runtime evidence without running code.** Codandy analyzes source statically and never executes a repository. Monitoring integrations add *observed* runtime evidence:
   - errors
   - traces and spans
   - logs
   - the release-to-commit association

   Codandy's own safety boundary stays intact.
2. **Tickets from anywhere a developer decides to act:**
   - Recommended changes
   - saved investigations
   - Whiteboard plans
   - dependency advisories
   - Ask Codandy answers

   The first trackers are Linear, ClickUp and Jira Cloud.
3. **Connect the evidence chain.** Runtime event → trace → release → commit → analyzed snapshot → source candidates → ticket, with every hop labelled by how it is known.

## 2. Non-negotiable rules

1. **Local only.** New routers use the existing `local_only` dependency, behind the global `AllowedHosts` middleware. The hosted proxy never forwards `/api/integrations`, `/api/tickets` or monitoring routes.
2. **Credentials live on the backend.**
   - Stored as `SecretStr` settings.
   - Never returned by any API, logged, placed in exports or reports, or sent to the AI.
   - The UI only sees *configured / verified / failing*, plus the last sanitized error.
3. **Least privilege.**
   - Monitoring connectors are read-only.
   - Ticketing connectors use write access only for *create issue* (later, *read issue status*).
   - Connectors never call provider endpoints that change monitoring data. Datadog Error Tracking's issue-state and assignee updates, for example, are out of scope.
4. **Fixed destinations.** Provider hosts come from an allowlist (§3). User-supplied base URLs (self-hosted Sentry, a Jira site name) must:
   - be HTTPS
   - carry no credentials, query string or fragment
   - resolve only to public addresses, with DNS pinned for the connection, reusing the approach in `ingestion.py`
   - A per-connection `allow_private_network` flag may relax the public-address rule for LAN-hosted providers. It is off by default and visible in the UI.
5. **Bounded I/O.**
   - Connect and read timeouts, plus a response byte cap per call (2 MiB, matching D1).
   - No redirects, and no proxy variables inherited from the environment.
   - Pagination cursors are validated against strict patterns and never followed from URLs in headers.
   - At most one page per user click unless the user asks for more.
   - On 429, honour `Retry-After`, with at most 3 attempts per PLAN.md D1 and no background retry loops.
6. **Normalize before storing.**
   - Provider payloads become Codandy contracts, with redaction, truncation and withheld sections recorded.
   - Raw provider responses are never persisted or sent to the AI.
7. **Evidence basis stays explicit.** Observed runtime data, provider-reported associations, static candidates, user notes and AI text remain distinct in storage, UI and prompts.
   - A span's `code.*` attributes produce **candidates**, not facts.
   - A release commit reported by a provider is **provider-reported**. It is shown as **matching** the snapshot only when the full SHA equals the snapshot's commit.
8. **Outbound writes are reviewed and explicit.**
   - Every ticket creation shows the exact payload.
   - The request is bound to that review by a digest, following the investigation brief pattern.
   - It needs a user click and an idempotency key, and is recorded in a local audit log.
   - The AI may **draft** a ticket; it can never create one. The Codex bridge keeps tools disabled.
9. **No webhooks or public receivers.** Everything is pulled on demand, as PLAN.md D6 requires. The optional OTLP receiver (§6, M3) listens on loopback only.
10. **Tests never touch real accounts.** Provider behaviour is tested with sanitized recorded fixtures and mocked transports. Live checks need Andrew's accounts, run manually, and are recorded in `progress.md`. The `conftest.py` isolation fixture already clears `CODANDY_*` variables, and new settings must be added to its overrides.

---

## 3. Verified provider facts (checked 2026-09-15; reconfirm at implementation)

| Provider | What we use | Auth | Notes |
|---|---|---|---|
| **Sentry** (existing connector) | `GET /api/0/organizations/{org}/issues/` (default query `is:unresolved`); issue events (already implemented); `GET /api/0/organizations/{org}/releases/{version}/commits/` | Bearer token. Scopes: `event:read`, plus `project:releases` for commits | Cursor pagination through the `Link` header with `results="true|false"`; cursors look like `0:100:0`. Cloud hosts are `sentry.io`, `us.sentry.io`, `de.sentry.io`. |
| **OpenTelemetry** | OTLP/HTTP `/v1/traces`, `/v1/logs` (and `/v1/metrics`, not planned) | Not applicable (local import or loopback receiver) | Default ports: 4318 (HTTP), 4317 (gRPC). Content types `application/x-protobuf` and `application/json`. **JSON:** lowerCamelCase keys, `traceId`/`spanId` as hex strings, enums as integers. Retry on 429/502/503/504, honouring `Retry-After`. Stable code attributes: `code.file.path`, `code.line.number`, `code.column.number`, `code.function.name`, `code.stacktrace`. Deprecated `code.filepath`, `code.lineno`, `code.column`, `code.function` and `code.namespace` must also be read. |
| **Datadog** | `POST /api/v2/error-tracking/issues/search`; `GET /api/v2/error-tracking/issues/{issue_id}`; `POST /api/v2/spans/events/search` | Reads need an API key **and** an application key, sent as the `DD-API-KEY` and `DD-APPLICATION-KEY` headers. Confirm header names and scoped application keys at implementation. | Nine independent sites: `datadoghq.com`, `us3.datadoghq.com`, `us5.datadoghq.com`, `datadoghq.eu`, `ap1.datadoghq.com`, `ap2.datadoghq.com`, `uk1.datadoghq.com`, `ddog-gov.com`, `us2.ddog-gov.com`. The API host is `api.{site}`. |
| **Linear** | GraphQL `https://api.linear.app/graphql`, `issueCreate` (`teamId` and `title` required; Markdown `description`) | Personal key sent as `Authorization: <API_KEY>`; OAuth uses `Bearer` | Rate limits aren't quantified in the docs, so handle 429. |
| **ClickUp** | `POST /v2/list/{list_id}/task` (only `name` required; `markdown_content` takes precedence over `description`) | Personal token sent as `Authorization: pk_…`; OAuth uses `Bearer` | Choosing a target means walking workspace → space → folder → list. |
| **Jira Cloud** | `POST /rest/api/3/issue`; `GET /rest/api/3/issue/createmeta/{projectIdOrKey}/issuetypes` and `…/issuetypes/{issueTypeId}` for required fields | Classic: email plus API token over Basic auth at `https://{site}.atlassian.net`. Scoped tokens: `https://api.atlassian.com/ex/jira/{cloudId}` | **Descriptions use Atlassian Document Format (ADF)** in v3. The older all-in-one createmeta endpoint is deprecated. API tokens expire within 1–365 days, so show an expiry-aware error. |

---

## 4. Architecture

```
backend/app/integrations/
  registry.py      provider manifests: id, kind (monitoring | tickets | source), settings, capabilities
  http.py          shared bounded client (grown out of debugging/sentry_client.py)
  credentials.py   settings-backed credential access (v1); single seam for a keychain later
  audit.py         local append-only log of outbound writes (tickets): who, when, target, digest, result
  sentry.py        extends today's connector (M1)
  otlp.py          OTLP/JSON parsing and normalization; loopback receiver (M2, M3)
  datadog.py       error tracking and spans (M4)
  tickets/         draft.py (contract, rendering), linear.py, clickup.py, jira.py (ADF)
  github.py        private repository access and commit metadata (S1)
backend/app/routers/
  integrations.py  GET /api/integrations (status), POST /api/integrations/{id}/test
  tickets.py       POST /api/tickets/review, POST /api/tickets, GET /api/tickets/links, POST /api/tickets/{id}/refresh
  debugging.py     gains provider-scoped routes for issue lists, traces and imports
app/integrations/page.tsx, components/integrations/*, components/create-ticket-dialog.tsx
lib/integrations-api.ts, lib/tickets-api.ts
```

### Shared HTTP client (`http.py`)

- Built on the `sentry_client.py` design: `ProxyHandler({})`, `NoRedirect`, a TLS context, a per-request deadline and a streamed byte cap.
- Adds a per-provider host allowlist, DNS pinning for user-supplied hosts, `Retry-After` parsing and cursor validators.
- **One error taxonomy**, whose messages never echo tokens or raw bodies: `unauthorized`, `forbidden`, `not_found`, `rate_limited(retry_after)`, `unavailable`, `malformed`, `too_large`, `timeout`.
- The existing Sentry event retrieval moves onto the shared client **without changing its behaviour or tests**.

### Credentials

- **v1 (recommended):** keep today's model. Settings in ignored `backend/.env`, loaded at startup:

  ```
  CODANDY_DATADOG_SITE, CODANDY_DATADOG_API_KEY, CODANDY_DATADOG_APP_KEY
  CODANDY_LINEAR_API_KEY
  CODANDY_CLICKUP_TOKEN
  CODANDY_JIRA_SITE, CODANDY_JIRA_EMAIL, CODANDY_JIRA_API_TOKEN, CODANDY_JIRA_CLOUD_ID (scoped tokens)
  CODANDY_GITHUB_TOKEN
  CODANDY_OTLP_RECEIVER_ENABLED, CODANDY_OTLP_RECEIVER_PORT
  ```

  - All secrets are `SecretStr`.
  - The Integrations page explains which setting to add and offers **Test connection**.
  - Changing settings requires a restart, as Sentry does today.
- **v2 (decision for Andrew, §10):** in-app entry backed by the OS credential store. It would sit behind the same `credentials.py` seam, after a dependency and licence review.

### Contracts (Python and TypeScript kept in sync, versioned)

| Contract | Change |
|---|---|
| `debugging-0.2` | **Additive** successor to `debugging-0.1`: adds provider `datadog` and `otlp`, and formats `datadog_error_tracking` and `otlp_span_exception`. `debugging-0.1` documents keep loading, and saved cases stay readable. |
| `trace-0.1` (new) | `trace_id` (32 hex characters), `source` (provider, format, fetched or received time, interpretation notes), and `spans[]`. Each span has `span_id`, `parent_span_id`, `name`, `kind`, `service`, `start`/`end` (Unix nanoseconds, strings in JSON), `status`, **allowlisted** `attributes`, `events[]` (e.g. `exception.type`, `exception.message`, `exception.stacktrace`) and `links[]`. Also `truncations`, `redactions`, `withheld`, `limitations`. Spans with missing parents are kept and flagged, never reparented. |
| `connection-0.1` | `provider`, `configured`, `verified_at`, `capabilities`, `last_error` (sanitized), `settings_hint`. |
| `ticket-draft-0.1` | `title`, `description_markdown`, `labels[]`, `priority` (suggestion), `source` (`kind`: recommendation / case / board_task / advisory / answer, plus `id`), `evidence_refs[]`, `basis_notes[]`, `digest`. |
| `ticket-link-0.1` | `source` reference, `provider`, `external_key`, `url`, `created_at`, `draft_digest`, `idempotency_key`, `last_status` (optional, read on demand). |

**Attribute allowlist for spans** (everything else is dropped and counted):

| Group | Attributes |
|---|---|
| Code | `code.*` |
| Service and deployment | `service.name`, `service.version`, `deployment.environment(.name)` |
| HTTP and routing | `http.request.method`, `http.route`, `http.response.status_code`, `url.path` (redacted) |
| Database | `db.system(.name)`, `db.operation(.name)` (no statement text) |
| Messaging and RPC | `messaging.system`, `rpc.system`, `rpc.method` |
| Errors and tracing | `error.type`, `exception.*`, `thread.name`, `otel.status_code` |

---

## 5. Milestones and order

| # | Slice | Depends on | Done when |
|---|---|---|---|
| **I0** | Integration foundations | none | Registry, shared client (Sentry migrated, tests unchanged), credentials seam, `/api/integrations` status and test, Integrations page, outbound audit log, fixture harness. |
| **T0** | Ticket drafts, review and links | I0 | Draft contract, digest-bound review endpoint, create endpoint with idempotency and audit, ticket links stored on source items, duplicate warning, and a `CreateTicketDialog` with provider/target picker and exact preview. |
| **T1** | **Linear** | T0 | Team (and optional project/labels) picker, `issueCreate`, link stored. First entry point: **Recommended changes**. |
| **M1** | **Sentry completion** | I0 | Project and issue browsing with validated cursors, then issue → latest/specific event (existing). Release commits drive the `provider-reported` / `matches snapshot` revision labels. Live gate on Andrew's account. |
| **M2** | **OpenTelemetry import** | I0 | OTLP/JSON trace file import into `trace-0.1`. Waterfall viewer (PLAN.md D3). Span → source candidates using `code.*` (stable and deprecated names) through the existing `path_hint` binding. Span exception events → `debugging-0.2` observations parsed by the existing stack parsers. |
| **T2** | **ClickUp** | T0 | Workspace → space → folder → list picker, create task with `markdown_content`, link stored. |
| **T3** | **Jira Cloud** | T0 | Site/email/token or scoped-token configuration. Project and issue-type picker from createmeta, with a required-field check that blocks creation with a clear message. Markdown → ADF conversion for a documented subset. Expiry-aware 401 message. |
| **M4** | **Datadog** | I0 | Site selection, API and application key test. Error Tracking issue search and detail → `debugging-0.2` observations. Spans search by `trace_id` → `trace-0.1`. Rate-limit handling. Live gate on Andrew's account. |
| **M3** | **Local OTLP receiver** (opt-in) | M2 | Loopback-only OTLP/HTTP **JSON** `POST /v1/traces` on a configurable port (off by default). Bounded in-memory buffer; nothing persists until a trace is saved to a case. A full buffer returns 429 with `Retry-After`; accepted payloads return 200 with `partialSuccess` semantics. Protobuf is out of scope until a dependency decision. |
| **T4** | Remaining ticket entry points | T1 | Errors & stacks cases, Whiteboard plans (one ticket per task, or a parent with sub-tasks where the tracker supports it, in dependency order), dependency advisories, Ask Codandy (AI **draft** only). |
| **M5** | Evidence correlation | M1, M2 or M4 | The case timeline links observations ↔ traces ↔ logs by `trace_id`. Release/version → commit → snapshot comparison. Service and environment filters. |
| **T5** | Ticket status read-back | T1–T3 | **Refresh status** per link, one GET on click, no webhooks. |
| **S1** | GitHub private repositories | I0 | Fine-grained token (contents read) used only during clone of `github.com` URLs, through a one-shot credential helper. Never persisted, logged or placed in atlas metadata. Commit metadata for revision checks. |
| **S2** | CI evidence import | I0 | JUnit XML test results and LCOV/Cobertura coverage imported as **reported** evidence per file. No test execution, and never labelled as analysis. |
| **S3** | IDE deep links | none | "Open in VS Code / JetBrains" links for source candidates and ticket descriptions, using local paths the user configures. No automatic filesystem access. |
| **Later** | Codandy MCP server (D5); Slack/Teams sharing of reviewed briefs; GitLab and GitHub Issues adapters; OTLP logs import; OAuth for trackers; self-managed Jira | as noted | Tracked in PLAN.md and ROADMAP.md when started. |

**Suggested order for Astra:** I0 → T0 + T1 → M1 → M2 → T2 → T3 → M4 → M3 → T4 → M5 → T5 → S1 → S2 → S3.

Ticketing gives the quickest visible win. Sentry completes the D1 gate. OpenTelemetry works without any account, so it can be fully fixture-tested before Datadog.

---

## 6. Milestone details

### I0: foundations

- Provider manifest per integration: `id`, `kind`, `display_name`, `required_settings[]`, `capabilities[]` (e.g. `issues.read`, `traces.read`, `tickets.create`), `docs_url`.
- `POST /api/integrations/{id}/test` performs one cheap authenticated read and returns only a sanitized status:
  - Sentry: organization.
  - Linear: viewer.
  - ClickUp: authorized user.
  - Jira: myself.
  - Datadog: key validation.
- **Audit log:** JSON Lines under `CODANDY_INTEGRATION_ROOT` (default `.integrations`), gitignored and covered by test isolation. It records only provider, target, draft digest, external key and outcome, never ticket bodies.
- **Tests:**
  - host allowlist
  - DNS pinning and private-address rejection for user hosts
  - no redirects
  - byte cap
  - timeout
  - error taxonomy messages never contain a token (run with a sentinel token)

### T0 + T1: tickets and Linear

1. **Draft builders per source kind**, using only data already shown to the user:
   - *Recommendation:* title, description, basis/confidence, approach steps, verification steps, evidence locations (paths and lines, no source bodies).
   - *Case:* observation title, exception chain summary, top in-app frames with candidate paths, revision label, and a link back to the provider (Sentry/Datadog URL).
   - *Board task:* title, description, acceptance criteria, verification, proposed paths labelled as proposed.
   - *Advisory:* dependency, version basis, advisory IDs and links.
   - *Answer:* the user's question, the AI answer labelled "AI draft; verify", and cited evidence IDs.
2. **Review step.** `POST /api/tickets/review` returns the rendered provider payload and a digest. `POST /api/tickets` must present that digest, a target and an idempotency key.
3. **Idempotency.** A per-source-item key prevents double creation on retries. If a link already exists, the UI warns before creating another.
4. **Linear target discovery:** teams (and optional projects/labels), bounded to the first page with a search box.
5. **Tests:**
   - payload rendering golden files per source kind
   - a changed draft makes the stale digest return 409
   - idempotent retry
   - duplicate warning
   - redaction of secrets in titles and descriptions
   - an AI answer draft is labelled

### M1: Sentry completion

- Browse the organization's projects, then issues for a project: `query` (bounded string), `limit` ≤ 50 (the PLAN.md bound), and cursor validated against `^\d+:\d+:[01]$`, confirmed against live responses.
- Issue titles and culprits pass through `Redactor`. Selecting an issue calls the existing event retrieval, with no automatic per-issue event fetch.
- **Release commits.** When an observation has a `release`, a **Check release commits** action lists the commits.
  - If a full SHA equals the linked snapshot's commit, the binding revision becomes `matches_snapshot (provider-reported)`.
  - Otherwise it stays `unknown` or `mismatch` with the reason.
  - A missing `project:releases` scope produces a clear 403 message.
- **Tests:** 401, 403, 404, 429 (with `Retry-After`), malformed `Link` header, forged cursor, oversized body, non-list body, redirect.

### M2 + M3: OpenTelemetry

- **Import:** accept a `.json` file (≤ 2 MiB, depth-bounded, no duplicate keys) holding an `ExportTraceServiceRequest` (`resourceSpans[] → scopeSpans[] → spans[]`).
  - Normalize IDs to lowercase hex and times to integer nanoseconds.
  - Map resource `service.name` to span `service`.
  - Apply the attribute allowlist and redaction.
- **Source candidates:** for spans with code attributes, pass `code.file.path` / `code.filepath` through `path_hint()` and bind to the selected snapshot, just like stack frames. Record which attribute generation was used. A span name alone never produces a candidate.
- **Exceptions:** span events named `exception` become `debugging-0.2` observations (`provider: otlp`). The stacktrace is parsed by the existing Python/JS/.NET parsers where recognised, and kept as text otherwise.
- **Viewer (D3):**
  - waterfall with depth and time scale
  - concurrency shown by overlap
  - missing parents flagged
  - a durations legend stating this is span wall time, not CPU time
  - V-track sequence components reused where lifelines help
- **Receiver (M3):** binds `127.0.0.1` only, checks `Content-Type: application/json`, and enforces a 2 MiB request cap, the host guard and a ring buffer (default 200 traces or 20 MiB). No authentication is needed because it's loopback-only; document that any local process can send to it.
- **Tests:**
  - fixtures from the OTLP JSON examples
  - hex ID validation
  - deprecated attribute mapping
  - orphan spans
  - an exception event parsed into an observation
  - receiver limits, content type, 429 when full, and loopback binding

### M4: Datadog

- **Settings:** site (enum of the nine sites), API key, application key. Test with a lightweight authenticated read.
- **Error Tracking:** search issues (bounded query, time window ≤ 7 days by default, first page), then issue detail → observation. Stack text comes from the issue or its sample error. Confirm field names against live responses and record the mapping in the adapter's interpretation notes.
- **Spans:** search by `@trace_id:<id>` within a bounded window, then normalize into `trace-0.1`. Datadog attribute names map into the allowlist.
- **Tests:** site allowlist, both headers present, 401/403/429, malformed body, empty results, sentinel token never echoed.

### T2 and T3: ClickUp and Jira

- **ClickUp:** a cascading picker (workspace → space → folder → list) with bounded list calls, then `POST /v2/list/{list_id}/task` with `name` and `markdown_content`.
- **Jira:**
  - Project search, then issue types for the project, then that type's fields. If a required field has no default and isn't supported, **block creation** and name the field.
  - **Markdown → ADF subset:** paragraphs, headings, bullet and ordered lists, code blocks (language kept), inline code, links, bold and italic. Anything else is sent as plain text paragraphs. Covered by golden tests.
  - Classic (site) and scoped (`api.atlassian.com/ex/jira/{cloudId}`) base URLs.
- **Tests:** payload goldens, a required-field block, ADF validity, a 401 message that suggests token expiry.

### S1–S3

- **S1:**
  - Reuse `clone_repository` hardening.
  - Pass the token through a one-shot `GIT_ASKPASS`/credential-helper script in the disposable workspace, deleted with it.
  - Never put the token in URLs, command lines, atlas metadata or error text.
  - Test that the token is absent from process arguments, events, errors and the atlas.
- **S2:**
  - Parse JUnit XML with `defusedxml`-style protections (no DTDs or entities, as the analyzer already requires for project XML), plus LCOV/Cobertura, with size limits.
  - Map results to files through path hints.
  - Label outcomes "imported CI result (date, source)".
- **S3:**
  - The user sets a local repository root per snapshot.
  - Links are built as `vscode://file/<root>/<path>:<line>` or the JetBrains equivalent.
  - Links are only rendered; nothing is opened automatically.

---

## 7. UI surfaces

- **Integrations page** (`/integrations`): one card per provider showing status (Not configured / Configured / Verified / Failing), capabilities, the setting names to add, **Test connection**, the last sanitized error and a docs link. The same page lists ticket links and the outbound audit.
- **Create ticket dialog**, available on each source kind:
  1. Choose a tracker and target.
  2. Edit the title and description.
  3. Review the exact payload preview and redaction summary.
  4. **Create in {Tracker}**.
  5. See the result link.

  The dialog opens in a working state with the draft prefilled.
- **Errors & stacks:** provider tabs (Sentry, Datadog, OpenTelemetry import, Local receiver when enabled), issue lists with pagination, and a trace view next to the observation.
- **Evidence labels:** *observed*, *provider-reported*, *matches snapshot*, *candidate*, *AI draft* and *user note*, shown consistently.

## 8. Testing and verification standards

- **Every slice:** backend pytest (full), ruff, contracts, `tsc`, changed-file ESLint and build, and personal storage hashes unchanged, including the new `.integrations` root.
- **Fixtures:** sanitized recorded responses under `backend/tests/fixtures/integrations/<provider>/`. Never commit real tokens, organization names, emails or customer data. Add a CI-style test that scans fixtures for token patterns.
- **Live gates** (manual, with Andrew's accounts): Sentry issue browse and release commits, Datadog issue and trace, one ticket per tracker in a throwaway project. Record them in `progress.md` with what was and wasn't verified.

## 9. Risks

- **API drift.** Datadog Error Tracking and some Jira endpoints change. Keep adapters thin, record interpretation notes, and pin expected shapes with fixtures.
- **Jira variability.** Required custom fields differ per project. Blocking with a clear message beats partial creation.
- **Data leaving the machine.** Tickets send content to third parties. Review, redaction and no source bodies by default are the mitigations.
- **Rate limits on large organizations.** Browse one page per click and keep queries bounded.
- **Receiver exposure.** Loopback only and off by default. Documented as accepting data from any local process.

## 10. Decisions for Andrew

1. **First tracker.** The plan assumes Linear; swap T1 and T3 if Jira is primary.
2. **Credential storage.** `.env` settings (v1, recommended) or in-app entry backed by the OS credential store (v2).
3. **Hosting of providers.** Sentry Cloud or self-hosted, and which Datadog site, before the M1/M4 live gates.
4. **OTLP receiver port.** Default 4318 (works with SDK defaults but may clash with a local Collector) or a custom default. Also, whether protobuf support justifies a new dependency.
5. **Code snippets in tickets.** Default is never; opt-in per ticket is possible.
6. **GitHub or GitLab first** for private repositories (S1).

## 11. Review protocol

- Astra works on `astra/integrations-<slice>` branches, one slice per branch. Each ends with a handoff note, `ASTRA-INTEGRATIONS-<slice>-<date>.md`, listing what was verified and what wasn't.
- Claude reviews and writes `CLAUDE-INTEGRATIONS-CR-<slice>-<date>.md`, keeping verified defects (with the command or test used) separate from suggestions.
- **Review checklist:**
  - §2 rules
  - no token leakage (sentinel tests)
  - digest-bound writes
  - contract sync
  - fixture hygiene
  - test isolation
- A branch merges after Andrew accepts the review. Commits use the approved `abwalls` identity per AGENTS.md.

## Sources

- Sentry: [List an Organization's Issues](https://docs.sentry.io/api/events/list-an-organizations-issues/), [Pagination](https://docs.sentry.io/api/pagination/), [List an Organization Release's Commits](https://docs.sentry.io/api/releases/list-an-organization-releases-commits/)
- OpenTelemetry: [OTLP specification](https://opentelemetry.io/docs/specs/otlp/), [Code attributes registry](https://opentelemetry.io/docs/specs/semconv/registry/attributes/code/)
- Datadog: [Error Tracking API](https://docs.datadoghq.com/api/latest/error-tracking/), [Spans API](https://docs.datadoghq.com/api/latest/spans/), [Authentication](https://docs.datadoghq.com/api/latest/authentication/), [Datadog sites](https://docs.datadoghq.com/getting_started/site/)
- Linear: [GraphQL API](https://linear.app/developers/graphql)
- ClickUp: [Create Task](https://developer.clickup.com/reference/createtask)
- Jira Cloud: [REST v3 Issues](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/), [REST v3 intro (ADF)](https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/), [Basic auth](https://developer.atlassian.com/cloud/jira/platform/basic-auth-for-rest-apis/), [Create issue metadata deprecation](https://community.developer.atlassian.com/t/create-issue-meta-endpoint-deprecation/75413), [API token management](https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/), [One-year token expiry](https://community.atlassian.com/forums/Jira-articles/API-tokens-will-now-have-a-maximum-one-year-expiry/ba-p/2880029)
