# Error Codes Reference

## Validation Error Codes

### E125 ALIAS_SUNSET_EXPIRED

**Trigger**: A canonical alias with a past `sunset_date` is used in a spec artifact.

**Resolution**: Replace the alias with the canonical term specified in the `replaced_by` field of the alias lifecycle block.

### E211 PARTIAL_DRIFT

**Trigger**: The same term maps to different canonical IDs across different spec artifacts (N-1 updated, 1 stale).

**Resolution**: Update the stale artifact(s) to use the current canonical ID. The error message includes per-artifact paths showing which file uses which canonical ID.

### E511 PLACEHOLDER_SCAN_MISMATCH

**Removed in v0.4.0**. E511 (`PLACEHOLDER_SCAN_MISMATCH`) was redundant with E510 independent placeholder scan. The associated sub-field has been removed.

### E561 / W561 UNCOVERED_FR

**Trigger**: A functional requirement defined in step 04 is not assigned to any milestone in step 14 (`fr_refs`).

**Resolution**: Add the FR ID to the appropriate milestone's `fr_refs` array in `14_roadmap.json`, or document why the FR is intentionally unscheduled.

### E562 / W562 ORPHAN_MILESTONE

**Trigger**: A milestone in step 14 is not referenced by any checklist item in step 16a.

**Resolution**: Either add FR references to the milestone or add checklist items that reference the milestone's tasks.

### E563 / W563 CHECKLIST_ROADMAP_MISMATCH

**Trigger**: A roadmap task exists in step 14 but has no corresponding checklist item in step 16a.

**Resolution**: Create a checklist item with `spec_ref.id` matching the roadmap `task_id`, or mark the task as deferred.

### E582 MILESTONE_REF_MISMATCH

**Trigger**: A checklist item's `milestone_ref` does not match the milestone that owns its `spec_ref.id` task in step 14.

**Resolution**: Update the checklist item's `milestone_ref` to match the milestone containing the referenced roadmap task.

### E150 / W150 SEED_MANIFEST_NOT_PROVIDED

**Trigger**: A step listed in `seed_manifest.json`'s `step_requirements` has no corresponding seed documents available, or a step outside the seed boundary (05+) incorrectly references seeds.

**Resolution**: Ensure the step's required seeds (as declared in `spec/common/seed_manifest.json` → `step_requirements`) are present and accessible.

**Promotable**: W150 → E150.

### W140 SEED_CONTENT_OVERLAP_LOW

**Trigger**: A spec artifact for a seed-consuming step (00–04) shares fewer than 3 content tokens with the seed documents required by `seed_manifest.json`.

**Resolution**: Either incorporate content from the required seed documents into the artifact or review whether the step truly depends on those seeds.

### E581 / W581 MILESTONE_REF_MISSING

**Trigger**: A non-deferred checklist item in step 16 lacks a `milestone_ref` field binding it to a step 14 milestone.

**Resolution**: Add a `milestone_ref` field to the checklist item with the `milestone_id` from step 14 that owns the referenced task.

**Promotable**: W581 → E581.

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

**Promotable**: W590 → E590.

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

**Trigger**: A prompt's extraction intent references an artifact from a step that is not in the step's `allowed_upstream_dependencies`.

**Resolution**: Either add the step to `allowed_upstream_dependencies` in step_order.json, or remove the reference from the prompt's extraction intent.

**Promotable**: No. W596 has different semantics from E596 (undeclared ref vs dead-end producer).

### E597 / W597 EXTRACTION_INTENT_UPSTREAM_GAP / EXTRACTION_INTENT_VAGUE

**Trigger (E597)**: A step's `allowed_upstream_dependencies` lists an upstream step, but the prompt's extraction intent has no entry for that upstream artifact.

**Trigger (W597)**: An extraction intent entry has vague text (fewer than 10 words or contains "relevant", "as needed", "as appropriate", "various", "TBD", "TODO").

**Resolution (E597)**: Add an extraction intent entry for the missing upstream artifact.

**Resolution (W597)**: Expand the vague intent text with specific field names and extraction purposes.

**Promotable**: W597 → E597.

### E598 EXTRACTION_INTENT_INVALID_REF

**Trigger**: An extraction intent entry references a step that does not exist in step_order.json's `steps` list.

**Resolution**: Fix the artifact reference to point to a valid step number.

**Promotable**: No (error only).

### E599 DAG_CONSUMER_INCONSISTENCY

**Trigger**: A step is listed in another step's `downstream_consumers`, but its own `allowed_upstream_dependencies` does not include the producer step.

**Resolution**: Ensure bidirectional consistency between `downstream_consumers` and `allowed_upstream_dependencies` in step_order.json.

**Promotable**: No (error only).

### E585 DAG_CIRCULAR_DEPENDENCY

**Trigger**: The `allowed_upstream_dependencies` graph contains a cycle.

**Resolution**: Remove the circular dependency from `allowed_upstream_dependencies` in step_order.json.

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

### Substep & Milestone Drift (58x)

### E580 / W580 SUBSTEP_DRIFT

**Trigger**: A substep reference in a checklist does not match the expected step structure.

**Resolution**: Update the substep reference to match the current step definition.

**Promotable**: W580 → E580.

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
