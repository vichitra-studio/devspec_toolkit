# RFC: DevSpec Toolkit Design Review Report (v0.2.x → v0.3.0)

> **Date:** 2026-02-23  
> **Author:** Design Review Agent  
> **Status:** Draft — Final (merged findings from Pass 1 + Pass 2)  
> **Scope:** Full toolkit architecture, prompts, schemas, tools, tests, migration, and path strategy

---

# Part A: Detailed Review Report

---

## 1. Pluggable Path Resolution Strategy

### 1.1 Current State

The toolkit is added as a git submodule at `<project_root>/devspec_toolkit/`. Path resolution currently relies on:

- `--repo-root ./devspec_toolkit` CLI flag passed to every command
- `run_specdev.sh` wrapper that locates `dev_env/` relative to `<project_root>/tools/..`
- `init_project.py` that hardcodes `devspec_toolkit/tools/requirements.txt` and `devspec_toolkit/tools/` for editable install
- Prompts use mixed relative paths: `spec/common/seed_manifest.json` (product-relative), `schema/16_impl_context.schema.json` (toolkit-relative)

### 1.2 Findings

| ID | Severity | Finding |
|----|----------|---------|
| F-P1 | **CRITICAL** | **No formal path variable convention exists.** Prompts intermix product-root and toolkit-root relative paths without declaring which root applies. When an agent reads `spec/00_charter.json`, this is product-root relative. When it reads `schema/00_charter.schema.json`, this is toolkit-root relative. `devspec_toolkit/docs/prompts/shared_expectations.md` is product-relative *through* the submodule. No `$PRODUCT_ROOT`/`$TOOLKIT_ROOT`/`$SPEC_ROOT` convention exists. |
| F-P2 | **HIGH** | **`init_project.py` L231 hardcodes nested path.** Looks for seed templates at `devspec_toolkit/devspec_toolkit/seed_templates` — double-nesting. Breaks if submodule is checked out differently or repo structure changes. |
| F-P3 | **HIGH** | **Schema URIs use `https://specdev.local/schema/...` which never resolve over HTTP.** By design (local-only), but `schema_registry.json` maps to toolkit-relative paths. Any tool must know the toolkit root. |
| F-P4 | **MEDIUM** | **`run_specdev.sh` ROOT resolution is fragile.** Computes `$(dirname "${BASH_SOURCE[0]}")/..` — resolves to product root. Requires toolkit on `PYTHONPATH` or editable install. Any directory move breaks silently. |

### 1.3 Recommended Strategy

All paths in prompts use NAMED VARIABLES, resolved at runtime:
- `$PRODUCT_ROOT` = git repo root (where `spec/`, `docs/`, `canon/` live)
- `$TOOLKIT_ROOT` = `$PRODUCT_ROOT/devspec_toolkit` (the submodule)
- `$SPEC_DIR` = `$PRODUCT_ROOT/spec`
- `$SEED_DIR` = `$PRODUCT_ROOT/docs/seed`
- `$CANON_DIR` = `$PRODUCT_ROOT/canon`
- `$SCHEMA_DIR` = `$TOOLKIT_ROOT/schema`
- `$PROMPTS_DIR` = `$TOOLKIT_ROOT/prompts`

`prompt_generator.py` should inject the actual resolved paths when generating prompts for an agent.

---

## 2. Prompt and Schema Efficacy

### 2.1 Are the step prompts self-explanatory and unambiguous?

**Assessment: MOSTLY YES, with critical gaps.**

All 22 prompts follow a consistent structure: Purpose → Role → Seed Order → Context → Operating Flow → Field Definitions → Forbidden Actions → Output Contract → Canonical Registry.

| ID | Severity | Finding | Location |
|----|----------|---------|----------|
| F-1.1a | **HIGH** | **Missing explicit cross-reference matrix in prompts.** Each prompt lists "Context To Ingest" but no structured, machine-checkable enumeration of which upstream spec IDs must be present in the output's `trace` or `links` array. Allows structurally valid but semantically incomplete artifacts. | All prompts, especially 04, 05, 06, 07, 08 |
| F-1.1b | **MEDIUM** | **Inconsistent "Context To Ingest" scope.** `prompt_00` L35 references `example/devspec_kit/spec/00_charter.json` and `example/devspec_kit/spec/07_nfrs.json` as shape references. This directory is not listed in repo root, not discoverable from seed_manifest, and may not exist in consumer repos. | `prompt_00_project_charter.md` L35 |
| F-1.1c | **RESOLVED** | ~~`shared_expectations.md` path inconsistent.~~ **Targeted review confirms path IS consistent** across all 23 prompts as `devspec_toolkit/docs/prompts/shared_expectations.md`. Only `prompt_00` adds `(formerly template/shared_expectations.md)` — a historical note, not a conflict. No action needed. | All prompts |
| F-1.1d | **LOW** | **Clarification Questions section is purely advisory.** No prompt mandates the agent MUST ask these questions under specific conditions. The `blocker report` in Hardening Protocol partially addresses this, but questions are not gated. | All prompts |

### 2.2 Do prompts/schemas guarantee comprehensive requirement translation from seeds?

**Assessment: PARTIAL — significant semantic drift risk.**

| ID | Severity | Finding | Location |
|----|----------|---------|----------|
| F-1.2a | **CRITICAL** | **No requirement-to-spec coverage matrix is enforced.** `seed_manifest.json` defines which seeds are required per step, but nothing validates that every requirement stated in seed documents is represented in the output artifact. | `seed_manifest.schema.json`, all prompts |
| F-1.2b | **HIGH** | **Seeds are read-only input references, not checksummed contracts.** `seed_refs` array records which seeds were used but includes no `hash`, `version`, or `last_modified` field. If a seed changes between steps, subsequent steps may operate on stale data. | `collections.schema.json#seedRef` (L467-496) |
| F-1.2c | **MEDIUM** | **`step_requirements` uses flat ID arrays, not relationship objects.** `seed_manifest.schema.json` L87-94 defines `step_requirements` as `{ "00": ["seed-overview", "seed-tech-stack"] }`. Tells the agent *which* seeds to read but not *how* they should influence the output. Intent mapping is implicit. | `seed_manifest.schema.json` L87-94 |

### 2.3 Do all roadmap items strictly comply with system requirements?

**Assessment: NO — the link chain has structural gaps.**

| ID | Severity | Finding | Location |
|----|----------|---------|----------|
| F-1.3a | **HIGH** | **Roadmap milestones not required to cite specific FR/capability IDs.** `14_roadmap.schema.json` requires `source_milestones` and `deliverables` but not `fr_refs` or `capability_refs`. A milestone can be semantically unlinked from system requirements. | `14_roadmap.schema.json`, `prompt_14_roadmap.md` |
| F-1.3b | **MEDIUM** | **No automated validator checks roadmap coverage against FRs.** `step_14.py` exists but does not cross-reference roadmap tasks against `04_fr_list.json`. | `validators/step_14.py` |

---

## 3. Seed Documents vs Specs: Deterministic Speccing

### 3.1 Findings

| ID | Severity | Finding |
|----|----------|---------|
| F-S1 | **CRITICAL** | **Specs are NOT seeded — they're informally referenced.** Each prompt lists which prior specs to read in prose guidance, but this is not machine-checkable. No equivalent of `seed_manifest.json` `step_requirements` for spec dependencies. If a prompt fails to list a required upstream spec, the agent won't read it, causing silent requirement drops. |
| F-S2 | **HIGH** | **`step_order.json` defines dependencies but prompts don't enforce them.** `step_order.json` says Step 04 depends on `["00", "01", "02", "03"]`, but `prompt_04` only mentions Steps 00, 01, 03 (not 02). Dependency graph and prompt "Context To Ingest" are disconnected. |
| F-S3 | **HIGH** | **No validation ensures an agent actually read all required prior specs.** `seed_refs` records seed docs used, but no `spec_refs_ingested` array proves upstream specs were read. |
| F-S4 | **MEDIUM** | **Seed documents are free-text with no structural requirements.** Intentional (keep human-readable), but the toolkit needs a way to deterministically extract requirements from free-text. Currently relies on agent intelligence. |

### 3.2 Recommended Approach

1. **Extend `step_order.json`** to be the single source of truth for ALL inputs (seeds + specs):
   ```json
   {
     "04": {
       "allowed_deps": ["00", "01", "02", "03"],
       "required_spec_inputs": ["00_charter.json", "01_capabilities.json", "03_glossary.json"],
       "required_seed_inputs": ["seed-overview", "seed-tech-stack"],
       "extraction_intent": {
         "00_charter.json": "Extract in-scope items → map to FRs",
         "01_capabilities.json": "Each capability → ≥1 FR"
       }
     }
   }
   ```
2. **Add `spec_refs_ingested`** to every schema — `{step_id, artifact_id, hash}`.
3. **Add a validator** that checks `spec_refs_ingested` against `step_order.json` `required_spec_inputs`.

---

## 4. Implementation Execution & Verification (Step 16)

### 4.1 Does Step 16 plan/implement all roadmap requirements?

| ID | Severity | Finding | Location |
|----|----------|---------|----------|
| F-2.1a | **CRITICAL** | **No validation cross-checks Step 16 checklist against Step 14 roadmap tasks.** `step_16.py` validates evidence, docs_impact, proof closure (E301/E302), but does not verify checklist covers every task from the corresponding roadmap milestone. Partial plans pass validation. | `validators/step_16.py` |
| F-2.1b | **HIGH** | **Step 16a planner prompt does not mandate ingesting roadmap milestone's task list.** `prompt_16a` says "Use the Step ID" but does not mandate every `tasks[]` item becomes a checklist item. | `prompt_16a_impl_planner.md` L36-37 |

### 4.2 Does the Trinity Loop enforce test/evidence for every implementation?

| ID | Severity | Finding | Location |
|----|----------|---------|----------|
| F-2.2a | **HIGH** | **Schema enforces evidence only via conditional `allOf`.** `16_impl_context.schema.json` L468-492 uses `if/then` to require `evidence` when `implementation.status == "verified"`. If `status` is absent, condition doesn't trigger, evidence not required. | `16_impl_context.schema.json` L468-492 |
| F-2.2b | **HIGH** | **`nfr_refs`/`fixture_ref` mandatory requirement is ONLY in deep validator, not schema.** `step_16.py` L56-64 errors when non-deferred item lacks these, but schema marks them optional. Confusing divergent error signals. | `step_16.py` L56-64 vs schema L350-354 |
| F-2.2c | **MEDIUM** | **16c reviewer does not programmatically verify `ci_status` gate.** Prompt forbids `verdict: verified` when `ci_status == red`, but deep validator doesn't check this. | `validators/step_16.py`, `prompt_16c` L104 |

### 4.3 Are test suite and documentation updated alongside code?

**Assessment: YES — strong enforcement.** `docs_impact` validation in `step_16.py` L142-164 correctly validates code changes trigger `docs_impact.status == "required"` with non-empty `docs_touched`, using `seed_manifest.json` `docs_policy.doc_paths` for path validation.

---

## 5. Trinity Loop Semantic Enforcement (Expanded)

### 5.1 Findings

| ID | Severity | Finding |
|----|----------|---------|
| F-T1 | **CRITICAL** | **The reviewer (16c) is prompted to do semantic review but has NO tooling support.** Prompt mandates "verify that the implementation matches the spec" but validator only checks structural elements (evidence exists, CI passed, files covered). Does NOT verify *behavior* matches FR statement or acceptance criteria. |
| F-T2 | **HIGH** | **No cross-reference from checklist items back to actual test assertions.** `linked_test_expectation` is a string; validator checks it exists but doesn't verify the test actually *asserts the FR's acceptance criteria*. |
| F-T3 | **HIGH** | **No validator verifies checklist covers ALL roadmap milestone tasks.** |
| F-T4 | **HIGH** | **`ci_status` gate is prompt-only, not enforced by tooling.** |
| F-T5 | **MEDIUM** | **No semantic diff between planned and executed actions.** Planner (16a) defines actions, Coder (16b) fills evidence. No validation checks every planned action was executed — only that verified items have evidence. |

### 5.2 Recommended Enforcement

1. Add roadmap-to-checklist coverage validator (E304).
2. Add `ci_status` gate enforcement (E303).
3. Add planned-vs-executed validator.
4. Add `semantic_review` section to schema:
   ```json
   "semantic_review": {
     "type": "object",
     "properties": {
       "fr_coverage": {
         "type": "array",
         "items": {
           "properties": {
             "fr_id": { "type": "string" },
             "satisfied": { "type": "boolean" },
             "evidence_summary": { "type": "string", "minLength": 20 }
           },
           "required": ["fr_id", "satisfied", "evidence_summary"]
         }
       },
       "hallucinated_features": { "type": "array", "items": { "type": "string" } }
     }
   }
   ```

---

## 6. Semantic Drift and System Integrity

| ID | Severity | Finding | Location |
|----|----------|---------|----------|
| F-3.1a | **CRITICAL** | **No end-to-end traceability validation from seeds to implementation.** Pipeline: Seed → Charter → Capabilities → FRs → Interfaces → ... → Roadmap → Implementation. Each step links to immediate upstream, but no tool validates the *transitive closure*. A requirement can be captured in Charter but dropped from FRs with no detection. | System-wide |
| F-3.1b | **HIGH** | **Forward replay check (`forward_replay_check.py`) validates structural changes, not semantic coverage.** Detects schema changes requiring downstream re-generation but doesn't check if downstream artifacts still cover the same requirements. | `forward_replay_check.py` |
| F-3.1c | **HIGH** | **`spec_quality_lint.py` checks for TBDs and empty arrays but not requirement coverage regression.** | `spec_quality_lint.py` |
| F-3.2a | **HIGH** | **Implementation discovery relies entirely on agent intelligence.** `prompt_16a` says "Scan existing files" but no tool verifies the agent did this correctly. `existing_structures` accepts free-form strings; hallucination is easy. | `prompt_16a` L38, schema L641-700 |
| F-3.2b | **MEDIUM** | **Edge cases and error paths are not mandated in checklist.** Mentioned in "Heuristics" but not required. | `prompt_16a_impl_planner.md` |

---

## 7. Roadmap Hardening for AI-Driven Development

| ID | Severity | Finding |
|----|----------|---------|
| F-R1 | **CRITICAL** | **Roadmap milestones don't link to specific FRs or capabilities.** No `fr_refs` or `capability_refs`. Impossible for AI agent to verify it's implementing the right things. |
| F-R2 | **CRITICAL** | **Roadmap tasks not atomic enough for AI-driven development.** Schema requires `task_id`, `description`, optional `acceptance_criteria`, but doesn't enforce testable outcomes. Example: `"Configure Docker compose for DB and App"` — unverifiable. |
| F-R3 | **HIGH** | **No dependency graph between tasks/milestones.** Individual tasks have no `depends_on` field. AI agent cannot determine execution order to minimize rework. |
| F-R4 | **HIGH** | **No `assumptions` or `decisions` field on tasks.** Agent has nowhere to record ambiguity decisions, causing undocumented assumptions and rework. |
| F-R5 | **HIGH** | **No hallucination guard on tech_stack reuse.** Prompt says "copy from Step 09" but validator doesn't check entries exist in `09_impl_plan.json`. Agent can invent frameworks. |
| F-R6 | **MEDIUM** | **Milestone sequencing partially enforced.** `step_14.py` L47-48 validates `target_date` ordering and L35-40 validates `source_milestones` against Step 09 IDs. However, no topological sort on milestone dependency relationships and no task-level dependency validation. |

---

## 8. Docs Discovery & Seed Processing

| ID | Severity | Finding | Location |
|----|----------|---------|----------|
| F-4.1a | **MEDIUM** | **`step_requirements` maps steps to seed IDs but not processing intent.** Current: `"04": ["seed-overview"]`. Better: `"04": [{"seed_id": "seed-overview", "extraction": "user_stories → FRs", "mandatory": true}]`. Without intent, agent may ignore critical sections. | `seed_manifest.schema.json` L87-94 |
| F-4.2a | **HIGH** | **No validation ensures `seed_manifest.json` is updated when new seed documents are created.** Prompt 16a says "add new seeds" but no tool verifies this. New doc can exist on disk without registration. | `prompt_16a` L32-33, `seed_lint.py` |
| F-4.2b | **MEDIUM** | **`seeds[].path` not validated against filesystem.** `seed_manifest.schema.json` requires `path` as string but `seed_lint.py` may not check existence. | `seed_manifest.schema.json` L57-59 |

---

## 9. Schema Validation & Reference Handling

### 9.1 Schema `$ref` resolution

**Assessment: ROBUST.** `validate.py` L46-48 uses `referencing.Registry` with `Resource.from_contents()`. Fail-closed on missing `$schema` (E520).

| ID | Severity | Finding | Location |
|----|----------|---------|----------|
| F-5.1a | **INFO** | **`$schema` stripped from validation payload but used as lookup key.** Correct behavior — no fallback to filename-based detection. If `$schema` missing, returns `E520 UNRESOLVED_INPUT`. Fail-closed ✓. | `validate.py` L93-114 |
| F-5.1b | **LOW** | **Some schemas registered in `schema_registry.json` but prompts don't reference them.** Not all steps have a prompt for `seed_manifest` itself. | `schema_registry.json` L27 |

### 9.2 Validation tooling correctness

| ID | Severity | Finding | Location |
|----|----------|---------|----------|
| F-5.2a | **CRITICAL** | **`16_impl_context.schema.json` contains hardcoded project-specific NFR IDs and timeout constants.** `nfr_measurement_methods` L747-788 hardcodes `nfr-availability-uptime` and `nfr-privacy-cookie-free` with `additionalProperties: false`. `timeout_constants` L789-803 hardcodes `EMAIL_DELIVERY_TIMEOUT`, `DNS_VERIFICATION_TIMEOUT`, `ANALYTICS_BEACON_TIMEOUT`. **Schema unusable for any other project.** | `16_impl_context.schema.json` L747-803 |
| F-5.2b | **RESOLVED** | ~~No deep validators for steps 16a, 16b, 16c.~~ Deep validators exist: `validate_step_16a/b/c()` are registered in `DEEP_VALIDATORS`. Task 1.6 verified this. | `validate.py` |
| F-5.2c | **MEDIUM** | **`_get_step_from_path()` may fail for `spec/impl_context/step-api-core.json`.** Regex `^(\d{2}[a-z]?)_` expects `16_impl_context.json`. Fallback `STEP_DIR_RE` checks parent for `step_(\d{2}[a-z]?)`. `impl_context/` matches neither → step = `"unknown"` → no deep validator. | `validate.py` L50-65 |
| F-5.2d | **MEDIUM** | **Canonical path inconsistency.** Prompts reference `canon/manifest.json`. `schema_registry.json` maps canon schemas under `canon/` not `schema/core/` like atoms/collections. Works but naming convention inconsistent. | `schema_registry.json` L4-5 |
| F-5.2e | **MEDIUM** | **Step 10 governance canonical-ref fields had schema descriptions with wrong `kind` constraints.** `commit_message_rules.id_pattern_ref` required `kind='action'|'term'`, `policy_ref` required `kind='risk_category'|'capability'`, `command_ref` required `kind='action'` — none matched the actual canon registry kinds (`id_pattern`, `policy`, `command`), making the fields effectively dead. Fixed by relaxing descriptions to the real kinds, adding `cn:core:command:governance-check` to the canon, and populating the host `spec/10_governance.json` with the three refs (2026-04-08). | `schema/10_governance.schema.json`, `canon/kinds/command.json`, `canon/manifest.json` |

### 9.3 Path consistency

| ID | Severity | Finding | Location |
|----|----------|---------|----------|
| F-5.3a | **MEDIUM** | **Prompts use relative paths inconsistently.** Some say `spec/common/seed_manifest.json` (product-root), others `schema/16_impl_context.schema.json` (toolkit-root). Dual-root convention documented nowhere. | All prompts |

---

## 10. Tools and Tests: Separation of Concerns

### 10.1 Current Organization

`tools/specdev_tools/` contains 24 Python modules + `validators/` (18 step validators).  
`tests/` contains 21 test files, `fixtures/` (21 step dirs), `integration/` (21 files).

### 10.2 Findings

| ID | Severity | Finding |
|----|----------|---------|
| F-TT1 | **HIGH** | **Tools serve TWO distinct purposes conflated:** (1) Validation/Linting (CI-time: `validate.py`, `*_lint.py`, `canonical_*.py`); (2) Generation/Transformation (dev-time: `prompt_generator.py` 30KB, `schema_differ.py` 48KB). Different consumers, different change frequencies. |
| F-TT2 | **HIGH** | **Tests are 1:1 with tools but NOT with validation surface.** `test_b4_schema_contracts.py` (781 lines) tests schema properties, not a specific tool. Mixes unit, integration, and contract tests in one flat directory. |
| F-TT3 | **MEDIUM** | **Test fixtures are step-specific but test files are tool-specific.** Schema change requires updating: `fixtures/step_XX/`, `test_*.py`, AND `validators/step_XX.py`. 3-way coupling makes changes error-prone. |
| F-TT4 | **MEDIUM** | **`schema_differ.py` (48KB) and `prompt_generator.py` (30KB) are disproportionately large.** Deserve own subdirectory or should be split. |
| F-TT5 | **LOW** | **No `conftest.py`.** Every test independently manages imports and repo root with `sys.path.insert()`. |

### 10.3 Recommended Reorganization

```
tools/specdev_tools/
  ├── cli.py
  ├── core/           (registry, errors, trace_types)
  ├── validation/     (validate, validators/, linting/, sync/)
  ├── generation/     (prompt_generator, schema_differ)
  └── canonical/      (autofix, registry, integrity, lint)

tests/
  ├── conftest.py
  ├── unit/           (per-tool unit tests)
  ├── integration/    (pipeline tests)
  ├── contracts/      (schema/prompt contract tests)
  └── fixtures/       (unchanged)
```

---

## 11. Codebase Cleanup

### 11.1 Test Suite: B* Legacy Naming

| ID | Severity | Finding |
|----|----------|---------|
| F-6.1a | **HIGH** | **8 test files use `B*` naming convention** referencing irrelevant batch numbering: `test_b4_schema_contracts.py`, `test_cli_b3.py`, `test_error_code_coverage_b2.py`, `test_fixtures_lint_b2.py`, `test_step_03_10_b2.py`, `test_step_validators_b2.py`, `test_validate_b2_integration.py`, `test_prompt_b4_contracts.py`. |
| F-6.1b | **MEDIUM** | **Tests use `unittest.TestCase` without test runner config** — no `pytest.ini` or `pyproject.toml[tool.pytest]`. |
| F-6.1c | **MEDIUM** | **No `conftest.py` or shared fixtures.** Every test independently computes `self.repo_root = Path(__file__).resolve().parents[1]` and `sys.path.insert(0, ...)`. |

### 11.2 Repository Structure

| ID | Severity | Finding |
|----|----------|---------|
| F-6.2a | **LOW** | **`UNKNOWN.egg-info` in `tools/` should be gitignored.** |
| F-6.2b | **LOW** | **`tools/trace_matrix.json` is a runtime artifact, not source.** Should be gitignored. |

---

## 12. Migration System Review

### 12.1 Current State

14 Handlebars-style templates in `migration_prompts/`: `template_add_field.md`, `template_add_step.md`, `template_archive_extension.md`, `template_infer_missing.md`, `template_json_to_prose.md`, `template_prose_to_json.md`, `template_remove_field.md`, `template_rename_field.md`, `template_resolve_conflict.md`, `template_step_merge.md`, `template_step_rename.md`, `template_step_split.md`, `template_type_coercion.md`, `template_validate_traces.md`.

### 12.2 Findings

| ID | Severity | Finding |
|----|----------|---------|
| F-M1 | **CRITICAL** | **No orchestration tool detects which migration template to apply.** No `migration_planner.py` comparing old schema against new to determine needed templates. Selection is manual. |
| F-M2 | **CRITICAL** | **`_migration_notes` and `_needs_review` are NOT in ANY schema.** Every schema has `additionalProperties: false`. Templates instruct agent to add these fields → resulting JSON **FAILS schema validation**. Templates produce invalid output by design. |
| F-M3 | **HIGH** | **No version comparison logic.** Templates reference `{{SOURCE_VERSION}}`/`{{TARGET_VERSION}}` but no tool reads current spec version, reads target toolkit version, computes diff, or generates migration plan. |
| F-M4 | **HIGH** | **No rollback mechanism.** Partial migration failure (e.g., `step_split` succeeds for file 1 but fails for file 2) is unrecoverable. |
| F-M5 | **HIGH** | **`template_step_merge.md` L109 emits relative `$schema` path** (`../devspec_toolkit/schema/...`) instead of canonical URI. Fails validation because `validate.py` uses `$schema` URI for registry lookup. |
| F-M6 | **HIGH** | **Templates don't mandate B4 fields.** Post-migration artifacts must include `generation_quality`, `canonical_refs_used`, etc. — no template mentions this. |
| F-M7 | **MEDIUM** | **No test coverage for any migration template.** No test validates templates produce valid output with real data. |
| F-M8 | **MEDIUM** | **Templates assume single-file operations.** Real migrations need coordinated multi-file changes. |
| F-M9 | **LOW** | **Handlebars syntax (`{{#each}}`) not natively parseable by Python.** Orchestrator would need Handlebars library or format change. |

---

## 13. Hallucination & Quality Safeguards

| ID | Severity | Finding | Location |
|----|----------|---------|----------|
| F-7.1a | **CRITICAL** | **Hardcoded project-specific fields in `16_impl_context.schema.json`.** `nfr_measurement_methods` and `timeout_constants` must use `patternProperties`. Same as F-5.2a. | `16_impl_context.schema.json` L747-803 |
| F-7.1b | **HIGH** | **No deep validators for 16a/16b/16c.** Same as F-5.2b. | `validate.py` L315-339 |
| F-7.1c | **HIGH** | **Reviewer `ci_status` gate prompt-only.** Same as F-2.2c / F-T4. | `step_16.py`, `prompt_16c` |
| F-7.1d | **HIGH** | **`seed_refs` has no integrity verification.** Same as F-1.2b. | `collections.schema.json#seedRef` |
| F-7.1e | **MEDIUM** | **`prompt_generator.py` (30KB) — largest tool.** Must stay in sync with prompt template changes. | `prompt_generator.py` |
| F-7.2 | **MEDIUM** | **Hallucination lint doesn't check** file paths in `existing_structures`, test commands in `linked_test_expectation`, or NFR IDs vs `07_nfrs.json`. | `hallucination_lint.py` |
| F-7.3 | **MEDIUM** | **`placeholder_scan.tokens_found` is agent self-reported.** No independent scan runs against output. | All schemas |
| F-7.4 | **MEDIUM** | **`generation_quality.assumptions` captured but never validated.** Agent declares assumptions but no tool checks them for anti-patterns (TBD markers, unbound IDs, vague language). | All schemas |
| F-PSS1 | **MEDIUM** | **`prompt_schema_sync.py` `_step_from_prompt_name()` L362-363 maps 16a/16b/16c → "16".** Sub-step-specific drift is undetectable — all three sub-step prompts are validated against the same Step 16 schema, but each sub-step generates different artifact shapes (planner vs coder vs reviewer). Drift specific to a sub-step will be missed. | `prompt_schema_sync.py` L357-364 |
| F-DOC1 | **MEDIUM** | **`getting_started.md` L66 shows version `0.1.0` in example.** Stale — toolkit is at v0.2.x heading to v0.3.0. | `docs/developers/getting_started.md` L63-68 |
| F-DOC2 | **LOW** | **`reference.md` L97-99 suggests running integration tests as standalone scripts.** Non-standard; should use `pytest` runner instead. | `docs/developers/reference.md` L94-99 |
| F-DOC3 | **LOW** | **`reference.md` L24 scope lock path says `devspec_toolkit/spec`.** Could confuse consumer repos whose spec dir is `spec/`, not inside the submodule. | `docs/developers/reference.md` L22-25 |

---

## 14. Toolkit Update Workflow Checklist

> [!CAUTION]
> No formal checklist exists. Prompt semantics, guidance, and documentation must all be updated — not just field definitions.

**Schema Change:**
1. [ ] Update the schema file (`schema/*.schema.json`)
2. [ ] Update `schema_registry.json` if URI changed or new schema
3. [ ] Update the corresponding prompt(s):
   - [ ] Field-by-Field Guidance section
   - [ ] Output Contract (JSON example)
   - [ ] Self-Audit Gate items
   - [ ] Negative Constraints / Forbidden Actions
   - [ ] Clarification Questions (if new fields create ambiguity)
   - [ ] Best Practices and Common Pitfalls
   - [ ] Quick Reference section  
   - [ ] Hardening Protocol (if new constraints)
4. [ ] Update `shared_expectations.md` if cross-step behavior affected
5. [ ] Update deep validator (`validators/step_*.py`)
6. [ ] Update `prompt_schema_sync.py` drift-sensitive fields if applicable
7. [ ] Update affected test fixtures (`tests/fixtures/step_*/*.json`)
8. [ ] Update affected test files (`tests/test_*.py`)
9. [ ] Run `prompt-schema-sync`
10. [ ] Run full test suite (`pytest tests/`)
11. [ ] Update documentation:
    - [ ] `docs/developers/reference.md`
    - [ ] `docs/developers/getting_started.md` (if new features)
    - [ ] `CHANGELOG.md` and `changelog/` machine entries  
    - [ ] `README.md` (if user-visible)
12. [ ] Bump version in `tools/pyproject.toml`
13. [ ] If migration needed: create migration template + test

**Prompt Change:**
1. [ ] Verify schema still matches prompt's field definitions
2. [ ] Run `prompt-schema-sync`
3. [ ] Update affected test expectations
4. [ ] If guidance/semantics changed: update corresponding documentation
5. [ ] If upstream/downstream steps affected: update those prompts too

**Canonical Registry Change:**
1. [ ] Update `canon/manifest.json`
2. [ ] Update `canon/aliases.json` if applicable
3. [ ] Run `canonical_lint` and `canonical_integrity` checks
4. [ ] Update `test_canonical_*.py` tests

---

## 15. `devspec_env` Clarification

**Status:** RESOLVED — gitignored virtual environment for running toolkit tools/scripts. `init_project.py` creates `dev_env/` in the product root (not inside toolkit). No action needed beyond documenting in README.

---

## 16. Step 13 Extension Generator Hardening (2026-04-10)

**Status:** IN-PROGRESS — Full plan at `WIP/step13-extension-generator-fix-plan.md`. 21 findings (F1, F3–F10, FC, F15–F21, F26–F28). Scope expanded from step 13 fix to full canonical-ref drift sweep across the toolkit.

Key findings:
- **F1**: Schema `minItems: 1` contradicts prompt "return empty array" — added `extension_decision` with `allOf` conditional
- **FC**: Canonical ref prose→const sweep across 15+ schemas — all `*_ref` fields now use `allOf: [$ref, {const}]`
- **F4**: Registered `mandatory`/`recommended`/`optional` governance labels in core canon
- **F9**: Aligned schema `required[]` with validator enforcement; deleted dead `verification_rules` branch
- **F10**: Dropped `file_name` field (derived from `extension_id`)
- **F15**: Bridge test rot repair — all scripts replaced with thin CLI wrappers, zero `TODO(TEST-004)` remaining
- **F19**: Closed all 5 W552 canon-schema-alignment warnings
- **F28**: Refactored `_load_governance_labels()` for testability (SoC, mirrors step_13a pattern)

---

## 17. Step 16 Anchor Architecture (2026-04-15)

**Status:** DECIDED — Full analysis in `WIP/trans/step16_anchor_bloat_report.md`. Root cause and architectural decision recorded below.

### 17.1 Problem Summary

The Step 16 Trinity Anchor (`spec/16_impl_context.json`) is a **scope declaration spanning all milestones**. The Step 16a planner (`spec/impl_context/*.json`) is a **detailed implementation contract for one milestone**. They share one schema (`vc:16-impl-context`) and one base validator (`validate_step_16()`). Every rule in the base validator was designed for 16a. The anchor is validated as if it were a milestone plan.

### 17.2 Findings

| ID | Severity | Finding | Location |
|----|----------|---------|----------|
| F-ANC-1 | **CRITICAL** | **E307 has no `spec_ref.type` filter.** `_check_behavior_validation_pairing` groups by `spec_ref.id` regardless of type. Task references (`type: "doc"`) require the same behavior+validation pairing as FRs, forcing 52 hollow stub items (26 tasks × 2) into the anchor. Docstring says "for every roadmap task" but code hits every ref id. | `step_16.py:51-85` |
| F-ANC-2 | **CRITICAL** | **E304 path resolution is backwards.** `roadmap_path = artifact_path.parent / "14_roadmap.json"` resolves correctly for the anchor (`spec/`) but fails silently for 16a plans (`spec/impl_context/` has no roadmap). E304 — which should enforce task coverage on 16a — fires only on the anchor, which should not need task-level coverage. | `step_16.py:364-365` |
| F-ANC-3 | **HIGH** | **The anchor's only unique purpose (drift check against active milestone contexts) is unenforced prose.** Prompt Operating Flow step 4: "MUST verify no `checklist[].id`, `scope_in`, or `scope_out` contradicts active 16a/b/c contexts." Zero lines of code implement this comparison in any validator. | `prompt_16_impl_context.md:53`, all `step_16*.py` |
| F-ANC-4 | **HIGH** | **Single schema enforces the wrong contract on the anchor.** `vc:16-impl-context` allows `execution` and `review` sections on the anchor (wrong), requires `fixture_ref`/`nfr_refs` on behavior/validation items (wrong for anchor), has no field to declare artifact role. Role is inferred from file path, which is brittle. | `16_impl_context.schema.json`, `step_16.py:130-137` |

### 17.3 Architectural Decision

> **Dedicated anchor schema (`vc:16-anchor`) must ship with the drift check implementation — either together or not at all.**

Rationale:
- Schema split alone (without drift check): correctly defines the anchor's structure but still provides near-zero unique value vs. 16a.
- Drift check alone (without schema split): implements the anchor's real job but LLMs can still author invalid anchors (with `execution`, `fixture_ref`, etc.) because the shared schema permits them.
- Together: schema makes incorrect anchors impossible by construction; drift check makes the anchor's enforcement role load-bearing.

Option A (role inference in validator via path heuristic) is a viable stopgap but not the correct end state — role must be encoded in the artifact, not reverse-engineered from file path.

### 17.4 What the Anchor Schema Enforces (vs. `vc:16-impl-context`)

| Field | `vc:16-anchor` | `vc:16-impl-context` (16a/16b/16c) |
|-------|---------------|--------------------------------------|
| `plan.summary` | required | required |
| `plan.summary.scope_in` / `scope_out` | required (capability categories) | required (per-milestone scope categories) |
| `plan.summary.target_file_patterns` | **absent** (per-milestone concern) | **required** (E520 file-scope guard in step_16.py) |
| `plan.ambiguities` | **required** | optional |
| `plan.drift` | **required** | optional |
| `plan.milestone_index` | **required** (can be `[]`) | **absent** |
| `plan.spec_alignment.checklist` | **absent** — replaced by `plan.milestone_index` | required (full detail) |
| `execution` | **forbidden** | optional (added by 16b) |
| `review` | **forbidden** | optional (added by 16c) |

> **Why `target_file_patterns` is per-milestone, not anchor-level (audit follow-up, 2026-04-16):** the anchor describes scope at the *category* level (`auth`, `payments`) so it can detect cross-milestone conflicts in `scope_in` ∩ `scope_out` without needing to know what files exist on disk. File-level enforcement is the per-milestone validator's job: `step_16.py` checks `implementation.files_touched ⊆ plan.summary.target_file_patterns` and fires E520 on violations. Putting `target_file_patterns` on the anchor would force the anchor to enumerate every file across every milestone (the bloat problem `WIP/step16_anchor_bloat_report.md` set out to eliminate) without adding any check the per-milestone validator does not already perform on a more targeted surface.

**Why checklist is absent from the anchor:**

The 16a planner prompt (line 28–29) says to "extract Trinity Anchor scope_in, scope_out, and active checklist items" to avoid drift. What 16a actually needs is: (a) which FRs/APIs are assigned to which milestone, and (b) which checklist ID prefixes are already allocated. `plan.milestone_index` provides both more compactly than a per-FR×2 checklist.

Cross-milestone drift detection (E309, see Task 2.8) is implemented by comparing milestone contexts against each other directly — this is strictly stronger than anchor-vs-milestone comparison because it catches conflicts between any two milestones regardless of what the anchor records.

**`plan.milestone_index` item shape:**
```json
{
  "milestone_id": "ms-auth",
  "context_path": "spec/impl_context/ms_auth_plan.json",
  "status": "pending | in_progress | done | deferred",
  "fr_refs": ["fr-login", "fr-signup"],
  "checklist_id_prefix": "AUTH",
  "summary": "One-line status"
}
```
`fr_refs` enables cross-milestone FR ownership conflict detection (same FR in-flight in two milestones). `checklist_id_prefix` gives 16a the namespace it needs to allocate IDs without collisions.

> **Implementation note (2026-04-16):** the original RFC draft listed the status enum as `"active | done | planned"`. The implemented schema reuses `vc:core:atoms#milestoneStatus` (the same atom `14_roadmap.json` uses) so the enum is `pending | in_progress | done | deferred`. Only `done` is exempt from FR ownership conflict detection; `pending`, `in_progress`, and `deferred` all participate. This deviation is intentional — sharing the atom keeps the anchor and roadmap milestone vocabulary in lockstep.

---

# Part B: Dependency-Ordered Implementation Plan

> [!IMPORTANT]
> **61 unique findings** from both review passes. Every finding maps to a task below.  
> Tasks are strictly dependency-ordered. No rework if executed in sequence.  
> Tags: **[SCHEMA]** = schema change, **[TOOL]** = tooling change, **[PROMPT]** = prompt change, **[TEST]** = test change, **[DOC]** = documentation.

---

## Phase 0: Foundation & Cleanup (No Dependencies)

### Task 0.1 — Generalize `16_impl_context.schema.json` [SCHEMA]
**Fixes:** F-5.2a, F-7.1a  
**Status: DONE** — `nfr_measurement_methods` and `timeout_constants` already use `patternProperties` (lines 884–927). No code change needed.  
**Files:** [schema/16_impl_context.schema.json](file:///Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/16_impl_context.schema.json)  
**Action:**
- ~~Replace `nfr_measurement_methods` (L747-788) with `patternProperties`~~: already implemented at lines 884–927 ✓
- ~~Replace `timeout_constants` (L789-803) with `patternProperties`~~: already implemented at lines 884–927 ✓
- Add `_migration_notes` as allowed optional property across all step schemas
- Update test fixtures referencing these fields

### Task 0.2 — Align schema vs validator requirements [SCHEMA]
**Fixes:** F-2.2a, F-2.2b  
**Files:** [16_impl_context.schema.json](file:///Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/16_impl_context.schema.json), [step_16.py](file:///Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/validators/step_16.py)  
**Action:**
- Make `nfr_refs` and `fixture_ref` required in schema via `allOf/if/then` for non-deferred items
- Fix evidence conditional to not rely on `default` value for `status`

> **Note:** `nfr_refs`/`fixture_ref` requirements apply to `vc:16-impl-context` (16a/16b/16c) only. The anchor (`vc:16-anchor`, Task 2.7) explicitly forbids these fields. Do not add the `allOf/if/then` constraint to the anchor schema when it is created.

### Task 0.3 — Repository cleanup [TOOL/DOC]
**Fixes:** F-6.2a, F-6.2b  
**Files:** `.gitignore`, `README.md`  
**Action:** Add `**/UNKNOWN.egg-info/`, `tools/trace_matrix.json` to `.gitignore`. Document `devspec_env` purpose.

### Task 0.4 — Fix migration template output contracts [PROMPT]
**Fixes:** F-M2, F-M5, F-M6  
**Files:** All 14 files in `migration_prompts/`  
**Action:** Fix `$schema` URIs to canonical form, add B4 fields to output contracts, reference `_migration_notes` allowed by Task 0.1.

### Task 0.5 — Unify path references across prompts [PROMPT/DOC]
**Fixes:** F-P1, F-P4, F-1.1b, F-5.3a  
**Files:** All 22 prompt files, NEW `docs/developers/path_conventions.md`  
**Action:**
- Define `$PRODUCT_ROOT`/`$TOOLKIT_ROOT`/`$SPEC_DIR`/`$SCHEMA_DIR` convention
- Remove `example/devspec_kit/` references from prompts 00, 01, 04, 08; use in-prompt Output Contract instead
- Document dual-root convention

> Note: F-1.1c (shared_expectations path) was marked RESOLVED after targeted review — path is consistent across all prompts.

---

## Phase 1: Seed & Spec Dependency Hardening (Depends on Phase 0)

### Task 1.1 — Extend `step_order.json` with required spec inputs [SCHEMA/TOOL]
**Fixes:** F-S1, F-S2, F-1.1a  
**Files:** [step_order.json](file:///Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/step_order.json), [dependency_order_lint.py](file:///Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/dependency_order_lint.py)  
**Action:** Add `required_spec_inputs`, `required_seed_inputs`, and `extraction_intent` per step. Update linter to validate prompts reference all required inputs.

### Task 1.2 — Add `spec_refs_ingested` to schemas [SCHEMA]
**Fixes:** F-S3  
**Files:** [collections.schema.json](file:///Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/core/collections.schema.json), all step schemas  
**Action:** Add `spec_refs_ingested` array (`{step_id, artifact_id, hash}`) to every step schema. Update all prompts.

### Task 1.3 — Add `seed_refs` integrity fields [SCHEMA]
**Fixes:** F-1.2b, F-7.1d  
**Files:** [collections.schema.json](file:///Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/schema/core/collections.schema.json) `seedRef`  
**Action:** Add optional `hash` (SHA-256, `"^[0-9a-f]{64}$"`) and `version` fields to `seedRef`.

### Task 1.4 — Add `extraction_intent` processing to prompts [PROMPT]
**Fixes:** F-1.2a, F-1.2c, F-4.1a, F-S4  
**Files:** All 22 prompt files  
**Action:** Each prompt's "Context To Ingest" must declare extraction intent for each seed/spec: what to extract, what output field it feeds. Reference `step_order.json` as authority.

### Task 1.5 — Validate seed manifest coverage [TOOL]
**Fixes:** F-4.2a, F-4.2b  
**Files:** [seed_lint.py](file:///Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/seed_lint.py)  
**Action:** Validate `seeds[].path` exists on disk. Warn if on-disk seed docs are not in manifest.

### Task 1.6 — Register deep validators for 16a/16b/16c [TOOL]
**Fixes:** F-5.2b, F-5.2c, F-7.1b  
**Files:** `tools/specdev_tools/validation/validate.py` (verification only — no code change)  
**Action:** VERIFICATION ONLY. Confirm existing implementation is correct before the anchor split:
- `DEEP_VALIDATORS["16"]` → `validate_step_16()` at line 472 ✓
- `DEEP_VALIDATORS["16a"]` → `validate_step_16a()` at line 473 ✓
- `DEEP_VALIDATORS["16b"]` → `validate_step_16b()` at line 474 ✓
- `DEEP_VALIDATORS["16c"]` → `validate_step_16c()` at line 475 ✓
- `IMPL_CONTEXT_DIR_RE` pattern at line 60 + `impl_context/` → `"16"` mapping at line 80-81 ✓ (accepted temporary limitation: all impl_context/ artifacts currently route to "16" dispatch → validate_step_16(); sub-step-specific routing is deferred to Task 2.8 resolution noted there)

No code change needed. The `"16"` dispatch entry and `impl_context/` path mapping are already correct for the current state. Both will be updated by Task 2.8 when the anchor split lands.

> **Note:** Do not modify `DEEP_VALIDATORS["16"]` here. The anchor split (Task 2.8) will replace it with `validate_step_16_anchor()` and fix the `impl_context/` path routing at the same time.

---

## Phase 2: Roadmap & Implementation Hardening (Depends on Phase 1)

### Task 2.1 — Harden roadmap schema for AI-driven development [SCHEMA/PROMPT/TOOL]
**Fixes:** F-R1 through F-R6, F-1.3a, F-1.3b  
**Files:** `schema/14_roadmap.schema.json`, `prompts/prompt_14_roadmap.md`, `validators/step_14.py`  
**Action:**
- Add required `fr_refs`, `capability_refs` to milestone schema
- Make `acceptance_criteria` required on all tasks with `minItems: 1`, `text.minLength: 15`
- Add `depends_on` (kebabIdArray), `assumptions` (array, can be empty), `exit_conditions` (array, minItems 1) to task schema
- Add validator: tech_stack cross-reference against `09_impl_plan.json`
- Add validator: milestone date ordering, task dependency acyclicity

### Task 2.2 — Fix roadmap-to-checklist coverage validator for 16a [TOOL]
**Fixes:** F-2.1a, F-2.1b, F-T3, F-ANC-1, F-ANC-2  
**Files:** `tools/specdev_tools/validation/validators/step_16.py`  
**Action:**
- **Fix E307 `spec_ref.type` filter (F-ANC-1):** `_check_behavior_validation_pairing` groups by `spec_ref.id` without filtering type, forcing task references (`type: "doc"`) to require behavior+validation pairs. Add a type filter to exclude non-behavioral ref types:
  ```python
  # In _check_behavior_validation_pairing — skip non-behavioral ref types
  if spec_ref.get("type") in {"doc", "code"}:
      continue
  ```
  This removes ~52 hollow stub items (26 task-* IDs × 2) from anchor artifacts and is correct for milestone plans too (task refs are work items, not testable behaviors). Fix the misleading docstring: "For every roadmap task" → "For every behavioral spec ref (fr, api, inv, nfr)".
- **Fix E304 path resolution (F-ANC-2):** `roadmap_path = artifact_path.parent / "14_roadmap.json"` resolves correctly for the anchor (`spec/`) but silently skips 16a plans (`spec/impl_context/` has no roadmap). Fix: when `spec_path` is inside `impl_context/`, resolve as `artifact_path.parent.parent / "14_roadmap.json"`.
- E304 must fire on 16a plans (currently it silently skips them). It must NOT fire on the anchor (the anchor's task-coverage enforcement is the drift check in Task 2.8, not E304).
- Add `_is_anchor(spec_path)` helper to gate E304 on anchor artifacts. **Use path heuristic only at this stage** (Task 2.7's `artifact_role` field does not exist yet):
  ```python
  def _is_anchor(spec_path: str | None) -> bool:
      if not spec_path:
          return False
      p = Path(spec_path)
      return p.name == "16_impl_context.json" and p.parent.name != "impl_context"
  ```
  Add a `# TODO: upgrade to artifact_role field check after Task 2.7` comment. This helper is reused by Task 2.8.
- **Extract `_load_roadmap(spec_path) -> Optional[dict]` as a shared helper** (DRY): both the E304 block (lines 362–418) and the W581 block (lines 419–450+) independently open `14_roadmap.json` with the same wrong path (`artifact_path.parent / "14_roadmap.json"`). Extract the helper with the **corrected path resolution** (parent.parent when inside impl_context/), and update **both** the E304 and W581 callers to use it. Fixing only E304's path without fixing W581's is a regression — W581 would still silently resolve the wrong path for 16a artifacts.

> **Scope clarification (vs. original plan):** E304 was originally added to `step_16.py` targeting the anchor. The anchor analysis (Section 17) showed E304 belongs on 16a, not the anchor. This task corrects that direction. The anchor's task-coverage enforcement is replaced by the drift check in Task 2.8. The E307 type-filter fix is also assigned here (not Tasks 2.7/2.8 as the original cross-ref table stated).

### Task 2.3 — Add `ci_status` gate enforcement [TOOL]
**Fixes:** F-2.2c, F-T4, F-7.1c  
**Files:** [step_16.py](file:///Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/validators/step_16.py)  
**Action:** Add E303 error for `verdict: verified` with `ci_status == red`.

### Task 2.4 — Add planned-vs-executed validator [TOOL]
**Fixes:** F-T5  
**Files:** [step_16.py](file:///Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/validators/step_16.py)  
**Action:** Diff planned actions (16a) vs executed actions (16b), flag gaps.

### Task 2.5 — Add `semantic_review` to implementation schema [SCHEMA/PROMPT]
**Fixes:** F-T1, F-T2  
**Files:** `schema/16_impl_context.schema.json`, `prompts/prompt_16c_impl_reviewer.md`  
**Action:** Add `semantic_review` object with `fr_coverage[]`, `hallucinated_features[]`. Add structured semantic review checklist to 16c prompt.

### Task 2.6 — Mandate roadmap task→checklist mapping in prompt 16a [PROMPT]
**Fixes:** F-2.1b, F-3.2b  
**Files:** `prompts/prompt_16a_impl_planner.md`  
**Action:** Mandate every roadmap `tasks[].task_id` → checklist item. Add error path rule: every `behavior` checklist item must have corresponding `validation` item.

### Task 2.7 — Create dedicated anchor schema `vc:16-anchor` [SCHEMA]
**Fixes:** F-ANC-4  
**Depends on:** Task 0.1 (schema generalization). (Task 1.6 is verification-only — confirm `DEEP_VALIDATORS` are in the correct state before merging Task 2.7.)  
**Must ship with:** Task 2.8 (drift check) — do not merge Task 2.7 without Task 2.8  
**Files:**
- NEW `schema/16_anchor.schema.json`
- `tools/schema_registry.json` (add `vc:16-anchor` entry — do NOT remove `vc:16-impl-context`)
- `tools/specdev_tools/generation/prompt_schema_sync.py` (step-key collision fix + `_PROMPT_STEP_OVERRIDE`)
- `prompts/prompt_16_impl_context.md` (update `# Schema Reference` section)
- `tests/fixtures/step_16/` (migrate all fixtures to new schema — see fixture migration note)

**Action:**
- **Define `plan.drift` schema structure before authoring the schema:**
  ```json
  "drift": {
    "type": "object",
    "required": ["checks"],
    "properties": {
      "checks": { "type": "array", "minItems": 0, "items": { "type": "string" } }
    }
  }
  ```
  Note: `minItems: 0` allows an initial anchor with no milestone contexts yet to be valid. Drift checks are populated as milestone plans are created and drift is detected.

  Define `plan.ambiguities` item schema — **reuse the shared `crossCycleAmbiguityItem` $def in `vc:core:collections`** (fields: `id`, `description`, `severity`, plus optional `impact`, `status`, `status_ref`). Note: the RFC previously listed `context` and `resolution` as field names — these are wrong. Use `description` instead of `context`; use `status`/`status_ref` for resolution tracking. The `crossCycleAmbiguityItem` $def was extracted (2026-04-16) from the previously-inlined emergent ambiguities shape so the anchor and `emergent_ambiguities` (16b) share one source of truth. `plan.ambiguities` is **required** in `vc:16-anchor`, can be empty array (`minItems: 0`).
- Define `vc:16-anchor` schema with the contract in Section 17.4:
  - Root-level `artifact_role: { "const": "anchor" }` — **required**, enables `_is_anchor()` upgrade in Task 2.8
  - `plan.ambiguities` and `plan.drift` as **required** (enforced by schema, not re-checked by validator)
  - `plan.milestone_index`: **required** array (`minItems: 0` — empty on initial anchor is valid). Each item: `milestone_id` (string, required), `context_path` (string, required), `status` (enum from `vc:core:atoms#milestoneStatus` — `pending | in_progress | done | deferred`, required; only `done` is exempt from FR-ownership conflict detection), `fr_refs` (array of `^(fr|api)-` IDs, required), `checklist_id_prefix` (string, required — the namespace 16a uses to allocate IDs without collision), `summary` (string, required, `minLength: 10`)
  - `plan.spec_alignment.checklist`: **absent** — do not define this field in `vc:16-anchor`. The anchor does not maintain a per-FR checklist; that detail lives in 16a. The `plan.milestone_index[].fr_refs` and `plan.milestone_index[].checklist_id_prefix` fields replace what 16a needs from the anchor for scope comparison and ID allocation.
  - `execution` and `review` sections: **forbidden** (`unevaluatedProperties: false` or `not` pattern)
- **Add `vc:16-anchor` entry to `schema_registry.json`:**
  ```json
  "vc:16-anchor": "schema/16_anchor.schema.json"
  ```
  **Do NOT remove `vc:16-impl-context`.** It is still referenced by 16a/16b/16c artifacts. The registry is URI-keyed — "remapping step 16" means adding a new entry, not touching the existing one.
- **Update `prompt_schema_sync.py` — fix step-key collision:**
  `run_prompt_schema_sync` extracts step from schema filenames via `Path(schema_file).name.split("_", 1)[0]`. After adding `schema/16_anchor.schema.json`, **both** `16_anchor.schema.json` and `16_impl_context.schema.json` produce step `"16"`. Alphabetically, `16_impl_context` is processed second and **overwrites** `schema_contracts["16"]`, making the anchor schema invisible. After Task 2.7, `prompt_16_impl_context.md` references `vc:16-anchor` but `schema_contracts["16"]` = impl-context schema → **false E310 fires**.

  **Fix 1 — unique step key in the schema-contracts loop** (line ~43 of `run_prompt_schema_sync`):
  ```python
  step = Path(schema_file).name.split("_", 1)[0]
  # Anchor schema has the same numeric prefix as impl-context — give it a distinct key
  if Path(schema_file).name == "16_anchor.schema.json":
      step = "16anchor"
  ```

  **Fix 2 — prompt-to-step override in `_validate_output_contracts`**:
  ```python
  # Prompt filename → step key override (for filenames the regex maps wrongly or ambiguously)
  _PROMPT_STEP_OVERRIDE: dict[str, str] = {
      "prompt_16_impl_context.md": "16anchor",
  }
  ...
  # In _validate_output_contracts loop (line ~339), replace the step extraction:
  step = _PROMPT_STEP_OVERRIDE.get(Path(prompt_path).name) or _step_from_prompt_name(Path(prompt_path).name)
  ```

  **Do NOT change `_SUBSTEP_TO_BASE_SCHEMA`** — keep it as `{"16a": "16", "16b": "16", "16c": "16"}`. With `schema_contracts["16"]` = impl-context schema (the anchor is under `"16anchor"`), 16a/16b/16c correctly validate against the impl-context schema. *(The previously proposed `"16-impl"` registry key was broken: `schema_contracts` is keyed by filename prefix, never by registry key; `schema_contracts["16-impl"]` would never be populated, causing 16a/b/c validation to be silently skipped.)*

  **`_step_from_prompt_name()` requires no change**: the regex `r"prompt_(\d{2}[a-z]?)_"` already matches `prompt_16_impl_context.md` — it matches `prompt_16_` and returns `"16"`. The previous claim that this prompt is "silently skipped" was incorrect.

  **Do NOT add `"16-impl"` to `schema_registry.json`** — it is not needed and was part of the broken approach above.
- Update `prompt_16_impl_context.md` schema reference from `vc:16-impl-context` to `vc:16-anchor`
- **Fixture migration (all `tests/fixtures/step_16/*.json`):**
  - Update `"$schema"` from `"vc:16-impl-context"` to `"vc:16-anchor"` in every fixture
  - Add `"artifact_role": "anchor"` to each
  - Add `"plan.drift": { "checks": ["..."] }` and `"plan.ambiguities": []` if missing
  - Add `"plan.milestone_index": []` (or a minimal populated entry for fixtures testing milestone_index behaviour)
  - **Remove `plan.spec_alignment.checklist`** entirely — the anchor schema does not define this field; presence will cause schema validation failure under `unevaluatedProperties: false`
  - Remove any `execution` or `review` sections present
  - Update test expectations in `tests/integration/test_step_16.py`: E309 tests that previously required an anchor checklist entry must be rewritten to use the cross-milestone comparison approach (two fixture milestone context files with conflicting IDs)

### Task 2.8 — Implement anchor↔milestone drift check [TOOL]
**Fixes:** F-ANC-2, F-ANC-3  
**Depends on:** Task 2.7 (anchor schema must exist first)  
**Must ship with:** Task 2.7 — do not merge Task 2.8 without Task 2.7  
**Files:**
- NEW `tools/specdev_tools/validation/validators/step_16_anchor.py`
- `tools/specdev_tools/validation/validate.py` (update `"16"` dispatch + fix `_get_step_from_path`)
- `tools/specdev_tools/core/errors.py` (register new error codes)
- NEW `tests/integration/test_step_16_anchor.py`

**Action:**
- **Register new error codes in `errors.py` first** (required before `make_error()` can use them):
  ```python
  "E308": "ANCHOR_SCOPE_DRIFT",
  "E309": "ANCHOR_CHECKLIST_DRIFT",
  ```
- **Write `validate_step_16_anchor(data, toolkit_root, spec_path)`:**
  - Do NOT call `validate_step_16()` — the anchor has its own contract. Schema validation handles required field presence (`plan.summary`, `plan.drift.checks`, `plan.ambiguities`). The anchor validator only implements cross-artifact logic that schema cannot express.
  - **`_is_anchor()` guard** — `step_16_anchor.py` must import this from `step_16.py`: `from .step_16 import _is_anchor`. Do not duplicate it. (`step_16.py` still needs it for E304/E307 gating; the anchor validator's guard is an additional consumer of the same function. Importing from a sibling validator is acceptable here — the anchor validator depends on the base validator's utility, not vice versa.) If called on a non-anchor artifact, return empty errors with a warning.
  - **Implement the drift check** (the anchor's only unique job — currently unenforced prose in `prompt_16_impl_context.md` Operating Flow step 4):
    - If `spec_path` is `None`: skip drift check, emit W-level warning (use W580 pattern), return early.
    - Derive impl_context dir: `impl_context_dir = Path(spec_path).parent / "impl_context"`. If dir doesn't exist: skip drift check silently (no milestone contexts yet is a valid state).
    - Load each `*.json` in `impl_context_dir`.
    - **E308 (ANCHOR_SCOPE_DRIFT)**: for each milestone context, check if any value in `milestone.plan.summary.scope_in` appears in the anchor's `plan.summary.scope_out`. A scope_in item that is also scope_out is a contradiction — fire E308 identifying the conflicting value and milestone file. Also check the reverse: if a value in `milestone.plan.summary.scope_out` appears in the anchor's `plan.summary.scope_in` — fire E308 (bidirectional). This covers both directions.
    - **E309 (ANCHOR_CHECKLIST_DRIFT) — cross-milestone comparison** (not anchor-vs-milestone): load ALL milestone contexts from `impl_context_dir`. Build a registry: `checklist_id → {spec_ref_id, source_file}`. For each item in each milestone's checklist, if the same `id` was already seen with a different `spec_ref.id`, fire E309. This is strictly stronger than anchor-vs-milestone comparison — it catches ID conflicts between any two milestone plans, not just those that happen to also be in the anchor.
      ```python
      id_registry: dict[str, tuple[str, str]] = {}  # id → (spec_ref_id, source_file)
      for ms_file, ms_data in milestone_contexts.items():
          for item in ms_data.get("plan", {}).get("spec_alignment", {}).get("checklist", []):
              item_id = item.get("id")
              spec_ref_id = (item.get("spec_ref") or {}).get("id")
              if item_id and spec_ref_id:
                  if item_id in id_registry:
                      prev_ref, prev_file = id_registry[item_id]
                      if prev_ref != spec_ref_id:
                          errors.append(make_error("E309", f"ANCHOR_CHECKLIST_DRIFT: checklist id '{item_id}' maps to '{spec_ref_id}' in {ms_file} but '{prev_ref}' in {prev_file}"))
                  else:
                      id_registry[item_id] = (spec_ref_id, ms_file)
      ```
    - **New check — cross-milestone FR ownership conflict**: for each FR/API ID that appears in `plan.milestone_index[].fr_refs` of more than one milestone with `status != "done"`, fire E308 with message "FR ownership conflict: fr-X is claimed by both active milestones ms-A and ms-B". Done milestones do not conflict (the FR has been delivered and may legitimately be referenced in a follow-on milestone for additional work).
  - E307, E304, E520 fixture/NFR checks must NOT be in the anchor validator. They live in `step_16.py` for 16a/16b/16c.
- **Update `validate.py` — two changes required:**
  1. Replace `"16"` dispatch: `"16" → validate_step_16_anchor()` (import the new module)
  2. **Fix `_get_step_from_path`** (currently `impl_context/` → `"16"` — will route 16a artifacts to anchor validator after step 1):
     - `impl_context/` directory → return `"16a"` (not `"16"`)
     - **Note:** All three sub-step artifact types (16a planner, 16b coder, 16c reviewer) reside in `impl_context/`. Routing by directory alone dispatches all to `validate_step_16a()`, silently skipping 16b/16c-specific checks. The correct fix distinguishes them by the artifact's `$schema` URI (`vc:16-impl-context` is shared) or by a `sub_step` field. Preferred approach: read the `$schema` value from the loaded artifact and use `_SUBSTEP_TO_VALIDATOR` dispatch: `{"vc:16-plan": validate_step_16a, "vc:16-code": validate_step_16b, "vc:16-review": validate_step_16c}` — this requires sub-step-specific `$schema` URIs OR a `sub_step: "plan" | "code" | "review"` field in the schema. Resolve this before implementing Task 2.8.
     - Filename `16_impl_context.json` NOT inside `impl_context/` → return `"16"` (anchor); add this rule before the `STEP_FILE_RE` match so the specific name takes priority
- **Upgrade `_is_anchor()` in `step_16.py`** (installed by Task 2.2 as path-heuristic): now that `artifact_role: "anchor"` exists in the schema (Task 2.7), prefer field check with path as fallback:
  ```python
  def _is_anchor(spec_path: str | None, data: dict | None = None) -> bool:
      if data and data.get("artifact_role") == "anchor":
          return True
      if not spec_path:
          return False
      p = Path(spec_path)
      return p.name == "16_impl_context.json" and p.parent.name != "impl_context"
  ```
  This function remains in `step_16.py` and is imported by `step_16_anchor.py` (see above).
- **Add integration tests in `test_step_16_anchor.py`** — no mocking of filesystem reads; use real temp directory fixtures:
  - Create temp dir structure: `tmpdir/spec/16_impl_context.json` + `tmpdir/spec/impl_context/m1_plan.json` + `tmpdir/spec/impl_context/m2_plan.json`
  - Anchor with no drift, clean milestone contexts → passes
  - **E308 (scope drift, forward):** anchor `scope_out: ["payments"]`, milestone `scope_in: ["payments"]` → E308 fires
  - **E308 (scope drift, reverse):** anchor `scope_in: ["auth"]`, milestone `scope_out: ["auth"]` → E308 fires (bidirectional check)
  - **E309 (cross-milestone ID drift):** m1_plan has `id: "CHK-001"` with `spec_ref.id: "fr-login"`, m2_plan has `id: "CHK-001"` with `spec_ref.id: "fr-signup"` → E309 fires (anchor has no checklist — the comparison is milestone-vs-milestone)
  - **E308 (FR ownership conflict):** anchor `milestone_index` has ms-1 (`status: "active"`, `fr_refs: ["fr-login"]`) and ms-2 (`status: "active"`, `fr_refs: ["fr-login"]`) → E308 fires (same FR claimed by two active milestones)
  - FR ownership conflict with one done milestone: ms-1 (`status: "done"`, `fr_refs: ["fr-login"]`), ms-2 (`status: "active"`, `fr_refs: ["fr-login"]`) → passes (done milestones do not block)
  - Anchor missing `plan.drift.checks` → schema validation fires (not validator — field is required in `vc:16-anchor` schema)
  - Anchor missing `plan.milestone_index` → schema validation fires
  - Anchor `spec_path=None` → drift check skipped, W-level warning, no crash
  - `impl_context/` dir empty (no milestone contexts yet) → passes silently (milestone_index may be `[]`)

---

## Phase 3: Semantic Drift Prevention (Depends on Phase 2)

### Task 3.1 — Build transitive traceability validator [TOOL]
**Fixes:** F-3.1a, F-1.2a (enforcement)  
**Files:** NEW `tools/specdev_tools/traceability_closure.py`, update `validate.py`  
**Action:** Validate: every capability → ≥1 FR → ≥1 roadmap milestone → ≥1 checklist item. Report coverage gaps.

### Task 3.2 — Add independent placeholder scan [TOOL]
**Fixes:** F-7.3  
**Files:** [spec_quality_lint.py](file:///Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/spec_quality_lint.py)  
**Action:** Recursively scan all string values for TBD/TODO/PLACEHOLDER/XXX/FIXME tokens. Compare against `placeholder_scan.tokens_found`.

### Task 3.3 — Enhance hallucination lint [TOOL]
**Fixes:** F-7.2, F-3.2a  
**Files:** [hallucination_lint.py](file:///Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/hallucination_lint.py)  
**Action:** Validate `existing_structures` file paths exist on disk. Validate `linked_test_expectation` test files exist. Validate `nfr_refs` against `07_nfrs.json`.

### Task 3.4 — Add coverage closure mandate to all prompts [PROMPT]
**Fixes:** F-1.1a, F-1.1d, F-3.1c  
**Files:** All 22 prompt files  
**Action:** Add "Coverage Closure" section to Self-Audit Gate: every upstream requirement represented, no drops without `out_of_scope`, all `trace` refs valid. Add extraction mandates for steps 04, 14, 16a.

### Task 3.5 — Fix `init_project.py` path resolution [TOOL]
**Fixes:** F-P2, F-P3  
**Files:** [init_project.py](file:///Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/scripts/init_project.py)  
**Action:** Fix seed_templates path resolution. Make toolkit path configurable instead of hardcoded.

### Task 3.6 — Add assumption validation to spec quality lint [TOOL]
**Fixes:** F-7.4  
**Files:** [spec_quality_lint.py](file:///Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/spec_quality_lint.py)  
**Action:** Pattern-based checks only (NLP-based cross-referencing against free-text seeds is not feasible with current tooling):
- Flag assumptions containing TBD/PLACEHOLDER/TODO markers
- Flag assumptions referencing unbound IDs (IDs not present in any spec)
- Flag assumptions with vague quantifiers ("some", "many", "several") without concrete values
- Warn when assumption count exceeds configurable threshold per step

### Task 3.7 — Enhance forward replay for semantic coverage [TOOL]
**Fixes:** F-3.1b  
**Files:** [forward_replay_check.py](file:///Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/forward_replay_check.py)  
**Action:** After detecting structural changes that require re-generation, also verify that the re-generated downstream artifacts maintain the same requirement coverage (IDs present in the old version must appear in the new). Integrate with traceability_closure (Task 3.1) for coverage comparison.

---

## Phase 4: Migration Hardening (Depends on Phase 1)

### Task 4.1 — Build migration orchestrator [TOOL]
**Fixes:** F-M1, F-M3  
**Files:** NEW `tools/specdev_tools/migration_planner.py`  
**Action:** Compare schema versions, detect changes via `schema_differ.py`, map to templates, generate ordered migration plan.

### Task 4.2 — Add migration rollback support [TOOL]
**Fixes:** F-M4  
**Files:** NEW `tools/specdev_tools/migration_runner.py`  
**Action:** Backup-before-modify, restore-on-failure wrapper.

### Task 4.3 — Support multi-file coordinated migrations [TOOL]
**Fixes:** F-M8  
**Files:** `migration_runner.py` (extends Task 4.2)  
**Action:** Atomic multi-file migration with transaction semantics.

### Task 4.4 — Add migration tests [TEST]
**Fixes:** F-M7  
**Files:** NEW `tests/test_migration_templates.py`, new fixtures  
**Action:** Instantiate each template with fixture data, validate results.

### Task 4.5 — Evaluate Handlebars vs Jinja2 [DOC]
**Fixes:** F-M9  
**Files:** Decision doc  
**Action:** If orchestrator is Python, evaluate switching to Jinja2 or Python string templates. Document decision.

---

## Phase 5: Test Suite Migration (Depends on Phase 2)

### Task 5.1 — Create test infrastructure [TEST]
**Fixes:** F-6.1b, F-6.1c, F-TT5  
**Files:** NEW `tests/conftest.py`, `tools/pyproject.toml`  
**Action:** Shared fixtures for `repo_root`, `schema_root`, `spec_root`. Add `[tool.pytest.ini_options]`.

### Task 5.2 — Rename B* test files [TEST]
**Fixes:** F-6.1a  
**Files:** 8 test files (rename + class rename)  
**Action:**
| Old | New |
|-----|-----|
| `test_b4_schema_contracts.py` | `test_schema_contracts.py` |
| `test_cli_b3.py` | `test_cli.py` |
| `test_error_code_coverage_b2.py` | `test_error_code_coverage.py` |
| `test_fixtures_lint_b2.py` | `test_fixtures_lint.py` |
| `test_step_03_10_b2.py` | `test_step_validators_03_10.py` |
| `test_step_validators_b2.py` | `test_step_validators_core.py` |
| `test_validate_b2_integration.py` | `test_validate_integration.py` |
| `test_prompt_b4_contracts.py` | `test_prompt_contracts.py` |

### Task 5.3 — Reorganize tools directory [TOOL]
**Fixes:** F-TT1, F-TT2, F-TT3, F-TT4  
**Files:** `tools/specdev_tools/` restructure  
**Action:** Create `validation/`, `generation/`, `core/`, `canonical/` subdirectories. Move files. Update all imports.

### Task 5.4 — Add tests for all new validators [TEST]
**Fixes:** Covers all new tools from Phases 2-4  
**Files:** NEW test files  
**Action:** Tests for traceability_closure, placeholder_scan, semantic_review, migration_planner, ci_status gate, roadmap-coverage.

---

## Phase 6: Documentation & Version Bump (Depends on All)

### Task 6.1 — Version bump to v0.3.0 [DOC]
**Files:** `tools/pyproject.toml`, `CHANGELOG.md`, `changelog/`

### Task 6.2 — Comprehensive CHANGELOG update [DOC]
**Action:** Document all schema, prompt, tool, and test changes from Phases 0-5.

### Task 6.3 — Update all documentation [DOC]
**Fixes:** F-5.2d, F-7.1e, F-DOC1, F-DOC2, F-DOC3  
**Files:** `docs/developers/reference.md`, `docs/developers/getting_started.md`, `README.md`  
**Action:**
- Path conventions guide, pytest setup, `prompt_generator.py` sync documentation
- Fix stale version `0.1.0` in `getting_started.md` L66
- Fix `reference.md` L97-99 to use pytest runner instead of direct script execution
- Clarify `reference.md` L24 scope lock path for consumer repos

### Task 6.4 — Formalize toolkit update workflow [DOC]
**Files:** NEW `docs/ops/toolkit_update_checklist.md`, NEW `.agents/workflows/toolkit_update.md`  
**Action:** Codify §14 checklist as workflow definition.

### Task 6.5 — Fix prompt_schema_sync sub-step mapping [TOOL]
**Fixes:** F-PSS1  
**Files:** [prompt_schema_sync.py](file:///Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/tools/specdev_tools/prompt_schema_sync.py) L357-364  
**Action:** Update `_step_from_prompt_name()` to return 16a/16b/16c individually (not collapse to "16"). Requires sub-step schemas or a schema variant mapping. May be deferred if sub-step schemas are not created in this release.

---

## Appendix: Complete Finding → Task Cross-Reference

| Finding | Description (abbreviated) | Task | Phase |
|---------|--------------------------|------|-------|
| **F-P1** | No path variable convention | 0.5 | 0 |
| **F-P2** | init_project.py hardcoded nested path | 3.5 | 3 |
| **F-P3** | Schema URIs never resolve HTTP | 3.5 | 3 |
| **F-P4** | run_specdev.sh fragile ROOT | 0.5 | 0 |
| **F-1.1a** | Missing cross-reference matrix | 1.1, 3.4 | 1, 3 |
| **F-1.1b** | example/devspec_kit references | 0.5 | 0 |
| **F-1.1c** | ~~shared_expectations path inconsistent~~ **RESOLVED** | — | — |
| **F-1.1d** | Clarification Questions advisory-only | 3.4 | 3 |
| **F-1.2a** | No requirement-to-spec coverage matrix | 1.4, 3.1 | 1, 3 |
| **F-1.2b** | seed_refs no checksum | 1.3 | 1 |
| **F-1.2c** | step_requirements flat IDs | 1.4 | 1 |
| **F-1.3a** | Roadmap no FR/capability refs | 2.1 | 2 |
| **F-1.3b** | No roadmap coverage validator | 2.1 | 2 |
| **F-S1** | Specs not seeded | 1.1, 1.2 | 1 |
| **F-S2** | step_order vs prompt disconnect | 1.1 | 1 |
| **F-S3** | No spec_refs_ingested | 1.2 | 1 |
| **F-S4** | Seeds free-text, no extraction | 1.4 | 1 |
| **F-ANC-1** | E307 no spec_ref.type filter — task refs get behavior+validation pairing | 2.2 | 2 |
| **F-ANC-2** | E304 path resolution backwards — fires on anchor, skips 16a | 2.2, 2.8 | 2 |
| **F-ANC-3** | Anchor drift check is unenforced prose | 2.8 | 2 |
| **F-ANC-4** | Single schema enforces wrong contract on anchor | 2.7 | 2 |
| **F-2.1a** | No 16↔14 cross-check | 2.2 | 2 |
| **F-2.1b** | 16a doesn't mandate task ingestion | 2.2, 2.6 | 2 |
| **F-2.2a** | Schema evidence conditional fragile | 0.2 | 0 |
| **F-2.2b** | nfr_refs schema vs validator split | 0.2 | 0 |
| **F-2.2c** | ci_status prompt-only | 2.3 | 2 |
| **F-R1** | Roadmap no FR links | 2.1 | 2 |
| **F-R2** | Tasks not atomic enough | 2.1 | 2 |
| **F-R3** | No task dependency graph | 2.1 | 2 |
| **F-R4** | No assumptions field | 2.1 | 2 |
| **F-R5** | No tech_stack hallucination guard | 2.1 | 2 |
| **F-R6** | No date ordering enforcement | 2.1 | 2 |
| **F-T1** | No semantic review tooling | 2.5 | 2 |
| **F-T2** | No test↔acceptance cross-ref | 2.5 | 2 |
| **F-T3** | No checklist↔roadmap validator | 2.2 | 2 |
| **F-T4** | ci_status gate not enforced | 2.3 | 2 |
| **F-T5** | No planned-vs-executed diff | 2.4 | 2 |
| **F-3.1a** | No transitive traceability | 3.1 | 3 |
| **F-3.1b** | Forward replay structural-only | 3.7 | 3 |
| **F-3.1c** | spec_quality no coverage regression | 3.4 | 3 |
| **F-3.2a** | Discovery agent-only | 3.3 | 3 |
| **F-3.2b** | Error paths not mandated | 2.6 | 2 |
| **F-4.1a** | step_requirements no intent | 1.4 | 1 |
| **F-4.2a** | No seed manifest coverage check | 1.5 | 1 |
| **F-4.2b** | seed path not validated | 1.5 | 1 |
| **F-5.1a** | $schema handling (correct) | — | — |
| **F-5.1b** | Unref'd schemas in registry | 6.3 | 6 |
| **F-5.2a** | Hardcoded project NFR IDs | 0.1 | 0 |
| **F-5.2b** | No 16a/b/c deep validators | 1.6 | 1 |
| **F-5.2c** | _get_step_from_path fails impl_context | 2.8 | 2 |
| **F-5.2d** | Canonical path naming inconsistent | 6.3 | 6 |
| **F-5.3a** | Dual-root path undocumented | 0.5 | 0 |
| **F-6.1a** | B* test naming | 5.2 | 5 |
| **F-6.1b** | No pytest config | 5.1 | 5 |
| **F-6.1c** | No conftest.py | 5.1 | 5 |
| **F-6.2a** | egg-info not gitignored | 0.3 | 0 |
| **F-6.2b** | trace_matrix.json not gitignored | 0.3 | 0 |
| **F-TT1** | Tools mix validation + generation | 5.3 | 5 |
| **F-TT2** | Tests mix unit/integration/contract | 5.3 | 5 |
| **F-TT3** | 3-way test/fixture/validator coupling | 5.3 | 5 |
| **F-TT4** | Oversized schema_differ/prompt_gen | 5.3 | 5 |
| **F-TT5** | No conftest.py | 5.1 | 5 |
| **F-M1** | No migration orchestrator | 4.1 | 4 |
| **F-M2** | _migration_notes schema conflict | 0.1, 0.4 | 0 |
| **F-M3** | No version comparison logic | 4.1 | 4 |
| **F-M4** | No rollback | 4.2 | 4 |
| **F-M5** | Bad $schema in merge template | 0.4 | 0 |
| **F-M6** | Templates missing B4 fields | 0.4 | 0 |
| **F-M7** | No migration tests | 4.4 | 4 |
| **F-M8** | Single-file assumption | 4.3 | 4 |
| **F-M9** | Handlebars not Python-native | 4.5 | 4 |
| **F-7.1a** | Hardcoded NFR (= F-5.2a) | 0.1 | 0 |
| **F-7.1b** | No 16a/b/c validators (= F-5.2b) | 1.6 | 1 |
| **F-7.1c** | ci_status gate (= F-2.2c) | 2.3 | 2 |
| **F-7.1d** | seed_refs no integrity (= F-1.2b) | 1.3 | 1 |
| **F-7.1e** | prompt_generator.py sync risk | 6.3 | 6 |
| **F-7.2** | Hallucination lint gaps | 3.3 | 3 |
| **F-7.3** | Placeholder self-reported | 3.2 | 3 |
| **F-7.4** | Assumptions never validated (pattern-based) | 3.6 | 3 |
| **F-PSS1** | prompt_schema_sync 16a/b/c → "16" collapse | 2.7 (anchor split), 6.5 (16a/b/c) | 2, 6 |
| **F-DOC1** | Stale version in getting_started.md | 6.3 | 6 |
| **F-DOC2** | Non-standard test invocation in reference.md | 6.3 | 6 |
| **F-DOC3** | Scope lock path confusing for consumers | 6.3 | 6 |

> **Verification:** 65 unique findings (excl. duplicates marked with `=`). F-5.1a is INFO-only (no task). F-1.1c is RESOLVED (no task). All remaining findings map to ≥1 task.
>
> **Audit log:**
> - 2026-02-23 Pass 1+2 merge: 61 findings
> - 2026-02-23 Targeted review: F-7.4 reassigned 0.2→3.6 (scope mismatch). F-3.1b reassigned 3.1→3.7 (wrong tool). F-1.1c downgraded to RESOLVED (path IS consistent). F-R6 updated (date ordering partially validated). Added 4 new findings: F-PSS1, F-DOC1, F-DOC2, F-DOC3. Task 3.6 descoped to pattern-based checks (NLP infeasible). Added Tasks 6.5 and updated 6.3.
