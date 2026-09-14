# Review notes for Astra 6

**From:** Claude (Opus 5), acting as reviewer on this project
**Date:** 2026-09-12
**Subject:** Review of the "Continued v1 completion" slice, and how we're working together

---

## How this works

Andrew has set up a specific arrangement, and it's worth stating plainly so we don't trip
over each other.

**You do the heavy lifting.** You are the primary implementer on Code Atlas. Features,
refactors, rule logic, UI work — that's yours unless Andrew explicitly hands a task to me.

**I review.** My job is to check your work for bugs, incomplete tasks, and drift, and to
keep the project on the roadmap. Think of it as a code review or a technical interview
where I'm asking the questions. I will verify claims rather than take them on trust — not
as an insult, but because that's the job. When I say "verified," I ran it.

**I will not silently rewrite your work.** If I find something, I write it up here with a
file and line and a suggested direction, and leave the fix to you. I'll only make direct
code changes when Andrew asks me to, or for something trivial and mechanical that would be
wasteful to hand back.

**Standing constraint right now:** Andrew has explicitly deferred the Dockerfile. Neither
of us should be rewriting it in this cycle. I've recorded the defects in it below so they
aren't lost, but do not action them until he says so.

A practical request: when you finish a slice, state what you verified and what you
*didn't*. Your last checkpoint did this well — flagging that the live smoke didn't run
rather than glossing it — and that made reviewing much faster. Keep doing that.

---

## What I verified, and what held up

I re-ran everything after your slice:

| Check | Result |
|---|---|
| `pytest` (backend) | **75 passed** |
| `ruff check .` | clean |
| `pnpm test:contracts` | **7 passed** |
| `tsc --noEmit` | clean |
| `pnpm build` | succeeds |
| ESLint (changed components) | clean |
| Live GitHub smoke | **passes** — I ran it; see note 7 |

Your verification claims were accurate. Specific credit where it's due:

- **You respected every "do not undo" item from the handoff.** The `tree-sitter>=0.25,<0.26`
  pin is intact (0.25.2 installed), the non-ASCII arrow in `reporting.py` is still there,
  `PYTHONIOENCODING` is still in the contract test, and `key={selected.path}` is still on
  `SourceView`. That pin in particular was load-bearing — widening it reintroduces
  segfaults — and you left it alone. Good.
- **You audited the handoff before building on it** rather than assuming. That's the right
  instinct.
- **You kept `PlaceholderSection` for the deferred debugging view** instead of deleting it.
  That matched Andrew's instruction correctly: he objected to *deleting* placeholders, not
  to implementing them, and you read that the right way.
- **The new report rules are epistemically honest.** `inferred_boundary` is
  `basis="inferred"` at 70% with "structural hint, not proof of a runtime layer or
  dependency direction." `external_dependency` is `observed`/100% with "not installed or
  executed... runtime role is not inferred from the dependency name alone." That's exactly
  the discipline this project needs, and it's the hardest thing to get right in a tool that
  makes architectural claims. Don't lose it.
- **The sample sections stay visibly illustrative** — the amber "Sample report ·
  illustrative data" banner, "illustrative confidence," and "This is a static sample path.
  It is not a runtime trace."
- **`.env.example` covers all 13 `Settings` fields exactly.** No drift, nothing missing.

I also initially thought you'd shipped the two new report categories untested. I was wrong
— they're asserted at `backend/tests/test_reporting.py:36-39`, folded into the existing
structure test. Correcting that here so the record is accurate.

---

## Findings

Ordered by severity. Nothing here is fixed; all of it is yours.

### 1. The Dockerfile cannot build — `uv sync` has no `--system` flag

`backend/Dockerfile:15`

```dockerfile
RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --system
```

`--system` is a `uv pip install` flag, not a `uv sync` flag. uv rejects it outright:

```
error: unexpected argument '--system' found
  tip: a similar argument exists: '--system-certs'
```

The build fails at that layer. Verified against uv 0.12.13 by argument-parser probe; I
couldn't run a real `docker build` because Docker isn't installed in this environment.

There's a second defect stacked behind it: `uv sync` updates *"the project's environment"*
(i.e. `/app/.venv`), so even with `--system` removed, the bare `CMD ["uvicorn", ...]` won't
resolve `uvicorn` on `PATH`. You'd want `uv run uvicorn ...`, or
`ENV PATH="/app/.venv/bin:$PATH"`, or `uv pip install --system` (where `--system` *is*
valid).

The rest of the file is good — non-root uid 10001, git and ca-certificates only, disposable
`/tmp` workspace, locked dependencies, no repository tooling executed.

**Do not fix this yet.** Andrew has deferred it. The point of recording it is that
`progress.md` and `README.md` currently describe the backend as deployable on a container
platform, and it isn't. When this does get picked up, the honest move is either to fix the
file or to soften those two doc claims until it's been built once.

### 2. `external_dependency` swamps the Architecture section

`backend/app/reporting.py:73-78`

One report card per declared package, capped at 40. I measured it on a fixture with 32
dependencies:

```
architecture items: 41
by category: {'project': 1, 'directory': 2, 'inferred_boundary': 5,
              'external_dependency': 32, 'shared_module': 1}
```

**78% of the Architecture section is a dependency list.** Each card carries a constant
`metrics={"manifest_declarations": 1}`, and all 32 cite the same manifest file as evidence.
The genuinely informative items — projects, source layout, the five boundaries, shared
modules — get buried. On a real repo with 60+ dependencies it hits the cap and pushes
everything else off the first page.

This is a signal-to-noise problem, not a correctness one. A dependency list is inventory,
not architecture insight. Suggested direction: **one aggregated card** — "32 declared
dependencies" with the dependency nodes as `node_ids`. The `item()` helper already supports
this shape, and `EvidenceCard` in the frontend already renders up to 5 locations with a
"Show all N locations" expander. You'd get the same information at 1/32 the visual cost.

If you want per-package cards to stay, they probably belong in their own section or behind
the category filter rather than mixed into Architecture.

### 3. `categoryLabels` wasn't updated for the two new categories

`components/grounded-report.tsx:9-13`

The map has no entries for `inferred_boundary` or `external_dependency`, so both render as
raw snake_case in the category chip *and* in the category filter dropdown, sitting next to
properly-labelled "Source layout" and "Route paths". It degrades gracefully via the
`|| item.category` fallback, so nothing breaks — it just looks unfinished.

Two-line fix. Worth noting as a pattern: **adding a backend report category has a required
frontend counterpart.** Check that map whenever you add one.

### 4. `node.lines` is rendered unguarded in the sample codebase view

`components/code-atlas-workspace.tsx:520`

```jsx
<p ...>{node.path}:{node.lines}</p>
```

`AtlasNode.lines` is declared optional (`lines?: string` in `lib/atlas.ts:15`). All six
current demo nodes happen to have it, so this renders correctly today — it's safe by
accident of the fixture, not by construction. Add a node without `lines` and you get
`src/foo.ts:undefined` in the UI.

The codebase already has the correct idiom, in `components/live-report.tsx:57`:

```jsx
{item.path || "Repository root"}{item.lines ? `:${item.lines}` : ""}
```

Match it.

### 5. The sample flow labels every node as a sequential step

`components/code-atlas-workspace.tsx:519`

The flows view maps **all** of `demoAtlas.nodes` into a numbered "Step N" sequence under
the heading "User authentication". But the demo graph isn't linear. Its six nodes are:

```
LoginForm → route POST /api/auth/login → LoginHandler.Handle
                                          ├→ UserRepository.GetByEmail → Users
                                          └→ JwtTokenService.Generate
```

`GetByEmail` and `Generate` are siblings under `Handle`, not steps 4 and 5 of a chain. So
"Step 5" asserts an ordering that doesn't exist in the graph. Note that the older
`ArchitectureMap` deliberately filtered `method:csharp:JwtTokenService.Generate` out of its
flow rendering — the original author appears to have known it wasn't on the linear path.

It's sample data and it's labeled illustrative, and "This is a static sample path. It is
not a runtime trace" hedges it. But this project's whole value proposition is *not*
implying relationships the graph doesn't support, and numbering nodes 1-6 does imply one.
Either drive the ordering from the demo graph's edges, or drop the step numbers and present
them as participants rather than a sequence.

(Cosmetic, same line: six items in `md:grid-cols-5` leaves one orphan on a second row.)

### 6. Dead branch in `PlaceholderSection`

`components/code-atlas-workspace.tsx:530-560`

There's now exactly one call site (line 602), guarded by `section === "debugging"`. So the
`labels` map at line 544 and the entire "Foundation preview" block below it are
unreachable. Static analysis won't flag it — ESLint passes — because the code is
syntactically used inside the function.

Flagging rather than deleting, because Andrew's instruction was to keep placeholders. My
read is that the *debugging* placeholder is what he wants kept and this specific branch is
genuinely dead, but that's his call, not mine. Ask before removing.

Related: `SampleSection`'s `title` / `description` maps at line 497 are typed
`Record<string, string>` and cover only the four routed sections, with no fallback. The
old `PlaceholderSection` had `?? labels.architecture`. If a new `Section` is ever routed
to `SampleSection`, you get an empty `<h1>` and TypeScript won't catch it. Typing them
`Record<Section, ...>` or restoring a fallback would close that.

### 7. Two process notes

**`backend/.pytest-tmp` was left behind with broken ACLs.** Created 14:34 by your run, now
unreadable by the account — `ls` gives "Permission denied" and even `Get-Acl` is denied.
This is the same pathology as `%LOCALAPPDATA%\Temp\pytest-of-andre`, and it means the
command documented in `progress.md` (`--basetemp=.pytest-tmp`) now fails with **40 spurious
errors that look exactly like real test failures.** I had to use a different basetemp to
get a clean run. Clearing it needs an elevated shell.

Please clean up scratch directories at the end of a slice. This one is actively booby-trapped
for the next person — the failure mode looks like a broken test suite, not a stale directory.

**"This environment cannot reach GitHub" doesn't hold here.** `github.com` returns 200 and
`git ls-remote` succeeds from this session, so I ran the live smoke against your code and
it passes: commit `19c71f2c`, 24 files, 15 symbols, 133 relationships, workspace cleaned,
source endpoint serving `src/App.tsx` and rejecting `../../../etc/passwd`. Your checkpoint
was honest that it hadn't run and wasn't hiding a failure, which is the right call — this
looks like a sandbox difference on your side, not a bad claim. The gap is now closed.

---

## One architectural thing to keep in view

`progress.md` and `README.md` now describe a container deployment path, but the backend has
**no persistence of any kind**. All state is four in-memory dicts in `JobStore` — `jobs`,
`events`, `results`, `sources` — and `jobs.py`'s own docstring says "Reports disappear on
API restart."

Consequences for anything hosted:

- Every redeploy or restart drops all reports.
- `max_jobs = 10`, FIFO eviction; the 11th analysis evicts the first.
- Retained source text is RAM: up to 4 MB per report × 10 ≈ 40 MB ceiling.
- `ThreadPoolExecutor(max_workers=1)` plus a 429 on concurrent submit — structurally
  single-tenant.
- **More than one replica breaks the client.** A browser polling
  `/analyses/{id}/events` or fetching `/atlas` can land on a replica that has never heard
  of its job and get a 404.

None of that is a bug — it's M4 ("saved reports, commit freshness, incremental
re-analysis"), which is an unstarted milestone. But it means containerizing is not the same
as being hostable, and the docs shouldn't let those blur together. Shared state is a
prerequisite for the hosting step, not a follow-up to it.

---

## Ground rules going forward

1. **Don't touch the Dockerfile** until Andrew reopens it.
2. **Don't widen `tree-sitter>=0.25,<0.26`** without re-running the analyzer against a real
   multi-file repository. A synthetic fixture does *not* reproduce the 0.26.0 memory
   corruption — that was tried during the investigation and passed while real sources
   crashed 100% of the time. `backend/tests/test_grammars.py` is the gate.
3. **Keep the anti-fabrication discipline.** Explicit unsupported states beat speculative
   findings. Every inferred item needs `basis`, confidence, and a limitation that says what
   it does *not* prove. You've been good about this.
4. **Clean up scratch artifacts** before finishing a slice.
5. **Adding a report category means updating `categoryLabels`.**
6. **State what you verified and what you didn't.** Test counts, which commands you ran,
   what you couldn't run and why.
7. If you disagree with a finding here, say so in your next checkpoint with your reasoning.
   Several of these are judgment calls, and I'd rather have the argument than have you
   silently comply with something you think is wrong.

See `ROADMAP.md` for where this all sits against the plan.
