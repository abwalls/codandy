# Codandy roadmap and status

**Status report for Andrew.** Last updated 2026-09-12 after reviewing Astra 6's
"Continued v1 completion" slice. Verified by re-running the full suite, not read off
checkpoints.

---

## Implementation update ? 2026-09-13

The review below is a historical snapshot. Since that review, defects 2-5 were fixed, deployment claims corrected, and cross-folder import/circular-import reports added. Saved atlas reopening, snapshot comparison, reverse dependency inspection, opt-in local completed-report persistence, recent reports and confirmed removal are now implemented. Five persistent color presets include Codandy Midnight (default), Forbright and Vol Orange. Verification now covers 87 backend tests and 13 frontend contracts; browser QA remains unavailable. Shared multi-user persistence/auth, uploads, Codex integration and hosted deployment are still unfinished. Dockerfile/debugging deferrals remain in effect.

## Where the project actually stood at review time

```
M0  Foundation                  ████████████████████  done
M1  Real repo analysis          ████████████████████  done, live-verified
M2  Grounded reports            ███████████████·····  ~75%
M3  Codex / Ask Codandy           ····················  not started
M4  Inputs & persistence        ····················  not started
M5  Debugging overlay (v2)      ····················  deliberately deferred
```

**One-line summary:** the deterministic engine is real and working across five languages
with evidence-backed reports and a source viewer. What's missing before this is a product
rather than a demo is persistence, AI answers, and hosting — in roughly that order of
difficulty.

---

## What works today, verified

I ran all of this against the current tree:

| Check | Result |
|---|---|
| Backend tests | 75 passed |
| `ruff` | clean |
| Frontend/API contract tests | 7 passed |
| `tsc --noEmit` | clean |
| Production build | succeeds |
| ESLint | clean |
| Live GitHub analysis (TypeScript repo) | passes end to end |
| Browser interaction (Python repo) | passes |

Concretely, you can point it at a public GitHub repo and get:

- **Bounded, safe ingestion** — HTTPS github.com only, credential and localhost URLs
  rejected, symlink/submodule/depth/size/file-count limits, disposable workspace, DNS
  pinned against rebinding.
- **Syntax indexing in 5 languages** — C#, TypeScript/TSX, JavaScript/JSX, Python, Go
  (10 file extensions). Classes, interfaces, methods, functions, types, enums.
- **Manifest detection** — `package.json`, `.csproj`/`.fsproj`/`.vbproj`, `pyproject.toml`,
  `requirements.txt`, `go.mod`. Dependencies extracted as names only, never versions.
- **Framework detection** — React, Next, Angular, Vue, Svelte, Express, FastAPI, Django,
  Flask, Gin, Echo, Chi, ASP.NET Core.
- **Route candidates** — minimal-API, Express, Flask/FastAPI decorators, Go mux/gin.
- **Local import resolution** — relative JS/TS, relative and repo-rooted Python, Go package
  directories under the declared module path. Ambiguity stays `unresolved` rather than
  guessing.
- **Five report sections** — Overview, Codebase index, Architecture, Application flows,
  Developer guide, Recommended changes. All graph-grounded with evidence, confidence, and
  explicit limitations.
- **Source viewer** — real code with line numbers, evidence range highlighted, whole-file
  toggle. Survives workspace destruction.
- **Live progress** — SSE with `Last-Event-ID` replay and status-poll recovery.
- **Crash containment** — parsing runs in a disposable process with a hard deadline. This
  has already earned its keep: it caught a native segfault and reported a dead worker
  instead of taking down the API.

**The single best quality signal in this project** is its refusal to fabricate. Every
inferred item carries a basis, a confidence, and a statement of what it does *not* prove.
Recommendations are labeled potential risks, never verified vulnerabilities, and an absence
of findings is explicitly not claimed as a clean audit. That discipline has survived three
sessions and two different models. Protect it — it's the hard part, and it's what would
distinguish this from a hundred "AI code analysis" tools.

---

## What's missing, by milestone

### M2 — Grounded reports (~75%)

Delivered: architecture rules (projects, source layout, inferred boundaries, external
dependencies, shared modules), flow rules (route paths, module dependencies), developer
guide rules, four recommendation rules, source viewer.

Still thin:

- **Architecture is structural, not architectural.** It reports manifests, top-level
  folders, conventional folder names, and a dependency list. It does not infer layers,
  dependency direction, boundary violations, or external systems. A folder named `domain/`
  produces "Domain boundary" — a naming hint, honestly labeled as such, but not analysis.
- **Flows are 1–4 hop local traversals**, capped at 16 links, not reconstructed request
  paths. Middleware, auth, dynamic dispatch, and downstream services are absent.
- **Confidence scores are fixed per-rule constants** (70/85/100), not computed from
  evidence strength. The plan called for "confidence scoring."
- **Only 4 recommendation rules** — long declarations, high import count, `eval`, raw HTML.
  No performance analysis, no data-flow, no vulnerability lookup.

### M3 — Codex / Ask Codandy (0%)

The "Ask Codandy" button exists on the sample path with canned answers; on the real path it
says "not available yet." Nothing behind it. Needs the ChatGPT-authenticated session
adapter, read-only investigation tools (symbols, callers, callees, routes, source), and
node-scoped questions with citations. The multi-tenant policy question in `PLAN.md` is
unanswered.

### M4 — Inputs and persistence (0%) — **this is the real blocker**

- **No database. No persistence of any kind.** All state is four in-memory dicts.
  `jobs.py`'s own docstring: "Reports disappear on API restart."
- ZIP and folder upload are disabled in the UI.
- No private repository support.
- No saved reports, no commit freshness, no incremental re-analysis.

### M5 — Debugging overlay (0%, deferred by you)

Sidebar entry exists, marked "Soon," button disabled. Untouched by design.

---

## Known defects

Full detail and suggested fixes are in `REVIEW-NOTES-FOR-ASTRA.md`. Summary:

| # | Severity | Issue | Owner |
|---|---|---|---|
| 1 | **High** | `backend/Dockerfile` cannot build — `uv sync` has no `--system` flag. Second defect behind it: CMD won't find `uvicorn` in the venv. Docs already claim it's deployable. | Deferred by you |
| 2 | Medium | `external_dependency` rule produces 78% of Architecture items (32 of 41 on a 32-dep fixture). Should be one aggregated card. | Astra 6 |
| 3 | Low | `categoryLabels` missing the two new categories — they render as raw snake_case. | Astra 6 |
| 4 | Low | `node.lines` rendered unguarded in sample codebase view; `lines` is optional. Safe only by fixture accident. | Astra 6 |
| 5 | Low | Sample flow numbers all 6 demo nodes "Step 1-6" but the graph branches — implies ordering that doesn't exist. | Astra 6 |
| 6 | Low | Dead unreachable branch in `PlaceholderSection` after `SampleSection` took over. | Your call |

None of these break the build or the tests. Nothing is on fire.

---

## Environment issues worth knowing

These are machine problems, not code problems, but they'll bite whoever works here next:

1. **`%LOCALAPPDATA%\Temp\pytest-of-andre`** is a stale directory your account can no longer
   read or write — even `Get-Acl` is denied. Without `--basetemp`, pytest reports 27 errors
   that look like real failures.
2. **`backend/.pytest-tmp`** is now in the same broken state, left behind by Astra 6's run
   at 14:34. This makes the *documented* workaround command fail with 40 spurious errors.
   **Both need an elevated shell to remove** — worth doing before the next session.
3. **`backend/.venv` is still broken** (points at a missing Python). Use
   `backend/.venv-managed/Scripts/python.exe`. `uv` is at `.tools/uv/uv.exe`, not on PATH.

---

## Critical path to something shippable

The ordering matters more than the individual items. My recommendation:

**Phase 1 — close the loop on what exists (small, high value)**
1. Fix defects 2–5 above. Half a day of work; makes the reports meaningfully better to read.
2. Mobile/responsive QA of the source viewer — never tested at any breakpoint.

**Phase 2 — decide what this is (blocking decision, yours)**
3. **Local tool, or hosted service?** Everything downstream forks here:
   - *Local tool* — skip persistence, skip auth, ship the Windows scripts, done. M4 mostly
     evaporates. This is achievable in days.
   - *Hosted service* — you need persistence **before** hosting, not after. In-memory state
     plus more than one replica means clients 404 on their own jobs. That's real work:
     a datastore, report lifecycle, auth, quotas, and a resolution to the multi-tenant Codex
     policy question.

**Phase 3 — depends on Phase 2**
4. If hosted: persistence, then the Dockerfile, then hosting, then `CODANDY_API_URL`.
5. If local: M2 depth, then M3 Codex, then M5 debugging.

**Phase 4 — differentiation**
6. Deeper M2 inference (real boundary/layer analysis, dependency-direction violations).
7. M3 Codex Q&A grounded in the graph.
8. More languages (Java, Rust, Ruby, PHP) — mostly mechanical now that the registry exists.
9. M5 debugging overlay — your stated v2 goal.

---

## Risks

**Scope drift toward hosting before the foundation supports it.** The Dockerfile and
`.env.example` landed before any persistence exists. That's building the second floor first.
The docs have already started describing the backend as deployable, which is how a demo
quietly starts getting treated as a service.

**"Architecture" over-promising.** The section is named for something it doesn't yet do.
The wording is honest — every item says what it doesn't prove — but a user reading
"Architecture" expects layers and boundaries, and gets a folder listing plus a dependency
list. Either deepen the analysis or rename the section until it earns the name.

**Single-worker throughput.** One analysis at a time, 429 on concurrent submit. Fine for a
local tool, a hard ceiling for anything else.

**No evaluation harness.** There's no fixture corpus measuring whether reports get *better*
across changes. Right now "did the rules improve?" is answered by eyeballing one repo. If
you keep adding inference rules, you'll want a small set of known repos with expected
outputs, or you'll have no way to detect regressions in report quality — only in crashes.

---

## Bottom line on the model comparison

Since that's what you're actually evaluating: Astra 6's slice was **accurate, honest, and
correctly scoped.** It read the handoff before building, preserved every constraint it was
given, flagged what it couldn't verify instead of glossing over it, and kept the project's
anti-fabrication discipline intact. Verification claims held up when I re-ran them.

The misses were in judgment rather than correctness: shipping a Dockerfile with an
unbuildable command and describing it as deployable, letting a dependency list crowd out the
Architecture section, and leaving a booby-trapped temp directory behind. All recoverable,
none of it architectural damage.

The project is on track. It has not gone off the rails.
