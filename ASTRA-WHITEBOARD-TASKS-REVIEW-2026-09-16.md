# Whiteboard planning review for Claude

## Changes to review

- Includes the previously interrupted checkpoint in ASTRA-DRAWING-SENTRY-REVIEW-2026-09-16.md: direct drawing, source ticket receipts, Sentry browsing and portable dev runtime.
- backend/app/boards.py includes bounded group IDs and clears unavailable container/frame references from the reviewed digest. The reading guide counts freehand, unlabeled shapes, unbound connectors and omissions. Counts describe saved input, not model capabilities or code evidence.
- Plan output endpoint now returns the structured plan and artifact/revision IDs alongside the existing Markdown. lib/board-api.ts validates the task fields.
- components/board-plan-tasks.tsx renders acceptance and verification lists, proposed paths, assistant handoff export/copy, and individual reviewed Linear drafts. Receipt source IDs are JSON tuples of board, plan artifact and task. A regenerated plan is a separate source; cross-version semantic duplicate detection is not implemented.
- Whole-plan ticket creation remains available under a disclosure. Task dependency IDs are written as text, not provider issue links. No bulk create or automatic external writes.
- Recommendation ticket editors now reset when repository/revision scope changes, preventing an old editor draft from carrying into a different report.

## Validation

- 309 isolated backend tests passed; Ruff and TypeScript/changed-file ESLint passed. Existing two dependency deprecation warnings remain.
- 47 existing frontend contracts passed; one new Python-to-TypeScript task output contract added for the final validation run.
- Mocked Edge workflow passed reading guide, context download, plan task rendering, individual ticket draft, assistant handoff download, edit invalidation and 390px mobile overflow checks. No page errors. Desktop screenshot inspected.
- Production build passed with existing bundle/plugin warnings.
- No live AI inference, Sentry calls or Linear writes were used for QA. The earlier direct-drawing save/reopen and Sentry browse browser tests passed in the interrupted checkpoint.

## Review focus / remaining work

1. Stale plan gating, task source identity, and preservation of existing output/download contracts.
2. Digest bounds/group handling and distinctions between user drawings and verified code.
3. Vision is still NOT implemented: pen strokes require text explanations. Next vision spike should verify local Codex image input, constrain/redact the visible payload and require explicit image review; don't silently upload an entire raw canvas.
4. Add evidence cards from retained snapshots/cases, structured clarification answers, plan-version comparison and fuller Linear targets before broadening providers.
5. Live provider validation needs user-configured accounts. Local-only boards and AI remain unavailable in the hosted preview.

See progress.md for the final publication/runtime checkpoint.
