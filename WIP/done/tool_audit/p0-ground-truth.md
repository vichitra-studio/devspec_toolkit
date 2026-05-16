> **ARCHIVE NOTE (2026-05-16):** Canonical trace_matrix path is now `spec/extras/trace_matrix.json`. The `tools/trace_matrix.json` references below reflect the state at the time of writing.

# P0: Ground Truth Data Snapshot

Captured at: 2026-03-17T00:00:00Z
Repo root: /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/
Branch: codex/canonical-drift-review-plan

---

## 1. Test Suite

### Collection
```
830 tests collected in 0.14s
```

### Full Run
```
830 passed in 36.16s
```

All 830 tests pass. Zero failures, zero skips, zero xfails.

---

## 2. File Inventories

### 2.1 tools/specdev_tools/ Python Files

**61 files, 13,228 total LOC**

| LOC | File |
|-----|------|
| 45 | `tools/specdev_tools/__init__.py` |
| 1 | `tools/specdev_tools/canonical/__init__.py` |
| 397 | `tools/specdev_tools/canonical/autofix.py` |
| 640 | `tools/specdev_tools/canonical/integrity.py` |
| 472 | `tools/specdev_tools/canonical/lint.py` |
| 318 | `tools/specdev_tools/canonical/registry.py` |
| 757 | `tools/specdev_tools/cli.py` |
| 12 | `tools/specdev_tools/core/__init__.py` |
| 394 | `tools/specdev_tools/core/changelog_parser.py` |
| 186 | `tools/specdev_tools/core/errors.py` |
| 85 | `tools/specdev_tools/core/registry.py` |
| 53 | `tools/specdev_tools/core/trace_types.py` |
| 1 | `tools/specdev_tools/generation/__init__.py` |
| 813 | `tools/specdev_tools/generation/prompt_generator.py` |
| 501 | `tools/specdev_tools/generation/prompt_schema_sync.py` |
| 1331 | `tools/specdev_tools/generation/schema_differ.py` |
| 18 | `tools/specdev_tools/migration/__init__.py` |
| 335 | `tools/specdev_tools/migration/planner.py` |
| 385 | `tools/specdev_tools/migration/runner.py` |
| 0 | `tools/specdev_tools/migration/scripts/__init__.py` |
| 66 | `tools/specdev_tools/migration/scripts/strip_generation_quality.py` |
| 1 | `tools/specdev_tools/validation/__init__.py` |
| 124 | `tools/specdev_tools/validation/_extraction_intent_parser.py` |
| 128 | `tools/specdev_tools/validation/canon_schema_alignment.py` |
| 307 | `tools/specdev_tools/validation/cross_artifact_checks.py` |
| 195 | `tools/specdev_tools/validation/dag_lint.py` |
| 94 | `tools/specdev_tools/validation/dependency_order_lint.py` |
| 119 | `tools/specdev_tools/validation/docs_lint.py` |
| 118 | `tools/specdev_tools/validation/extraction_intent_check.py` |
| 109 | `tools/specdev_tools/validation/fixtures_lint.py` |
| 385 | `tools/specdev_tools/validation/forward_replay_check.py` |
| 37 | `tools/specdev_tools/validation/governance.py` |
| 440 | `tools/specdev_tools/validation/hallucination_lint.py` |
| 86 | `tools/specdev_tools/validation/invariants.py` |
| 353 | `tools/specdev_tools/validation/matrix.py` |
| 310 | `tools/specdev_tools/validation/seed_lint.py` |
| 257 | `tools/specdev_tools/validation/spec_quality_lint.py` |
| 152 | `tools/specdev_tools/validation/traceability_closure.py` |
| 537 | `tools/specdev_tools/validation/validate.py` |
| 11 | `tools/specdev_tools/validation/validators/__init__.py` |
| 81 | `tools/specdev_tools/validation/validators/step_01.py` |
| 167 | `tools/specdev_tools/validation/validators/step_02.py` |
| 17 | `tools/specdev_tools/validation/validators/step_02a.py` |
| 111 | `tools/specdev_tools/validation/validators/step_03.py` |
| 82 | `tools/specdev_tools/validation/validators/step_04.py` |
| 105 | `tools/specdev_tools/validation/validators/step_05.py` |
| 158 | `tools/specdev_tools/validation/validators/step_06.py` |
| 99 | `tools/specdev_tools/validation/validators/step_07.py` |
| 171 | `tools/specdev_tools/validation/validators/step_08.py` |
| 71 | `tools/specdev_tools/validation/validators/step_09.py` |
| 83 | `tools/specdev_tools/validation/validators/step_10.py` |
| 154 | `tools/specdev_tools/validation/validators/step_11.py` |
| 197 | `tools/specdev_tools/validation/validators/step_12.py` |
| 112 | `tools/specdev_tools/validation/validators/step_13.py` |
| 142 | `tools/specdev_tools/validation/validators/step_13a.py` |
| 250 | `tools/specdev_tools/validation/validators/step_14.py` |
| 102 | `tools/specdev_tools/validation/validators/step_15.py` |
| 415 | `tools/specdev_tools/validation/validators/step_16.py` |
| 46 | `tools/specdev_tools/validation/validators/step_16a.py` |
| 45 | `tools/specdev_tools/validation/validators/step_16b.py` |
| 47 | `tools/specdev_tools/validation/validators/step_16c.py` |

### 2.2 tests/ Python Files

**73 files, 17,709 total LOC**

- **Unit tests** (tests/ top-level, excluding conftest): 50 files, 14,690 LOC
- **Integration tests** (tests/integration/, excluding conftest): 21 files, 2,933 LOC
- **Conftest files**: 2 files (tests/conftest.py: 46 LOC, tests/integration/conftest.py: 40 LOC)

| LOC | File |
|-----|------|
| 46 | `tests/conftest.py` |
| 40 | `tests/integration/conftest.py` |
| 87 | `tests/integration/test_seed_manifest.py` |
| 94 | `tests/integration/test_step_00.py` |
| 84 | `tests/integration/test_step_01.py` |
| 134 | `tests/integration/test_step_02.py` |
| 110 | `tests/integration/test_step_02a.py` |
| 216 | `tests/integration/test_step_03.py` |
| 108 | `tests/integration/test_step_04.py` |
| 97 | `tests/integration/test_step_05.py` |
| 123 | `tests/integration/test_step_06.py` |
| 123 | `tests/integration/test_step_07.py` |
| 161 | `tests/integration/test_step_08.py` |
| 91 | `tests/integration/test_step_09.py` |
| 157 | `tests/integration/test_step_10.py` |
| 189 | `tests/integration/test_step_11.py` |
| 177 | `tests/integration/test_step_12.py` |
| 113 | `tests/integration/test_step_13.py` |
| 142 | `tests/integration/test_step_14.py` |
| 133 | `tests/integration/test_step_15.py` |
| 454 | `tests/integration/test_step_16.py` |
| 54 | `tests/integration/test_step_scripts_bridge.py` |
| 86 | `tests/integration/test_v2_migration.py` |
| 222 | `tests/test_canon_schema_alignment.py` |
| 321 | `tests/test_canonical_integrity_drift.py` |
| 421 | `tests/test_canonical_integrity.py` |
| 434 | `tests/test_canonical_lint.py` |
| 360 | `tests/test_canonical_registry.py` |
| 45 | `tests/test_cli_submodule_params.py` |
| 1801 | `tests/test_cli.py` |
| 168 | `tests/test_dependency_order_lint.py` |
| 62 | `tests/test_error_code_coverage.py` |
| 52 | `tests/test_errors_submodule.py` |
| 76 | `tests/test_fixtures_lint.py` |
| 107 | `tests/test_forward_replay_check_integration.py` |
| 320 | `tests/test_forward_replay_check.py` |
| 91 | `tests/test_forward_replay_submodule.py` |
| 132 | `tests/test_gap_remediation.py` |
| 320 | `tests/test_hallucination_lint.py` |
| 35 | `tests/test_init_project_submodule.py` |
| 301 | `tests/test_invariants.py` |
| 186 | `tests/test_migration_planner.py` |
| 325 | `tests/test_migration_runner.py` |
| 101 | `tests/test_migration_templates.py` |
| 192 | `tests/test_prompt_contracts.py` |
| 656 | `tests/test_prompt_schema_sync.py` |
| 286 | `tests/test_r9_cli.py` |
| 1047 | `tests/test_r9_cross_step.py` |
| 461 | `tests/test_r9_dag_lint.py` |
| 84 | `tests/test_r9_error_codes.py` |
| 459 | `tests/test_r9_extraction_intent.py` |
| 648 | `tests/test_r9_forward_replay.py` |
| 584 | `tests/test_r9_hallucination.py` |
| 263 | `tests/test_r9_matrix.py` |
| 433 | `tests/test_r9_quality_lint.py` |
| 475 | `tests/test_r9_validate.py` |
| 67 | `tests/test_registry_error_handling.py` |
| 866 | `tests/test_schema_contracts.py` |
| 79 | `tests/test_seed_content_overlap.py` |
| 131 | `tests/test_seed_path_validation.py` |
| 398 | `tests/test_seed_propagation_trim.py` |
| 66 | `tests/test_seed_strict_mode.py` |
| 140 | `tests/test_spec_quality_lint.py` |
| 91 | `tests/test_step_05_route_fix.py` |
| 100 | `tests/test_step_07_deep.py` |
| 82 | `tests/test_step_10_deep.py` |
| 156 | `tests/test_step_11_deep.py` |
| 162 | `tests/test_step_validators_03_10.py` |
| 146 | `tests/test_step_validators_core.py` |
| 56 | `tests/test_trace_types.py` |
| 185 | `tests/test_traceability_closure.py` |
| 419 | `tests/test_validate_integration.py` |
| 78 | `tests/test_validate_submodule.py` |

### 2.3 Schema Files

**24 files** in `schema/`

```
schema/00_charter.schema.json
schema/01_capabilities.schema.json
schema/02_system_sketch.schema.json
schema/02a_delivery_baseline.schema.json
schema/03_glossary.schema.json
schema/04_fr_list.schema.json
schema/05_interface_contracts.schema.json
schema/06_invariants.schema.json
schema/07_nfrs.schema.json
schema/08_fixtures.schema.json
schema/09_impl_plan.schema.json
schema/10_governance.schema.json
schema/11_redteam.schema.json
schema/12_ci_gates.schema.json
schema/13_extension_generator.schema.json
schema/13a_completeness_assessment.schema.json
schema/14_roadmap.schema.json
schema/15_scaffold.schema.json
schema/16_impl_context.schema.json
schema/core/atoms.schema.json
schema/core/canon.schema.json
schema/core/collections.schema.json
schema/core/errors.schema.json
schema/seed_manifest.schema.json
```

### 2.4 Schema Registry (tools/schema_registry.json)

**30 entries** mapping URI → file path:

| URI | File Path |
|-----|-----------|
| `https://specdev.local/schema/core/atoms/1` | `schema/core/atoms.schema.json` |
| `https://specdev.local/schema/core/canon/1` | `schema/core/canon.schema.json` |
| `https://specdev.local/schema/canon/aliases/1` | `canon/aliases.schema.json` |
| `https://specdev.local/schema/canon/kind/1` | `canon/kind.schema.json` |
| `https://specdev.local/schema/core/collections/1` | `schema/core/collections.schema.json` |
| `https://specdev.local/schema/core/errors/1` | `schema/core/errors.schema.json` |
| `https://specdev.local/schema/00_charter.schema.json` | `schema/00_charter.schema.json` |
| `https://specdev.local/schema/01_capabilities.schema.json` | `schema/01_capabilities.schema.json` |
| `https://specdev.local/schema/02_system_sketch.schema.json` | `schema/02_system_sketch.schema.json` |
| `https://specdev.local/schema/03_glossary.schema.json` | `schema/03_glossary.schema.json` |
| `https://specdev.local/schema/04_fr_list.schema.json` | `schema/04_fr_list.schema.json` |
| `https://specdev.local/schema/05_interface_contracts.schema.json` | `schema/05_interface_contracts.schema.json` |
| `https://specdev.local/schema/06_invariants.schema.json` | `schema/06_invariants.schema.json` |
| `https://specdev.local/schema/07_nfrs.schema.json` | `schema/07_nfrs.schema.json` |
| `https://specdev.local/schema/08_fixtures.schema.json` | `schema/08_fixtures.schema.json` |
| `https://specdev.local/schema/09_impl_plan.schema.json` | `schema/09_impl_plan.schema.json` |
| `https://specdev.local/schema/10_governance.schema.json` | `schema/10_governance.schema.json` |
| `https://specdev.local/schema/11_redteam.schema.json` | `schema/11_redteam.schema.json` |
| `https://specdev.local/schema/12_ci_gates.schema.json` | `schema/12_ci_gates.schema.json` |
| `https://specdev.local/schema/13a_completeness_assessment.schema.json` | `schema/13a_completeness_assessment.schema.json` |
| `https://specdev.local/schema/13_extension_generator.schema.json` | `schema/13_extension_generator.schema.json` |
| `https://specdev.local/schema/14_roadmap.schema.json` | `schema/14_roadmap.schema.json` |
| `https://specdev.local/schema/15_scaffold.schema.json` | `schema/15_scaffold.schema.json` |
| `https://specdev.local/schema/16_impl_context.schema.json` | `schema/16_impl_context.schema.json` |
| `https://specdev.local/schema/16a_impl_context.schema.json` | `schema/16_impl_context.schema.json` |
| `https://specdev.local/schema/16b_impl_context.schema.json` | `schema/16_impl_context.schema.json` |
| `https://specdev.local/schema/16c_impl_context.schema.json` | `schema/16_impl_context.schema.json` |
| `https://specdev.local/schema/02a_delivery_baseline.schema.json` | `schema/02a_delivery_baseline.schema.json` |
| `https://specdev.local/schema/seed_manifest.schema.json` | `schema/seed_manifest.schema.json` |

Note: Steps 16a, 16b, 16c all map to `schema/16_impl_context.schema.json`.

### 2.5 Step Order (tools/step_order.json)

**22 steps** in the `steps` array:
```
00, 01, 02, 02a, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 13a, 14, 15, 16, 16a, 16b, 16c
```

Policy: `strict_waterfall`, no self-dependency, no forward-dependency, full forward replay on change.

Status write exemptions: Step 09 (`milestones[].status`) and Step 14 (`milestones[].status`).

Coverage thresholds: `fr_coverage: 80`, mode: `warn`.

Downstream consumers DAG is fully populated for all 22 steps.

### 2.6 Canon Files

**29 files** in `canon/`:

```
canon/aliases.json
canon/aliases.schema.json
canon/kind.schema.json
canon/kinds/acronym.json
canon/kinds/action.json
canon/kinds/capability.json
canon/kinds/command.json
canon/kinds/completeness_dimension.json
canon/kinds/dependency.json
canon/kinds/entity.json
canon/kinds/environment.json
canon/kinds/event.json
canon/kinds/governance_label.json
canon/kinds/id_pattern.json
canon/kinds/interface.json
canon/kinds/metric.json
canon/kinds/nfr_category.json
canon/kinds/owner.json
canon/kinds/policy.json
canon/kinds/risk_category.json
canon/kinds/role.json
canon/kinds/stage.json
canon/kinds/status.json
canon/kinds/tag.json
canon/kinds/tech_stack.json
canon/kinds/term.json
canon/kinds/trace_type.json
canon/kinds/unit.json
canon/manifest.json
```

25 kind files in `canon/kinds/`.

### 2.7 Prompts Files

**41 files** in `prompts/`:

- 22 step prompts: `prompts/prompt_00_project_charter.md` through `prompts/prompt_16c_impl_reviewer.md`
- 19 migration templates: `prompts/migration/template_*.md`

### 2.8 Scripts Files

**5 files** in `scripts/`:

```
scripts/analyze_schema_usage.py
scripts/generate_fixtures_02a.py
scripts/init_project.py
scripts/setup_devspec_env.sh
scripts/templates/ensure_venv.py
scripts/templates/run_specdev.sh
```

### 2.9 Spec Directory

**3 files** in `spec/`:

```
spec/.gitkeep
spec/05_interface_contracts.json
spec/common/seed_manifest.json
```

### 2.10 Test Fixtures

**132 total fixture files** across 22 directories:

| Count | Directory |
|-------|-----------|
| 3 | `tests/fixtures/canonical/` |
| 3 | `tests/fixtures/dependency_order/` |
| 1 | `tests/fixtures/migration/` |
| 2 | `tests/fixtures/seed_manifest/` |
| 4 | `tests/fixtures/step_00/` |
| 2 | `tests/fixtures/step_01/` |
| 24 | `tests/fixtures/step_02/` |
| 4 | `tests/fixtures/step_02a/` |
| 11 | `tests/fixtures/step_03/` |
| 2 | `tests/fixtures/step_04/` |
| 2 | `tests/fixtures/step_05/` |
| 4 | `tests/fixtures/step_06/` |
| 4 | `tests/fixtures/step_07/` |
| 6 | `tests/fixtures/step_08/` |
| 4 | `tests/fixtures/step_09/` |
| 5 | `tests/fixtures/step_10/` |
| 3 | `tests/fixtures/step_11/` |
| 3 | `tests/fixtures/step_12/` |
| 6 | `tests/fixtures/step_13/` |
| 17 | `tests/fixtures/step_14/` |
| 6 | `tests/fixtures/step_15/` |
| 16 | `tests/fixtures/step_16/` |

### 2.11 tools/ Top-Level Contents

```
tools/command_prefixes.json
tools/context/
tools/core/
tools/pyproject.toml
tools/README.md
tools/requirements.txt
tools/schema_registry.json
tools/setup.py
tools/specdev_tools/
tools/specdev_tools.egg-info/
tools/step_order.json
tools/trace_matrix.json
tools/UNKNOWN.egg-info/
```

### 2.12 docs/ Directory

Exists. Contents:

```
docs/
  README.md
  agents/
    agents.md
    manifest.json
  architecture/
    governance_architecture.md
  audit/
    findings/ (10 files: r1_plan.md through r9_findings.md)
    r1_hygiene_invariants.md
    r2_validation_infrastructure.md
    r3_canonical_drift.md
    r4_traceability_chain.md
    r5_generation_quality.md
    r6_schema_prompt_alignment.md
    r7_prompt_completeness.md
    r8_schema_alignment.md
    r9_validator_ci_closure.md
    review_index.md
    review_prompt_01_system.md
    review_prompt_02_tooling.md
    review_prompt_03_docs.md
    review_prompt_04_canonical_drift_pending.md
    review_prompt_04_canonical_drift.md
    review_protocol.md
  developers/
    design/migration_system_spec.md
    error-codes.md
    extension_schemas.md
    getting_started.md
    index.md
    path_conventions.md
    reference.md
    tooling/coverage_matrix.md, gap_hunter_checklist.md
    tools/align.md, changelog_parser.md, prompt_context.md, schema_differ.md
    workflows/discovery.md, spec_to_impl.md, workflow_align.md, workflow_bootstrap_legacy.md, workflow_feature_extension.md, workflow_migration.md
  ops/
    adr_template_engine.md
    toolkit_update_checklist.md
  plans/
    optimisation_backlog.md
    phase_0_governance_plan.md
  prompts/
    shared_expectations.md
```

### 2.13 .pre-commit-config.yaml

Exists. Two hooks:

1. **dag-lint**: Runs `python -m specdev_tools.cli dag-lint --repo-root .` on changes to `tools/step_order.json` or `prompts/prompt_*.md`
2. **extraction-intent-check**: Runs `python -m specdev_tools.cli extraction-intent-check --repo-root .` on same file patterns

### 2.14 CI Configuration

File: `.github/workflows/ci.yml`

**4 jobs**:
1. `validate` (Schema & Spec Validation) — 15 steps including: prompt-sync, canonical-lint, canonical-integrity, validate-all, spec-quality-lint, hallucination-lint, seed-lint, docs-lint, dependency-order-lint, dag-lint, forward-replay-check, governance-check (PR only), fixtures-lint, matrix build, artifact upload
2. `redteam` (Red-Team Lint) — depends on validate, runs fixtures-lint
3. `deploy-staging` (placeholder) — main branch only, depends on redteam
4. `deploy-prod` (placeholder) — main branch only, depends on deploy-staging

Environment: `SPECDEV_WARNINGS_AS_ERRORS=1`, `SPECDEV_REPLAY_DIFF_ERROR_MODE=error`

Triggers: push (all branches), pull_request, workflow_dispatch, daily cron at 02:00 UTC.

---

## 3. CLI Subcommands

### 3.1 All Subcommands (25 total)

From `cli.py` `sub.add_parser()` calls:

1. `validate`
2. `validate-all`
3. `matrix`
4. `fixtures-lint`
5. `invariants-check`
6. `seed-lint`
7. `docs-lint`
8. `prompt-sync`
9. `canonical-lint`
10. `canonical-integrity`
11. `canonical-autofix`
12. `spec-quality-lint`
13. `hallucination-lint`
14. `traceability-check`
15. `dependency-order-lint`
16. `forward-replay-check`
17. `governance-check`
18. `ai-help`
19. `changelog`
20. `align`
21. `prompt-context`
22. `canon-schema-alignment`
23. `env-check`
24. `dag-lint`
25. `extraction-intent-check`

### 3.2 Align Sub-subcommands

`align` uses a positional `action` argument with choices:
```
status, diff, plan, apply, prompts, rollback, validate
```

### 3.3 Subcommands with --json Flag

Two subcommands support `--json`:
- `validate` (line 54)
- `traceability-check` (line 117)

---

## 4. Validator Details

### 4.1 Step Validator Files (21 files)

```
step_01.py  step_02.py  step_02a.py  step_03.py  step_04.py
step_05.py  step_06.py  step_07.py   step_08.py  step_09.py
step_10.py  step_11.py  step_12.py   step_13.py  step_13a.py
step_14.py  step_15.py  step_16.py   step_16a.py step_16b.py
step_16c.py
```

Note: No `step_00.py` validator exists. Step 00 has no deep validator.

### 4.2 DEEP_VALIDATORS Dict (validate.py:376-403)

21 entries mapping step IDs to validator lambdas:

```python
"01"  -> step_01.validate_step_01(instance, root, ctx.get("component_ids"))
"02"  -> step_02.validate_step_02(instance, root, ctx.get("capability_ids"))
"02a" -> step_02a.validate_step_02a(instance, root)
"03"  -> step_03.validate_step_03(instance, root, ctx.get("nfrs_data"), ctx.get("monitoring_data"))
"04"  -> step_04.validate_step_04(instance, root)
"05"  -> step_05.validate_step_05(instance, root)
"06"  -> step_06.validate_step_06(instance, root)
"07"  -> step_07.validate_step_07(instance, root)
"08"  -> step_08.validate_step_08(instance, root)
"09"  -> step_09.validate_step_09(instance, root)
"10"  -> step_10.validate_step_10(instance, root)
"11"  -> step_11.validate_step_11(instance, root)
"12"  -> step_12.validate_step_12(instance, root)
"13"  -> step_13.validate_step_13(instance, root)
"13a" -> step_13a.validate_step_13a(instance, root)
"14"  -> step_14.validate_step_14(instance, root, ctx.get("artifact_path"))
"15"  -> step_15.validate_step_15(instance, root)
"16"  -> step_16.validate_step_16(instance, root, ctx.get("artifact_path"))
"16a" -> step_16a.validate_step_16a(instance, root, ctx.get("artifact_path"))
"16b" -> step_16b.validate_step_16b(instance, root, ctx.get("artifact_path"))
"16c" -> step_16c.validate_step_16c(instance, root, ctx.get("artifact_path"))
```

### 4.3 All `_load_*` Functions (23 total)

```
step_04.py:63   _load_capability_ids(toolkit_root)
step_05.py:85   _load_fr_ids(toolkit_root)
step_06.py:117  _load_fr_ids(toolkit_root)
step_06.py:139  _load_api_ids(toolkit_root)
step_07.py:67   _load_canonical_stages(toolkit_root)
step_07.py:83   _load_fr_ids(toolkit_root)
step_08.py:86   _load_fr_ids(toolkit_root)
step_08.py:108  _load_api_ids(toolkit_root)
step_08.py:130  _load_inv_ids(toolkit_root)
step_08.py:152  _load_nfr_ids(toolkit_root)
step_09.py:52   _load_capability_ids(toolkit_root)
step_11.py:114  _load_component_ids(toolkit_root)
step_11.py:135  _load_api_ids(toolkit_root)
step_12.py:122  _load_fr_ids(toolkit_root)
step_12.py:145  _load_nfr_ids(toolkit_root)
step_13.py:78   _load_governance_labels(toolkit_root)
step_13a.py:101 _load_fr_ids(toolkit_root)
step_13a.py:123 _load_api_ids(toolkit_root)
step_14.py:152  _load_step09_milestone_ids(toolkit_root, artifact_path)
step_14.py:184  _load_step09_tech_stack_names(toolkit_root, artifact_path)
step_14.py:203  _load_step04_fr_ids(toolkit_root, artifact_path)
step_14.py:228  _load_step01_cap_ids(toolkit_root, artifact_path)
step_15.py:81   _load_api_ids(toolkit_root)
```

### 4.4 All `validate_step_*` Entry Points (21 total)

```
step_01.py:44   validate_step_01(instance, toolkit_root, component_ids)
step_02.py:114  validate_step_02(instance, toolkit_root, capability_ids)
step_02a.py:6   validate_step_02a(instance, toolkit_root)
step_03.py:3    validate_step_03(instance, toolkit_root, nfrs_data, monitoring_data)
step_04.py:9    validate_step_04(instance, toolkit_root)
step_05.py:8    validate_step_05(instance, toolkit_root)
step_06.py:12   validate_step_06(instance, toolkit_root)
step_07.py:13   validate_step_07(instance, toolkit_root)
step_08.py:12   validate_step_08(instance, toolkit_root)
step_09.py:9    validate_step_09(instance, toolkit_root)
step_10.py:11   validate_step_10(instance, toolkit_root)
step_11.py:47   validate_step_11(instance, toolkit_root)
step_12.py:14   validate_step_12(instance, toolkit_root)
step_13.py:13   validate_step_13(instance, toolkit_root)
step_13a.py:11  validate_step_13a(instance, toolkit_root)
step_14.py:15   validate_step_14(instance, toolkit_root, artifact_path)
step_15.py:6    validate_step_15(instance, toolkit_root)
step_16.py:65   validate_step_16(data, toolkit_root, spec_path)
step_16a.py:13  validate_step_16a(data, toolkit_root, spec_path)
step_16b.py:13  validate_step_16b(data, toolkit_root, spec_path)
step_16c.py:15  validate_step_16c(data, toolkit_root, spec_path)
```

---

## 5. Import Graph

### 5.1 core/ (no cross-package imports)

Only external dependency: `yaml` in `changelog_parser.py`.

### 5.2 validation/ -> other packages

```
canon_schema_alignment.py   -> canonical.registry.CanonicalRegistry
cross_artifact_checks.py    -> core.trace_types (is_valid_trace_type, normalize_trace_type)
fixtures_lint.py            -> core.trace_types (is_valid_trace_type, normalize_trace_type)
hallucination_lint.py       -> canonical.lint.lint_canon_dir
                            -> canonical.registry.CanonicalRegistry
                            -> core.trace_types.is_valid_trace_type
matrix.py                   -> core.trace_types (normalize_trace_type, is_valid_trace_type)
traceability_closure.py     -> core.trace_types (is_valid_trace_type, normalize_trace_type)
validate.py                 -> canonical.integrity (validate_canonical_integrity, validate_canonical_integrity_file)
                            -> canonical.lint.lint_canon_dir
                            -> generation.prompt_schema_sync.run_prompt_schema_sync
                            -> core.errors.PROMOTABLE_PAIRS
                            -> core.registry.SchemaRegistry
validators/step_01.py       -> core.registry.SchemaRegistry, core.trace_types
validators/step_02.py       -> core.registry.SchemaRegistry, core.trace_types
validators/step_10.py       -> core.trace_types.is_valid_trace_type
validators/step_11.py       -> core.trace_types (is_valid_trace_type, normalize_trace_type)
```

### 5.3 canonical/ -> other packages

```
autofix.py     -> core.registry.SchemaRegistry
integrity.py   -> core.registry.SchemaRegistry
lint.py        -> core.registry.SchemaRegistry
```

### 5.4 generation/ -> other packages

```
prompt_generator.py     -> core.changelog_parser
prompt_schema_sync.py   -> core.registry.SchemaRegistry
schema_differ.py        -> core.changelog_parser
```

### 5.5 migration/ -> other packages

```
planner.py -> generation.schema_differ, core.changelog_parser
runner.py  -> generation.schema_differ
```

### Dependency Direction Summary

```
core/       <- (depended on by all)
canonical/  <- depends on core/
generation/ <- depends on core/
validation/ <- depends on core/, canonical/, generation/
migration/  <- depends on core/, generation/
cli.py      <- depends on all subpackages
```

No circular cross-package dependencies detected.

---

## 6. Error System

### 6.1 errors.py Summary

**File**: `tools/specdev_tools/core/errors.py` (186 LOC)

**Error code families**:
- 1xx: Canonical integrity (E110, E120, E125, E130, E140, E150, W110, W120, W130, W140, W150)
- 2xx: Cross-artifact drift (E210, E211)
- 3xx: Proof/review closure (E301-E310)
- 4xx: Canonical registry (E410, E420)
- 5xx: Spec content quality (E510-E599, W550-W597)

**Total error codes**: 85 (counted from ERROR_CODES dict)
- E-codes: 41
- W-codes: 19

Wait, let me recount from the file:

**E-codes (errors)**: E110, E120, E125, E130, E140, E150, E210, E211, E301, E302, E303, E304, E305, E306, E307, E310, E410, E420, E510, E512, E520, E521, E530, E540, E541, E550, E551, E552, E553, E554, E555, E560, E561, E562, E563, E571, E572, E573, E580, E581, E582, E585, E590, E591, E592, E593, E594, E595, E596, E597, E598, E599 = **52 E-codes**

**W-codes (warnings)**: W110, W120, W130, W140, W150, W550, W552, W560, W561, W562, W563, W570, W571, W572, W573, W580, W581, W590, W591, W592, W593, W594, W595, W596, W597 = **25 W-codes**

**Total: 77 error/warning codes**

**PROMOTABLE_PAIRS**: 18 entries mapping W-codes to E-codes:
```python
W550 -> E550    W560 -> E560    W561 -> E561
W562 -> E562    W563 -> E563    W571 -> E571
W572 -> E572    W573 -> E573    W580 -> E580
W581 -> E581    W150 -> E150    W590 -> E590
W591 -> E591    W592 -> E592    W593 -> E593
W594 -> E594    W595 -> E595    W597 -> E597
```

**Non-promotable W-codes** (7): W110, W120, W130, W140, W552, W570, W596

**Exception classes**: SpecdevError (base), SubmoduleDetectionError, SchemaRegistryError

### 6.2 validate.py Schema Validation Usage

```python
# Line 136:
errors = sorted(v.iter_errors(data_for_validation), key=lambda e: e.path)
```

Uses jsonschema `iter_errors` for schema validation. Single call site.

---

## 7. Schema Details

### 7.1 Step 00 (00_charter.schema.json)

- `$id`: `https://specdev.local/schema/00_charter.schema.json`
- Uses `$ref`: Yes
- Has `$defs`: No
- Has `description` on properties: Yes
- `additionalProperties`: false
- Max nesting depth: 8
- Top-level properties: id, owner, created_at, spec_refs_ingested, seed_refs, title, problem_statement, in_scope, out_of_scope, assumptions, risks, stakeholders, user_segments, success_metrics, links, generation_quality, canonical_refs_used, canonical_proposals, canonical_conflicts, coverage_gaps, _migration_notes (21 properties)

### 7.2 Step 05 (05_interface_contracts.schema.json)

- `$id`: `https://specdev.local/schema/05_interface_contracts.schema.json`
- Uses `$ref`: Yes
- Has `$defs`: No
- Has `description` on properties: Yes
- `additionalProperties`: false
- Max nesting depth: 10
- Top-level properties: id, owner, created_at, spec_refs_ingested, seed_refs, apis, generation_quality, canonical_refs_used, canonical_proposals, canonical_conflicts, coverage_gaps, _migration_notes (12 properties)

### 7.3 Step 16 (16_impl_context.schema.json)

- `$id`: `https://specdev.local/schema/16_impl_context.schema.json`
- Uses `$ref`: Yes
- Has `$defs`: Yes
- Has `description` on properties: Yes
- `additionalProperties`: false
- Max nesting depth: 19
- Top-level properties: id, owner, created_at, spec_refs_ingested, seed_refs, extensions, plan, execution, review, policy_ref, risk_category_ref, generation_quality, canonical_refs_used, canonical_proposals, canonical_conflicts, coverage_gaps, _migration_notes (17 properties)

### 7.4 Core Atoms (schema/core/atoms.schema.json)

`$id`: `https://specdev.local/schema/core/atoms/1`

Provides 5 shared `$defs` with `$anchor` references:
1. **metadata** — Generic key-value store (patternProperties: `^[a-zA-Z0-9_]+$` -> string)
2. **kebabId** — Kebab-case identifier pattern: `^[a-z0-9]+(?:-[a-z0-9]+)*$`
3. **timestamp** — ISO 8601 date-time string
4. **owner** — Pattern: `^[a-z][a-z0-9_-]*$`, validated against `canon/kinds/owner.json`
5. **screamingSnakeId** — Pattern: `^[A-Z0-9_]+$`

Also: **tag** — Pattern: `^[A-Za-z0-9_.:-]{1,64}$`

Total: 6 `$defs`.

---

## 8. Conftest Comparison

### tests/conftest.py (46 LOC)

- `REPO_ROOT = Path(__file__).resolve().parents[1]` (goes up 1 level from tests/)
- 5 fixtures: `repo_root`, `schema_root`, `spec_root`, `canon_root`, `fixtures_root`, `migration_prompts_root`

### tests/integration/conftest.py (40 LOC)

- `REPO_ROOT = Path(__file__).resolve().parents[2]` (goes up 2 levels from tests/integration/)
- 5 fixtures: `repo_root`, `schema_root`, `spec_root`, `canon_root`, `fixtures_root`
- **Missing**: `migration_prompts_root` fixture (present in top-level conftest but not integration conftest)

### Exact Diff

```diff
--- tests/conftest.py
+++ tests/integration/conftest.py
@@ -1,4 +1,4 @@
-"""Shared test fixtures for DevSpec Toolkit test suite."""
+"""Shared test fixtures for DevSpec Toolkit integration tests."""
 import sys
 from pathlib import Path

@@ -7,7 +7,7 @@
-REPO_ROOT = Path(__file__).resolve().parents[1]
+REPO_ROOT = Path(__file__).resolve().parents[2]
 TOOLS_DIR = REPO_ROOT / "tools"
 ...

 (missing from integration conftest):
-@pytest.fixture
-def migration_prompts_root(repo_root):
-    """Return the migration prompts directory path."""
-    return repo_root / "prompts" / "migration"
```

---

## 9. Version Information

### 9.1 pyproject.toml

```
version = "0.4.0"
```

### 9.2 tools/specdev_tools/__init__.py

No `__version__` string defined. The `__init__.py` contains only a lazy import compatibility shim (`_MOVED` dict with `__getattr__`).

### 9.3 CLAUDE.md Version Claim

```
Current version: **0.3.0** (see `tools/pyproject.toml`).
```

**VERSION MISMATCH**: CLAUDE.md claims 0.3.0, pyproject.toml has 0.4.0.

---

## 10. Code Health Signals

### 10.1 TODO/FIXME/HACK/XXX in Source Code

**Zero actual TODOs**. The only matches are regex patterns used for detection:

```
spec_quality_lint.py:9:  PLACEHOLDER_RE = re.compile(r"\b(TBD|TODO|FIXME|XXX|placeholder|<[^>]+>)\b", re.IGNORECASE)
extraction_intent_check.py:17:  r"\b(?:relevant|as needed|as appropriate|etc\.?|various|TBD|TODO)\b",
```

### 10.2 pragma: no cover / noqa

**One instance**:
```
validators/__init__.py:7: from . import (  # noqa: F401 – re-exported for validate.py DEEP_VALIDATORS
```

### 10.3 @pytest.mark.skip / @pytest.mark.xfail

**None found**. All 830 tests run without skips or expected failures.

### 10.4 warnings.warn Usage (12 instances)

```
__init__.py:38                     - Deprecation warning for old import paths
prompt_generator.py:192            - (generation context)
prompt_generator.py:225            - (generation context)
traceability_closure.py:32         - (traceability context)
validators/step_11.py:34           - (step 11 validation)
validators/step_11.py:41           - (step 11 validation)
validators/step_01.py:21           - (step 01 validation)
validators/step_02.py:83           - (step 02 validation)
cross_artifact_checks.py:46        - (cross-artifact context)
fixtures_lint.py:20                - (fixtures context)
matrix.py:42                       - (matrix context)
migration/planner.py:309           - (migration context)
```

---

## 11. R9 Feature Round

### R9 Markers in Source Code (13 markers)

```
forward_replay_check.py:293     # R9/T22: Content staleness
hallucination_lint.py:293       # R9/T20: Content derivation check
hallucination_lint.py:337       # R9/T20: Check that downstream content derives from upstream
spec_quality_lint.py:13         # R9: additional vague terms
spec_quality_lint.py:149        # R9/T18: Scan all free-text fields for vague language
validate.py:263                 # R9/T26: Extraction intent validation
validate.py:267                 # R9/T26: Dynamic W→E promotion using PROMOTABLE_PAIRS
cli.py:166                      # R9: New commands
cli.py:690                      # R9/T28: Read-only diagnostic (env-check)
matrix.py:296                   # R9/T24: Configurable coverage threshold enforcement
matrix.py:305                   # R9/T24: Enforce coverage thresholds from step_order.json
errors.py:84                    # R9: Cross-step validation (59x)
```

R9 scope covers:
- T18: Vague language scanning in free-text fields
- T20: Content derivation checks (hallucination lint)
- T22: Content staleness detection (forward replay)
- T24: Configurable coverage thresholds (matrix)
- T26: Extraction intent validation + W->E promotion
- T28: env-check diagnostic command
- 59x error code family (E590-E599, W590-W597)
- New CLI commands: dag-lint, extraction-intent-check, env-check

---

## 12. Spec Directory Usage in Tests

### 12.1 Tests with Actual File I/O from spec/

Only `tests/integration/test_step_11.py` does direct file I/O from `spec/`:

```python
test_step_11.py:14  def load_json_file(filepath):
test_step_11.py:58  contracts = load_json_file("spec/05_interface_contracts.json")
test_step_11.py:64  sketch = load_json_file("spec/02_system_sketch.json")
test_step_11.py:70  frs = load_json_file("spec/04_fr_list.json")
test_step_11.py:76  nfrs = load_json_file("spec/07_nfrs.json")
test_step_11.py:82  invs = load_json_file("spec/06_invariants.json")
test_step_11.py:88  caps = load_json_file("spec/01_capabilities.json")
test_step_11.py:94  fixtures = load_json_file("spec/08_fixtures.json")
```

Note: Most of these spec files do NOT exist in the repo (only `spec/05_interface_contracts.json` exists). These tests likely guard against missing files gracefully.

### 12.2 Tests Using spec_root Fixture

```
tests/conftest.py:26                  - defines spec_root fixture
tests/integration/conftest.py:26      - defines spec_root fixture
tests/test_cli.py:1363               - spec_root=None
tests/test_cli_submodule_params.py    - tests --spec-root help visibility
tests/test_validate_submodule.py      - tests _detect_spec_root
tests/test_forward_replay_submodule.py - tests spec_root param in replay
tests/test_init_project_submodule.py  - tests submodule spec_root setup
```
