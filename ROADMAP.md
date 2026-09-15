# Codandy roadmap

The debugging pivot replaces the old M0–M5 ordering. Detailed contracts and acceptance criteria live in [PLAN.md](PLAN.md); architectural boundaries live in [ARCHITECTURE.md](ARCHITECTURE.md). This is an ordered backlog, not a completion claim or calendar estimate.

| Gate | Outcome | Dependencies | Status |
|---|---|---|---|
| D0 | Research, current-code audit and debugging-first plan | Existing foundation | Complete: documentation only |
| D1a | Sanitized event/stack import and investigation contracts | None beyond foundation | Implemented; fixture validated |
| D1b | Read-only Sentry connection, issues and event retrieval | D1a; account/region/scopes | Event retrieval implemented; browsing and live validation pending |
| D1c | Frame/source binding and persistent investigation UI | D1a; snapshot identity | Local persistence and candidate matching implemented; independent revision verification pending |
| D1d | Live issue → source → reviewed AI brief | D1b + D1c | Brief export/local Q&A implemented; live end-to-end gate remains open |
| D2 | Evidence follow-ups, verification attachments and source-access improvements | D1 | Planned |
| D3 | Trace waterfall and one profile-format spike | D1 observation layer | Planned |
| D4 | Single-user whiteboard: draw → AI clarifying questions → agent plan.md and human ticket | Local Codex bridge; optional repository snapshot | **Next track** (Andrew, 2026-09-14). Plan drafted in docs/WHITEBOARD-PLAN.md; W0 spike not started. Evidence cards from the original D4 scope moved to W6. |
| V | Visual atlas: layered dependency graph, dependency matrix, stack and call-site sequence views, treemap and evidence charts | Existing atlas and observation data | Planned in docs/VISUALIZATION-PLAN.md; V0–V2 in progress (Claude implements, Astra reviews) |
| D5 | Read-only MCP, IDE handoff, later trusted DAP experiment | Stable investigation services | Later |
| D6 | Change verification, webhooks and team workflows | Evaluation data; hosting/auth where needed | Later |
| I | Integrations: Sentry completion, OpenTelemetry and Datadog runtime evidence; Linear, ClickUp and Jira Cloud tickets; GitHub private repos, CI evidence, IDE links | Local-only foundations (I0); provider accounts for live gates | Planned in docs/INTEGRATIONS-PLAN.md (2026-09-15); Astra implements, Claude reviews; decisions pending in its §10 |
| AD | Architecture diagrams: data-model ERDs, class/type and data-contract diagrams, static/observed/traced sequence diagrams, endpoint-to-data map, API contracts, deployment, messaging and frontend maps | V1/V2 merged; separate `structure-0.1` artifact (atlas 0.2 unchanged); INTEGRATIONS M2/M4 for traced sequences | Planned in docs/ARCHITECTURE-DIAGRAMS-PLAN.md (2026-09-15); implementer and decisions pending in its §11 |

## Work that remains useful

Keep the static analyzer, source viewer, dependency checks, report persistence, comparison tools, themes and local subscription AI. Move codebase reports into supporting navigation only when the investigation workspace works. No schema migration or dependency upgrades are necessary just to adopt this plan.

## Release gates

- D1 cannot be labeled integrated until an authorized live Sentry event is retrieved and viewed; synthetic fixtures and a mocked connection are not substitutes.
- Mapping quality is evaluated against revision-aware fixtures. Ambiguity and missing artifacts must be explicit.
- Sensitive fields are withheld before persistence/export/model submission, with adversarial fixture coverage and visible truncation.
- Stack inspection is available without a live debugger. Timing appears only when the input carries timing/profiling evidence.
- A whiteboard must persist and round-trip; its AI handoff must work as text plus references before image analysis is considered.
- Existing analysis/source/report functionality must remain usable. Re-run focused backend/contracts/type/build checks with implementation changes; perform keyboard, mobile and browser QA before v1.

## Unresolved choices

Sentry cloud versus self-hosted target, organization region, an authorized test project and sanitized representative events; whether first adopters require private source immediately; the first live trace/profile endpoint; and whether whiteboard exports need image input inside the current local AI bridge. Default to Sentry Cloud plus offline fixtures, local persistence and text-based AI handoffs until confirmed.

## Scope explicitly deferred

Automatic production log collection, own telemetry infrastructure, full IDE editing, native replay recording, autonomous fixes or Sentry writes, test execution inside static ingestion, arbitrary webhook receiver exposure, numerical change-risk scores without calibration, cross-repository federation and realtime collaborative boards.

The previous delivery plan/status report remain in docs/archive/. Their dates, counts, defects and deferrals are historical; they must not override this roadmap or current progress.md checkpoints.
