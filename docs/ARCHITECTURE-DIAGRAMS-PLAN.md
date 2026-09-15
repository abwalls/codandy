# Architecture diagrams plan: data models, sequences, deployment and flows

**Status:** plan dated 2026-09-15. AD0, AD1 and parts of AD2 and AD6 are implemented on branch `claude/architecture-diagrams`; see §13.
**Written by:** Claude, at Andrew's request.
**Implementer:** to be decided (§11).
**Relationship to other plans:**
- Builds on `docs/VISUALIZATION-PLAN.md` (V-track). That file and V1/V2 (the layered graph and dependency matrix) exist only on branch `claude/visual-atlas`, which is under Astra's review and not yet merged.
- Uses runtime data from `docs/INTEGRATIONS-PLAN.md`.

> Andrew: "Illustrations are a dev's best friend." The Architecture page should explain a system,
> not just list which folders import which.

---

## 1. Why the current diagrams feel weak

Codandy's atlas records files, declarations, imports, name-matched call candidates, route candidates, manifests and dependencies. Every diagram built from that data is a variation of "who imports whom".

The questions developers actually bring to an unfamiliar codebase are different:

| Question | Diagram that answers it | Data we don't extract yet |
|---|---|---|
| What data exists and how is it related? | ERD / data model | Tables, columns, keys, foreign keys, ORM relations |
| What shapes flow through the API? | Data contracts diagram | DTO/schema fields and nested types |
| How are the core types organised? | Class and interface diagram | `extends`/`implements`, typed members |
| What happens when this request arrives? | Sequence diagram | Cross-file call resolution, dependency injection wiring, runtime traces |
| Which endpoints read or write which data? | Endpoint-to-data map | ORM/query usage per function |
| What does the API expose? | API contract map | OpenAPI, GraphQL and protobuf definitions |
| What runs where, and what does it talk to? | Deployment / container diagram | Dockerfile, Compose, Kubernetes, Terraform declarations |
| What happens asynchronously? | Event and messaging flow | Topic/queue producers and consumers, background jobs |
| How is the frontend put together? | Route and component maps | File-based routes, component composition |

**The fix is mostly new *extracted facts*, not new renderers.** Every diagram below is paired with the static extractor that makes it honest.

---

## 2. Diagram catalogue

1. **Data model ERD (database schema).**
   - Shows tables or collections, columns with type, primary key, foreign key, unique and nullable markers, and relationships with cardinality where declared.
   - Tables can be grouped by schema, app or module.
2. **Data contracts diagram.**
   - Request/response and domain types (Pydantic, dataclasses, TypeScript interfaces and zod objects, C# records, Go structs) and how they nest.
   - Codandy can demo this on itself: `AtlasDocument` → `AtlasNode` / `AtlasRelationship` / `AtlasReport` → `ReportSection` → `ReportItem` → `Evidence`.
3. **Class and interface diagram (UML-lite).** Inheritance, interface implementation, members, and composition inferred from typed fields and constructor parameters.
4. **Sequence diagrams, with three sources that are always labelled:**
   - **Static:** call sites in source order, through cross-file calls and dependency-injection wiring. *Source order, not runtime order.*
   - **Observed:** the stack of a captured exception. *Observed order at failure.*
   - **Traced:** spans from OpenTelemetry or Datadog, with real timing and nesting. *Observed runtime.*
   - **Comparison mode:** the static expected path next to the traced path, highlighting hops that are missing or extra. This is a strong differentiator.
5. **Endpoint-to-data map.**
   - A CRUD matrix of routes against entities (read, write, unknown).
   - A flow view: route → handler → service → data access → table, with every hop a labelled candidate.
6. **API contract map.** OpenAPI operations and schemas, GraphQL types and relations, protobuf services, RPCs and messages. Each is linked to the matching route candidates.
7. **Deployment / container diagram.**
   - Services, images, ports, `depends_on` links, networks and volumes.
   - Datastores and brokers recognised by image name.
   - Kubernetes workloads and Services matched by label selector.
   - Terraform resources and the references between them.
   - Always labelled **declared, not deployed**.
8. **Event and messaging flow.** Channels (topics, queues, events) with publisher and subscriber candidates matched by literal channel name, plus background jobs (for example Celery tasks, MediatR handlers).
9. **Frontend maps.**
   - A file-based route tree (Next.js `app/` and `pages/`, route groups, dynamic segments).
   - A React component composition tree, built from JSX elements that resolve to local components.
10. **Layered dependency graph and dependency matrix.** Already built as V1/V2.
11. **Small illustrations across the app:**
    - an Overview "system at a glance" card (deployment and ERD thumbnails)
    - neighbourhood graphs in the Codebase inspector
    - before/after impact sketches in Recommended changes
    - "where to change X" path diagrams in the Developer guide
    - a dependency graph with health status
    - a timeline strip for investigations

---

## 3. Rules

These add to VISUALIZATION-PLAN's eight rules.

1. **Static only.**
   - Never import or execute model code, run migrations, or connect to databases, clusters or cloud accounts.
   - Never render templates, or download Terraform providers or modules.
   - OpenAPI `$ref`s resolve only within the same file or repository; remote references aren't fetched.
2. **Declared isn't deployed.** Label ERDs "declared in `<file>`" and deployment views "declared in manifests". The live database or cluster may differ.
3. **Relationship evidence comes in tiers:**
   - `declared` (an explicit foreign key or relation)
   - `orm_relation` (a relation without a foreign-key column)
   - `name_convention` (`user_id` → `users`). Hidden by default, dashed when shown, and never counted as fact.
4. **Secrets never enter the structure document.**
   - From Compose, Kubernetes and Terraform, keep environment and variable **keys only**, never values.
   - Redact connection strings.
   - Exclude `*.tfstate`, `*.tfvars` and `*.auto.tfvars` alongside the existing `.env` rule. Add them to `SECRET_NAME`, with tests.
5. **Parse safely:**
   - YAML through a safe loader with size, depth and alias-count limits; reject documents that use too many aliases.
   - SQL with statement-count and byte limits.
   - XML without DTDs or entities, as the analyzer already requires.
   - JSON with depth limits and duplicate-key rejection.
   - Every parse failure becomes a limitation, never a crash.
6. **Every element carries evidence** (file and line) and a visible evidence basis. Unresolved references stay visible: a foreign key to an unknown table is drawn to an "unresolved" stub, not dropped.
7. **`atlas.json` schema 0.2 stays unchanged.** New facts live in a separate document (§5), which keeps AGENTS.md's rule and saved-atlas compatibility.
8. **Repository text is untrusted.** Table, field and service names render as React text. They are never rendered through Mermaid in the page, and they are data in AI prompts.

---

## 4. Extractors (backend, static)

Frameworks are listed in suggested priority order. Everything reuses the existing file walk, exclusions, size limits and tree-sitter grammars, whose version pin stays below 0.26.

### A. Declarative schemas (highest confidence)

- **Prisma** (`schema.prisma`), using a small bounded parser. Extracts:
  - `model` and field types
  - `@id`, `@unique`, `@default` (literal kinds only)
  - `@relation(fields: [...], references: [...])`
  - `@@map` / `@map` table and column names
  - `enum`
- **SQL DDL** in `.sql` files and SQL migration folders, using `sqlglot` (§9). Extracts:
  - `CREATE TABLE`, column types, `PRIMARY KEY`, `UNIQUE`, `NOT NULL`
  - `REFERENCES` and `ALTER TABLE … ADD CONSTRAINT … FOREIGN KEY`
  - `CREATE VIEW` names (listed, not related)

  Migrations are aggregated in filename order and labelled "cumulative declarations; apply order, conditions and data migrations not evaluated".

### B. ORM models (tree-sitter)

| ORM | What is recognised |
|---|---|
| SQLAlchemy | `DeclarativeBase` or `declarative_base()` subclasses, `__tablename__`, `Column(...)` / `mapped_column(...)` with `ForeignKey("table.col")`, `relationship("Model")` |
| Django | `models.Model` subclasses, fields, `ForeignKey` / `OneToOneField` / `ManyToManyField` (target model), `Meta.db_table` |
| Drizzle | `pgTable` / `mysqlTable` / `sqliteTable` calls, columns, `.primaryKey()`, `.references(() => table.col)` |
| TypeORM | `@Entity`, `@Column`, `@PrimaryGeneratedColumn`, `@ManyToOne` / `@OneToMany` / `@OneToOne` / `@ManyToMany`, `@JoinColumn` |
| EF Core | `DbSet<T>` properties on `DbContext` subclasses; `[Table]`, `[Key]`, `[ForeignKey]`; navigation properties (the Fluent API is a later refinement) |
| Later | GORM struct tags, Sequelize, Mongoose (document refs), ActiveRecord if Ruby is added |

### C. Types and contracts

- **Inheritance for all five languages:**
  - TypeScript/JavaScript `extends` and `implements`
  - Python base classes
  - the C# base list
  - Go struct embedding. Go interface satisfaction is **not** inferred.
- **Fields and typed references:**
  - Pydantic `BaseModel` fields and dataclasses (annotations)
  - TypeScript interfaces and type-alias object types
  - `z.object({...})`
  - C# class and record properties
  - Go struct fields

  A field whose type names another local type becomes a `has_field_of_type` link, marked **inferred** when resolution relies on the unique-name rule.

### D. API contracts

- **OpenAPI 3.x** (JSON/YAML): paths, operations (method, operationId), parameters, request/response schemas, local `$ref` graph.
- **GraphQL SDL:** object and input types, fields, lists and non-null, `Query`/`Mutation` roots.
- **Protobuf:** `service`, `rpc`, request/response `message`s, field types, `import`.
- **Parsing:** safe YAML/JSON loaders; small bounded parsers for SDL and proto unless tree-sitter grammars prove compatible with the pinned core (spike in AD7).

### E. Deployment

- **Dockerfile:** `FROM` (stage graph), `EXPOSE`, `WORKDIR`, `CMD`/`ENTRYPOINT` program names. Arguments aren't evaluated.
- **Compose:** services, `image`/`build`, `depends_on`, `ports`, `networks`, `volumes`, environment **keys**. Datastore or broker kind comes from well-known image names (postgres, mysql, mariadb, mongo, redis, rabbitmq, kafka, elasticsearch, …), labelled "by image name".
- **Kubernetes manifests:**
  - Deployment, StatefulSet, DaemonSet, Job/CronJob
  - Service matched to workloads by label selector
  - Ingress rules pointing at Services
  - ConfigMap and Secret **names only**
- **Terraform** (`*.tf`, HCL): `resource`/`module`/`data` blocks with type and name, and references between resources (`aws_db_instance.main.address`). No state files, no variable values, no module downloads.

### F. Messaging

Literal channel names in producer and consumer calls, matched by exact string:
- Kafka clients (kafkajs `send({ topic })`, confluent-kafka, …)
- amqplib/RabbitMQ `publish`/`consume`
- AWS SQS/SNS SDK calls with literal queue/topic identifiers
- Azure Service Bus sender/receiver
- Celery `@app.task` and `.delay` / `.apply_async`
- MediatR `IRequestHandler<T>` / `INotificationHandler<T>` with `Send` / `Publish`
- NestJS `@EventPattern` / `@MessagePattern`
- Node `EventEmitter` `emit`/`on`

Names that aren't literals are counted as unresolved.

### G. Data access (for the endpoint-to-data map and to end sequences at entities)

| Stack | Patterns recognised |
|---|---|
| SQLAlchemy | `session.query(Model)`, `select(Model)` |
| Django | `Model.objects.<op>` |
| Prisma | `prisma.<model>.<op>` |
| Drizzle | `db.select().from(table)`, `db.insert(table)` |
| EF Core | `context.<DbSet>` / `Set<T>()` |
| TypeORM | repository or entity-manager calls |
| Raw SQL | String literals parsed by `sqlglot` for table names; low confidence, labelled "SQL string" |

Operations are classified as read, write or unknown by method name.

### H. Frontend

- **Routes:** Next.js `app/**/page.tsx` and `layout.tsx` (route groups `(x)`, dynamic `[id]`, catch-all `[...x]`) and `pages/**`. Other frameworks' file-based routes are inventory only until indexed.
- **Components:** JSX elements whose tag resolves through a local import to a component declaration.

### I. Call resolution for sequence diagrams

- Cross-file method calls through import bindings (`import { orders } from "./orders"` + `orders.create()`).
- Class and instance calls (`this.repo.save()` through a typed constructor parameter or field).
- **Dependency-injection wiring,** all labelled **static candidates**:
  - ASP.NET `AddScoped/AddTransient/AddSingleton<IService, Service>()` + constructor parameters
  - NestJS providers + constructor injection
  - FastAPI `Depends(fn)`

---

## 5. Data contract: `structure-0.1`

A separate artifact, `.codandy/structure.json`, written next to `atlas.json`. It's served at `GET /api/analyses/{id}/structure`, retained and evicted with the report, and included in persistence snapshots.

As implemented for AD0–AD2 (`backend/app/structure/models.py`, mirrored by `lib/structure-api.ts`):

```
structure-0.1
  schema_version: "structure-0.1", atlas_schema: "0.2"
  sources[]:       { id, kind: prisma|sql|sqlalchemy|django, root (nearest project directory, "" = repository root), files[] }
  entities[]:      { id, source_id, name, table?, namespace?, kind: table|view|model,
                     fields[] { name, type, primary, unique, foreign, nullable?, line? },
                     omitted_fields, node_id? (atlas declaration node), evidence[] }
  entity_links[]:  { id, source_id,
                     source { entity, name, fields[], cardinality: one|many|unknown, optional? }   (holds the reference)
                     target { entity?, name, fields[], cardinality, optional? }                    (is referenced)
                     label, basis: declared|orm_relation, resolution: resolved|unresolved|ambiguous, evidence[] }
  types[]:         { id, name, language: Python|TypeScript, kind: pydantic|dataclass|typed_dict|interface|type_alias,
                     path, members[] { name, type, line? }, omitted_members, node_id?, evidence[] }
  type_links[]:    { id, source, target, kind: extends|field_type, member?, resolution: resolved|inferred, evidence[] }
  counts{}, limitations[]
```

- `target.cardinality` is how many referenced rows one referencing row relates to; `source.cardinality` is the reverse. Only resolved links name `target.entity`, and a link never crosses schema sources.
- `name_convention` links are not produced yet (decision 4 in §11).
- Later milestones add optional top-level sections without breaking 0.1 readers:

```
  contracts:       { openapi[], graphql[], protobuf[] }    operations, schemas, refs; each with evidence
  deployment:      { services[] { id, name, source: dockerfile|compose|kubernetes|terraform, image?, ports[], env_keys[] },
                     links[] { from, to, kind: depends_on|selects|routes_to|references|network, evidence },
                     datastores[] { service, kind, basis: image_name } }
  messaging:       { channels[] { name, kind }, publishers[] { channel, function_node }, subscribers[] { channel, function_node } }
  data_access[]:   { function_node, entity, operation: read|write|unknown, basis, evidence }
  frontend:        { routes[] { path, file_node, kind: page|layout|route }, component_links[] { from, to, evidence } }
```

- **Evidence:** every `evidence` entry is `{ path, lines, reason }`, and paths must exist as atlas file nodes. `function_node` must be an atlas node ID.
- **Validation:** Python (Pydantic) and TypeScript (zod) schemas are checked against each other. References must resolve within the document or the atlas.
- **Why a separate document:**
  - atlas 0.2 stays unchanged, so saved atlases and snapshot comparison are unaffected
  - structure extraction can fail or be skipped without harming the atlas
  - the extractors can evolve independently
- **Budgets** (tunable):

  | Limit | Value |
  |---|---|
  | Entities | 2,000 |
  | Fields per entity | 300 |
  | Types | 5,000 |
  | Services | 500 |
  | Channels | 500 |
  | Document size | 8 MiB |

---

## 6. Rendering and interaction

- **The Architecture tab becomes a diagram hub:**
  - a rail listing diagram types with availability counts ("12 tables", "3 services")
  - each unavailable diagram explains what Codandy looks for ("No schema detected: we read Prisma, SQL DDL, SQLAlchemy…")
  - a main canvas and an evidence drawer
- **Engines:**
  - **`@xyflow/react` 12.11.6 plus `@dagrejs/dagre` 3.1.1** (both MIT, verified 2026-09-14) for interactive node-heavy diagrams: ERD, class, deployment, API contracts. The VISUALIZATION-PLAN switch conditions (dragging, more than 60 nodes) are met. It loads lazily on the Architecture tab only.
  - Plain **React SVG** for sequence diagrams and matrices (shared with V-track components).
  - **recharts** for charts.
  - **Mermaid as text export only**, not rendered in the page: `erDiagram`, `classDiagram`, `sequenceDiagram`, `flowchart`.
- **ERD details:**
  - table nodes list columns with PK/FK/unique markers and can collapse to key columns
  - crow's-foot ends only where cardinality is declared
  - dashed edges for inferred tiers, and stubs for unresolved targets
  - grouping by schema, module or app
  - search, focus on a neighbourhood, and "declared in" on hover
- **Sequence diagram details:**
  - lifelines grouped by service, class or file
  - three message kinds: *call* (static), *frame* (observed), *span* (traced, with duration bars and gaps)
  - no invented `alt`/`loop`/`async` fragments; only structure present in evidence is drawn (for example, async boundaries from stacks and trace span kinds)
  - comparison mode overlays static and traced paths
- **Deployment details:**
  - containers show their ports, and datastores show kind icons labelled "by image name"
  - `depends_on` arrows, networks as swim lanes
  - a "declared, not deployed" banner
  - an **Open in Whiteboard** handoff
- **Cross-links:**
  - entity → endpoint-to-data row and source
  - route → sequence diagram
  - service → its code
  - span → source candidate
  - type → class diagram focus
- **Exports:** SVG/PNG images, and Mermaid text for docs, agents, Whiteboard `plan.md` and tickets (via INTEGRATIONS-PLAN T4).
- **Rendering budgets per view,** with search and clusters beyond them:

  | View | Limit |
  |---|---|
  | ERD | 80 tables |
  | Class diagram | 100 types |
  | Deployment | 60 nodes |
  | Sequence | 40 messages |

---

## 7. Milestones (AD track)

| # | Slice | Depends on | Done when |
|---|---|---|---|
| **AD0** | Structure foundations | V1/V2 merged | `structure-0.1` contract, extractor registry, persistence, API endpoint. Diagram hub shell with availability and empty states. Evidence drawer. Mermaid exporter. A spike adopting `@xyflow/react` plus dagre, measuring bundle size, both themes, keyboard use and client-only loading. |
| **AD1** | ERD I: declarative | AD0 | Prisma and SQL DDL (with migration aggregation) produce entities and links. The ERD view renders with notation, grouping, search, unresolved stubs and Mermaid `erDiagram` export. |
| **AD2** | Types and class diagram | AD0 | Inheritance and field-type links for all five languages. Data contracts view (demoed on Codandy's own Pydantic models). Class diagram with focus. |
| **AD3** | Sequence I: static and observed | AD0 (+ V3/V4 designs) | Upgraded cross-file and dependency-injection call resolution. Shared lifeline component. Static call-site sequences from routes (source order). Exception-stack sequences from investigations. |
| **AD4** | Deployment | AD0 | Dockerfile, Compose, Kubernetes and Terraform extractors, with tests showing no secrets are kept. Deployment diagram. Open in Whiteboard. |
| **AD5** | Endpoint-to-data map | AD1 or AD6, AD3 | Data-access extractor, CRUD matrix, and route → entity flow. Sequences end at entities. |
| **AD6** | ERD II: ORMs | AD1 | SQLAlchemy, Django, Drizzle, TypeORM and EF Core attributes, merged with declarative sources (the same table from two sources shows both pieces of evidence). |
| **AD7** | API contracts | AD0 | OpenAPI, GraphQL SDL and protobuf views, with operations linked to route candidates. A parser spike for grammar compatibility. |
| **AD8** | Sequence II: traced | INTEGRATIONS M2/M4, AD3 | Span-based sequences with timing, plus the static-vs-traced comparison mode. |
| **AD9** | Messaging flow | AD0 | Channel extractor for the listed clients, and a publisher → channel → subscriber diagram. |
| **AD10** | Frontend maps | AD0 | File-based route tree and component composition tree. |
| **AD11** | Small illustrations | Relevant slices above | Overview system card, Codebase neighbourhood graph, before/after sketches in Recommended changes, Developer guide paths, dependency health, investigation timeline strip. |

**Order:** numbered in suggested delivery order. AD9–AD11 can move earlier or run in parallel, because they depend only on AD0.

- ERDs and sequence diagrams are what developers ask for first.
- Type and class diagrams reuse existing grammars, and Codandy can demo them on itself.
- Deployment formats are simple and high-value, and they connect to the Whiteboard's cloud-architecture flow.

---

## 8. Fixtures and testing

- **A shared domain fixture corpus.** Codandy's own repository has little schema material (one `backend/Dockerfile` and an empty Drizzle schema). Build `backend/tests/fixtures/structure/<framework>/`: one small "orders" domain (users, products, orders, order_items; one-to-many and many-to-many) written in each supported framework.
  - Every framework must produce the **same expected entities and links** (golden `structure.json`), which catches extractor drift between frameworks.
- **Adversarial fixtures:**
  - YAML alias bombs and deep nesting
  - oversized SQL
  - Compose/Kubernetes/Terraform files with passwords, tokens and connection strings, asserting values never appear anywhere
  - OpenAPI remote `$ref`, asserting nothing is fetched
  - a foreign key to a missing table
  - prompt-injection text in comments and table names, asserting it is rendered and prompted only as data
  - unsupported dialects producing limitations, not crashes
- **Frontend:**
  - derivation tests (ERD graph inputs, sequence ordering and merging, CRUD matrix aggregation, Mermaid output goldens)
  - a Python/TypeScript contract test for `structure-0.1`
  - DOM interaction QA
  - **screenshot QA in headless Edge** (Astra's environment works; Claude's Chrome pauses painting when the tab is hidden)
- **Real-repository smoke tests:** choose public examples per framework at implementation time (a Django app, a Prisma app, a NestJS/TypeORM app, an EF Core reference app, a Compose-based microservice demo). Record entity, link and service counts, plus notable limitations, in `progress.md`.
- **Every slice:** full pytest, ruff, contracts, `tsc`, changed-file ESLint and build, with personal storage hashes unchanged.

---

## 9. Dependencies and licences

All checked 2026-09-14/15; reconfirm at adoption.

| Package | Version | Licence | Use | Notes |
|---|---|---|---|---|
| `sqlglot` | 30.18.0 | MIT | SQL DDL and raw SQL table names | No required runtime dependencies; spike dialect coverage, error tolerance and limits |
| `PyYAML` | 6.0.3 | MIT | Compose, Kubernetes, OpenAPI YAML | `safe_load` only, behind size, depth and alias limits |
| `@xyflow/react` | 12.11.6 | MIT | Interactive diagrams | Lazy-loaded on the Architecture tab |
| `@dagrejs/dagre` | 3.1.1 | MIT | Layered layout for node diagrams | Keep the in-house layout for small SVG views |
| Tree-sitter SQL/GraphQL/protobuf/HCL grammars | — | varies | Optional | Only if they pass the pinned-core gate (`test_grammars.py`); otherwise use small bounded parsers |
| `elkjs` | 0.12.0 | EPL-2.0 or GPL-3.0 | Not adopted | Needs a licence review first |

---

## 10. Honesty edge cases (decided up front)

- **Migrations:** the cumulative declared state can differ from the live database (conditional or data migrations, manual changes). Show "declared across N migrations", with optional per-migration history.
- **Relations without columns:** an ORM relation with no foreign-key column declared gets basis `orm_relation`, and cardinality `unknown` unless the ORM states it.
- **Polymorphic and generic relations** (for example Django `GenericForeignKey`) are drawn as unresolved stubs.
- **Views, triggers and stored procedures** are listed, but only related to tables when their DDL names them.
- **Name-convention links** are off by default, always dashed and labelled, and excluded from counts.
- **Sequences:** static sequences always say *source order*; no conditional or loop fragments without evidence; traced sequences show span wall time, not CPU time.
- **Deployment:** recognising a datastore by image name is inference; service discovery through environment variables or DNS isn't modelled; Kubernetes selectors are matched literally only.
- **Frontend:** component trees reflect static JSX usage, not conditional rendering at runtime.

---

## 11. Decisions for Andrew

1. **Implementer and pacing.** Astra (alongside the integrations track) or Claude (continuing from V1/V2), and whether both tracks run in parallel.
2. **Adopt `@xyflow/react` plus dagre now** for ERD, class and deployment diagrams (recommended), or keep extending the in-house SVG.
3. **ERD framework priority** for the stacks your target users run. The default order is Prisma, SQL, SQLAlchemy, Django, Drizzle, TypeORM, EF Core.
4. **Name-convention relationships:** hidden by default (recommended), or omitted entirely.
5. **A separate `structure-0.1` artifact** (recommended), or an atlas schema bump to 0.3.

---

## 12. How this relates to the other plans

| Other plan item | Covered here by |
|---|---|
| VISUALIZATION-PLAN V1/V2 (layered graph, matrix) | Kept; built on branch `claude/visual-atlas` |
| VISUALIZATION-PLAN V3 (stack sequence), V4 (call-site sequence) | Superseded by **AD3** (shared lifeline component, better call resolution) |
| VISUALIZATION-PLAN V5/V6 (treemap, charts) | Folded into **AD11** |
| VISUALIZATION-PLAN V7 (Open in Whiteboard) | Delivered through **AD4** (deployment first), then other diagrams |
| INTEGRATIONS-PLAN M2/M4 (OpenTelemetry, Datadog traces) | Required by **AD8** |
| INTEGRATIONS-PLAN T4 (ticket entry points) | Tickets can embed Mermaid exports from any diagram |

---

## 13. Implementation status

**2026-09-15, Claude, branch `claude/architecture-diagrams`.** The branch is stacked on `claude/visual-atlas` and is awaiting Astra's review. Handoff: `CLAUDE-HANDOFF-2026-09-15.md`.

| Milestone | Done | Not yet |
|---|---|---|
| AD0 | `structure-0.1` contract; extraction in the analysis worker with its own time share, never failing the atlas; snapshot persistence; `GET /api/analyses/{id}/structure`; Architecture switcher (Dependencies, Data model, Data contracts); evidence panels; Mermaid copy | `@xyflow/react` spike. Diagrams use an in-house SVG record layout shared with V1/V2, so decision 2 is still open. |
| AD1 | Prisma (multi-file, implicit many-to-many, `@@map`/`@@schema`, datasource blocks never read); SQL DDL in path order (CREATE/ALTER/DROP, inline and table constraints, quoted identifiers, dollar-quoted bodies, string contents withheld); ERD with crow's-foot ends, schema selector, search, Keys only, focus, unresolved stubs | Per-migration history view |
| AD2 (part) | Pydantic, dataclasses, TypedDict, TypeScript interfaces and object type aliases; `extends` and member-type links resolved by same file, then resolved local import, then unique name (inferred); folder view with stubs for types elsewhere; Mermaid `classDiagram` | C#, Go and JavaScript classes, zod, `implements`, methods |
| AD6 (part) | SQLAlchemy (`__tablename__`, `Column`/`mapped_column`, `Mapped[]` nullability, mixins, `ForeignKey`, `relationship(secondary=)`) and Django (fields, FK/OneToOne/M2M, abstract parents, implicit `id`, `db_table`, `AUTH_USER_MODEL` kept unresolved), each drawn as its own schema source | Merging the same table across sources; Drizzle, TypeORM, EF Core |
| AD3 (observed part) | On branch `claude/observed-sequences`, awaiting review. Observed stack sequences in Errors & stacks: a Frames/Sequence toggle, one lifeline per file or function, library frames collapsed into dashed arrows, async boundaries dotted, a raise marker, and every frame active until the raise. Traced span sequences beside the OTLP waterfall: one lifeline per service, parent service to child service in start order, activation until the last descendant, root, missing and cyclic parents drawn from "Outside this trace", durations under each arrow. Both share one SVG lifeline component and export Mermaid `sequenceDiagram`. Frontend only; the observation and trace contracts are unchanged. | Static call-site sequences with cross-file and DI resolution; static-versus-traced comparison (AD8); source binding from arrows |
| WHITEBOARD-PLAN W6 (AI edits via element skeletons) | Shares the diagram-to-board conversion |


## Review refinement — 2026-09-15

Prioritize useful visual evidence: ship the reviewed ERD and type/contract diagrams, then add observed stack sequences and traced span sequences, static call-site sequences, and declared deployment diagrams. Pattern illustrations belong in a labeled reference/proposal view until concrete evidence supports a pattern match. A whiteboard proposal must not mutate the extracted architecture graph; ticket creation and any implementation remain separate explicit actions. See ASTRA-DIAGRAMS-CR-2026-09-15.md for verified extraction fixes.
