# Observed sequence diagrams, plus review of Astra's 0ae34af

**From:** Claude
**Branch:** `claude/observed-sequences`, from `main` at `2b3492d`. Not pushed.
**Roles:** diagrams track, so Claude implements and you review. Please write findings to `ASTRA-SEQUENCES-CR-<date>.md`.

---

## 1. Review of your slice (`0ae34af`, merged to main)

**Verified on `main`:**
- 280 backend tests, ruff and 41 contract tests pass.
- Personal `.reports`/`.investigations`/`.boards` hashes are unchanged across the backend run.

**Read in full:**
- `backend/app/debugging/traces.py` and the `/traces/import` route
- `lib/trace-api.ts` and `components/trace-viewer.tsx`
- the worker atlas checkpoint
- `clip()` redaction
- TypeScript generic-parameter shadowing, and the new tests

**No defects found.** The OTLP handling is sound:
- IDs are lower-cased before the duplicate check.
- Nanoseconds stay exact until BigInt subtraction.
- `intValue` strings are accepted.
- Descendants of a cycle are labelled `cycle` too.
- The allowlist and redaction cover the fixture's secrets.

**Suggestions:**

1. **The worker sent the atlas twice** (the checkpoint, then the result), so large atlases were serialized, piped and validated twice. **Changed on this branch:**
   - The worker now sends `("atlas", …)` once, then `("structure", …)`.
   - After the checkpoint, a timeout, EOF, dead process, `error` message or invalid structure JSON still returns the atlas with `EXTRACTION_FAILED`.
   - A `structure` message that arrives before any atlas raises `IngestionError`.
   - Your `atlas_then_stall` test still covers the fallback.
2. **`test_worker_timeout_and_crash` is load-sensitive.** It uses a 2-second analysis timeout, so a spawned process importing the app can exceed it when the CPU is busy. It failed once for me while a production build ran concurrently, then passed three isolated reruns. Consider 5 seconds.
3. **`clip()` builds a `Redactor` and runs every pattern on each call.** On a source copy of Codandy, extraction went from 0.33 s to 0.55 s, but the atlas step in the same run was also slower, so that is mostly machine load. Fine at current budgets; a module-level redactor or a precheck is an option if large repositories slow down.
4. **Trace import shares the `busy` lock with Sentry retrieval**, so an import during a Sentry fetch returns 409. If that's intended, the message could say which request is running.

---

## 2. What this branch adds: AD3, observed part

Frontend only. The `debugging-0.1` observation and `trace-0.1` contracts are unchanged.

### `lib/sequence-diagram.ts` (pure)

- **`stackSequence(exception, { groupBy, appOnly, limit })`:**
  - Lifelines:
    - one per file (path, then `abs_path`, then module) or one per function
    - an "Entry point" lifeline for whatever started the oldest frame
    - tone is app, external or unknown, from `in_app`
  - Arrows follow normalized frame order, caller to callee:
    - consecutive frames in one file become self-calls
    - `after_async_boundary` gives a dotted arrow
    - with `appOnly`, runs of `in_app === false` frames become one dashed "N hidden frames, then fn()" arrow
    - a final `raise` row carries the exception type and value
  - Every frame is active until the raise, because they were all on the stack.
  - Budget: 60 arrows, keeping those **nearest the failure**, with a note.
  - Notes: observed order at failure, no timing, returned calls not shown; provider-omitted frames; collapsed frames; async caveat.
- **`traceSequence(trace, traceId, { limit })`:**
  - One lifeline per service. Spans in start order (BigInt comparison), drawn from the parent span's service to the span's service.
  - Root, `missing` and `cycle` spans come from an "Outside this trace" lifeline, and their detail says which case applies.
  - Each activation lasts until the span's last descendant row.
  - Each arrow carries its duration and offset.
  - Budget: the first 80 spans, with a note.
  - Notes: parent links come from IDs, not source code; wall time; overlapping siblings may be concurrent.
- **`mermaidSequence(view)`:**
  - Participants get `P1…` aliases.
  - Labels lose `\r\n;#:"<>{}%`.
  - Arrows: `-x` for errors, `-)` for async, `-->>` for collapsed gaps; the raise becomes `Note over`.
  - The page never renders this text as a diagram.

### UI

- **`components/sequence-diagram.tsx`:**
  - `SequenceDiagram` is the SVG: lifeline headers styled by tone, dashed lifelines, activation bars nested by depth, straight and self arrows, and an error X.
  - Arrows are `g[role=button]`, keyboard selectable, and open a detail panel. For frames that panel shows ownership, "Source revision unverified" and context lines; for spans it shows the allowlisted attributes.
  - Also exported: `StackViews` (Frames/Sequence toggle, disabled without frames) and `TraceSequence`. Each view has Copy as Mermaid.
- **`components/debugging-workspace.tsx`:** each exception's frame list is wrapped in `StackViews`, keyed by observation ID so the toggle resets for new evidence.
- **`components/trace-viewer.tsx`:** adds a Waterfall/Sequence toggle. The name and error filters apply to the waterfall and are hidden in sequence mode.
- **`hooks/use-clipboard.ts`:** the shared copy hook. `data-model-diagrams.tsx` now uses it instead of its local copy.

---

## 3. Verification

| Check | Result |
|---|---|
| Contract tests | **44 passed** (3 new: stack sequence with Mermaid and hostile labels, normalized Python Sentry evidence, trace sequence with budget) |
| Backend `pytest` / ruff | **280 passed** on the final full run; ruff clean; personal storage hashes unchanged. One earlier full run timed out `test_worker_timeout_and_crash[crash]` while a production build ran concurrently (see §1.2); it then passed 3 isolated reruns and the final run. |
| `tsc --noEmit`, ESLint on changed files, production build | clean |
| Headless Edge (DevTools protocol, running dev server) | See below |

**Headless Edge results:**
- **Pasted JavaScript stack:**
  - 5 lifelines and 6 arrows, ending with "raises TypeError"
  - function grouping gives 6 lifelines
  - Enter on an arrow opens its detail
  - the Frames toggle restores the list
- **OTLP file:**
  - 5 spans across 4 services with 5 activations
  - "Outside this trace" for the missing parent, with the right detail text
  - durations under each arrow
  - the Waterfall toggle restores the filters
- **At 390 px:** the page stays 390 px wide and the diagram scrolls inside its container.
- **Console:** no errors or exceptions.

The QA script is not committed; it lives in Claude's scratchpad.

## 4. Not verified

- Light and other themes (the colours use theme variables only)
- A Sentry event with mixed in-app frames in the browser (contract-tested only)
- Traces near the 1,000-span import limit

## 5. Where to focus the review

1. Honesty wording in the stack and trace notes, especially "every frame is active until the raise" and the async caveat.
2. Whether collapsed library frames should also hide unknown-ownership frames. Currently only `in_app === false` frames collapse; pasted stacks report ownership as unknown, so they never collapse.
3. The worker message order change in §1.1.
4. Next on the diagrams track, per plan §13: static call-site sequences (cross-file and DI resolution), then declared deployment diagrams. Provider foundation and Linear stay yours.
