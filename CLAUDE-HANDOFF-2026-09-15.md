# Claude session handoff for Astra: 2026-09-15

**From:** Claude
**Covers:** everything Claude changed since your Whiteboard work.
**Roles on the diagrams track** (Andrew's decision): Claude implements, you review. Please write findings to `ASTRA-DIAGRAMS-CR-<date>.md`, keeping verified defects (with the command or test used) separate from suggestions.

---

## 1. Where everything is

| Ref | What | Pushed? |
|---|---|---|
| `main` `460a9d3` | Your Whiteboard work, committed as-is at Andrew's request | No |
| `main` `c4c6782` | `docs/INTEGRATIONS-PLAN.md` (Sentry, OpenTelemetry, Datadog, Linear, ClickUp, Jira and supporting integrations). **You implement; Claude reviews.** Andrew's decisions are pending in its §10. | No |
| `main` `8d334c5` | `docs/ARCHITECTURE-DIAGRAMS-PLAN.md` (ERDs, sequences, deployment and more; milestones AD0–AD11) | No |
| `claude/visual-atlas` | V0–V2: layered dependency graph and matrix. Awaiting your review; details in `CLAUDE-VISUALS-2026-09-15.md`. | No |
| `claude/architecture-diagrams` | Stacked on `claude/visual-atlas` with `main` merged in. Adds the data model and data contract diagrams in this note. | No |

`main` is 3 commits ahead of `origin/main`. Nothing was pushed and no remote branch was created.

**Merge order if both branches are accepted:** `claude/visual-atlas`, then `claude/architecture-diagrams`.

---

## 2. What the diagrams branch adds

### Contract: `structure-0.1`

- **Where it lives:**
  - Stored as `.codandy/structure.json`, beside `atlas.json`. Atlas 0.2 is unchanged.
  - Python: `backend/app/structure/models.py`. TypeScript (zod): `lib/structure-api.ts`. Both validators enforce the same rules; keep them in step.
- **Sections:**
  - `sources`: one per declaration kind per project directory. The project directory is the nearest atlas manifest folder.
  - `entities`: fields and evidence, plus `node_id` when an atlas declaration node matches.
  - `entity_links`:
    - `source` holds the reference and `target` is referenced.
    - Cardinality and optionality are recorded for each end.
    - `basis` is `declared` or `orm_relation`. `resolution` is `resolved`, `unresolved` or `ambiguous`.
  - `types`, `type_links` (`extends` or `field_type`), `counts`, `limitations`.
- **Invariants:**
  - IDs are unique.
  - Only resolved links name `target.entity`.
  - Links never cross schema sources.
  - `validate_against_atlas` requires every cited path to be an indexed file and every `node_id` to exist.

### Extraction (`backend/app/structure/`)

All extraction is static: nothing is imported, executed, migrated or connected to.

- **`extract.py`:** the orchestrator.
  - Only atlas file nodes are candidates, so the analyzer's exclusions and secret-name rule apply. Paths are re-checked with `sources._inside`, which refuses symlinks and paths outside the workspace.
  - Budgets: 2,000 entities, 300 fields each, 5,000 types, 300 members each, 20,000 links.
  - `build_structure` turns any exception into a document whose only limitation is `EXTRACTION_FAILED`.
- **`prisma.py`:**
  - Line parser that strips comments while respecting strings.
  - Reads `model`, `view`, `@id`, `@unique`, `@@id`, `@@unique`, `@@map`, `@@schema` and `@relation(fields, references)`.
  - Detects implicit many-to-many relations and relations to undeclared models.
  - **`datasource` and `generator` blocks are skipped without keeping their contents.**
- **`sql.py`:** tokenizer plus parser, applied in path order within each project directory.
  - Statements: `CREATE TABLE`/`VIEW`, `ALTER TABLE ADD`/`DROP` (column, constraint, FK) and `DROP TABLE`.
  - Handles quoted, backtick and bracket identifiers, `$$` bodies, comments and SQL Server `GO`.
  - **String literal contents are never kept.**
  - Columns without `NOT NULL` are nullable, following the SQL default.
- **`python_models.py`:** tree-sitter only; each class is reduced to plain facts.
  - **SQLAlchemy:**
    - `__tablename__`, or `Column` calls on a `*.Model` base
    - `Column`/`mapped_column`, with `Mapped[...]` nullability
    - mixin columns
    - `ForeignKey` given as a string or `Class.attr`
    - `relationship(secondary=)` as many-to-many
    - a plain `relationship()` is dropped when a declared FK already joins the pair
  - **Django:**
    - classic fields with documented defaults (`null=False`)
    - FK, OneToOne and M2M (`through` is skipped because the through model shows it)
    - abstract parent fields
    - implicit `id`
    - `Meta.db_table`
    - `settings.AUTH_USER_MODEL` stays unresolved
    - multi-table inheritance as an ORM relation
  - **Contracts:** Pydantic (including through local base classes), `@dataclass` and TypedDict. `_private`, `model_config` and `ClassVar` members are skipped.
- **`typescript.py`:** interfaces and object type aliases, `extends`, member types and a `?` optional marker. `.d.ts` files are skipped.
- **Contract link resolution:**
  1. A type in the same file is **resolved**.
  2. Otherwise, a type in a file reached through a resolved atlas import is **resolved**.
  3. Otherwise, a unique name in the repository is **inferred**.
  4. Ambiguous names are not linked and are counted instead.

### Integration

- **`worker.py`:**
  - After the atlas, the worker sends a `reporting` progress event at 89, so the UI step list is unchanged.
  - It builds the structure with a deadline of 85% of the analysis timeout, then sends `("result", atlas, structure)`.
  - `analyze_isolated` now returns `(atlas, structure)`.
- **`jobs.py`:** `checked_structure` validates against the final atlas, the result is written to `.codandy/structure.json`, and it is kept in `structures` and evicted with the report.
- **`report_storage.py`:** the new `Snapshot.structure` field is optional, so older snapshots load. An invalid structure is dropped and the report kept.
- **`routers/analyses.py`:** `GET /{id}/structure` returns 409 when not ready and 404 with a "Run the analysis again" message when absent.
- **Hosted proxy:** `app/api/analyses/[[...path]]/route.ts` now allows `structure`, forwarding no query string.

### UI

- **`components/architecture-hub.tsx`:** replaces the direct `ArchitectureMap` in `live-report.tsx`. It switches between Dependencies (V1/V2, unchanged), Data model and Data contracts, and fetches the structure once per report. A saved-atlas import without a job ID shows an explanation.
- **`components/data-model-diagrams.tsx`:**
  - `RecordDiagram` is the SVG renderer:
    - referenced tables on the left
    - crow's-foot ends drawn from cardinality and optionality
    - dashed amber for ORM relations, undeclared targets and inferred links
    - hollow triangles for `extends`
    - stubs as dashed boxes
    - records are keyboard buttons that focus a neighbourhood
  - **Data model view:**
    - schema selector, search, Keys only, zoom
    - Copy as Mermaid
    - legend with drawn end marks
    - column table
    - "Declared in" evidence that opens the declaration node, or the file
    - reference list with plain-language cardinality
    - Ask scope, mobile list, limitations
  - **Data contracts view:** folder selector (a focused view crosses folders), Inheritance toggle, "Uses" and "Used by" lists, and Mermaid `classDiagram`.
- **`lib/structure-diagram.ts`:** pure view builders (`erdView`, `contractsView`, `contractAreas`), descriptions, and Mermaid export. Identifiers are reduced to `[A-Za-z0-9_]`, labels lose quotes and newlines, and the text is never rendered as a diagram in the page.
- **`lib/architecture-layout.ts`:** `orderLayers` is factored out of `layeredLayout` without changing its output (the V1/V2 tests still pass). New pieces:
  - `recordLayout`: left-to-right columns, waypoint slots, row anchors, back edges, self loops, and a masonry area for unlinked records
  - `recordEdgePath`
  - `recordEndDirections`

---

## 3. Verification

| Check | Result |
|---|---|
| Backend `pytest` | **267 passed** (11 new in `tests/test_structure.py`, plus the updated `test_worker.py`) |
| `ruff check .` | clean |
| Contract tests | **40 passed** (6 new: Python-generated structure through zod, ERD layout, record layout cycles and waypoints, Mermaid, contract folders, proxy) |
| `tsc --noEmit` | clean |
| ESLint on changed frontend files | clean |
| Production build | succeeds |
| Personal `.reports`/`.investigations`/`.boards` hashes before and after pytest | unchanged |

**Backend fixture:** the same orders domain (users, products, orders, order_items) is written in Prisma, SQL, SQLAlchemy and Django, and all four produce identical core tables and links. Adversarial cases:

- a datasource password
- `CREATE TABLE` inside a comment, a string and a `$$` body
- `DROP TABLE`
- an FK to a missing table
- `node_modules` and secret-named `.sql` files
- an injection-style table name, kept as bounded data
- a budget cap, a past deadline, and an extractor exception
- dangling references

**On a source copy of Codandy:** 88 types and 92 links (86 resolved, 6 inferred) in 0.33 s. `Contract` in `backend/app/debugging/models.py` is a hub with 21 `extends` links, which is what the Inheritance toggle is for.

## 4. Not verified: please cover in review

- **The new views have not been rendered in a browser.** The running :8000 backend was not restarted, so it has no `/structure` endpoint. Please run your headless Edge desktop and mobile passes:
  1. Restart the backend.
  2. Reanalyze a repository with a schema (any public Prisma or Django sample) and one with Pydantic models.
  3. Check Data model and Data contracts in each theme.
- Large real schemas (hundreds of tables) for layout readability and speed.
- Keyboard and screen-reader behaviour of SVG `g[role=button]` records, and stub records using `role="img"`.

## 5. Where to focus the review

1. **Honesty labels:**
   - "declared, not a live database"
   - SQL nullable-by-default and Django `null=False` defaults
   - Unstated optionality exports to Mermaid as zero-or-one/zero-or-more, the weaker claim
   - Inferred contract links shown dashed
2. **Parser edge cases:** MySQL `KEY idx (col)` versus a column named `key`; Prisma relation names on self relations; SQLAlchemy mixins in other files (their field `line` is `None`).
3. **Worker contract change:** `analyze_isolated` now returns a tuple. Everything that calls or monkeypatches it in the repository was updated.
4. **Grouping by nearest manifest folder:** a SQL `migrations/` folder with no manifest groups at the repository root.
5. **Resolution order:** whether import-resolved contract links should outrank same-file matches when both exist. Same-file currently wins.

## 6. Known follow-ups (not defects)

- **Plan decisions still open:** `@xyflow/react` adoption (decision 2), framework priority (3), name-convention links (4).
- **Next slices, per plan §13:**
  - AD3 sequence diagrams (static call sites and observed stacks)
  - AD4 deployment (Dockerfile, Compose, Kubernetes, Terraform)
  - remaining ORMs (Drizzle, TypeORM, EF Core)
  - C#, Go and zod contracts
- **Integrations are yours to implement** from `docs/INTEGRATIONS-PLAN.md` (I0 first). Claude will review each slice.
