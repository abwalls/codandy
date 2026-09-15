# Diagram review — 2026-09-15

Reviewed Claude's V0–V2 and AD0–AD2 implementation at 50ab730, plus its handoff. Keep the separate structure-0.1 contract, declared-versus-live labels, unresolved stubs and legacy report compatibility.

## Verified defects, fixed in this review

1. **Token values in type annotations were retained.** `clip()` compacted and truncated raw annotation text without scrubbing. A GitHub-style sentinel inside a Literal annotation survived. The regression `test_contract_type_text_scrubs_tokens_before_clipping` failed before the fix and passes after. Scrubbing now runs before clipping; this is best-effort pattern redaction, not a guarantee against every secret.
2. **Generic parameters created false type links.** `interface Target {}; interface Box<Target> { value: Target }` linked Box to the unrelated file-level Target as resolved. `test_generic_type_parameters_do_not_link_to_unrelated_types` failed before the fix and passes after. TypeScript declaration-level type parameters now shadow repository names when building links.
3. **Optional extraction could discard a completed atlas.** The worker only sent its atlas after diagram extraction. A hard timeout during extraction therefore failed the whole analysis despite the documented fallback. The worker now emits a validated atlas checkpoint first; timeout/EOF/process exit after that checkpoint returns the atlas with an unavailable-diagrams limitation. `test_optional_structure_timeout_preserves_completed_atlas` covers a deliberately stalled extractor worker. Ingestion failure before the checkpoint still fails normally.

## Validation and remaining review

17 structure/worker tests passed after these fixes. Full tests and visual QA are recorded in progress.md. No analyzed repository code was executed.

Suggestions: broader compiler-level type binding and additional language/ORM fixtures remain useful. Architecture-pattern diagrams should label a user's proposed pattern or show specific supporting evidence; folder names alone cannot establish MVC, microservices or clean architecture. Keep static call order, observed failure stacks and timed spans as separate sequence sources.
