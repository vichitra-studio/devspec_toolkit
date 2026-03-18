# P0: Ground Truth Data Snapshot (Agent B)

Captured at: 2026-03-17T17:54:07Z
Repo root: /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/
Branch: codex/canonical-drift-review-plan

## 1. Test Suite

### Command: pytest tests/ --collect-only -q (last 5 lines)
```
tests/test_validate_submodule.py::TestDeepValidators16abc::test_16c_routes_to_step_16c
tests/test_validate_submodule.py::TestIsGitRepoTimeout::test_logs_on_timeout

830 tests collected in 0.14s
```

### Command: pytest tests/ -x --tb=line (last 5 lines)
```
tests/test_validate_integration.py ...................                   [ 98%]
tests/test_validate_submodule.py .........                               [100%]

============================= 830 passed in 36.19s =============================
```

**Summary**: 830 tests collected, 830 passed, 0 failed, 0 skipped, 0 xfailed.

## 2. File Inventories

### 2.1 tools/specdev_tools/ Python Files
```
      45 tools/specdev_tools/__init__.py
       1 tools/specdev_tools/canonical/__init__.py
     397 tools/specdev_tools/canonical/autofix.py
     640 tools/specdev_tools/canonical/integrity.py
     472 tools/specdev_tools/canonical/lint.py
     318 tools/specdev_tools/canonical/registry.py
     757 tools/specdev_tools/cli.py
      12 tools/specdev_tools/core/__init__.py
     394 tools/specdev_tools/core/changelog_parser.py
     186 tools/specdev_tools/core/errors.py
      85 tools/specdev_tools/core/registry.py
      53 tools/specdev_tools/core/trace_types.py
       1 tools/specdev_tools/generation/__init__.py
     813 tools/specdev_tools/generation/prompt_generator.py
     501 tools/specdev_tools/generation/prompt_schema_sync.py
    1331 tools/specdev_tools/generation/schema_differ.py
      18 tools/specdev_tools/migration/__init__.py
     335 tools/specdev_tools/migration/planner.py
     385 tools/specdev_tools/migration/runner.py
       0 tools/specdev_tools/migration/scripts/__init__.py
      66 tools/specdev_tools/migration/scripts/strip_generation_quality.py
       1 tools/specdev_tools/validation/__init__.py
     124 tools/specdev_tools/validation/_extraction_intent_parser.py
     128 tools/specdev_tools/validation/canon_schema_alignment.py
     307 tools/specdev_tools/validation/cross_artifact_checks.py
     195 tools/specdev_tools/validation/dag_lint.py
      94 tools/specdev_tools/validation/dependency_order_lint.py
     119 tools/specdev_tools/validation/docs_lint.py
     118 tools/specdev_tools/validation/extraction_intent_check.py
     109 tools/specdev_tools/validation/fixtures_lint.py
     385 tools/specdev_tools/validation/forward_replay_check.py
      37 tools/specdev_tools/validation/governance.py
     440 tools/specdev_tools/validation/hallucination_lint.py
      86 tools/specdev_tools/validation/invariants.py
     353 tools/specdev_tools/validation/matrix.py
     310 tools/specdev_tools/validation/seed_lint.py
     257 tools/specdev_tools/validation/spec_quality_lint.py
     152 tools/specdev_tools/validation/traceability_closure.py
     537 tools/specdev_tools/validation/validate.py
      11 tools/specdev_tools/validation/validators/__init__.py
      81 tools/specdev_tools/validation/validators/step_01.py
     167 tools/specdev_tools/validation/validators/step_02.py
      17 tools/specdev_tools/validation/validators/step_02a.py
     111 tools/specdev_tools/validation/validators/step_03.py
      82 tools/specdev_tools/validation/validators/step_04.py
     105 tools/specdev_tools/validation/validators/step_05.py
     158 tools/specdev_tools/validation/validators/step_06.py
      99 tools/specdev_tools/validation/validators/step_07.py
     171 tools/specdev_tools/validation/validators/step_08.py
      71 tools/specdev_tools/validation/validators/step_09.py
      83 tools/specdev_tools/validation/validators/step_10.py
     154 tools/specdev_tools/validation/validators/step_11.py
     197 tools/specdev_tools/validation/validators/step_12.py
     112 tools/specdev_tools/validation/validators/step_13.py
     142 tools/specdev_tools/validation/validators/step_13a.py
     250 tools/specdev_tools/validation/validators/step_14.py
     102 tools/specdev_tools/validation/validators/step_15.py
     415 tools/specdev_tools/validation/validators/step_16.py
      46 tools/specdev_tools/validation/validators/step_16a.py
      45 tools/specdev_tools/validation/validators/step_16b.py
      47 tools/specdev_tools/validation/validators/step_16c.py
   13228 total
```
Total files: 60
Total LOC: 13228

### 2.2 tests/ Python Files
```
      46 tests/conftest.py
      40 tests/integration/conftest.py
      87 tests/integration/test_seed_manifest.py
      94 tests/integration/test_step_00.py
      84 tests/integration/test_step_01.py
     134 tests/integration/test_step_02.py
     110 tests/integration/test_step_02a.py
     216 tests/integration/test_step_03.py
     108 tests/integration/test_step_04.py
      97 tests/integration/test_step_05.py
     123 tests/integration/test_step_06.py
     123 tests/integration/test_step_07.py
     161 tests/integration/test_step_08.py
      91 tests/integration/test_step_09.py
     157 tests/integration/test_step_10.py
     189 tests/integration/test_step_11.py
     177 tests/integration/test_step_12.py
     113 tests/integration/test_step_13.py
     142 tests/integration/test_step_14.py
     133 tests/integration/test_step_15.py
     454 tests/integration/test_step_16.py
      54 tests/integration/test_step_scripts_bridge.py
      86 tests/integration/test_v2_migration.py
     222 tests/test_canon_schema_alignment.py
     321 tests/test_canonical_integrity_drift.py
     421 tests/test_canonical_integrity.py
     434 tests/test_canonical_lint.py
     360 tests/test_canonical_registry.py
      45 tests/test_cli_submodule_params.py
    1801 tests/test_cli.py
     168 tests/test_dependency_order_lint.py
      62 tests/test_error_code_coverage.py
      52 tests/test_errors_submodule.py
      76 tests/test_fixtures_lint.py
     107 tests/test_forward_replay_check_integration.py
     320 tests/test_forward_replay_check.py
      91 tests/test_forward_replay_submodule.py
     132 tests/test_gap_remediation.py
     320 tests/test_hallucination_lint.py
      35 tests/test_init_project_submodule.py
     301 tests/test_invariants.py
     186 tests/test_migration_planner.py
     325 tests/test_migration_runner.py
     101 tests/test_migration_templates.py
     192 tests/test_prompt_contracts.py
     656 tests/test_prompt_schema_sync.py
     286 tests/test_r9_cli.py
    1047 tests/test_r9_cross_step.py
     461 tests/test_r9_dag_lint.py
      84 tests/test_r9_error_codes.py
     459 tests/test_r9_extraction_intent.py
     648 tests/test_r9_forward_replay.py
     584 tests/test_r9_hallucination.py
     263 tests/test_r9_matrix.py
     433 tests/test_r9_quality_lint.py
     475 tests/test_r9_validate.py
      67 tests/test_registry_error_handling.py
     866 tests/test_schema_contracts.py
      79 tests/test_seed_content_overlap.py
     131 tests/test_seed_path_validation.py
     398 tests/test_seed_propagation_trim.py
      66 tests/test_seed_strict_mode.py
     140 tests/test_spec_quality_lint.py
      91 tests/test_step_05_route_fix.py
     100 tests/test_step_07_deep.py
      82 tests/test_step_10_deep.py
     156 tests/test_step_11_deep.py
     162 tests/test_step_validators_03_10.py
     146 tests/test_step_validators_core.py
      56 tests/test_trace_types.py
     185 tests/test_traceability_closure.py
     419 tests/test_validate_integration.py
      78 tests/test_validate_submodule.py
   17709 total
```
Total test files: 71 (2 conftest + 50 unit test_*.py + 19 integration test_*.py + 2 integration non-test)
Total test LOC: 17709

### 2.3 Unit vs Integration Test Files
- Unit test files (tests/test_*.py): **50**
- Integration test files (tests/integration/test_*.py): **21** (includes test_seed_manifest.py, test_step_scripts_bridge.py, test_v2_migration.py)
- Conftest files: 2 (tests/conftest.py, tests/integration/conftest.py)

### 2.4 Schema Files (.schema.json)
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
Total: **24** schema files (19 step schemas + 4 core schemas + 1 seed_manifest schema)

### 2.5 tools/schema_registry.json
Full contents (30 entries mapping URIs to schema file paths):
- 4 core schemas (atoms/1, canon/1, canon/aliases/1, canon/kind/1)
- 2 core shared schemas (collections/1, errors/1)
- 19 step schemas (00 through 16, including 02a, 13a)
- 3 virtual aliases (16a, 16b, 16c all map to 16_impl_context.schema.json)
- 1 seed_manifest schema
- 1 02a_delivery_baseline schema

Total entries: **30**

### 2.6 tools/step_order.json
- Version: "1.0.0"
- Policy mode: "strict_waterfall"
- Steps array: ["00", "01", "02", "02a", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "13a", "14", "15", "16", "16a", "16b", "16c"] (**22 steps**)
- Status write exemptions: step 09 (milestones[].status), step 14 (milestones[].status)
- Coverage thresholds: fr_coverage=80, mode=warn
- downstream_consumers: 22 entries (00 through 16c)

### 2.7 Canon Files
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
Total: **29 files** (1 manifest + 1 aliases.json + 2 schemas + 25 kind files)

### 2.8 Prompt Files
```
prompts/migration/                      (directory with 19 template files)
prompts/prompt_00_project_charter.md
prompts/prompt_01_capabilities.md
prompts/prompt_02_system_sketch.md
prompts/prompt_02a_delivery_baseline.md
prompts/prompt_03_glossary.md
prompts/prompt_04_functional_requirements.md
prompts/prompt_05_interface_contracts.md
prompts/prompt_06_invariants.md
prompts/prompt_07_nfrs.md
prompts/prompt_08_fixtures.md
prompts/prompt_09_impl_plan.md
prompts/prompt_10_governance.md
prompts/prompt_11_redteam.md
prompts/prompt_12_ci_gates.md
prompts/prompt_13_extension_generator.md
prompts/prompt_13a_completeness_assessment.md
prompts/prompt_14_roadmap.md
prompts/prompt_15_scaffold.md
prompts/prompt_16_impl_context.md
prompts/prompt_16a_impl_planner.md
prompts/prompt_16b_impl_coder.md
prompts/prompt_16c_impl_reviewer.md
```
Total prompt files: **22** (+ migration/ directory with 19 migration templates)

Migration templates:
```
template_capabilities.md
template_charter.md
template_ci_gates.md
template_completeness_assessment.md
template_delivery_baseline.md
template_extension_generator.md
template_fixtures.md
template_frs.md
template_glossary.md
template_governance.md
template_impl_context.md
template_impl_plan.md
template_interfaces.md
template_invariants.md
template_nfrs.md
template_redteam.md
template_roadmap.md
template_scaffold.md
template_system_sketch.md
```

### 2.9 Script Files
```
scripts/analyze_schema_usage.py
scripts/generate_fixtures_02a.py
scripts/init_project.py
scripts/setup_devspec_env.sh
scripts/templates/ensure_venv.py
scripts/templates/run_specdev.sh
```
Total: **6 files**

### 2.10 Spec Files
```
spec/.gitkeep
spec/05_interface_contracts.json
spec/common/seed_manifest.json
```
Total: **3 files**

### 2.11 Test Fixtures
Fixture directories:
```
14_roadmap.json          (file, not directory)
canonical/
dependency_order/
migration/
seed_manifest/
step_00/
step_01/
step_02/
step_02a/
step_03/
step_04/
step_05/
step_06/
step_07/
step_08/
step_09/
step_10/
step_11/
step_12/
step_13/
step_14/
step_15/
step_16/
```
Total fixture files: **133**

### 2.12 tools/ Top-Level Contents
```
command_prefixes.json
context/                (empty directory)
core/                   (contains json_utils.py)
pyproject.toml
README.md
requirements.txt
schema_registry.json
setup.py
specdev_tools/
specdev_tools.egg-info/
step_order.json
trace_matrix.json
UNKNOWN.egg-info/
```

### 2.13 docs/ Directory
EXISTS. Contents:
```
docs/agents/            (agents.md, manifest.json)
docs/architecture/      (governance_architecture.md)
docs/audit/             (review_index.md, review prompts, findings r1-r9)
docs/developers/        (getting_started.md, reference.md, error-codes.md, etc.)
docs/ops/               (adr_template_engine.md, toolkit_update_checklist.md)
docs/plans/             (optimisation_backlog.md, phase_0_governance_plan.md)
docs/prompts/           (shared_expectations.md)
docs/README.md
```
Total docs files: ~40 (including .DS_Store files)

### 2.14 .pre-commit-config.yaml
```yaml
# Pre-commit hooks for the DevSpec Toolkit.
# Install: pip install pre-commit && pre-commit install
# Run manually: pre-commit run --all-files
repos:
  - repo: local
    hooks:
      - id: dag-lint
        name: DAG completeness lint
        entry: python -m specdev_tools.cli dag-lint --repo-root .
        language: system
        pass_filenames: false
        files: (tools/step_order\.json|prompts/prompt_.*\.md)$
        types: [file]
      - id: extraction-intent-check
        name: Extraction intent validation
        entry: python -m specdev_tools.cli extraction-intent-check --repo-root .
        language: system
        pass_filenames: false
        files: (tools/step_order\.json|prompts/prompt_.*\.md)$
        types: [file]
```
2 hooks: dag-lint, extraction-intent-check

### 2.15 CI Configuration
- `.github/workflows/ci.yml`: EXISTS (119 lines)
  - Jobs: validate, redteam, deploy-staging, deploy-prod
  - validate job runs: prompt-sync, canonical-lint, canonical-integrity, validate-all, spec-quality-lint, hallucination-lint, seed-lint, docs-lint, dependency-order-lint, dag-lint, forward-replay-check, governance-check, fixtures-lint, matrix (14 steps)
  - Sets SPECDEV_WARNINGS_AS_ERRORS=1 and SPECDEV_REPLAY_DIFF_ERROR_MODE=error
- `.gitlab-ci.yml`: DOES NOT EXIST
- `Makefile`: DOES NOT EXIST

## 3. CLI Subcommands

### All subcommands (from sub.add_parser calls in cli.py)
1. `validate` (line 49)
2. `validate-all` (line 56)
3. `matrix` (line 62)
4. `fixtures-lint` (line 67)
5. `invariants-check` (line 71)
6. `seed-lint` (line 76)
7. `docs-lint` (line 80)
8. `prompt-sync` (line 84)
9. `canonical-lint` (line 88)
10. `canonical-integrity` (line 92)
11. `canonical-autofix` (line 97)
12. `spec-quality-lint` (line 105)
13. `hallucination-lint` (line 109)
14. `traceability-check` (line 114)
15. `dependency-order-lint` (line 119)
16. `forward-replay-check` (line 122)
17. `governance-check` (line 129)
18. `ai-help` (line 134)
19. `changelog` (line 138)
20. `align` (line 145)
21. `prompt-context` (line 159)
22. `canon-schema-alignment` (line 163)
23. `env-check` (line 167)
24. `dag-lint` (line 170)
25. `extraction-intent-check` (line 173)

Total: **25 subcommands**

### align sub-actions
`choices=["status", "diff", "plan", "apply", "prompts", "rollback", "validate"]`
7 actions via positional `action` argument.

### Commands supporting --json
1. `validate` (line 54)
2. `traceability-check` (line 117)

## 4. Validator Details

### Step Validator Files (21 files)
```
step_01.py, step_02.py, step_02a.py, step_03.py, step_04.py,
step_05.py, step_06.py, step_07.py, step_08.py, step_09.py,
step_10.py, step_11.py, step_12.py, step_13.py, step_13a.py,
step_14.py, step_15.py, step_16.py, step_16a.py, step_16b.py, step_16c.py
```
No step_00.py validator file exists.

### DEEP_VALIDATORS Dict (22 entries, lines 376-403)
Maps steps: 01, 02, 02a, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 13a, 14, 15, 16, 16a, 16b, 16c
Notable: Step 00 has NO deep validator. Steps 03, 14, 16/16a/16b/16c receive extra context parameters.

### All _load Functions (22 functions across validators)
```
step_04.py:63  _load_capability_ids
step_05.py:85  _load_fr_ids
step_06.py:117 _load_fr_ids
step_06.py:139 _load_api_ids
step_07.py:67  _load_canonical_stages
step_07.py:83  _load_fr_ids
step_08.py:86  _load_fr_ids
step_08.py:108 _load_api_ids
step_08.py:130 _load_inv_ids
step_08.py:152 _load_nfr_ids
step_09.py:52  _load_capability_ids
step_11.py:114 _load_component_ids
step_11.py:135 _load_api_ids
step_12.py:122 _load_fr_ids
step_12.py:145 _load_nfr_ids
step_13.py:78  _load_governance_labels
step_13a.py:101 _load_fr_ids
step_13a.py:123 _load_api_ids
step_14.py:152 _load_step09_milestone_ids
step_14.py:184 _load_step09_tech_stack_names
step_14.py:203 _load_step04_fr_ids
step_14.py:228 _load_step01_cap_ids
step_15.py:81  _load_api_ids
```
Total: **23 _load functions**

### All validate_step_ Entry Points (21 functions)
One per validator file: validate_step_01 through validate_step_16c.

### _load_fr_ids Comparison (step_05 vs step_06 vs step_07)
**NOT identical.** Differences:
- step_05 (line 85): Uses `for fn in os.listdir(spec_dir) if os.path.isdir(spec_dir) else []:` inline conditional, variable named `fr`
- step_06 (line 117): Uses separate `if not os.path.isdir(spec_dir): return None` guard, variable named `item`, intermediate `items` variable
- step_07 (line 83): Uses same inline conditional as step_05, variable named `fr` -- nearly identical to step_05, uses `set[str] | None` type hint instead of `Optional[Set[str]]`

All three load FR IDs from step 04's `functional_requirements` array. Logic is functionally equivalent but implementations differ in style (type hints, variable names, guard clause pattern).

## 5. Import Graph

### core/ -- Cross-package imports
NO OUTPUT (core imports nothing from parent packages -- it is the leaf dependency)

### validation/ -- Cross-package imports (excluding validators/)
```
traceability_closure.py:7   from ..core.trace_types import is_valid_trace_type, normalize_trace_type
cross_artifact_checks.py:16 from ..core.trace_types import is_valid_trace_type, normalize_trace_type
validate.py:14              from ..canonical.integrity import validate_canonical_integrity, validate_canonical_integrity_file
validate.py:15              from ..canonical.lint import lint_canon_dir
validate.py:20              from ..generation.prompt_schema_sync import run_prompt_schema_sync
validate.py:21              from ..core.errors import PROMOTABLE_PAIRS
validate.py:22              from ..core.registry import SchemaRegistry
matrix.py:6                 from ..core.trace_types import normalize_trace_type, is_valid_trace_type
canon_schema_alignment.py:8 from ..canonical.registry import CanonicalRegistry
fixtures_lint.py:4          from ..core.trace_types import is_valid_trace_type, normalize_trace_type
hallucination_lint.py:8     from ..canonical.lint import lint_canon_dir
hallucination_lint.py:9     from ..canonical.registry import CanonicalRegistry
hallucination_lint.py:10    from ..core.trace_types import is_valid_trace_type
```

### validation/validators/ -- Cross-package imports
```
step_10.py:8  from ...core.trace_types import is_valid_trace_type
step_11.py:8  from ...core.trace_types import is_valid_trace_type, normalize_trace_type
step_01.py:6  from ...core.registry import SchemaRegistry
step_01.py:7  from ...core.trace_types import is_valid_trace_type, normalize_trace_type
step_02.py:6  from ...core.registry import SchemaRegistry
step_02.py:7  from ...core.trace_types import is_valid_trace_type, normalize_trace_type
```

### canonical/ -- Cross-package imports
```
lint.py:13      from ..core.registry import SchemaRegistry
autofix.py:15   from ..core.registry import SchemaRegistry
integrity.py:12 from ..core.registry import SchemaRegistry
```

### generation/ -- Cross-package imports
```
prompt_schema_sync.py:15  from ..core.registry import SchemaRegistry
prompt_generator.py:46    from ..core.changelog_parser import (...)
schema_differ.py:15       from ..core.changelog_parser import (...)
```

### migration/ -- Cross-package imports
```
runner.py:16   from ..generation.schema_differ import (...)
planner.py:18  from ..generation.schema_differ import (...)
planner.py:26  from ..core.changelog_parser import compare_versions, get_changes_between
```

### Does validate.py import from generation?
YES. Line 20: `from ..generation.prompt_schema_sync import run_prompt_schema_sync`

### Import Dependency Graph Summary
```
core/         --> (nothing -- leaf)
canonical/    --> core
generation/   --> core
validation/   --> core, canonical, generation
migration/    --> core, generation
```
Note: validation imports from ALL other subpackages (core, canonical, generation).

## 6. Error System

### tools/specdev_tools/core/errors.py (187 lines)
- `SpecError` dataclass: code, message, path (optional)
- `ERROR_CODES` dict: **77 total entries** (52 E-codes + 25 W-codes)
- `PROMOTABLE_PAIRS` dict: **18 entries** (W-code -> E-code mappings)
- `make_error()` factory function
- Exception classes: `SpecdevError` (base), `SubmoduleDetectionError`, `SchemaRegistryError`

### E-code ranges
- 1xx: Canonical integrity (E110, E120, E125, E130, E140, E150)
- 2xx: Cross-artifact drift (E210, E211)
- 3xx: Proof/review closure (E301-E307, E310)
- 4xx: Canonical registry (E410, E420)
- 5xx: Spec content quality (E510-E599, 34 codes)

### W-code ranges
- 1xx: W110, W120, W130, W140, W150
- 5xx: W550, W552, W560-W563, W570-W573, W580-W581, W590-W597

### Non-promotable W-codes (excluded from PROMOTABLE_PAIRS)
W110, W120, W130, W140, W552, W570, W596

### grep -c "E[0-9]\|W[0-9]" output
99 matching lines

### validate.py usage of jsonschema
Line 136: `errors = sorted(v.iter_errors(data_for_validation), key=lambda e: e.path)`
(Uses jsonschema `iter_errors` for schema validation)

## 7. Schema Details

### 00_charter.schema.json (202 lines)
- Has `$id`: YES (`https://specdev.local/schema/00_charter.schema.json`)
- Has `$defs`: NO
- Uses `$ref`: YES (extensive -- atoms, collections refs)
- Has `additionalProperties`: YES (false, at root and nested objects)
- Has `description` on properties: NO (only on `_migration_notes`)
- Max nesting depth: 4 (root -> stakeholders -> items -> properties -> needs)
- Required fields: 14

### 05_interface_contracts.schema.json (220 lines)
- Has `$id`: YES (`https://specdev.local/schema/05_interface_contracts.schema.json`)
- Has `$defs`: NO
- Uses `$ref`: YES (atoms, collections, errors refs)
- Has `additionalProperties`: YES (false, at root + nested objects)
- Has `description` on properties: YES (on `enum_provenance` and `resolver`)
- Max nesting depth: 5 (root -> apis -> items -> parameters -> items -> properties)
- Required fields: 11 (root), 6 (per api), 3 (per parameter)
- Enums: protocol (http/grpc/ws/mqtt), method (GET/POST/PUT/PATCH/DELETE), security (none/api-key/oauth2/jwt/mTLS), parameter.in (query/path/header)

### 16_impl_context.schema.json (1868 lines)
- Has `$id`: YES (`https://specdev.local/schema/16_impl_context.schema.json`)
- Has `$defs`: YES (4 defs: specRef, severityLevel, executionStatus, evidenceObject)
- Uses `$ref`: YES (atoms, collections, local $defs, core refs)
- Has `additionalProperties`: YES (false at root)
- Has `description`: YES (top-level description)
- Max nesting depth: DEEP (6+ levels through plan/code/review nested objects)
- Top-level properties: 17
- Required fields: 11

### core/atoms.schema.json (56 lines)
- Has `$id`: YES (`https://specdev.local/schema/core/atoms/1`)
- Has `$defs`: YES (5 defs: metadata, kebabId, timestamp, owner, tag, screamingSnakeId -- actually 6 items in $defs)
- Uses `$ref`: NO
- Has `additionalProperties`: YES (false on metadata)
- Has `description` on properties: YES (on metadata, owner)
- Uses `$anchor`: YES (each def has a corresponding anchor)
- Max nesting depth: 2 ($defs -> metadata -> patternProperties)
- Defines primitive types reused across all step schemas

## 8. Conftest Comparison

### tests/conftest.py (46 lines)
- REPO_ROOT = Path(__file__).resolve().parents[1]
- 5 fixtures: repo_root, schema_root, spec_root, canon_root, fixtures_root, migration_prompts_root

### tests/integration/conftest.py (40 lines)
- REPO_ROOT = Path(__file__).resolve().parents[2]  (goes up one more level)
- 5 fixtures: repo_root, schema_root, spec_root, canon_root, fixtures_root
- MISSING: migration_prompts_root fixture

### Diff
```diff
1c1
< """Shared test fixtures for DevSpec Toolkit test suite."""
---
> """Shared test fixtures for DevSpec Toolkit integration tests."""
7c7
< REPO_ROOT = Path(__file__).resolve().parents[1]
---
> REPO_ROOT = Path(__file__).resolve().parents[2]
41,46d40
<
<
< @pytest.fixture
< def migration_prompts_root(repo_root):
<     """Return the migration prompts directory path."""
<     return repo_root / "prompts" / "migration"
```

## 9. Version Information

### tools/pyproject.toml
```
version = "0.4.0"
```

### tools/specdev_tools/__init__.py
No `__version__` variable. File contains a `_MOVED` dict for deprecated import paths with `__getattr__` lazy-loading pattern (45 lines).

### CLAUDE.md
```
Current version: **0.3.0** (see `tools/pyproject.toml`).
```

**VERSION MISMATCH**: CLAUDE.md says 0.3.0 but pyproject.toml says 0.4.0.

## 10. Code Health Signals

### TODO/FIXME/HACK/XXX in tools/specdev_tools/
Only regex pattern definitions (not actual TODOs):
```
validation/extraction_intent_check.py:17:    r"\b(?:relevant|as needed|as appropriate|etc\.?|various|TBD|TODO)\b",
validation/spec_quality_lint.py:9:PLACEHOLDER_RE = re.compile(r"\b(TBD|TODO|FIXME|XXX|placeholder|<[^>]+>)\b", re.IGNORECASE)
```
One actual TODO in tools/core/json_utils.py:
```python
## TODO: Refine and expose as a tool
```

### pragma: no cover / noqa
```
validation/validators/__init__.py:7: from . import (  # noqa: F401 -- re-exported for validate.py DEEP_VALIDATORS
```
1 occurrence total.

### @pytest.mark.skip / @pytest.mark.xfail
NO OUTPUT -- none found in any test file.

### warnings.warn usage (12 occurrences)
```
generation/prompt_generator.py:192, 225
__init__.py:38 (deprecated import warning)
validation/traceability_closure.py:32
migration/planner.py:309
validation/cross_artifact_checks.py:46
validation/matrix.py:42
validation/validators/step_02.py:83
validation/fixtures_lint.py:20
validation/validators/step_11.py:34, 41
validation/validators/step_01.py:21
```

## 11. R9 Feature References

R9 comments found in source code:
```
validation/forward_replay_check.py:293  # R9/T22: Content staleness
validation/spec_quality_lint.py:13      # R9: additional vague terms
validation/spec_quality_lint.py:149     R9/T18: Scan all free-text fields
validation/validate.py:263              # R9/T26: Extraction intent validation
validation/validate.py:267              # R9/T26: Dynamic W->E promotion
validation/matrix.py:296                # R9/T24: Configurable coverage threshold
validation/matrix.py:305                R9/T24: Enforce coverage thresholds
validation/hallucination_lint.py:293    # R9/T20: Content derivation check
validation/hallucination_lint.py:337    R9/T20: Check downstream content
cli.py:166                              # R9: New commands
cli.py:690                              # R9/T28: Read-only diagnostic
core/errors.py:84                       # R9: Cross-step validation (59x)
```

R9 task IDs referenced: T18, T20, T22, T24, T26, T28

## 12. Spec Directory Usage in Tests

### load_json_file / open.*spec/ references
Only `tests/integration/test_step_11.py` uses a `load_json_file` helper that reads from `spec/` paths:
```python
def load_json_file(filepath):  # line 14
contracts = load_json_file("spec/05_interface_contracts.json")  # line 58
sketch = load_json_file("spec/02_system_sketch.json")           # line 64
frs = load_json_file("spec/04_fr_list.json")                    # line 70
nfrs = load_json_file("spec/07_nfrs.json")                      # line 76
invs = load_json_file("spec/06_invariants.json")                # line 82
caps = load_json_file("spec/01_capabilities.json")              # line 88
fixtures = load_json_file("spec/08_fixtures.json")              # line 94
```

### spec_root fixture usage
Used in: test_cli.py, test_forward_replay_submodule.py, test_cli_submodule_params.py, test_validate_submodule.py, test_init_project_submodule.py, conftest.py, integration/conftest.py

## 13. Additional Findings

### tools/command_prefixes.json
Lists 20 allowed command prefixes for agent sandboxing:
```json
["python", "python3", "bash", "sh", "npm", "pnpm", "yarn", "npx", "make", "pytest", "uv", "node", "go", "cargo", "bun", "vitest", "jest", "tsx", "ruff", "poetry"]
```

### tools/context/
Empty directory (no files).

### tools/core/json_utils.py
A standalone JSON manipulation tool for AI agents (not part of specdev_tools package). Uses jq subprocess calls. 345 lines. Provides: read, patch, insert, delete, keys, structure, schema discovery commands. Contains one TODO comment.

### Packaging Artifacts
- `tools/specdev_tools.egg-info/`: EXISTS (6 files: dependency_links.txt, entry_points.txt, PKG-INFO, requires.txt, SOURCES.txt, top_level.txt)
- `tools/UNKNOWN.egg-info/`: EXISTS (4 files: dependency_links.txt, PKG-INFO, SOURCES.txt, top_level.txt) -- orphaned/stale egg-info

### tools/setup.py
Minimal: `from setuptools import setup; setup()`

### tools/README.md (first 30 lines)
Title: "AI Spec Driven Development CLI (v3 Full)". Describes installation, project initialization with `init_project.py`.

### tools/requirements.txt
```
jsonschema>=4.21.1
pyyaml>=6.0.1
jsonschema-specifications>=2023.12.1
pyjwt>=2.8.0
```
4 dependencies.

### tools/trace_matrix.json
Last modified: 2025-02-22 16:06. Contents: empty matrix with all-zero coverage counters.

### tools/pyproject.toml
- Build system: setuptools>=61.0
- Python requires: >=3.9
- Entry point: `specdev = specdev_tools.cli:main`
- Test config: testpaths=["tests"], patterns test_*.py, classes Test*/*Tests

### .github/workflows/ci.yml
- 4 jobs: validate, redteam, deploy-staging (placeholder), deploy-prod (placeholder)
- Runs on: ubuntu-latest
- Python: "3.x"
- Schedule: daily at 02:00 UTC
- Concurrency: cancels in-progress on same ref
- 14 validation steps in the validate job
