# DevSpec Canonical Drift Hardening

Status: Proposed  
Authoring Date: 2026-02-22  
Scope: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit`

## 1. Objective

Provide an implementation-grade, dependency-ordered plan to eliminate cross-artifact semantic drift across the entire DevSpec lifecycle (`00` through `16c`) with deterministic enforcement.

This document is intentionally prescriptive so AI agents can execute it without guessing.

## 2. Repository Facts (No Assumptions)

1. Step order policy is strict waterfall (`allow_forward_dependency=false`) in `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/step_order.json:4`.
2. Canonical schemas are already registered in `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/schema_registry.json:3`.
3. Canonical registry exists at `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/canon/manifest.json`.
4. Current core canonical reference type is generic in `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/core/collections.schema.json:97`.
5. Most `*_ref` fields are optional across step schemas; only a small subset is required.
6. Prompt output examples commonly include empty `canonical_refs_used` (for example `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_00_project_charter.md:162`).
7. Shared prompt expectations already require canonical reuse-first behavior in `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/docs/prompts/shared_expectations.md:22`.
8. Single-file validation path disables unresolved semantic enforcement (`enforce_unresolved_semantics=False`) in `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/validate.py:156`.
9. Toolkit-level sample spec currently contains only Step 05 artifact in `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/spec/05_interface_contracts.json`.
10. Workspace root has no host `spec/` directory at `/Users/vichitracollective/vc-code/vc_wesbite/spec`.

## 3. Findings (Prioritized)

## 3.1 F-001 (Critical): Field-level Kind Safety Is Missing

Impact: a semantically wrong canonical kind can pass validation.

Evidence:
- Generic canonical ref shape allows any `kind` in `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/core/collections.schema.json:97`.
- Registry validates ref-internal `id` vs `kind`, but not field expectation vs ref kind in `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/canonical_registry.py:110`.
- Reproduced behavior: Step 07 `metric_ref` accepted `cn:core:status:pending` with `kind=status`.

Required fix:
- Introduce typed canonical reference definitions and bind each `*_ref` schema property to the expected type.
- Add explicit validator error `E121 CANONICAL_FIELD_KIND_MISMATCH`.

## 3.2 F-002 (Critical): Unresolved Semantic Detection Has Mapping Gaps

Impact: unresolved canonicalizable values can bypass integrity checks.

Evidence:
- Only one source alias mapping exists (`category -> risk_category_ref`) in `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/canonical_integrity.py:245`.
- Step 03 uses `units` with `unit_ref` in `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/03_glossary.schema.json:47`.
- `units` without `unit_ref` can pass when `term_ref` is present.

Required fix:
- Replace hardcoded source mapping with schema-driven mapping metadata.
- Cover plural/synonym source forms (`units`, `stages`, `actors`, etc).

## 3.3 F-003 (Critical): Canonicalization Is Optional In Most Places

Impact: semantic drift is structurally allowed by schema.

Evidence:
- Canonical-ref-capable fields across step schemas: 82.
- Required canonical-ref fields: 3.
- Example required set exists in Step 07 only (`metric_ref`, `unit_ref`, `environment_ref`) at `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/07_nfrs.schema.json:98`.

Required fix:
- Define a lifecycle-wide required canonicalization policy.
- Require refs for all canonicalizable fields in strict mode, with transitional mode for migration.

## 3.4 F-004 (High): Prompt Examples Normalize Empty Canonical Metadata

Impact: model outputs trend toward low-binding artifacts despite policy.

Evidence:
- Empty canonical refs in many output contracts, e.g.
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_00_project_charter.md:162`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_05_interface_contracts.md:153`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_14_roadmap.md:208`
- Shared expectations require canonical reuse first at `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/docs/prompts/shared_expectations.md:22`.

Required fix:
- Replace all empty canonical examples with non-empty, schema-valid references (or proposals/conflicts where unresolved).

## 3.5 F-005 (High): Validation UX Is Inconsistent Across `validate` vs `validate-all`

Impact: developers get different behavior and can miss unresolved semantics locally.

Evidence:
- Single-file validation disables unresolved semantic enforcement in `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/validate.py:156`.
- Directory flow enforces unresolved semantics later in aggregate.

Required fix:
- Align behavior so single-file validation can run strict semantic mode (default in CI, configurable locally).

## 3.6 F-006 (High): Canonical Registry Coverage Is Insufficient For Required Lifecycle Enums

Impact: strict canonicalization would fail due to missing canonical entries.

Evidence:
- Only one metric canonical exists (`error_rate`) at `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/canon/manifest.json:516`.
- Status canonicals omit values used in schemas (`in_progress`, `done`, `pass`, `fail`, `skip`, `success`).

Required fix:
- Add baseline lifecycle canonicals before enabling strict required refs.

## 3.7 F-007 (Medium): Tooling Uses Parallel Static Vocab Sources

Impact: divergence risk between schema enums, canonical registry, and lints.

Evidence:
- Static stage/unit sets in hallucination lint at `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/hallucination_lint.py:12`.
- Step schemas include local enums not canon-bound.

Required fix:
- Make lints consume canonical registry + schema annotations as primary source of truth.

## 3.8 F-008 (High): One-Go Completeness/No-Assumption Policy Is Not Machine-Enforced

Impact: prompts can claim strict one-go behavior, but CI does not deterministically enforce "no assumptions/no hallucinations" completion.

Evidence:
- `generationQuality` schema allows assumptions/unresolved metadata without strict closure semantics in `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/core/collections.schema.json:431`.
- Current validator/lint flow does not enforce "assumptions empty + unresolved inputs empty + self-check closure" as a mandatory gate.
- Prompt guidance contains fail-closed language, but enforcement is mostly textual.

Required fix:
- Add a deterministic one-go quality gate that fails artifacts with unresolved inputs, open assumptions (strict mode), placeholder tokens, or incomplete self-check closure.
- Wire this gate into both single-file and directory validation paths.

## 4. Target Architecture

## 4.1 Canonical Registry Topology

Use 3-layer registry model:

1. Base toolkit canon:
   - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/canon/kinds/*.json`
   - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/canon/aliases.json`
2. Project overlay canon (host repo):
   - `spec/common/canon/kinds/*.json`
   - `spec/common/canon/aliases.json`
3. Resolved lock snapshot:
   - `spec/common/canon/registry.lock.json`
   - Generated deterministically by tooling; consumed by prompts/validators.

Lock file becomes CI source of truth for artifact validation in host projects.

## 4.2 Canonical ID Contract

1. Approved canonical IDs:
   - `cn:<namespace>:<kind>:<slug>`
2. Proposal IDs:
   - `cp:<namespace>:<kind>:<slug>`
3. Namespace policy:
   - `core` reserved for toolkit defaults.
   - `project.<repo>` for host-repo canonicals.
   - `domain.<team>` allowed for delegated ownership.

## 4.3 Canonical Reference Contract

Adopt strict canonical reference object:

```json
{
  "id": "cn:core:metric:error-rate",
  "kind": "metric",
  "version": "1.0.0",
  "alias_used": "error rate"
}
```

Rules:
1. `id`, `kind`, `version` required.
2. `kind` must match field-bound kind.
3. `version` must be exact semver (no range) in artifacts.
4. `alias_used` required when alias resolution was used.

## 4.4 Schema Binding Model

Add typed defs in core collections:

- `canonicalRefOfMetric`
- `canonicalRefOfUnit`
- `canonicalRefOfStatus`
- `canonicalRefOfEnvironment`
- `canonicalRefOfStage`
- `canonicalRefOfTerm`
- `canonicalRefOfAcronym`
- `canonicalRefOfRole`
- `canonicalRefOfEntity`
- `canonicalRefOfAction`
- `canonicalRefOfCapability`
- `canonicalRefOfPolicy`
- `canonicalRefOfTag`
- `canonicalRefOfRiskCategory`
- `canonicalRefOfGovernanceLabel`
- `canonicalRefOfIdPattern`
- `canonicalRefOfInterface`
- `canonicalRefOfEvent`
- `canonicalRefOfCommand`
- `canonicalRefOfTechStack`
- `canonicalRefOfDependency`
- `canonicalRefOfCompletenessDimension`

Each typed def:
1. `allOf` generic canonicalRef + `kind: const`.
2. optional ID segment regex guard (`^cn:[^:]+:metric:` etc).

## 4.5 Semantic Versioning + Deprecation Lifecycle

Keep entry lifecycle states in `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/core/canon.schema.json`.

Enforcement policy:
1. `active`: allowed.
2. `deprecated`: warning in default mode, error in strict mode.
3. `sunset`: error for new/changed artifacts; warning for untouched legacy only during migration.
4. `retired`: hard error.

## 5. Schema Change Specification (Exact)

## 5.1 Core Schemas

### A) `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/core/collections.schema.json`

Required edits:
1. Make `version` required in `canonicalRef`.
2. Add typed canonical ref defs listed in section 4.4.
3. Add `canonicalFieldBinding` metadata def:
   - `source_field`
   - `ref_field`
   - `kind`
   - `required_mode` (`strict|lenient`)
4. Add `x-canonical-binding` extension support pattern for step schemas.

### B) `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/core/canon.schema.json`

Required edits:
1. Add proposal entry type (`cp:*`) support in schema.
2. Add `review_status` for proposals (`open|accepted|rejected|superseded`).
3. Add `breaking_change` boolean for versioned updates.
4. Add mandatory `change_note` for version increments.

## 5.2 Step Schema Changes (00–16)

Apply to all step schema files under `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/*.schema.json`:

1. Replace generic canonicalRef usage with typed defs for each field.
2. Add `x-canonical-binding` metadata to canonicalizable source fields.
3. Require canonical refs for canonicalizable fields in strict mode.
4. Require top-level canonical metadata arrays in schema `required`:
   - `canonical_refs_used`
   - `canonical_proposals`
   - `canonical_conflicts`
5. Enforce `canonical_refs_used` closure against all `*_ref`.

Step-specific mandatory additions:

1. Step 00 (`00_charter.schema.json`)
   - Add `metric_ref` for `success_metrics[].name`.
   - Keep `unit_ref`.
   - Require both in strict mode.
2. Step 03 (`03_glossary.schema.json`)
   - Explicit `units -> unit_ref` mapping metadata.
   - Require `term_ref` always.
   - Require `unit_ref` when `units` present.
3. Step 05 (`05_interface_contracts.schema.json`)
   - Require `interface_ref` and `entity_ref` for each API.
   - Add canonical refs for `security` and `protocol` only if canonicalized in registry.
4. Step 09 (`09_impl_plan.schema.json`)
   - Require `status_ref` when `status` present.
   - Require `tech_stack_ref` on each tech stack item.
5. Step 14 (`14_roadmap.schema.json`)
   - Require `status_ref` for milestone + task status.
   - Add `risk_status_ref` bound to `risk_category` canonical kind (or add distinct kind).
6. Step 15 (`15_scaffold.schema.json`)
   - Add `build_status_ref` (status kind).
7. Step 16 (`16_impl_context.schema.json`)
   - Require `status_ref` for all status-like fields.
   - Add missing refs for `ci_status` and `security_status`.

## 6. Prompt Hardening Specification (Exact)

## 6.1 Shared Prompt Baseline

Update `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/docs/prompts/shared_expectations.md`:

1. Add mandatory "One-Go Deterministic Protocol":
   - Preflight input closure
   - Canonical resolution closure
   - Schema closure
   - Trace closure
   - Hallucination closure
2. Add fail-closed output rule:
   - If unresolved input remains, emit blocker report instead of artifact.
3. Add explicit "No unstated assumptions":
   - `generation_quality.assumptions` must be empty in strict mode.
4. Add required unresolved handling:
   - unresolved semantic must be in `canonical_proposals` or `canonical_conflicts`, never silent.

## 6.2 Per-Prompt Contract Changes

Apply to every prompt file under `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_*.md`:

1. Add "Canonical Inputs" section:
   - Read `spec/common/canon/registry.lock.json` first.
2. Add deterministic resolution order:
   - exact id -> alias -> proposal -> conflict.
3. Replace empty canonical examples with non-empty examples where canonicalizable fields exist.
4. Add strict closure checklist at end:
   - no canonicalizable field without `*_ref` or proposal/conflict.
5. Add explicit no-hallucination blockers:
   - unknown enum/id/value = stop and ask or emit blocker.
6. Add "No downstream invention" reinforcement:
   - do not invent terms, metrics, statuses, stage names.

Files to update:

- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_00_project_charter.md`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_01_capabilities.md`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_02_system_sketch.md`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_02a_delivery_baseline.md`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_03_glossary.md`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_04_functional_requirements.md`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_05_interface_contracts.md`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_06_invariants.md`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_07_nfrs.md`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_08_fixtures.md`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_09_impl_plan.md`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_10_governance.md`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_11_redteam.md`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_12_ci_gates.md`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_13_extension_generator.md`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_13a_completeness_assessment.md`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_14_roadmap.md`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_15_scaffold.md`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_16_impl_context.md`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_16a_impl_planner.md`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_16b_impl_coder.md`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/prompt_16c_impl_reviewer.md`

## 7. Tooling Hardening Specification (Exact)

## 7.1 Validator Engine

### A) `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/canonical_integrity.py`

Required changes:
1. Add field-kind binding checks (schema-driven):
   - Emit `E121 CANONICAL_FIELD_KIND_MISMATCH`.
2. Replace hardcoded fallback mapping with schema metadata (`x-canonical-binding`).
3. Ensure unresolved semantics include plural/synonym source fields.
4. Add strict mode requiring:
   - no missing refs for canonicalizable fields.
   - no empty `canonical_refs_used` when refs present.

### B) `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/validate.py`

Required changes:
1. Add flag `--strict-canonical` to `validate` and `validate-all`.
2. In strict mode, single-file validation must enforce unresolved semantics.
3. Align error classes between single-file and directory paths.

### C) `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/canonical_registry.py`

Required changes:
1. Enforce exact version presence in refs.
2. Validate canonical status policy (deprecated/sunset/retired) with strict mode gating.
3. Add proposal resolution support (`cp:*`) with governance status checks.

## 7.2 Autofix and Migration

### A) `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/canonical_autofix.py`

Required changes:
1. Remove hardcoded inference table as primary source.
2. Use schema `x-canonical-binding` metadata to infer refs.
3. Auto-create proposals for unresolved values.
4. Preserve existing valid refs; never overwrite without explicit conflict.

### B) New script

Add `specdev_tools/canonical_backfill.py`:
1. Backfill refs across existing spec directories.
2. Produce deterministic report:
   - resolved refs
   - unresolved proposals
   - conflicts.

## 7.3 Prompt/Schema Sync Gates

### A) `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/prompt_schema_sync.py`

Required changes:
1. Extend checks beyond required refs:
   - verify canonicalizable field coverage includes typed refs.
2. Enforce non-empty canonical examples for prompts with canonicalizable fields.
3. Enforce canonical input section presence in each prompt.

### B) `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/spec_quality_lint.py`

Required changes:
1. Promote top-level canonical metadata fields from lint-only to schema-required for all step schemas.
2. Add rule:
   - if canonicalizable fields exist, `canonical_refs_used` cannot be empty unless proposals/conflicts justify all.

### C) `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/hallucination_lint.py`

Required changes:
1. Replace static stage/unit vocab with canonical registry lookup.
2. Enforce schema enum + canonical consistency.

## 7.4 One-Go Completeness Gate

### A) New module `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/one_go_lint.py`

Required checks (strict mode):
1. `generation_quality.preflight_passed == true`.
2. `generation_quality.placeholder_scan.has_placeholders == false`.
3. `generation_quality.unresolved_inputs` must be empty when field exists.
4. `generation_quality.assumptions` must be empty (or explicitly allowed by project policy toggle).
5. `generation_quality.self_check_results` must be present and all checks passed for steps that define self-check protocol.
6. Canonical closure must hold:
   - all canonicalizable fields resolved with typed refs, or represented as proposal/conflict.
7. If any item above fails, emit deterministic `E24x ONE_GO_INCOMPLETE_*` errors.

### B) Validation pipeline integration

Update:
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/validate.py`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/cli.py`

Required behavior:
1. New CLI switch `--strict-one-go` (independent of `--strict-canonical`, but enabled by default in CI).
2. Execute one-go lint in both `validate` and `validate-all`.
3. Keep error semantics consistent between single-file and full-directory runs.

## 8. Test Plan Changes (Exact)

Update/add tests in:

- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tests/test_canonical_integrity.py`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tests/test_prompt_schema_sync.py`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tests/test_prompt_b4_contracts.py`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tests/test_validate_b2_integration.py`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tests/test_cli_b3.py`

Add mandatory new test cases:
1. `metric_ref` pointing to `status` fails with `E121`.
2. `units` without `unit_ref` fails when strict canonical enabled.
3. Prompt output example with empty canonical refs fails for canonicalizable steps.
4. Single-file strict validation catches unresolved semantics.
5. Deprecated/sunset canonical behavior matches policy.
6. `generation_quality.preflight_passed=false` fails strict one-go gate.
7. Non-empty `generation_quality.unresolved_inputs` fails strict one-go gate.
8. Non-empty `generation_quality.assumptions` fails strict one-go gate when strict assumption policy is enabled.

## 9. Documentation Changes (Exact)

Update:

- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/docs/developers/getting_started.md`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/docs/developers/reference.md`
- `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/README.md`

Add sections:
1. Canonical lock workflow.
2. Strict canonical validation usage.
3. Proposal and conflict lifecycle.
4. One-go prompt quality protocol and fail-closed behavior.

## 10. Atomic Implementation Plan (Dependency-Ordered, No Rework)

This sequence is designed to prevent backtracking and minimize AI agent calls.

## 10.1 Phase A: Contract Foundation

### Task A1 (Atomic)
- Goal: freeze canonical contract decisions before touching step schemas/prompts.
- Files:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/core/collections.schema.json`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/core/canon.schema.json`
- Deliverables:
  - typed canonical refs
  - strict canonicalRef version requirement
  - proposal contract support
- Depends on: none
- Verification:
  - `./tools/run_specdev.sh validate-all ./spec --repo-root ./devspec_toolkit` (toolkit repo context)
  - schema unit tests pass.

### Task A2 (Atomic)
- Goal: expand baseline canonical registry coverage required by existing enums/fields.
- Files:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/canon/kinds/*.json`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/canon/aliases.json`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/canon/manifest.json` (if kept as compiled artifact)
- Depends on: A1
- Verification:
  - `./tools/run_specdev.sh canonical-lint canon --repo-root ./devspec_toolkit`

## 10.2 Phase B: Step Schema Binding

### Task B1 (Atomic)
- Goal: apply typed refs and canonical bindings to all step schemas.
- Files:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/00_charter.schema.json`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/01_capabilities.schema.json`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/02_system_sketch.schema.json`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/02a_delivery_baseline.schema.json`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/03_glossary.schema.json`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/04_fr_list.schema.json`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/05_interface_contracts.schema.json`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/06_invariants.schema.json`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/07_nfrs.schema.json`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/08_fixtures.schema.json`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/09_impl_plan.schema.json`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/10_governance.schema.json`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/11_redteam.schema.json`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/12_ci_gates.schema.json`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/13_extension_generator.schema.json`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/13a_completeness_assessment.schema.json`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/14_roadmap.schema.json`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/15_scaffold.schema.json`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/16_impl_context.schema.json`
- Depends on: A1, A2
- Verification:
  - schema validation tests pass
  - no unresolved `$ref` in registry map.

## 10.3 Phase C: Validator/CLI Hardening

### Task C1 (Atomic)
- Goal: enforce field-kind matching and schema-driven unresolved detection.
- Files:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/canonical_integrity.py`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/canonical_registry.py`
- Depends on: B1
- Verification:
  - add failing fixtures for previous false-negatives.

### Task C2 (Atomic)
- Goal: align strict behavior between `validate` and `validate-all`.
- Files:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/validate.py`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/cli.py`
- Depends on: C1
- Verification:
  - strict single-file run equals directory run for same file set.

### Task C3 (Atomic)
- Goal: replace static hallucination vocab with canonical-driven checks.
- Files:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/hallucination_lint.py`
- Depends on: A2, C1
- Verification:
  - lint tests updated and passing.

### Task C4 (Atomic)
- Goal: add deterministic one-go completeness/no-assumption enforcement.
- Files:
  - new `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/one_go_lint.py`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/validate.py`
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/cli.py`
- Depends on: C1, C2
- Verification:
  - strict one-go test fixtures fail/pass deterministically.

## 10.4 Phase D: Autofix/Backfill

### Task D1 (Atomic)
- Goal: migrate autofix from hardcoded rules to schema annotations.
- Files:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/canonical_autofix.py`
  - new `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/canonical_backfill.py`
- Depends on: B1, C1
- Verification:
  - backfill on fixture corpus yields deterministic output.

## 10.5 Phase E: Prompt Hardening

### Task E1 (Atomic)
- Goal: harden shared prompt baseline.
- Files:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/docs/prompts/shared_expectations.md`
- Depends on: B1, C1
- Verification:
  - prompt lint enforces new mandatory sections.

### Task E2 (Atomic)
- Goal: update all step prompts to strict one-go fail-closed behavior.
- Files:
  - all `prompt_*.md` under `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/prompts/`
- Depends on: E1
- Verification:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/prompt_schema_sync.py` passes
  - prompt contract tests pass.

## 10.6 Phase F: Tests

### Task F1 (Atomic)
- Goal: codify all new failure classes and strict behavior.
- Files:
  - canonical, prompt-sync, CLI, validate integration tests listed in section 8.
- Depends on: C1, C2, C3, C4, D1, E2
- Verification:
  - full test suite green.

## 10.7 Phase G: Docs + Rollout

### Task G1 (Atomic)
- Goal: update user-facing docs for new workflows.
- Files:
  - docs listed in section 9.
- Depends on: F1
- Verification:
  - docs-lint passes.

### Task G2 (Atomic)
- Goal: migration rollout with minimal disruption.
- Actions:
  1. Run backfill in report-only mode.
  2. Review proposals/conflicts.
  3. Apply backfill.
  4. Run strict validation.
  5. Enable strict mode in CI.
- Depends on: D1, F1, G1
- Verification:
  - zero `E*` canonical errors on target specs.

## 11. CI Gate Design

Recommended gate order:

1. `canonical-lint`
2. schema validate (`validate-all`)
3. `canonical-integrity --strict`
4. `hallucination-lint`
5. `one-go-lint --strict`
6. `prompt-sync`
7. forward replay check

Failure class policy:
1. `E1xx` canonical identity/type/version: block merge.
2. `E2xx` unresolved/cross-artifact drift: block merge.
3. `E3xx` prompt-schema drift: block merge.
4. `W1xx` deprecation warnings: block only if `SPECDEV_WARNINGS_AS_ERRORS=1`.
5. `E24x` one-go incompleteness/assumption/hallucination closure errors: block merge.

## 12. Agent Execution Plan (Minimize Calls/Rework)

Recommended AI execution batching:

1. Call 1: complete Phase A (A1, A2) in one branch.
2. Call 2: complete Phase B (all step schemas) with generated diff.
3. Call 3: complete Phase C (validator/CLI/lints, including one-go gate).
4. Call 4: complete Phase D (autofix/backfill).
5. Call 5: complete Phase E (shared expectations + all prompts).
6. Call 6: complete Phase F (tests).
7. Call 7: complete Phase G (docs + rollout scripts).

Rationale: each call consumes stable outputs of previous phase; avoids churn from contract changes.

## 13. Definition Of Done

All conditions must be true:

1. All canonicalizable fields are type-bound and enforced.
2. No artifact passes with unresolved canonicalizable values unless explicitly proposed/conflicted.
3. Single-file and directory validations have consistent strict semantics.
4. Prompts produce non-empty canonical coverage where applicable.
5. CI gates fail fast on drift, hallucinations, and prompt-schema drift.
6. Migration tooling can backfill existing specs deterministically.
7. Docs fully reflect the hardened workflow.
8. Strict one-go gate blocks incomplete artifacts with unresolved assumptions/hallucination markers.

## 14. Non-Goals

1. Redesign of business semantics in existing specs.
2. Runtime code generation redesign outside canonical/reference enforcement scope.
3. Introducing forward dependencies contrary to step-order policy.

## 15. Immediate Next Execution Command Set

After implementation starts, run in this exact order:

1. `./tools/run_specdev.sh canonical-lint canon --repo-root ./devspec_toolkit`
2. `./tools/run_specdev.sh validate-all ./spec --repo-root ./devspec_toolkit`
3. `./tools/run_specdev.sh canonical-integrity ./spec --repo-root ./devspec_toolkit`
4. `./tools/run_specdev.sh hallucination-lint ./spec --repo-root ./devspec_toolkit`
5. `./tools/run_specdev.sh prompt-sync ./spec --repo-root ./devspec_toolkit`
6. `./tools/run_specdev.sh one-go-lint ./spec --repo-root ./devspec_toolkit`

## 16. Finding-to-Task Traceability Matrix

This matrix is the coverage proof that every finding has an implementation path.

| Finding | Core Tasks | Supporting Tasks | Acceptance Evidence |
|---|---|---|---|
| F-001 Field-kind safety | A1, B1, C1 | F1 | `E121` test fails wrong-kind refs |
| F-002 Unresolved mapping gaps | B1, C1 | D1, F1 | `units -> unit_ref` and synonym cases fail/pass deterministically |
| F-003 Canonical optionality | B1 | C1, 7.3.B, F1 | schemas require refs/metadata in strict mode |
| F-004 Empty canonical prompt examples | E1, E2 | 7.3.A, F1 | prompt-sync and prompt contract tests fail on empty examples |
| F-005 validate vs validate-all mismatch | C2 | F1 | same strict results for single-file vs directory |
| F-006 Registry coverage gaps | A2 | B1, C1, F1 | canonical-lint passes and strict validation no false missing refs |
| F-007 Parallel static vocab in lint | C3 | A2, F1 | hallucination lint consumes canon and removes static drift |
| F-008 One-go completeness not enforced | C4 | E1, E2, F1 | `E24x` failures for unresolved inputs/assumptions/placeholders |
