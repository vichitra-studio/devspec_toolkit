# P1-C: Bloat & Over-Engineering -- Findings

## Summary
- Total findings: 10
- Critical: 0 | High: 2 | Medium: 4 | Low: 3 | Info: 1

---

## Findings

### FINDING-C01: `spec_refs_ingested` is dead schema -- zero tool consumers

- **Severity**: HIGH
- **Category**: BLOAT
- **Location**: All 19 step schemas (e.g., `schema/00_charter.schema.json` through `schema/16_impl_context.schema.json`); definition at `schema/core/collections.schema.json:specRefIngested` and `specRefsIngestedArray`
- **Description**: `spec_refs_ingested` is required in all 19 step schemas but has ZERO consumers in the tool codebase. No Python module in `tools/specdev_tools/` reads, validates, or acts on this field. Notably, `spec_quality_lint.py` (lines 175-183) checks 8 of the 10 common required fields and deliberately omits `spec_refs_ingested` (and `coverage_gaps`). Every prompt file includes `"spec_refs_ingested": []` as an empty array, and every test fixture populates it as `[]`.
- **Evidence**:
  - `grep -r "spec_refs_ingested" tools/specdev_tools/` returns **zero results**.
  - `spec_quality_lint.py:175-183` checks: `id`, `owner`, `created_at`, `seed_refs`, `generation_quality`, `canonical_refs_used`, `canonical_proposals`, `canonical_conflicts` -- 8 fields, skipping `spec_refs_ingested` and `coverage_gaps`.
  - `spec_refs_ingested` does NOT appear in `DRIFT_SENSITIVE_FIELDS` in `prompt_schema_sync.py:24-31`.
  - 38 occurrences across 19 schema files (2 per file: property definition + required array entry).
  - All 24+ prompt files reference it only as `"spec_refs_ingested": []`.
  - All test fixtures populate it as `[]`.
- **Recommendation**: Remove `spec_refs_ingested` from the `required` array in all 19 step schemas. Make it optional or remove entirely. The core definition (`specRefIngested`, `specRefsIngestedArray`) can remain in `core/collections.schema.json` for future use but should not be mandated. Update all prompt templates to remove or mark optional. Since it is NOT in `DRIFT_SENSITIVE_FIELDS`, removal will not break prompt-schema sync. However, 24+ prompt files will need their example JSON updated.

---

### FINDING-C02: `coverage_gaps` -- mandatory in 19 schemas, consumed by only 1 step validator

- **Severity**: MEDIUM
- **Category**: BLOAT
- **Location**: All 19 step schemas; consumer at `tools/specdev_tools/validation/validators/step_12.py:67-72`
- **Description**: `coverage_gaps` is required in all 19 step schemas but is only read by the Step 12 (CI Gates) validator, which checks `upstream_item_id` references against upstream spec files. No other validator, linter, or generator reads this field. Like `spec_refs_ingested`, `spec_quality_lint.py` deliberately skips it in its common required field checks (line 175-183). However, unlike `spec_refs_ingested`, `coverage_gaps` IS referenced in all 24+ prompt files with active instructions ("MUST be recorded in `coverage_gaps[]`") and serves a genuine traceability purpose for the AI generation workflow.
- **Evidence**:
  - `tools/specdev_tools/validation/validators/step_12.py:67-72`: Iterates `coverage_gaps` array, validates `upstream_item_id` against upstream spec files via `_check_ref()`.
  - No other module in `tools/specdev_tools/` reads `coverage_gaps`.
  - `coverage_gaps` does NOT appear in `DRIFT_SENSITIVE_FIELDS` (`prompt_schema_sync.py:24-31`).
  - All 24+ prompt files instruct LLMs: "MUST be recorded in `coverage_gaps[]` with: upstream_item_id, source_step, reason".
  - `spec_quality_lint.py` skips it in the 8/10 common field check.
- **Recommendation**: Keep `coverage_gaps` as a property in all 19 schemas (it serves a design-time traceability purpose in the prompt contract), but consider making it optional rather than required in schemas where no validator reads it (all schemas except step 12). Alternatively, add a cross-step `coverage_gaps` validator to `spec_quality_lint.py` to justify mandatory status. The deliberate omission from `spec_quality_lint.py`'s check list suggests the original authors considered it less critical than the other 8 fields.

---

### FINDING-C03: `generation_quality` -- mandatory overhead with minimal value payload

- **Severity**: MEDIUM
- **Category**: BLOAT
- **Location**: All 19 step schemas; definition at `schema/core/collections.schema.json:generationQuality`; consumers at `tools/specdev_tools/validation/spec_quality_lint.py:180` and `tools/specdev_tools/generation/prompt_schema_sync.py:27`
- **Description**: `generation_quality` is required in all 19 step schemas and IS actively consumed by 2 modules. However, its actual data structure contains only `{"assumptions": []}` -- a single string array. The question is whether this minimal-value object justifies mandatory status in every step. The field IS in `DRIFT_SENSITIVE_FIELDS` (prompt_schema_sync.py:27), meaning removal would break prompt-schema sync validation. A migration script (`strip_generation_quality.py`) already exists to normalize it to assumptions-only format, confirming it once had more fields that were stripped.
- **Evidence**:
  - `spec_quality_lint.py:180`: Checks presence in `_check_required_top_level()` -- will flag E520 if missing.
  - `prompt_schema_sync.py:27`: Listed in `DRIFT_SENSITIVE_FIELDS` -- schema-prompt drift detection will fire if the field changes.
  - `migration/scripts/strip_generation_quality.py`: Normalizes to `{"assumptions": <existing>}`, confirming historical bloat was already reduced.
  - `core/collections.schema.json:generationQuality`: Defines as object with only `required: ["assumptions"]` where `assumptions` is a `stringArray`.
  - All 24+ prompt files instruct: "`generation_quality` is REQUIRED. Populate `generation_quality.assumptions` with specific, testable claims."
- **Recommendation**: Keep `generation_quality` as required -- it is actively consumed by 2 modules, is a drift-sensitive field, and prompt contracts depend on it. However, consider whether the `assumptions` array could be promoted to a top-level `assumptions` field, eliminating the wrapper object overhead (19 schemas x unnecessary nesting). This would require updating `DRIFT_SENSITIVE_FIELDS`, all 24+ prompts, `spec_quality_lint.py`, and the `generationQuality` core definition. The migration cost is high enough that this is LOW priority.

---

### FINDING-C04: `spec_quality_lint.py` checks 8/10 common required fields -- intentional signal, not a bug

- **Severity**: INFO
- **Category**: BLOAT
- **Location**: `tools/specdev_tools/validation/spec_quality_lint.py:175-183`
- **Description**: The `_check_required_top_level()` function checks 8 of the 10 common required fields, deliberately skipping `spec_refs_ingested` and `coverage_gaps`. This is an intentional signal that these two fields were always considered less important than the other 8. The 8 checked fields (`id`, `owner`, `created_at`, `seed_refs`, `generation_quality`, `canonical_refs_used`, `canonical_proposals`, `canonical_conflicts`) are all actively consumed by at least one tool module. The 2 skipped fields have zero or near-zero tool consumers.
- **Evidence**:
  - Checked fields and their consumers:
    - `id`: Used by validators, linters, matrix (kebab-case ID validation)
    - `owner`: Validated by canonical integrity
    - `created_at`: Timestamp format validation
    - `seed_refs`: 11+ hits in `seed_lint.py` (hash verification, required seeds, unknown seeds)
    - `generation_quality`: `spec_quality_lint.py`, `prompt_schema_sync.py`
    - `canonical_refs_used`: `canonical/integrity.py`, `canonical/autofix.py`, `step_13.py`
    - `canonical_proposals`: `canonical/integrity.py`
    - `canonical_conflicts`: `canonical/integrity.py`
  - Skipped fields:
    - `spec_refs_ingested`: Zero tool consumers (FINDING-C01)
    - `coverage_gaps`: 1 consumer, step_12.py only (FINDING-C02)
- **Recommendation**: No action needed on the linter itself. This finding corroborates FINDING-C01 and FINDING-C02.

---

### FINDING-C05: `docs_policy` in seed_manifest -- well-consumed but location is debatable

- **Severity**: LOW
- **Category**: BLOAT
- **Location**: `spec/common/seed_manifest.json:58-82`; consumers at `tools/specdev_tools/validation/docs_lint.py:46-52` and `tools/specdev_tools/validation/validators/step_16.py:180-183`
- **Description**: `docs_policy` is consumed by 2 validators and is NOT dead. However, it lives in `seed_manifest.json`, which is semantically about "seed documents for the spec pipeline." Docs policy (README requirements, scope, exclusions, doc_paths) is not about seed documents -- it is about project-level documentation governance. Its co-location with seed data is architecturally confusing.
- **Evidence**:
  - `docs_lint.py:46-52`: Reads `readme_required`, `root_readme_required`, `readme_depth_default`, `readme_depth_by_scope`, `scope`, `exclusions` from `docs_policy`.
  - `step_16.py:180`: Reads `docs_policy.doc_paths` to validate docs_impact paths.
  - `seed_manifest.json:58-82`: Contains 6 sub-fields under `docs_policy` including `doc_paths` array.
  - `seed_manifest.schema.json`: `docs_policy` is in the `required` array.
- **Recommendation**: Consider moving `docs_policy` to `step_order.json` or a separate `docs_config.json` file. The seed manifest should remain focused on seed document registry. However, this is a LOW-priority structural concern -- the current approach works and is consumed correctly. If step_order.json gains a JSON schema (see P1-E), `docs_policy` would be a natural fit there.

---

### FINDING-C06: `nested_order` in seed_manifest -- consumed but low-value structure

- **Severity**: LOW
- **Category**: BLOAT
- **Location**: `spec/common/seed_manifest.json:11-20`; consumer at `tools/specdev_tools/validation/seed_lint.py:263-266`
- **Description**: `nested_order` is consumed by `seed_lint.py` to validate that referenced `seed_ids` exist in the seed registry. However, the current data shows only 1 layer (`"foundation"`) with the same 2 seeds as `global_seed_order`. The validation is a simple referential integrity check (does the seed_id exist?), which `global_seed_order` already receives (lines 259-261). The `nested_order` structure adds a hierarchical grouping concept (level_id + description + seed_ids) that is architecturally sound but currently adds no value beyond what `global_seed_order` provides.
- **Evidence**:
  - `seed_lint.py:263-266`: `for layer in manifest.get("nested_order", []): for sid in layer.get("seed_ids", []): if sid not in seed_id_set: errors.append(...)`.
  - `seed_manifest.json:11-20`: Single layer "foundation" with the same 2 seeds as `global_seed_order`.
  - `seed_manifest.schema.json`: `nested_order` is in the `required` array.
- **Recommendation**: Keep `nested_order` -- it provides a hierarchical grouping concept that will become valuable as projects grow beyond 2 seeds. However, it should be made optional (not required) in the schema, since small projects may not need hierarchical seed ordering. Current data shows it is redundant with `global_seed_order` for simple cases.

---

### FINDING-C07: `allowed_upstream_dependencies` in step_order.json -- well-consumed, not bloat

- **Severity**: LOW
- **Category**: BLOAT
- **Location**: `tools/step_order.json:allowed_upstream_dependencies`; consumers in 5 modules
- **Description**: `allowed_upstream_dependencies` is actively consumed by 5 tool modules. It is NOT dead or redundant. The baseline raised the question of whether it is redundant with `downstream_consumers`, but they serve complementary purposes: `allowed_upstream_dependencies` defines what each step MAY consume (permissions), while `downstream_consumers` defines what each step DOES consume (actual usage). The DAG lint (`dag_lint.py`) validates consistency between them.
- **Evidence**:
  - `dag_lint.py:56`: Loads `allowed_upstream_dependencies`, checks consumer consistency (E599), circular dependencies (E585).
  - `dependency_order_lint.py:60`: Loads both `steps` and `allowed_upstream_dependencies` for waterfall validation.
  - `extraction_intent_check.py:57`: Cross-references extraction intents against allowed dependencies.
  - `hallucination_lint.py:324`: Uses `allowed_upstream_dependencies` to determine valid upstream steps for hallucination checking.
  - `cli.py:1052`: Checks if a step is in `allowed_upstream_dependencies` for prompt-context commands.
  - `dag_lint.py:77-96`: Validates that `downstream_consumers` entries are consistent WITH `allowed_upstream_dependencies` -- proving they are complementary, not redundant.
- **Recommendation**: No changes needed. Both `allowed_upstream_dependencies` and `downstream_consumers` are well-consumed and architecturally sound. The question "is it redundant with downstream_consumers?" is answered: NO, they serve distinct purposes (permissions vs. actual usage) and are cross-validated by `dag_lint.py`.

---

### FINDING-C08: `coverage_thresholds` in step_order.json -- well-consumed, correct location

- **Severity**: INFO (reclassified from original question)
- **Category**: BLOAT
- **Location**: `tools/step_order.json:coverage_thresholds`; consumers in `tools/specdev_tools/validation/matrix.py:301-357` and `tools/specdev_tools/cli.py:1108-1172`
- **Description**: `coverage_thresholds` is consumed by 2 modules and enforces FR coverage thresholds with configurable warn/error modes. Its location in `step_order.json` is appropriate -- it governs cross-step traceability behavior, which is logically part of the step ordering/policy configuration.
- **Evidence**:
  - `matrix.py:308-340`: `_check_coverage_thresholds()` loads thresholds, checks `fr_coverage` percentage against configured value, emits E592/W592 based on `mode`.
  - `matrix.py:343-357`: `_load_coverage_thresholds()` reads from `step_order.json`, returns `_MISSING_FILE` sentinel for graceful degradation.
  - `cli.py:1108-1131`: Loads `coverage_thresholds` and passes to matrix generation.
  - Current value: `{"fr_coverage": 80, "mode": "warn"}`.
- **Recommendation**: No changes needed. Well-consumed with appropriate graceful degradation.

---

### FINDING-C09: `status_write_exemptions` in step_order.json -- consumed, serves critical cycle-prevention role

- **Severity**: INFO (reclassified)
- **Category**: BLOAT
- **Location**: `tools/step_order.json:policy.status_write_exemptions`; consumer at `tools/specdev_tools/validation/forward_replay_check.py:142`
- **Description**: `status_write_exemptions` is consumed by 1 module (`forward_replay_check.py`) and serves a critical architectural purpose: preventing infinite replay cycles when step 16c writes milestone status back to steps 09/14. Without it, file-level change detection would trigger E550 requiring full downstream replay, creating a cycle. The inline `_notes` in `step_order.json` explicitly documents this rationale.
- **Evidence**:
  - `forward_replay_check.py:139-143`: `def _load_steps_and_exemptions(path): ... exemptions = data.get("policy", {}).get("status_write_exemptions", {})`.
  - `step_order.json:4-5`: `"_notes": {"status_write_exemptions": "Step 16c writes milestones[].status='done' to Steps 09/14... Without this exemption... creating an infinite cycle."}`.
  - Current value: `{"09": ["milestones[].status"], "14": ["milestones[].status"]}`.
- **Recommendation**: No changes needed. Single consumer is justified by the critical cycle-prevention purpose.

---

### FINDING-C10: Canonical triad (`canonical_refs_used`, `canonical_proposals`, `canonical_conflicts`) -- well-consumed, mandatory status justified

- **Severity**: MEDIUM
- **Category**: BLOAT
- **Location**: All 19 step schemas; consumers in `tools/specdev_tools/canonical/integrity.py`, `tools/specdev_tools/canonical/autofix.py`, `tools/specdev_tools/generation/prompt_schema_sync.py`, `tools/specdev_tools/validation/spec_quality_lint.py`, `tools/specdev_tools/validation/validators/step_13.py`
- **Description**: The canonical triad is required in all 19 step schemas and is actively consumed by 5 tool modules. All three fields are in `DRIFT_SENSITIVE_FIELDS`. However, the question remains whether mandatory status is justified for ALL 19 steps. Early steps (00, 01) may not meaningfully use canonical references, yet they must still emit empty arrays to pass validation. The mandatory overhead adds ~15 lines of boilerplate to every spec file (3 fields x ~5 lines of JSON each for empty arrays). Note: P1-A owns the architectural simplification question; this finding addresses only the consumer analysis.
- **Evidence**:
  - `canonical/integrity.py:182-186`: Validates `canonical_refs_used` completeness (E210 for missing/extra IDs).
  - `canonical/integrity.py:204`: `_collect_declared_canonical_refs()` reads `canonical_refs_used`.
  - `canonical/integrity.py:299-300`: Reads `canonical_proposals` and `canonical_conflicts` for unresolved candidate validation.
  - `canonical/autofix.py:60,331-355`: `_sync_canonical_refs_used()` reads and modifies `canonical_refs_used`.
  - `step_13.py:101`: Reads `canonical_refs_used` to validate extension refs.
  - `prompt_schema_sync.py:28-30`: All three fields in `DRIFT_SENSITIVE_FIELDS`.
  - `spec_quality_lint.py:181-183`: All three fields checked in `_check_required_top_level()`.
- **Recommendation**: The canonical triad is NOT bloat -- it is well-consumed by 5 modules. However, consider whether steps 00-03 (pre-FR discovery) genuinely produce canonical references. If not, the schema could use `allOf` conditional requirement (require triad only for steps >= 04). This is a structural optimization question deferred to P1-A.

---

### FINDING-C11: seed_manifest.json merge into step_order.json -- NOT recommended

- **Severity**: MEDIUM
- **Category**: BLOAT
- **Location**: `spec/common/seed_manifest.json` (83 lines) vs. `tools/step_order.json`
- **Description**: The audit plan asked whether `seed_manifest.json` could be absorbed into `step_order.json`. After tracing consumers, this is NOT recommended. The two files serve distinct domains: `seed_manifest.json` is project-level data (lives in `spec/common/`, varies per host repo, contains user-authored seed descriptions) while `step_order.json` is toolkit-level config (lives in `tools/`, constant across all host repos, defines pipeline structure). Merging them would violate the separation between toolkit config (vendored, shared) and project config (per-repo, user-authored).
- **Evidence**:
  - `seed_manifest.json` is loaded from `spec/common/` (project data dir) by `seed_lint.py:22`, `docs_lint.py:15`, `step_16.py:26-38`.
  - `step_order.json` is loaded from `tools/` (toolkit config dir) by `dag_lint.py:43`, `dependency_order_lint.py:60`, `forward_replay_check.py:371`, `matrix.py:351`, `cli.py:1052`.
  - Different lifecycles: `seed_manifest.json` changes per project; `step_order.json` changes per toolkit version.
  - `seed_manifest.json` has its own JSON schema (`schema/seed_manifest.schema.json`); `step_order.json` has no schema.
  - Submodule deployments: `seed_manifest.json` lives in host repo's `spec/` dir while `step_order.json` lives inside the vendored submodule.
- **Recommendation**: Keep them separate. The `docs_policy` field could migrate OUT of `seed_manifest.json` (see FINDING-C05) but the seed registry itself should NOT merge into `step_order.json`. The separation of project data vs. toolkit config is architecturally correct.

---

## Cross-Reference Notes

- **FINDING-C01** (`spec_refs_ingested` dead): Corroborated by P1-A scope (GAP-001 in audit plan). P1-A should note this when assessing seed_refs/spec_refs_ingested pair.
- **FINDING-C10** (canonical triad consumers): P1-A owns the architectural simplification question. This finding provides the consumer evidence P1-A needs.
- **FINDING-C03** (`generation_quality`): The `DRIFT_SENSITIVE_FIELDS` check requested by the plan (P1-A scope) confirms removal would break prompt-schema sync.
- **FINDING-C05** (`docs_policy` location): P1-E may want to consider this when proposing structural reorganization.
