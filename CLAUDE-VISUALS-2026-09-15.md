# Visual atlas V0–V2: handoff for Astra's review

**From:** Claude (Opus 5)
**Date:** 2026-09-15
**Branch:** `claude/visual-atlas`
**Plan:** [docs/VISUALIZATION-PLAN.md](docs/VISUALIZATION-PLAN.md)
**Roles for this track** (Andrew's decision): Claude implements, Astra reviews. Please write findings to `ASTRA-VISUALS-CR-<date>.md`, keeping verified defects (with the command or test used) separate from suggestions.

**History note:** before starting, I committed your uncommitted Whiteboard work on `main` as `460a9d3`, at Andrew's request. It has its own commit and isn't mixed into this branch's diff.

---

## What changed

### V0: foundations

- **`backend/app/analyzer.py`:** `EXCLUDED_DIRS` now also skips `__pycache__`, `.pytest_cache`, `.mypy_cache` and `.ruff_cache`. ZIP intake picks these up automatically, since it imports the same set. Test: `test_python_and_tool_caches_are_not_indexed`.
- **`lib/architecture-layout.ts` (new):** pure, deterministic functions.
  - `layeredLayout(groups, links)`:
    1. A depth-first search in group-rank order marks **back edges**.
    2. Longest-path **layering** runs over the remaining acyclic edges. Importers are placed above their dependencies.
    3. Edges that span several layers pass through **virtual waypoints**.
    4. Four **barycenter sweeps** reduce crossings; ties keep the previous order.
    5. **Tarjan's algorithm** reports groups that form a cycle.
    6. Groups with no cross-group imports go in a separate **isolated row**.
    7. Back edges are drawn as arcs to the right, and the canvas widens to make room.
  - `edgePath` and `labelPoint` compute the SVG geometry.
  - `dependencyMatrix(groups, links)` orders rows and columns by layer, so forward dependencies always land **above** the diagonal and back edges **below** it.
  - **Why the diagonal rule holds:** a back edge's target is an ancestor on the depth-first tree path, and every tree edge is a forward edge that goes down a layer, so the target always sits in a higher layer.
- **`lib/architecture-map.ts`:** a new optional `expanded` set. An expanded folder splits into its subfolders; files directly inside it stay in that folder's group. Existing callers are unchanged.

### V1 and V2: Architecture tab

- **`components/architecture-diagrams.tsx` (new):**
  - **`LayeredDiagram`:** edge width follows import count. Inferred edges are amber and dashed. The edge that closes a cycle is rose and dotted. Groups are SVG `role="button"` elements, keyboard-operable, with focus dimming unrelated groups.
  - **`DependencyMatrixView`:** cell intensity follows the log of the import count. Cells above the diagonal use `--primary` and cells below use `--chart-5`. Every cell is a focusable button with a full spoken description.
- **`components/architecture-map.tsx` (rewritten around the new renderers):**
  - **The ring layout is removed.** It was capped at 10 groups and hid dependency direction.
  - New **Layered / Matrix** toggle.
  - Rendering budgets: 40 groups (layered), 60 (matrix), 12 (mobile).
  - **Split into subfolders** and **Collapse all folders** in the side panel.
  - A **cycle notice** (`role="status"`) listing the groups in each cycle.
  - A **matrix cell evidence panel** listing the files behind a selected cell.
  - Kept unchanged: the mobile card fallback, search, zoom, Ask scope, side panels and the legend's unresolved/external counts.
- **Tests:** four contract tests in `tests/analysis-api.test.mjs` cover:
  - layering and determinism
  - cycles as back edges
  - the matrix diagonal property
  - folder expansion
- **Docs:** `docs/VISUALIZATION-PLAN.md`, a `ROADMAP.md` row, and a `progress.md` checkpoint.

No new dependencies. React Flow and dagre are deferred until graphs need dragging or editing, or grow past about 60 groups; see the plan's library table.

---

## Verification

| Check | Result |
|---|---|
| `pytest` (full backend) | **256 passed** |
| `ruff check .` | clean |
| `pnpm test:contracts` | **34 passed** (4 new) |
| `tsc --noEmit` | clean |
| ESLint on the four changed frontend files | clean |
| Production build | succeeds |
| Personal storage SHA-256 (`.reports`, `.investigations`, `.boards`) before and after pytest | unchanged |

### On Codandy's own atlas

Using `lib/`, `components/`, `app/`, `hooks/` and `backend/app/` with the real configs:

| View | Layers | Isolated row | Cycles |
|---|---|---|---|
| Depth 1 | `app` → `components` → `lib`, `hooks` | `backend`, repository root | none |
| Depth 2 | `app`, `app/debugging` → `components` → `components/ui` → `hooks`, `lib` | shown separately | none |
| Depth 1 with `components` split | `components/ui` becomes its own layer | — | none |

### Timing (synthetic graphs)

| Size | Layout | Matrix |
|---|---|---|
| 40 groups, 135 links | 4 ms | 4 ms |
| 60 groups, 303 links | 16 ms | 15 ms |
| 300 groups (never rendered, because of the budgets) | about 0.7 s | about 0.7 s |

### Browser, local dev server with the saved Codandy atlas, checked through the DOM

- **Layered:** 6 groups, 3 edges.
- **Focus:** focusing `components` sets `aria-pressed="true"` and offers the split action.
- **Split:** 7 groups and 5 edges, with collapse offered.
- **Matrix:** 7 groups and 5 focusable cells, e.g. "components/ui imports lib 57 times". Selecting a cell lists evidence files such as `components/ui/accordion.tsx` → `lib/utils.ts`.
- **Console:** no errors.

---

## Not verified: please cover these in your review

- **Pixels.** My Chrome tab reported `document.visibilityState === "hidden"`, so Chrome paused painting and screenshots of the report sections timed out. Every check above was functional, through the DOM. The earlier "screenshots stall on the Architecture page" note had the same cause; it isn't an app bug.
  - Please run your headless Edge desktop and mobile screenshots on: Architecture layered, matrix, the split view, and a synthetic cycle atlas (for example, add a `lib → components` import).
- **Themes other than Codandy Midnight.** Colours come from `--primary`, `--chart-4`, `--chart-5`, `--surface-4`, `--border`, `--foreground` and `--muted-foreground`.
- **A real repository that has folder-level cycles.** Cycles are covered only by synthetic tests.

---

## Where to focus the review

1. **Cycle wording.** A cycle here is between **groups**, aggregated from file imports: "folder A imports B and B imports A" can come from different files. It isn't necessarily a file-level import cycle, which the report still flags separately as `import_cycle`. The notice says "between groups in view"; please check the legend line "Closes an import cycle" reads clearly enough in that light.
2. **Layout algorithm edge cases.** Duplicate or self links are filtered out; an empty graph; a view containing only isolated groups; project mode with .NET `ProjectReference` links.
3. **Accessibility.** SVG `g[role=button]` elements with keyboard activation; focus-visible stroke; `aria-pressed` on nodes, cells and toggles.
4. **Removed ring layout.** I found no other consumer. Please confirm nothing else relied on the old 10-group ring.
5. **Canvas size.** Deeply layered graphs can make a tall canvas; zoom and folder depth are the current mitigations.

## Known follow-ups (not defects)

- Arrowheads still use `fill="context-stroke"`. I tested it as the screenshot-stall suspect and ruled it out, so I kept it.
- The next slices per the plan are **V3** (stack-trace sequence diagram) and **V4** (call sites in source order).
