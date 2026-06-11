# Error Codes Reference

## Validation Error Codes

### E110 UNKNOWN_CANONICAL_ID

**Trigger**: A `cn:`-prefixed ID used in a spec artifact is not registered in any loaded canon directory (toolkit core canon or project canon).  Commonly fires when `--spec-root` / `--git-root` are omitted and the project-level canon is not discovered, or when the ID is genuinely absent from all canon files.

**Resolution**: Run `specdev guide E110` for the full playbook.  Quick summary:
1. Re-run the check with the correct flags so the project canon is loaded:
   ```
   specdev spec-check spec --repo-root ./devspec_toolkit --spec-root ./spec --git-root .
   ```
2. If the ID is new, declare it in `canonical_proposals` in the artifact, then promote with `specdev canon-accept`.

**See also**: E120, E211.

### E520 UNRESOLVED_INPUT / SCHEMA_NOT_FOUND

**Trigger**: A validator could not resolve a required input and fails closed rather than crashing. Two message families share this code:
- `UNRESOLVED_INPUT` — a required directory, file, or spec input was missing or unreadable (e.g. `missing_spec_dir`, `missing_canon_dir`, `invalid_json`), or a CLI input precondition was not met.
- `schema_not_found` — the schema registry could not load the schema for a `$schema` URI. As of 1.1.0, `specdev validate` / `spec-check` fail closed on **all** registry I/O errors (previously only `FileNotFoundError` was caught; `PermissionError` and other `OSError`s now route here instead of escaping uncaught). The step-11 validator likewise emits a structured `E520` for malformed `threats[]` / `target_ids[]` entries that previously raised an unhandled `AttributeError`.

**Resolution**: Supply the missing input (pass the correct `--spec-root` / `--git-root`, create the expected `spec_dir`, or fix the malformed JSON). For `schema_not_found`, confirm the `$schema` URI is registered in `tools/schema_registry.json` and that the target schema file exists and is readable.

### E530 INVENTED_ENUM_OR_ID

**Trigger**: A value in a spec artifact does not match any allowed enum member, canonical ID, or registered entry.  The most common variant is a leading verb in a `command` field that is not in the toolkit or project allowlist.

**Resolution**: Run `specdev guide E530-INVENTED_ENUM_OR_ID` for the full playbook.  Quick summary: extend `spec/canon/command_prefixes.json` with the allowed verb, or register the verb as a canonical command entry and attach a sibling `command_ref`.

**See also**: E530-LINKED_TEST_FILE_NOT_FOUND, E110.

### E530 LINKED_TEST_FILE_NOT_FOUND

**Trigger**: A `linked_test_expectation` field contains a path-shaped token (containing a slash or a recognised extension: `.py`, `.ts`, `.js`, `.go`, `.java`, `.rb`, `.sh`, `.json`) that does not exist on disk.  `bash -c "..."` / `sh -c '...'` wrappers are unwrapped before the check.  Compound commands (`&&`, `||`, `;`) are skipped.

**Resolution**: Run `specdev guide E530-LINKED_TEST_FILE_NOT_FOUND` for the full playbook.  Quick summary: correct the path in the artifact with `specdev json patch`, or create the missing test file at the referenced path.

**See also**: E530-INVENTED_ENUM_OR_ID.

### E125 ALIAS_SUNSET_EXPIRED

**Trigger**: A canonical alias with a past `sunset_date` is used in a spec artifact.

**Resolution**: Replace the alias with the canonical term specified in the `replaced_by` field of the alias lifecycle block.

### E211 PARTIAL_DRIFT

**Trigger**: The same term maps to different canonical IDs across different spec artifacts (N-1 updated, 1 stale).

**Resolution**: Update the stale artifact(s) to use the current canonical ID. The error message includes per-artifact paths showing which file uses which canonical ID.

### E511 PLACEHOLDER_SCAN_MISMATCH

**Removed prior to 1.0.0**. E511 (`PLACEHOLDER_SCAN_MISMATCH`) was redundant with E510 independent placeholder scan. The associated sub-field has been removed.

### E535 CONTRADICTORY_OUT_OF_SCOPE_FR

**Trigger**: A functional requirement appears in both `apis.out_of_scope[]` in step 05 (declaring it has no HTTP API surface) and in an API's `trace[]` in the same step 05 file (declaring it is covered by an API endpoint). The two claims are mutually exclusive.

**Resolution**: Remove the FR from `out_of_scope[]` if an API does cover it, or remove the trace reference from the API if the FR genuinely has no API surface.

**Note**: `out_of_scope[]` entries suppress W564 (UNCOVERED_FR_API). Without this check, a contradicted `out_of_scope[]` entry would silently mask a real API trace from coverage reporting.

### E541 UNBOUND_CANONICAL_TERM

**Trigger**: A free-text field (e.g. a `description`, `rationale`, or `intent`) mentions a canonical term registered in `canon/` without a sibling binding reference (a `*_ref` slot) that pins the term to its canonical ID. The mention reads as an unbound, hallucination-prone reference.

**Resolution**: Add the appropriate `*_ref` (e.g. `fr_ref`, `capability_ref`, `term_ref`) alongside the free-text field to bind the canonical term to its ID, or reword the field so it no longer names the canonical term.

**Note**: E541 is suppressed through three independent mechanisms; a free-text field is checked only if none of them apply:

1. **Structural suppression** (as of 1.1.0) — fields whose enclosing object is *structurally unbindable*: the object's schema sets `additionalProperties: false` and declares no `*_ref`/`*_refs` slot, so it physically cannot carry a binding reference. Ref-capable objects (e.g. `14_roadmap` milestones with `fr_refs`/`capability_refs`) still fire E541, so legitimate unbound mentions are not over-suppressed.

2. **Term-specific runtime suppression** (the `bound_refs` path) — when a sibling `*_ref`/`*_refs` key is present at the same object level, it suppresses E541 only for the specific term(s) it binds: suppression applies when one of the ref's *values* is one of the mentioned term's canonical IDs. An unrelated reference (binding a different ID) does **not** suppress, so a genuinely unbound term in the same object still fires. (Prior to this release the check was object-level — any ref present suppressed every free-text field — which over-suppressed legitimate unbound mentions.)

3. **Key-name skip fallback** (the `_E541_SKIP_KEYS` / `_E541_SKIP_KEYS_BY_FILE` path) — certain keys are always exempt regardless of schema, because their subtrees are vocabulary definitions or free-form runner output rather than spec content that should bind refs (e.g. the `execution` subtree's `test_results[].name`). This key-name skip is the only active suppressor for artifacts with no resolvable `$schema` (where structural suppression is inactive).

### E561 / W561 UNCOVERED_FR

**Trigger**: A functional requirement defined in step 04 is not assigned to any milestone in step 14 (`fr_refs`).

**Resolution**: Add the FR ID to the appropriate milestone's `fr_refs` array in `14_roadmap.json`. If the FR has no implementation surface (e.g. an infra or ops constraint), add it to `out_of_scope[]` in `05_interface_contracts.json` with a non-empty rationale — that exempts it from W561, W564, and W566.

### E562 / W562 ORPHAN_MILESTONE

**Trigger**: A milestone in step 14 is not referenced by any checklist item in step 16a.

**Resolution**: Either add FR references to the milestone or add checklist items that reference the milestone's tasks.

### E563 / W563 CHECKLIST_ROADMAP_MISMATCH

**Trigger**: A roadmap task exists in step 14 but has no corresponding checklist item in step 16a.

**Resolution**: Create a checklist item with `spec_ref.id` matching the roadmap `task_id`, or mark the task as deferred.

### E564 / W564 UNCOVERED_FR_API

**Trigger**: A functional requirement defined in step 04 has no API trace reference — no API in step 05 has a trace link with type "fr" pointing to this FR.

**Resolution**: Add a trace link of type "fr" in the appropriate API contract in `05_interface_contracts.json`. If the FR genuinely has no HTTP API surface (infra, ops, external constraint), add it to `out_of_scope[]` in `05_interface_contracts.json` with a non-empty rationale — that suppresses W564, W561, and W566 for that FR. See also E535 for the contradiction check.

**Promotable**: W564 → E564.

### E565 / W565 UNCOVERED_FR_FIXTURE

**Trigger**: A functional requirement defined in step 04 has no fixture coverage — no fixture in step 08 has a target with type "fr" pointing to this FR.

**Resolution**: Add a fixture in `08_fixtures.json` with a target referencing the FR, or document why the FR requires no fixture.

**Promotable**: W565 → E565.

### E566 / W566 UNCOVERED_FR_MILESTONE

**Trigger**: A functional requirement defined in step 04 is not referenced in any step 14 milestone `fr_refs`.

**Resolution**: Add the FR ID to the appropriate milestone's `fr_refs` array in `14_roadmap.json`. If the FR has no implementation surface, use `out_of_scope[]` in `05_interface_contracts.json` with a non-empty rationale — that exempts it from W566, W564, and W561.

**Promotable**: W566 → E566.

### E567 / W567 INCOMPLETE_MILESTONE_DECOMPOSITION

**Trigger**: A milestone in step 14 has no tasks, or the milestone's `fr_refs` are not covered by any task's `fr_refs`.

**Resolution**: Add tasks to the milestone, or ensure task `fr_refs` collectively cover the milestone's `fr_refs`.

**Promotable**: W567 → E567.

### E568 / W568 UNCOVERED_CAPABILITY

**Trigger**: A capability defined in step 01 has no functional requirement tracing to it. This replaces the former E560 `capability_without_fr` check.

**Resolution**: Add an FR in `04_fr_list.json` that traces to the uncovered capability, or remove the capability if it is no longer relevant.

**Promotable**: W568 → E568.

### E582 / W582 UNCOVERED_FR_REVIEW_COVERAGE

**Trigger** (E582): Fired in step 16 under two conditions: (1) a checklist item's `milestone_ref` names a milestone that does not exist in the step 14 roadmap; or (2) a non-deferred checklist item's `milestone_ref` does not match the milestone that owns its `spec_ref.id` task in the step 14 roadmap.

**Trigger** (W582): Fired in step 16c when a review artifact with `verdict: verified` has FRs declared in the corresponding step 14 roadmap milestone(s) that are not present in `semantic_review.fr_coverage`. If no milestone is scoped, the check runs against all milestones in the roadmap.

**Resolution**: For E582 — correct the checklist item's `milestone_ref` to match an existing step 14 milestone that owns the referenced task. For W582 — add the missing FR IDs to `semantic_review.fr_coverage` in the step 16c artifact, or verify that the FR is intentionally excluded.

**Promotable**: W582 → E582.

### E150 / W150 SEED_MANIFEST_NOT_PROVIDED

**Trigger**: A step listed in `seed_manifest.json`'s `step_requirements` has no corresponding seed documents available.

**Resolution**: Ensure the step's required seeds (as declared in `spec/common/seed_manifest.json` → `step_requirements`) are present and accessible.

**Promotable**: W150 → E150.

### W140 SEED_CONTENT_OVERLAP_LOW

**Trigger**: A spec artifact for a seed-consuming step shares fewer than 3 content tokens with the seed documents required by `seed_manifest.json` for that step. Applies to any pipeline step (00–16c) for which `step_requirements` declares seeds.

**Resolution**: Either incorporate content from the required seed documents into the artifact or review whether the step truly depends on those seeds.

### W551 UNDECLARED_SEED

**Trigger**: An on-disk seed file (under a directory declared in the manifest's `seeds[].path` entries) is not declared in the `seeds[]` array of `spec/common/seed_manifest.json`.

**Resolution**: Either add the file to the `seeds[]` array in `seed_manifest.json` with an appropriate `seed_id` and `path`, or remove the undeclared file from the seed directory.

### W553 SEED_STEP_UNKNOWN

**Trigger**: A key in `seed_manifest.json` `step_requirements` is not a recognized pipeline step in `step_order.json` (e.g. a typo such as `"9"` instead of `"09"`, a non-existent step `"02b"`, or an out-of-range value `"17"`). Real pipeline steps including `"16"`, `"16a"`, `"16b"`, and `"16c"` do not trigger this warning.

**Resolution**: Fix the typo in the `step_requirements` key to match a real step ID, or remove the phantom entry.

**Note**: W553 was previously named `SEED_STEP_OUT_OF_RANGE` (fired for any step outside 00–02a). It was repurposed in DEVSPEC-43 to fire only on genuinely unknown steps, enabling seed routing to all pipeline steps.

### W554 HARDCODED_SEED_REFERENCE

**Trigger**: A prompt file contains a literal `seed_*.md` filename (matched by the pattern `seed_\w+\.md`). `spec/common/seed_manifest.json` is the authoritative source for seed names; hardcoding seed filenames in prompts duplicates that authority and drifts silently when seed names change.

**Resolution**: Remove the literal seed filename from the prompt. Reference seed documents through the manifest's `step_requirements` routing, not by name in prompt prose. Run `specdev hardcoded-seed-check` to identify all occurrences.

**Warning-only and non-promotable**: W554 has no E-counterpart (E554 is `CANON_ENUM_DRIFT`) and is excluded from `PROMOTABLE_PAIRS`, so neither `SPECDEV_WARNINGS_AS_ERRORS` nor `SPECDEV_PROMOTE_CODES` can escalate it to an error.

### E581 / W581 MILESTONE_REF_MISSING

**Trigger**: A non-deferred checklist item in step 16 lacks a `milestone_ref` field binding it to a step 14 milestone.

**Resolution**: Add a `milestone_ref` field to the checklist item with the `milestone_id` from step 14 that owns the referenced task.

**Promotable**: W581 → E581.

### W583 API_UNCOVERED_BY_THREAT

**Trigger**: Fired by the Step 11 (red-team) validator when Step 05 interfaces are present and a public API ID is not named by the `target_ids` (entries with `type: api`) of any threat in the artifact. Each public API should be targeted by at least one threat. The check only runs when Step 05 is present (`api_ids` is not None).

**Resolution**: Add a threat in Step 11 whose `target_ids` includes the uncovered API (`{"type": "api", "id": "<api-id>"}`), or confirm the API is intentionally outside threat scope.

**Warning-only and non-promotable**: W583 has no E-counterpart and is excluded from `PROMOTABLE_PAIRS`, so neither `SPECDEV_WARNINGS_AS_ERRORS` nor `SPECDEV_PROMOTE_CODES` can escalate it to an error.

### E604 / W604 TRACE_MATRIX_STALE

**Trigger** (W604): Fired by the Step 14 validator when `extras/trace_matrix.json` is missing, or when its modification time is older than `14_roadmap.json` — an mtime-based freshness heuristic indicating the trace matrix may not reflect the current roadmap. Only W604 is emitted; E604 is registered as the nominal error form but is not currently produced by any code path.

**Resolution**: Regenerate `extras/trace_matrix.json` so it post-dates `14_roadmap.json`, or confirm the staleness is benign (e.g. a checkout reordered file modification times).

**Warning-only and non-promotable**: W604 is excluded from `PROMOTABLE_PAIRS` because matrix staleness is advisory rather than a hard correctness failure; `SPECDEV_WARNINGS_AS_ERRORS` and `SPECDEV_PROMOTE_CODES` therefore do not escalate it. E604 exists in the registry as the same-named error form but is not wired to promotion.

### E210 CROSS_ARTIFACT_DRIFT

**Trigger**: Fired by the canonical-integrity check when an artifact's `canonical_refs_used[]` array drifts from the canonical references actually present in the document body. Three subcodes: `canonical_refs_used_missing` (a canonical ID is referenced in the body but absent from `canonical_refs_used[]`), `canonical_refs_used_extra` (an ID is listed in `canonical_refs_used[]` but not used in the body), and `unresolved_canonical_semantic` (a semantic field carries a value with no resolved canonical ref).

**Resolution**: For the `canonical_refs_used_*` subcodes, run `./tools/run_specdev.sh canonical-autofix <file> --write` to sync `canonical_refs_used[]` with the body. For `unresolved_canonical_semantic`, supply the missing canonical reference (declare it in `canonical_proposals` and run `canon-accept`, or correct the semantic value).

**Promotable**: No — error-only; there is no `W210` counterpart.

---

## R9 Error Codes — Validator & CI Enforcement

### Canon/Schema Alignment (55x)

### E551 SCHEMA_ENUM_EXTRA

**Trigger**: A JSON Schema enum contains values that are not present in the paired canonical kind.

**Resolution**: Remove the extra values from the schema enum, or register them in the canonical kind via `canon/manifest.json`.

**Promotable**: No (error only).

### E552 MISSING_PAIRED_SCHEMA

**Trigger**: A schema file referenced in the canon/schema pairing configuration does not exist on disk.

**Resolution**: Verify the schema path in the pairing config and ensure the schema file exists at the expected location.

**Promotable**: No (error only).

### E553 MISSING_ENUM_PATH

**Trigger**: A JSON path referenced in the canon/schema pairing configuration does not exist in the target schema.

**Resolution**: Fix the JSON path in the pairing config to match the actual schema structure, or add the missing enum field to the schema.

**Promotable**: No (error only).

### W552 POTENTIAL_UNREGISTERED_PAIRING

**Trigger**: An unregistered schema enum has high overlap (>=80%) with a canonical kind, suggesting a pairing should be declared.

**Resolution**: Add an explicit pairing entry in the canon/schema alignment configuration, or document why the overlap is coincidental.

**Promotable**: No (warning only — advisory for canon maintenance).

### E554 CANON_ENUM_DRIFT

**Trigger**: A JSON Schema enum does not include all values defined in the canonical registry for that kind.

**Resolution**: Add the missing canonical values to the schema enum, or register the missing values in `canon/manifest.json`.

**Promotable**: No (error only).

### E555 SEMANTIC_COVERAGE_REGRESSION

**Trigger**: IDs present in the old version of an upstream artifact are absent from the new version, indicating dropped coverage.

**Resolution**: Restore the dropped IDs or update all downstream artifacts that reference them.

**Promotable**: No (error only).

### Cross-Step Validation (59x)

### E590 / W590 CROSS_STEP_ID_NOT_FOUND / CROSS_STEP_UPSTREAM_MISSING

**Trigger (E590)**: A spec artifact references an ID (FR, API, INV, NFR, capability, governance label) that does not exist in the upstream artifact.

**Trigger (W590)**: The upstream artifact file is missing entirely; cross-step validation is skipped for that upstream.

**Resolution (E590)**: Fix the broken ID reference to match an ID that exists in the upstream artifact.

**Resolution (W590)**: Generate the missing upstream artifact first, then re-validate.

**Promotable**: No. W590 (CROSS_STEP_UPSTREAM_MISSING — upstream file absent) and E590 (CROSS_STEP_ID_NOT_FOUND — ID absent from a present file) describe different defects with different resolutions. Promoting W590 to E590 would mislabel a missing-file condition as a broken ID reference, so W590 stays a warning; a fatal "upstream missing" would require a dedicated E-code.

### E591 / W591 EXTRACTION_INTENT_EMPTY

**Trigger**: A prompt has a `### Extraction Intent` section header but no parseable artifact entries beneath it.

**Resolution**: Add extraction intent entries listing each upstream artifact and what to extract from it.

**Promotable**: W591 → E591.

### E592 / W592 COVERAGE_THRESHOLD_BREACH / COVERAGE_THRESHOLD_WARN

**Trigger**: The traceability matrix FR coverage percentage falls below the configured threshold in `tools/step_order.json` → `coverage_thresholds.fr_coverage` (default: 80%).

**Resolution**: Increase FR coverage by adding API contracts, fixtures, or NFR bindings for uncovered FRs.

**Promotable**: W592 → E592. Mode controlled by `coverage_thresholds.mode` in step_order.json (`"warn"` or `"error"`).

### E593 / W593 VAGUE_LANGUAGE_FREE_TEXT

**Trigger**: A free-text field (description, statement, rationale, justification, notes, narrative, postconditions, preconditions, risks, spikes, migration_plan, definition) contains vague quantifiers (few, some, many, several, various, appropriate, adequate, sufficient, reasonable, significant, typical, generally, usually, fast, reliable, easy, hard, quick).

**Resolution**: Replace vague language with specific, measurable terms.

**Promotable**: W593 → E593. Note: W571 is emitted for vague language in `assumptions` fields specifically.

### E594 / W594 CONTENT_DERIVATION_LOW_OVERLAP

**Trigger**: A downstream artifact's free-text content shares fewer than the configured threshold (default: 5) of distinct tokens with its declared upstream artifacts.

**Resolution**: Ensure downstream content is derived from upstream artifacts. Review extraction intent and incorporate upstream terminology.

**Promotable**: W594 → E594. W594 is advisory by default — content derivation is heuristic with inherent false-positive risk.

### E595 / W595 CONTENT_STALENESS

**Trigger**: An upstream artifact has been modified with new content tokens, but none of those new tokens appear in downstream artifacts that consume it.

**Resolution**: Review the upstream changes and update downstream artifacts to reflect the new content.

**Promotable**: W595 → E595.

### E596 DAG_DEAD_END_PRODUCER

**Trigger**: A non-terminal step has zero entries in `downstream_consumers` in step_order.json.

**Resolution**: Add the consuming steps to the step's `downstream_consumers` array in `tools/step_order.json`.

**Promotable**: No. E596 is error-only (emitted by dag-lint).

### W596 UNDECLARED_UPSTREAM_REF

**Trigger**: A prompt's extraction intent references an artifact from a step that is not in the computed allowed upstream steps (all steps preceding the current step in `tools/step_order.json`).

**Resolution**: Either adjust the step ordering in `steps` so the referenced step precedes the current step, or remove the reference from the prompt's extraction intent.

**Promotable**: No. W596 has different semantics from E596 (undeclared ref vs dead-end producer).

### E597 / W597 EXTRACTION_INTENT_UPSTREAM_GAP / EXTRACTION_INTENT_VAGUE

**Trigger (E597)**: A step has an allowed upstream step (computed at runtime from the `steps` order in step_order.json), but the prompt's extraction intent has no entry for that upstream artifact.

**Trigger (W597)**: An extraction intent entry has vague text (fewer than 10 words or contains "relevant", "as needed", "as appropriate", "various", "TBD", "TODO").

**Resolution (E597)**: Add an extraction intent entry for the missing upstream artifact.

**Resolution (W597)**: Expand the vague intent text with specific field names and extraction purposes.

**Promotable**: No. W597 (EXTRACTION_INTENT_VAGUE) and E597 (EXTRACTION_INTENT_UPSTREAM_GAP) have different semantics — vague text in a present entry vs. a missing entry for a required upstream artifact. W597 has no fatal counterpart and is not promoted; promoting it would mislabel a vague entry as an upstream gap.

### E598 EXTRACTION_INTENT_INVALID_REF

**Trigger**: An extraction intent entry references a step that does not exist in step_order.json's `steps` list.

**Resolution**: Fix the artifact reference to point to a valid step number.

**Promotable**: No (error only).

### E599 DAG_CONSUMER_INCONSISTENCY

**Trigger**: A step is listed in another step's `downstream_consumers`, but the consumer step does not appear after the producer in the `steps` ordering (i.e., the consumer precedes or equals the producer in the `steps` list).

**Resolution**: Ensure `downstream_consumers` entries are consistent with the positional ordering of steps in `tools/step_order.json`. Every declared consumer must appear after its producer in the `steps` list.

**Promotable**: No (error only).

### E585 DAG_CIRCULAR_DEPENDENCY

**Trigger**: The computed upstream dependency graph (derived from `steps` positional order) contains a cycle.

**Resolution**: Remove the circular dependency from the `steps` ordering in `tools/step_order.json`.

**Promotable**: No (error only).

### Vague Language & Quality (57x)

### E571 / W571 ASSUMPTION_VAGUE_QUANTIFIER

**Trigger**: An assumption in the `assumptions` array contains vague quantifiers.

**Resolution**: Replace vague language with specific, measurable terms.

**Promotable**: W571 → E571.

### E572 / W572 ASSUMPTION_COUNT_HIGH

**Trigger**: The number of assumptions exceeds the configured threshold.

**Resolution**: Review assumptions and remove or consolidate redundant entries.

**Promotable**: W572 → E572.

### E573 / W573 ASSUMPTION_UNBOUND_ID

**Trigger**: An assumption references an ID that cannot be resolved to any known artifact.

**Resolution**: Bind the assumption to a valid spec artifact ID or remove the reference.

**Promotable**: W573 → E573.

### W570 GRACEFUL_SKIP

**Trigger**: A validator cannot resolve an optional upstream input needed for a cross-reference check, so it skips that check rather than emitting a false unresolved-reference error. W570 is a general graceful-skip signal emitted from several validators (`hallucination_lint`, `traceability_closure`, `seed_lint`, `canonical/autofix`, and the step-16 validator) whenever a dependency they would cross-check is absent. The representative case is the NFR-ref check in `hallucination_lint`: when `spec/07_nfrs.json` is absent, `nfr_refs` in downstream artifacts (e.g. `13_impl.json`) cannot be validated, so the linter records `W570 GRACEFUL_SKIP nfr_refs 07_nfrs.json_absent` and proceeds without flagging any `nfr-*` reference as unresolved. Each emitter's message payload names the specific check and the missing input.

**Resolution**: None required — the skip is intentional and informational. To make the skipped check actually run, provide the missing upstream artifact named in the message (e.g. `spec/07_nfrs.json` via the step-07 NFR prompt) and re-run the validator.

**Promotable**: No. W570 has no `E570` counterpart — a graceful skip is the *absence* of a checkable condition, not a defect, so there is nothing to promote to an error.

### Substep & Milestone Drift (58x)

### E580 / W580 SUBSTEP_DRIFT

**Trigger**: A substep reference in a checklist does not match the expected step structure.

**Resolution**: Update the substep reference to match the current step definition.

**Promotable**: W580 → E580.

### E608 TOOLKIT_VERSION_MISMATCH

**Trigger**: Fires in any of three cases: (1) `spec/specdev_version` is absent or is present but malformed / missing the `toolkit_version` key; (2) the active toolkit version cannot be read from `tools/pyproject.toml` (file missing or unparseable); (3) the `toolkit_version` recorded in `spec/specdev_version` differs from the active toolkit version.

**Resolution**: Run `specdev update <spec_dir>` to sync your project to the current toolkit version. When there are no schema changes, `update` re-stamps `spec/specdev_version` instantly. When schema changes are required, it directs you through the `specdev align` flow (`apply --auto`, optionally `prompts`, then `validate`), finalizing with `specdev align validate <spec_dir>` — which runs full post-migration validation and stamps the new version with a migration-history entry.

**Promotable**: No (error only).

### W615 / E615 INVARIANT_UNEXERCISED_BY_THREAT

**Trigger**: A step-06 invariant has a non-empty `risk_category_ref` field (marking it as security-relevant) but no step-11 threat has a mitigation of type `inv` referencing its `inv_id`. This indicates that a security-relevant invariant is not exercised by any threat in the red-team assessment, creating a gap between invariant definitions and threat coverage.

Only fires when step 06 is present (absent step-06 file → check skipped silently). Invariants without a `risk_category_ref` are not flagged — only those explicitly marked as belonging to a risk category are expected to have a corresponding threat.

**Resolution**: Either add a threat in `11_redteam.json` with a mitigation of type `inv` referencing the flagged `inv_id`, or remove `risk_category_ref` from the invariant if it is not genuinely security-relevant.

**Promotable**: W615 → E615 (via `SPECDEV_WARNINGS_AS_ERRORS=1` or `SPECDEV_PROMOTE_CODES=W615`).

### Step-16 Anchor Validation (W611 / W612)

#### W611 ANCHOR_DRIFT_SUPPRESSED

**Trigger**: The Trinity Anchor's `impl_context/` directory contains one or more JSON files, but none of them declare `$schema='vc:16-impl-context'`, so every per-milestone plan was filtered out (typically because each tripped W588/W589). With zero surviving milestone contexts, the cross-milestone E308 (scope drift) and E309 (checklist drift) checks are completely suppressed — the anchor looks clean while contributing nothing to drift detection. Does not fire when `impl_context/` is genuinely empty (`files_seen == 0`), which is a valid state for a fresh anchor.

**Resolution**: Fix the W588/W589 warnings reported above the W611 line so the per-milestone plans are recognized (correct each plan's `$schema` to `vc:16-impl-context`). Once at least one plan survives filtering, E308/E309 drift detection is restored.

**Promotable**: No. W611 flags a suppressed-coverage condition, not a concrete drift defect; it has no `E611` counterpart.

#### W612 ANCHOR_PHANTOM_MILESTONE

**Trigger**: A `milestone_index` entry in the Trinity Anchor names a `milestone_id` that does not match any `milestone_id` in `14_roadmap.json`. Phantom milestones bypass ownership, prefix, and scope-drift detection, so the mismatch is surfaced as a warning. Only checked when `14_roadmap.json` is present and readable.

**Resolution**: Verify the `milestone_id` is not a typo. Either correct it to reference an existing roadmap milestone, or add the milestone to `14_roadmap.json` if it is legitimately new (replaying the step-14 roadmap step).

**Promotable**: No. W612 has no `E612` counterpart — a phantom-milestone reference is advisory because the roadmap may legitimately lag a freshly-scaffolded anchor.

## Exception Classes

### SubmoduleDetectionError

**Module**: `specdev_tools.core.errors`

**Raised when**: The toolkit cannot detect the git root in a submodule deployment.

**Common triggers**:
- Running from a detached HEAD state in the submodule
- `--repo-root` pointing to the wrong directory

**Resolution**: Pass `--git-root` pointing to the host repo's git root, and `--spec-root` pointing to the spec directory.

### SchemaRegistryError

**Module**: `specdev_tools.core.errors`

**Raised when**: A schema URI cannot be resolved from `tools/schema_registry.json`.

**Common triggers**:
- Missing entry in `tools/schema_registry.json`
- `--repo-root` not pointing to the toolkit directory
- Schema file referenced in the registry doesn't exist on disk

**Resolution**: Check `tools/schema_registry.json` for the expected URI mapping and verify `--repo-root` points to the devspec_toolkit directory.
