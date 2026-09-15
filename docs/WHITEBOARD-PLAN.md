# Whiteboard: draw → clarify → plan

**Status:** draft plan for review. No code has been written.
**Owner decisions:** Andrew, 2026-09-14. **Written by:** Claude (Opus 5), for Astra to implement and Andrew to approve.
**Replaces:** the scope of PLAN.md gate D4. The investigation evidence cards from the original D4 remain a later step (see W6).

---

## 1. Product promise

A developer draws a system on a whiteboard, for example a new cloud architecture. Codandy's
AI reads the drawing, explains how it understood it, and asks clarifying questions. It then
produces two outputs:

1. **`plan.md`**: a complete implementation plan that another coding agent can execute.
2. **A ticket**: a plain-language report sheet a human developer can read and use to
   supervise the work to completion.

Andrew sees this as Codandy's main differentiator.

**v1 is single-user and plan-only.** Later stages add live collaboration, code suggestions
and, eventually, implementations. Implementations will need the separately designed,
explicitly trusted execution boundary that PLAN.md D5 describes. Nothing in this plan runs
code.

**What v1 must never do:**

- Present an AI guess as something the user drew.
- Turn a drawn arrow into a code-graph relationship.
- Send a board to the AI without an explicit, reviewed action.
- Overwrite the repository's own `PLAN.md`.

## 2. Decisions already made

| Question | Decision |
|---|---|
| Sequencing | **Whiteboard now.** The Sentry live test (D1 gate) runs whenever Andrew's account is ready. |
| Repository link | **Optional.** A board can be a blank-slate design, or linked to a retained repository report so the plan cites real files, routes and dependencies. |
| AI provider | **The local ChatGPT/Codex subscription connection** (the existing `CodexBridge`). No API keys and no per-request billing. |
| Outputs | **Markdown files** (`plan.md` and `ticket.md`), a **printable in-app report page**, and a **GitHub issue draft**. The draft is copy/download only in v1; creating an issue on GitHub needs a later connector and explicit approval each time. |
| Canvas library | **Excalidraw**, as the existing strategy review recommended. tldraw needs a production license key. |

## 3. Verified facts this plan relies on

All checked on 2026-09-14.

- **The Excalidraw package** is `@excalidraw/excalidraw` **0.18.1**, **MIT**-licensed. Its supported React versions are `^17.0.2 || ^18.2.0 || ^19.0.0`, and Codandy runs React 19.2. ([npm registry](https://registry.npmjs.org/@excalidraw/excalidraw/latest))
- **The editor can't be server-rendered.** It must load with `dynamic(..., { ssr: false })` and needs `import "@excalidraw/excalidraw/index.css"`. Its container must have an explicit size. ([integration docs](https://docs.excalidraw.com/docs/@excalidraw/excalidraw/integration)) vinext's `next/dynamic` shim supports `ssr: false` (see `node_modules/vinext/dist/shims/dynamic.js`).
- **Fonts come from the `esm.run` CDN by default.** Self-hosting them means copying `dist/prod/fonts` and setting `window.EXCALIDRAW_ASSET_PATH`. ([installation docs](https://docs.excalidraw.com/docs/@excalidraw/excalidraw/installation)) Codandy should self-host, so drawing works offline and makes no third-party requests.
- **Scene utilities:**
  - `serializeAsJSON`, plus `restore` and `restoreElements` (options `refreshDimensions`, `repairBindings`, `normalizeIndices`), for saving and loading. ([restore](https://docs.excalidraw.com/docs/@excalidraw/excalidraw/api/utils/restore))
  - `exportToBlob` and `exportToSvg`. Scene data is embedded in the image only when `exportEmbedScene` is set. ([export](https://docs.excalidraw.com/docs/@excalidraw/excalidraw/api/utils/export))
- **`convertToExcalidrawElements`** turns simple "skeleton" objects into real elements: shapes with `label.text`, and arrows whose `start`/`end` bind to element IDs. **The docs mark this API as beta.** ([skeleton API](https://docs.excalidraw.com/docs/@excalidraw/excalidraw/api/excalidraw-element-skeleton))
- **Component props:** `onChange(elements, appState, files)`, `initialData`, `excalidrawAPI`, `UIOptions`, `validateEmbeddable`, `renderEmbeddable`, `onLinkOpen` and `viewModeEnabled`. ([props](https://docs.excalidraw.com/docs/@excalidraw/excalidraw/api/props))
- **Mermaid import:** `@excalidraw/mermaid-to-excalidraw` **2.2.2**, MIT-licensed. It depends on `mermaid ^11`, which is heavy, so it would be an optional, lazily loaded feature.
- **Codex app-server input:** `turn/start` accepts `text`, `image` (`url`) and `localImage` (`path`) items, and `outputSchema` applies per turn. The docs don't state image limits or which models accept images. ([app-server docs](https://learn.chatgpt.com/docs/app-server))
- **Today's `CodexBridge`** (`backend/app/codex_bridge.py`):
  - sends text input only, with one fixed `{answer, citations}` schema
  - disables all tools, including `view_image`
  - allows 150 s per turn
  - closes the process after each answer
  - existing callers cap prompts at about 64–68 KB

## 4. User flow (v1)

1. **Boards.** A `/whiteboard` page lists local boards: create, rename, delete, import, export.
2. **Draw.** Use Excalidraw's shapes, arrows, text, sticky notes and frames. Boards autosave, and a *saved / unsaved* status is always visible.
3. **Link a repository (optional).** Choose a retained report, exactly as saved investigations do today. Show when that snapshot expires.
4. **Interpret.** Codandy builds a text **board digest** (section 6) and shows the exact packet that will be sent: components, arrows, labels, omissions. The user ticks *reviewed*, then asks for an interpretation.
5. **Review the interpretation.** A side panel lists the components, connections, groups, assumptions and **clarifying questions** the AI found. Each item highlights its source elements on the canvas. The user can correct an item ("that's a queue, not a database") or mark it wrong.
6. **Clarify.** The user answers the questions, either by picking an offered option or writing free text. Answers are stored as **user answers** (a distinct basis from drawn shapes). Re-interpretation runs on the updated digest plus answers, with at most **5 rounds** per board revision.
7. **Generate the plan.** From the final interpretation, the user asks for a plan. The AI returns structured plan JSON, which is validated and then rendered **deterministically** into the outputs.
8. **Use the outputs.** Download `plan.md` and `ticket.md`, open the printable report page, or copy the GitHub issue draft. Each output records the board revision it came from. If the board changes afterwards, the plan is marked **stale**; it's never silently updated.

## 5. Architecture

### Frontend

- **Page.** `app/whiteboard/page.tsx` renders `components/whiteboard/whiteboard-workspace.tsx`, mirroring `/debugging`. Board selection lives in component state, which avoids depending on vinext dynamic-segment behavior for v1. Add a navigation entry alongside *Errors & stacks*.
- **Canvas.** `components/whiteboard/board-canvas.tsx` is a `"use client"` component:
  - load Excalidraw with `dynamic(() => import("@excalidraw/excalidraw").then(m => m.Excalidraw), { ssr: false })`, show a loading skeleton, and give the container an explicit height
  - map the Codandy theme to Excalidraw's `theme`
  - `validateEmbeddable={false}`, so no iframe embeds
  - `onLinkOpen` → `preventDefault()`; offer only `http(s)` links, behind an explicit *Open link* confirmation
  - hide or disable the image tool for v1 via `UIOptions` (**confirm the exact option in W0**)
  - autosave `onChange` debounced to about 1.5 s, sending the board revision for optimistic concurrency
- **Fonts.** A build step copies `node_modules/@excalidraw/excalidraw/dist/prod/fonts` into `public/excalidraw-assets/`, and the page sets `window.EXCALIDRAW_ASSET_PATH` before Excalidraw loads. **W0 must confirm the exact path layout and that no CDN requests remain.**
- **API client.** `lib/board-api.ts` holds zod schemas mirroring the Python contracts, and calls `/api/boards/*` with the `X-Codandy-Local` header, as `lib/debugging-api.ts` does.
- **Interpretation panel.** Selecting an item highlights its `element_ids` via `excalidrawAPI.updateScene` selection and `scrollToContent`. **W2 verifies the exact API.**
- **Security.** All AI and board text renders as React text children, never HTML. Mermaid and SVG output from the AI is never injected into the page.

### Backend

- **Modules.** `backend/app/boards/` contains `models.py` (contracts), `store.py` (local store), `digest.py` (scene → text digest), `prompts.py` (stage instructions and schemas) and `render.py` (plan JSON → Markdown).
- **Router.** `backend/app/routers/boards.py` exposes `/api/boards`, guarded by `local_only` and the global `AllowedHosts` middleware. The hosted proxy doesn't allowlist `/api/boards`, so boards stay local.
- **Store.** Same pattern as `app/debugging/cases.py`:
  - atomic writes, UUID file names, no symlinks
  - bounded sizes, recovery on restart, explicit deletion
  - storage root `CODANDY_BOARD_ROOT`, default `.boards`, added to `.env.example`, `.gitignore` and the test isolation fixture
- **`CodexBridge.complete(prompt, schema, instructions, *, images=(), timeout=150)`** is a general structured-completion method. `answer()` becomes a thin wrapper, so existing callers don't change. Tools stay disabled, threads stay ephemeral, and the one-request-at-a-time lock still applies. Image items are sent only if W0 proves they work.

### Contracts (Python and TypeScript kept in sync, versioned)

| Contract | Contents |
|---|---|
| `board-0.1` | `id`, `title`, `created_at`/`updated_at`, `revision` (integer, increments on save), `scene` (Excalidraw elements plus an **allowlisted** subset of `appState`), `files` (empty in v1), `snapshot_id` (optional), `snapshot_repository`, `rounds`, `plans` |
| `board-digest-0.1` | Deterministic text model of the board (section 6), plus `omissions` and a SHA-256 `digest_id` |
| `interpretation-0.1` | `summary`, `components[]`, `connections[]`, `groups[]`, `assumptions[]`, `questions[]`, `unreadable_element_ids[]`; every item carries `element_ids` and a `basis` |
| `round-0.1` | The digest ID sent, interpretation, user corrections, answers, model, effort, timestamps |
| `plan-0.1` | Structured plan (section 7), plus `board_revision`, `round_id`, `snapshot_id`, `model`, `generated_at` |

**Bounds** (tunable engineering limits, not provider limits):

| Limit | Value |
|---|---|
| Saved board size | 4 MiB |
| Elements per board | 5,000 |
| Characters per text element | 2,000 |
| Title | 200 characters |
| Stored boards | 200 |
| Clarification rounds per revision | 5 |
| Plan versions kept per board | 20 |
| Digest sent to the AI | ≤ 40 KB, larger boards are truncated with counts |
| Full prompt | ≤ 64 KB |

## 6. Board digest: how the AI "reads" the drawing

**The digest is text-first by design.** It works without any vision model, and every AI
claim can be checked against element IDs. `digest.py` runs on the server, over the saved
scene, and never on anything the client builds.

- **Elements.** Each non-deleted element becomes one record: `id`, `type`, `text`
  (standalone text, or the container's bound label), rounded bounding box, `groupIds`,
  `frameId`, and whether it's a sticky note.
- **Arrows and lines.** `start_id`/`end_id` come from Excalidraw bindings, plus the arrow's
  label and its direction as drawn. Unbound arrow ends are reported as `dangling`, never
  guessed.
- **Containment.** Computed geometrically: a shape wholly inside a larger rectangle or frame
  is listed as `inside` it, marked `basis: geometric` so it's visibly a layout inference.
- **Freehand strokes and unlabeled shapes** are counted and listed as `unlabeled`. Without
  vision they can't be interpreted, and the UI says so ("3 unlabeled drawings were not
  interpreted; add labels").
- **Sanitising.** Text goes through the existing `Redactor` (secrets and tokens) and control
  characters are stripped. Records sort deterministically (top-to-bottom, left-to-right,
  then ID), so the same board produces the same `digest_id`.
- **Budget.** Keep text and labels first; drop coordinates for the largest boards; always
  report omitted counts.
- **Prompt framing.** The digest is wrapped as `BEGIN UNTRUSTED BOARD DATA … END`. Board text
  is data, never instructions, and the model has no tools.

**Image input is optional, gated by W0.** If `localImage` works with the subscription's
models:

- Export a bounded PNG (`exportToBlob`, max 2048 px, no embedded scene) to a per-request
  temporary file under `CODANDY_CODEX_HOME/context`.
- Send it alongside the text digest, and delete it afterwards.
- The image may only help interpret `unlabeled` elements. Anything taken from the image is
  marked `basis: visual_inference`, and validation of element IDs still applies.

## 7. AI stages and schemas

Every stage follows the existing reviewed-brief pattern:

- The server builds the packet, and the client shows it with a `review_digest`.
- The request must present the same digest (409 if the board changed).
- The response must match the schema, and every referenced `element_id`, question ID or
  atlas node ID must exist in the packet. Otherwise it's a 502 with "retry".

**1. Interpret** returns `interpretation-0.1`:

- **Components.** `id`, `name`, `kind` (`client | service | function | datastore | cache | queue | stream | storage | gateway | network | identity | external | other`), `responsibility`, `element_ids`, and `basis` (`drawn_label | geometric | inferred`).
- **Connections.** `from`/`to` component IDs, `label`, a `protocol` hint or `null`, `element_ids`, and `basis` (`drawn_arrow | inferred`).
- **Assumptions.** Every inference that isn't visible on the board must be listed as an assumption.
- **Questions.** At most 8 per round, each with `why_it_matters`, `element_ids` and optional `options[]`. Priority goes to ambiguities that change the plan: scale, data ownership, auth, sync vs async, deployment target, failure handling.

**2. Clarify** re-runs Interpret over the digest plus the stored answers and corrections.
Answered questions must not be asked again. Corrections outrank drawn labels.

**3. Plan** returns `plan-0.1`:

- `title`, `objective`, `context`, `in_scope[]`, `out_of_scope[]`
- `architecture`: components and connections, carried over with their bases
- `decisions[]`: `statement`, `basis` (`drawn | answered | assumed | repository_evidence`), `rationale`
- `milestones[]` containing `tasks[]`: `id`, `title`, `description`, `depends_on[]`, `acceptance_criteria[]`, `verification[]`, `effort` (`small | medium | large`, labelled as an AI estimate), `areas[]`
- `risks[]` (`description`, `mitigation`), `open_questions[]`, `assumptions[]`

**`areas[]` depends on the repository link:**

- **With a link:** each area is either an existing indexed path or atlas node ID (validated against the snapshot) or `{"proposed_path": …}`, clearly marked new.
- **Without a link:** proposed paths only.

The model never states that a file exists unless the snapshot contains it.

**When a repository is linked**, a bounded context goes into the Interpret and Plan
packets, built like `grounded_prompt` in `routers/assistant.py`: repository metadata,
projects, technologies, top-level areas, routes, dependencies and Architecture-map groups.
It's capped (for example 24 KB) and cited by node ID. An expired snapshot blocks grounded
generation with a clear message; blank-slate generation still works.

## 8. Outputs

All outputs are rendered by `render.py` from the **validated plan JSON**. The model never
writes raw Markdown straight into a file.

- **`plan.md`** (for coding agents):
  1. Objective, context, and provenance (board, revision, round, repository and commit or archive, model, time)
  2. Constraints and non-goals
  3. Architecture tables for components and connections, with bases
  4. Decisions with bases, then assumptions
  5. Milestones: ordered tasks with IDs, dependencies, acceptance criteria and verification
  6. Risks, then open questions
  7. A standing instruction for the executing agent: *"Items marked assumed or proposed are unverified; confirm them before implementing."*

  It downloads as `plan.md` and is never written into any repository automatically.
- **`ticket.md`** (for humans): title, plain-language summary, why, scope, an
  acceptance-criteria checklist, a milestone checklist, decisions needing sign-off, and a
  *supervisor checklist* (what to verify at each milestone). Efforts are shown as AI
  estimates; there are no dates or invented hour counts.
- **Printable report page:** an in-app view of the ticket, with a board image (`exportToSvg`
  rendered as an image, not inline SVG markup) and `@media print` styles. *Print / Save as
  PDF* uses the browser's print dialog.
- **GitHub issue draft:** title, body (the ticket, trimmed under GitHub's body size limit
  with a note) and suggested labels, with copy buttons. **v1 creates nothing on GitHub** and
  never puts plan content in a URL. A later connector must follow AGENTS.md's `abwalls`
  identity rules and require explicit approval for each issue.

## 9. Security and honesty rules

- Board text, labels, answers and linked-repository content are **untrusted input**: they are prompt data only, and the model runs with tools disabled.
- **Nothing is sent to the AI automatically.** Each stage is one explicit, reviewed request.
- **A drawing is intent, not fact.** Nothing on a board creates atlas relationships. The plan distinguishes drawn, answered, assumed and repository-evidence items.
- **Imported boards pass through `restore()` in the browser and strict server validation:**
  - unknown element types rejected
  - sizes and counts bounded
  - `link` values limited to `http(s)`
  - embeddables removed
  - image `files` rejected in v1
  - `appState` allowlisted
- **Nothing on the board reaches the network.** No remote images, iframe embeds or automatic link fetches, and the fonts are self-hosted.
- **Local only.** All board APIs pass `local_only` plus the host guard. Tests use the isolated storage fixture, including `board_root`.
- **Boards can be truly deleted.** Deleting a board removes its plans, rounds and any temporary image files.

## 10. Milestones

Each milestone is a separate slice with its own checks (pytest, ruff, contracts, `tsc`,
ESLint, build) and a `progress.md` checkpoint.

| # | Slice | Done when |
|---|---|---|
| **W0** | **Spike** | Excalidraw 0.18.1 renders in vinext (dynamic `ssr: false`, CSS, React 19, both themes). Fonts are self-hosted with **zero CDN requests** in the network log. The change in bundle size and build time is recorded. The image-tool `UIOptions` switch is confirmed. A `localImage` probe runs against each subscription model: accepted or not, latency, and a note on answer quality. The outcome is recorded in this document. |
| **W1** | **Boards** | Create, rename, delete, list, autosave with revision conflicts (409), reload survives a backend restart, JSON export/import round-trips losslessly, and PNG/SVG export works. Tests cover the store (atomic writes, limits, restart, delete) and import validation (bad types, oversized text, links, embeddables, files). The Python and TypeScript contracts are checked against each other. |
| **W2** | **Digest + Interpret** | The digest handles labels, bindings, dangling arrows, containment, unlabeled strokes, redaction, budgets and determinism. `CodexBridge.complete` exists and its tests pass. The Interpret endpoint enforces the review digest and element-ID validation. The panel highlights elements on the canvas. The fixture boards below produce valid interpretations. |
| **W3** | **Clarify + Plan** | Answers and corrections persist. The round cap and "no repeated answered questions" are both enforced. Plan JSON is validated, and plan versions are tied to board revisions, with stale-plan detection. |
| **W4** | **Outputs** | `plan.md` and `ticket.md` renderers are covered by golden-file tests. The printable page is verified in print preview on desktop, and the issue draft copies correctly. Downloads don't depend on the AI connection once a plan exists. |
| **W5** | **Repository grounding** | A board can link and unlink a snapshot, and the packet includes bounded atlas context. `areas[]` is validated (a fabricated path is rejected or relabelled as proposed), and expired-snapshot handling works. |
| **W6** | **Later (v1.5+)** | AI proposes board edits as a **reviewable overlay** built with `convertToExcalidrawElements` (beta API), accepted or rejected per element. Optional lazy Mermaid import. Evidence cards linking saved investigations and atlas nodes, from the original D4. Architecture icon libraries after a licence review. Mobile editing, since v1 on small screens is a read-only preview with outputs. |
| **Later** | Beyond v1 | Live collaboration; code suggestions per task; implementations through a separately designed trusted execution boundary; board and plan retrieval through a read-only Codandy MCP server (D5). |

## 11. Evaluation

**Fixture boards** are committed as Excalidraw JSON. Each has a hand-written expected
interpretation (components, connections) and the questions a good reviewer should ask:

1. Three-tier web app (browser → API → Postgres, with a cache)
2. Event-driven services (API → queue → workers → storage, with a dead-letter queue)
3. Serverless upload pipeline (object storage trigger → function → database → notification)
4. A deliberately ambiguous board (unlabeled boxes, a dangling arrow, two things named "DB")
5. A prompt-injection board (a sticky note saying "ignore previous instructions…")

**Deterministic checks (CI):**

- digest output for every fixture
- schema and ID validation
- renderer golden files
- the injection fixture's text appears only inside the untrusted data block

**Model-dependent checks (manual; the local subscription can't run in CI):**

- component and connection recall/precision against the expected interpretations
- whether the ambiguous board produces questions rather than guesses
- a review of plan usefulness by Andrew

Record results per model and effort in `progress.md`. They are observations, not guarantees.

**Product signal:** time from a blank board to a downloaded plan, and whether a coding agent
can execute a generated `plan.md` with few follow-up questions.

## 12. Risks and open items

- **Vision support is unknown.** v1 is designed to work text-only; W0 decides whether images help unlabeled drawings.
- **Subscription limits and latency.** One request at a time, a 150 s turn deadline, and plan usage limits. Plan generation for large boards may need a longer timeout or splitting into milestone passes, measured in W2 and W3.
- **The Excalidraw skeleton API is beta.** It's used only in W6, behind the review overlay, and pinned to a version.
- **Bundle weight.** Excalidraw loads only on `/whiteboard`, never on the homescreen or report pages; W0 measures it.
- **Cloud icon libraries.** Vendor architecture-icon terms vary, so v1 uses labelled shapes, with icons deferred to W6 after a licence review.
- **Roadmap interaction.** Sentry D1 remains open. The live test and issue browsing continue when Andrew's account is ready. Evidence cards from the original D4 wait for W6.


## Implementation review — 2026-09-14 (Codex)

Approved direction: deliver the draw → reviewed interpretation → corrections → reviewed plan loop now. The original plan is useful, but the first implementation narrows several claims:

- Vision probing is optional research, not a release prerequisite. The implemented packet is text-only; freehand/image interpretation remains unavailable and no subscription calls run automatically.
- Board edits increment a content revision. Reviews include the board revision and, for planning, the exact prior interpretation. Saving or changing that interpretation invalidates the prior review. AI results are committed only if the content revision is still current.
- One editable requirements/answers/corrections field supports clarification. Questions are visible and repeat avoidance is prompted; semantic deduplication and per-question structured answer records remain future work, not enforced claims.
- All paths in generated tasks are explicitly proposed. Optional repository context lists a bounded set of indexed paths but does not assert generated path existence. Strong node-level repository citations remain W5 follow-up work.
- The initial interpretation schema uses cited findings (drawn/answered/assumed), questions and assumptions. Detailed component/connection taxonomies and geometric containment inference remain later refinements.
- Imports reject links, images, embeds and custom data; only element data is retained. Arbitrary Excalidraw appState is excluded. JSON round trips preserve accepted element content, title and notes, not editor UI state.
- Plans and tickets are deterministic Markdown rendered from validated JSON. Printable text and issue-draft copy are included; a board image in the printable report is still pending.
- The first canvas supports desktop drawing and responsive layout. Excalidraw is lazy-loaded, pinned at 0.18.1, with self-hosted fonts. Validate no external requests in browser QA.
- Store bounds: 200 boards, 4 MiB per saved board including artifacts, 5,000 elements, 2,000 characters per text element, 20 combined saved AI artifacts, five requests per stage per revision. Tests must isolate board_root as well as reports and cases.

Implementation checks and remaining work are recorded in progress.md. Do not mark W0–W5 wholly complete based on this first functional loop.
