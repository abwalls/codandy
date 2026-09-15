# Visual atlas: build plan

**Status:** active since 2026-09-15.
**Roles:** Claude implements; Astra 6 code-reviews each slice (Andrew's call, 2026-09-15).
**Origin:** Claude's proposal to Andrew, a private "Codandy Diagram Atlas" page. Every sketch in it was drawn from Codandy's own atlas: 170 files, 712 symbols, 2,178 relationships.

## Goal

Replace walls of text with diagrams that show structure, coupling and flow. None of them may
assert anything the atlas can't back up. Codandy's differentiator is saying what it doesn't
know, so every visual shows the basis of its evidence.

## Rules for every visual

1. **Draw only atlas relationships or observed telemetry.** No invented nodes, layers, services or edges.
2. **State the basis visibly:** *observed*, *inferred*, *source order* or *observed order*.
3. **Static data never implies runtime order.** No step numbers, timings or return arrows derived from `CALLS` or `ROUTES_TO`.
4. **Repository and telemetry text is untrusted.** Render it as React SVG/HTML text nodes only: never `dangerouslySetInnerHTML`, and never through Mermaid in the page.
5. **Keep logic out of components.** Derivations are pure functions in `lib/`, covered by contract tests.
6. **Use theme variables for all colour:** `--primary`, `--chart-4` (inferred), `--chart-5` (cycles, exceptions), `--foreground`, `--muted-foreground`, `--surface-4`, `--border`. Every theme must work.
7. **Keyboard and small screens.** Every interactive mark is focusable and responds to Enter/Space. State shows through `aria-pressed` or `role="status"`. Small screens get a readable fallback without the SVG.
8. **Budgets.** Say what is omitted ("40 of 212 groups"). Narrow the view by search, focus or expansion instead of shrinking the text.

## Library decisions (checked 2026-09-14)

| Need | Decision |
|---|---|
| Layered dependency layout | **In-house** (`lib/architecture-layout.ts`). A small deterministic layered layout for tens of groups: depth-first back edges, longest-path layering, virtual waypoints for long edges, barycenter crossing reduction. It adds no dependency and can be tested exactly. |
| When to switch to a library | Switch to `@xyflow/react` 12.11.6 plus `@dagrejs/dagre` 3.1.1 (both MIT) once we need node dragging, editable graphs, or layouts beyond about 60 groups. |
| Charts, treemap | `recharts` 3.8.0, already a dependency. |
| `elkjs` 0.12.0 | Not adopted: EPL-2.0 or GPL-3.0 licence. |
| Mermaid | Text export only, if ever. Never render repository labels through it in the page. |

## Milestones

| # | Visual | Where | Backed by | Done when |
|---|---|---|---|---|
| **V0** | Foundations | Architecture; analyzer | Existing atlas | Layout and matrix derivations are covered by contract tests. Folder expansion works in `architectureMap`. Tool caches (`__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`) are excluded from analysis and ZIP intake. |
| **V1** | Layered dependency graph | Architecture | `IMPORTS` joined to `RESOLVES_TO`; project `DEPENDS_ON` | Replaces the ring layout. Importers sit above their dependencies; cycles are drawn and listed; a folder can be expanded into its subfolders in place. Up to 40 groups, with the omitted count shown. |
| **V2** | Dependency matrix | Architecture | Same links as V1 | Rows import columns, ordered by layer: forward dependencies sit above the diagonal and cycle back-edges below it. Selecting a cell lists the evidence files. Up to 60 groups. |
| **V3** | Stack-trace sequence diagram | Errors & stacks | Normalized observation frames, exception chains, source bindings | One lifeline per file in frame order. Exception-chain links (`relation_to_next`). Async-boundary, external-frame and omitted-frame markers. In-app frames open their matched source candidate. Labelled *observed order*. |
| **V4** | Call sites in source order | Application flows | `route_flow` report steps plus `CALLS` evidence lines | Lifelines per function, grouped by file. Calls sorted by call-site line within each caller, capped at the existing 4 levels and 16 steps. Labelled *source order*, with no numbering. |
| **V5** | Codebase treemap and import hotspots | Overview, Codebase | `CONTAINS`, `line_count`, extensions, resolved import pairs | Treemap sized by declared symbol lines (toggle: symbols or files), coloured by language. Fan-in and fan-out bars open Dependency impact. |
| **V6** | Evidence strip, symbol sizes, dependency health | Overview, Codebase, Dependencies | Relationship `resolution`, `local_import`, `line_count`, dependency checks | Stacked evidence bar, size histogram, and ecosystem composition with check status. Unchecked dependencies stay visibly distinct. |
| **V7** | Open in Whiteboard | Architecture, Whiteboard | V1 layout, Excalidraw element skeleton (beta) | A reviewed conversion into editable board shapes. Drawn arrows never become atlas facts. Depends on Whiteboard W6. |

### V1 and V2 details

- **Layout algorithm:**
  - Depth-first search in group rank order marks back edges.
  - The remaining acyclic edges get longest-path layers.
  - Edges that span several layers pass through virtual waypoints.
  - Four barycenter sweeps reduce crossings, with ties keeping the previous order.
  - Tarjan's algorithm reports strongly connected groups as cycles.
- **Guaranteed properties (tested):**
  - Every forward edge goes to a lower layer.
  - Every back edge goes to a higher one.
  - The matrix order therefore places forward edges above the diagonal and back edges below it.
  - Output is identical for identical input.
- **Isolated groups** go in a separate row labelled as having no cross-group imports in view.
- **Expansion:** expanding folder `X` regroups files under `X/<subfolder>`. Files directly inside `X` stay grouped as `X`. Changing mode or depth collapses all expansions.

## Tests per milestone

- **V0–V2:**
  - Contract tests: layering, virtual waypoints, back edges and cycles, determinism, the diagonal property, and expansion.
  - A pytest test for tool-cache exclusion.
  - QA: Codandy's own atlas and a synthetic cycle, on desktop, on a small screen, and with keyboard focus.
- **V3:** a contract test that builds the sequence model from the normalized `sentry_python_chained.json` fixture, checking frame order, cause links, and that no redacted value appears.
- **V4:** a derivation test covering ordering by line, depth and branch limits, and the absence of step numbers.
- **V5–V6:** aggregation tests. Chart rendering snapshots aren't required.

## Review protocol for Astra

- Claude works on branch `claude/visual-atlas`, one commit per slice. Each slice gets a handoff note `CLAUDE-VISUALS-<date>.md` listing what was verified and what wasn't.
- Astra reviews the branch diff and writes `ASTRA-VISUALS-CR-<date>.md`, separating **verified defects** (with the command or test used) from **suggestions**.
- **Review checklist:**
  - rules 1–8 above
  - deterministic derivations
  - a large atlas (300 or more groups) keeps within the budgets
  - contrast in every theme
  - no new dependency without a version and licence note
  - tests isolated from personal storage
  - a `progress.md` checkpoint
- The branch merges to `main` after Andrew accepts Astra's review.

## Status

- **2026-09-15:** plan written. V0–V2 implemented by Claude on branch `claude/visual-atlas` and awaiting Astra's review; see `CLAUDE-VISUALS-2026-09-15.md`.
