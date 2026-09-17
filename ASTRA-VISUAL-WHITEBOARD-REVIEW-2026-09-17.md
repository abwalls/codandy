# Visual whiteboard review for Claude

## User-visible flow

1. Save a drawing, then choose **Interpret drawing visually**.
2. Review the sanitized PNG preview and exact text packet. Confirm both image contents and packet sharing, check the local AI connection, and choose model/effort.
3. Generate interpretation. Visual findings are marked visual_inference; ambiguous symbols, handwriting or relationships prompt questions.
4. Answer inline and apply answers to requirements. Autosave creates a new revision; review/reinterpret it before planning. Existing task cards, handoffs and reviewed Linear drafts remain unchanged.

## Implementation and review focus

- `backend/app/board_images.py`: allowlisted scene data, typed-text redaction, deleted/omitted element exclusion, strict PNG signature/chunks/CRC/dimensions and bounded decompression, metadata stripping, image hash bound into packet digest. No Pillow/new dependency. Bounds: 2 MiB, 2048 per dimension, RGB/RGBA8 noninterlaced. Handwriting cannot be scrubbed; explicit image review is required.
- `backend/app/routers/board_routes.py`: local-only visual-review preparation and bounded generation body; reject unapproved images, plan-stage image submissions and stale image/text/revision digests before model calls. Blocking completion runs in the worker threadpool. Existing text-only calls remain compatible.
- `backend/app/codex_bridge.py`: keyword-only image bytes become a temporary localImage file under the managed context directory. The TemporaryDirectory scope removes it on success or failure; tools remain disabled and threads ephemeral. No arbitrary path/URL from client input.
- `backend/app/boards.py` and `lib/board-api.ts`: optional backward-compatible artifact visual_input flag, visual_inference basis, citation validation including downstream plans derived from visual interpretations. No raw image is retained in board artifacts.
- `lib/board-image.ts`: lazy Excalidraw export of the server-sanitized scene, self-hosted assets, 2048px cap, no embedded scene, 2 MiB output cap.
- UI: separate image review checkbox; edits/load/generation clear approval; exact PNG displayed without optimizer changes. `board-questions.tsx` keeps answers by question index (duplicate strings do not collide), appends them as user answers and enforces the existing notes budget.

## Validation

- 322 backend tests and Ruff pass (two existing dependency deprecation warnings). New tests cover metadata stripping, invalid/unbounded PNGs, image-sensitive digest, typed-text scrubbing, hidden elements, image-required visual claims, citations, local-only routes, consent, stale image/revision rejection, questions/provenance and temporary-file cleanup on success/error.
- 49 frontend/API contracts pass, including Python/Zod visual provenance and rejection of remote image preview URLs. TypeScript and changed-file lint pass. Production build passes with existing bundle/plugin warnings.
- Edge mocked flow uses actual local board storage and PNG rendering, mocks only inference, verifies separate consent, questions, applying answers and 390px overflow. No page errors. Desktop image preview inspected.
- Two small synthetic live requests used the already connected default GPT-6-Astra with low effort. The first synthetic freehand fixture omitted simulated pressure and rendered invisibly; the model correctly reported it could not see the listed stroke. Corrected fixture rendered a pen stroke; the second request identified the visible API box and ambiguous freehand shape and asked three clarification questions rather than inventing meaning. Test boards deleted by their returned IDs. No personal board content or Linear/Sentry data used.

## Remaining limits

This is drawing interpretation, not verified code architecture. A matching element ID does not prove the model's reading is correct. Handwritten secrets are not automatically detected. A browser-generated preview is user-provided image evidence, not a server-attested rendering; the exact image must be reviewed. We do not accept external images/embeds, create tickets automatically, execute implementation tasks or attach to existing external chat threads. Other models/accounts were not live-tested. Future source/case evidence cards and plan comparison remain open.

Official protocol reference: https://learn.chatgpt.com/docs/app-server (turn/start image/localImage inputs).
See progress.md for publication details and resume point.
