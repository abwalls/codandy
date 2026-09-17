# Evidence cards and plan comparison — Claude review

## Implemented

- `backend/app/boards.py`: server-owned EvidenceCard model; max 10 cards with 2,500-character summaries; revision-checked pin/removal; deduplication by origin/snapshot/revision; persistence and artifact snapshots. Findings add evidence_ids and captured_evidence, validated against the exact bounded review. Old artifacts still load; strict AI schema requires the new field in new responses. Historical plan Markdown includes its retained evidence even after a card is removed.
- `backend/app/routers/board_routes.py`: local-only source/case search (50 results per query), pinning from backend-retained data, deletion and generation provenance. No client-supplied summary or credential is accepted. Case cards distinguish observed stack from user notes; static cards do not imply runtime matching. Notes/text redacted before retention. No source bodies are included.
- `components/board-evidence.tsx`: explicit search/pin/remove, captured metadata, summary inspection and retention wording. Original source deletion does not cascade; removing a card affects later requests but existing plans retain their evidence until the board is deleted. Drawing-only exports do not silently claim to preserve evidence; evidence-bearing imports are rejected with instructions to re-pin locally.
- `lib/board-plan-comparison.ts` and its component: compare saved plan content by task ID, with field-level details, added/removed tasks, reordering and changed plan sections. Duplicate task IDs fail clearly. This does not claim semantic rename detection or completed implementation.

## Verified

- 327 backend tests, 51 frontend/API contracts, Ruff, TypeScript, changed-file ESLint and production build pass; existing dependency and bundle/plugin warnings remain.
- New regression cases cover stale revisions, persistence, deduplication, card limits, forged draft rejection, local-only routes, wrong source snapshot, redaction, deletion retention, exact citation allowlists, historical exports and strict schema/backward compatibility.
- A synthetic live request initially failed with the optional evidence_ids output schema. Making model output require every Finding field corrected it; the repeated live check cited the retained observation and kept the cause unknown. No personal evidence was submitted.
- Edge verified case card search/pin, redaction, retaining the copy after source deletion, explicit AI review and citation, removal, desktop/mobile and zero page errors. Mocked plan comparison passed changed task detail and mobile overflow checks; no mutations occurred.
- Source-node selection is covered by backend tests, not an additional live report browser flow. No live Linear/Sentry call was made.

## Review focus and limits

1. Retention UX versus old artifact snapshots: removing a card is intentionally not a purge of history; deleting the board removes all its retained copies.
2. Cards summarize bounded data and are not live links, full source bodies or verified source/runtime bindings. Do not upgrade their factual meaning.
3. Exact packet budgets may omit cards/elements; citations can only reference retained entries.
4. Strict output schema compatibility and default-empty evidence_ids for old storage.
5. Comparison depends on stable task IDs from the model. ID renames appear as removal/addition, not guessed equivalence.

Next: bounded Linear team pagination and optional targeting, then additional integration slices with explicit review before provider writes. See progress.md for publication checkpoint.
