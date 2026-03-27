# Implementation Plan: ALIGN-2 — Migrate schema URIs from URL to vc: prefix

Topic: align2-uri
Generated: 2026-03-20
Source: inline

## Goal

Replace all `https://specdev.local/schema/...` URIs with short `vc:` prefixed identifiers across the entire codebase. This is a mechanical find-and-replace migration — no logic changes except one regex in cli.py.

## URI Mapping Table

All tasks reference this canonical mapping. Fragment suffixes (#anchor, #/$defs/...) are preserved — only the base URI changes.

| Old URI | New URI |
|---------|---------|
| `https://specdev.local/schema/00_charter.schema.json` | `vc:00-charter` |
| `https://specdev.local/schema/01_capabilities.schema.json` | `vc:01-capabilities` |
| `https://specdev.local/schema/02_system_sketch.schema.json` | `vc:02-system-sketch` |
| `https://specdev.local/schema/02a_delivery_baseline.schema.json` | `vc:02a-delivery-baseline` |
| `https://specdev.local/schema/03_glossary.schema.json` | `vc:03-glossary` |
| `https://specdev.local/schema/04_fr_list.schema.json` | `vc:04-fr-list` |
| `https://specdev.local/schema/05_interface_contracts.schema.json` | `vc:05-interface-contracts` |
| `https://specdev.local/schema/06_invariants.schema.json` | `vc:06-invariants` |
| `https://specdev.local/schema/07_nfrs.schema.json` | `vc:07-nfrs` |
| `https://specdev.local/schema/08_fixtures.schema.json` | `vc:08-fixtures` |
| `https://specdev.local/schema/09_impl_plan.schema.json` | `vc:09-impl-plan` |
| `https://specdev.local/schema/10_governance.schema.json` | `vc:10-governance` |
| `https://specdev.local/schema/11_redteam.schema.json` | `vc:11-redteam` |
| `https://specdev.local/schema/12_ci_gates.schema.json` | `vc:12-ci-gates` |
| `https://specdev.local/schema/13_extension_generator.schema.json` | `vc:13-extension-generator` |
| `https://specdev.local/schema/13a_completeness_assessment.schema.json` | `vc:13a-completeness-assessment` |
| `https://specdev.local/schema/14_roadmap.schema.json` | `vc:14-roadmap` |
| `https://specdev.local/schema/15_scaffold.schema.json` | `vc:15-scaffold` |
| `https://specdev.local/schema/16_impl_context.schema.json` | `vc:16-impl-context` |
| `https://specdev.local/schema/16a_impl_context.schema.json` | `vc:16-impl-context` |
| `https://specdev.local/schema/16b_impl_context.schema.json` | `vc:16-impl-context` |
| `https://specdev.local/schema/16c_impl_context.schema.json` | `vc:16-impl-context` |
| `https://specdev.local/schema/core/atoms/1` | `vc:core:atoms` |
| `https://specdev.local/schema/core/collections/1` | `vc:core:collections` |
| `https://specdev.local/schema/core/errors/1` | `vc:core:errors` |
| `https://specdev.local/schema/core/step_base/1` | `vc:core:step-base` |
| `https://specdev.local/schema/core/canon/1` | `vc:core:canon` |
| `https://specdev.local/schema/canon/kind/1` | `vc:canon:kind` |
| `https://specdev.local/schema/canon/aliases/1` | `vc:canon:aliases` |
| `https://specdev.local/schema/seed_manifest.schema.json` | `vc:seed-manifest` |
| `https://specdev.local/schema/step_order.schema.json` | `vc:step-order` |

## Scope

- Files to modify: 106
- Files to create: 0
- Estimated tasks: 6
- Execution batches: 3

## Reference Patterns

- URI mapping table above is the single source of truth for all replacements
- Fragment preservation: `https://specdev.local/schema/core/atoms/1#kebabId` → `vc:core:atoms#kebabId` (only base URI changes)
- JSON Pointer fragments: `https://specdev.local/schema/core/collections/1#/$defs/dependencyList` → `vc:core:collections#/$defs/dependencyList`

## Tasks

### Batch 1 — Foundation

#### T-align2-uri-001 — Update schema_registry.json keys to vc: URIs

Task 001:
  file: tools/schema_registry.json
  mode: modify
  reads: tools/schema_registry.json
  action: Replace all 32 JSON object keys from old `https://specdev.local/schema/...` URLs to new `vc:` URIs per the URI Mapping Table. Values (file paths) remain unchanged. The 16a/16b/16c aliases all map to `vc:16-impl-context` pointing to `schema/16_impl_context.schema.json`.
  verify: All 32 keys start with `vc:`. No key contains `specdev.local`. All values (file paths) are unchanged.
  test_gate: none
  depends_on: none
  parallel_group: 1
  source: T-align2-uri-001

### Batch 2 — Schema files, canon/spec data, Python source (parallel)

#### T-align2-uri-002 — Update $id and $ref in all 26 schema files

Task 002:
  file: schema/00_charter.schema.json, schema/01_capabilities.schema.json, schema/02_system_sketch.schema.json, schema/02a_delivery_baseline.schema.json, schema/03_glossary.schema.json, schema/04_fr_list.schema.json, schema/05_interface_contracts.schema.json, schema/06_invariants.schema.json, schema/07_nfrs.schema.json, schema/08_fixtures.schema.json, schema/09_impl_plan.schema.json, schema/10_governance.schema.json, schema/11_redteam.schema.json, schema/12_ci_gates.schema.json, schema/13_extension_generator.schema.json, schema/13a_completeness_assessment.schema.json, schema/14_roadmap.schema.json, schema/15_scaffold.schema.json, schema/16_impl_context.schema.json, schema/core/atoms.schema.json, schema/core/collections.schema.json, schema/core/errors.schema.json, schema/core/step_base.schema.json, schema/core/canon.schema.json, canon/kind.schema.json, canon/aliases.schema.json
  mode: modify
  reads: tools/schema_registry.json
  action: In each schema file, replace the `$id` value and all `$ref` values that contain `https://specdev.local/schema/...` with the corresponding `vc:` URI per the URI Mapping Table. Preserve all fragment suffixes (#anchor and #/$defs/... portions) — only the base URI before the # changes. For files that only have a `$id` and no cross-schema `$ref`, just update the `$id`.
  verify: No file contains the string `specdev.local`. Every `$id` starts with `vc:`. Every `$ref` that previously pointed to `https://specdev.local/...` now starts with `vc:`. All fragment suffixes are preserved.
  test_gate: none
  depends_on: 1
  parallel_group: 2
  source: T-align2-uri-002

#### T-align2-uri-003 — Update $schema and $ref in canon and spec JSON data files

Task 003:
  file: canon/manifest.json, canon/aliases.json, canon/kinds/owner.json, canon/kinds/trace_type.json, canon/kinds/nfr_category.json, spec/05_interface_contracts.json, spec/common/seed_manifest.json
  mode: modify
  reads: tools/schema_registry.json
  action: In each JSON data file, replace the `$schema` value from `https://specdev.local/schema/...` to the corresponding `vc:` URI per the URI Mapping Table. These are data files (not schemas) so they have `$schema` (not `$id`). Some canon kind files reference `https://specdev.local/schema/canon/kind/1` → `vc:canon:kind`. The manifest references `https://specdev.local/schema/core/canon/1` → `vc:core:canon`. The aliases file references `https://specdev.local/schema/canon/aliases/1` → `vc:canon:aliases`.
  verify: No file contains the string `specdev.local`. Every `$schema` value starts with `vc:`.
  test_gate: none
  depends_on: 1
  parallel_group: 2
  source: T-align2-uri-003

#### T-align2-uri-004 — Update Python source: cli.py regex and lint.py URI constants

Task 004:
  file: tools/specdev_tools/cli.py, tools/specdev_tools/canonical/lint.py
  mode: modify
  reads: tools/specdev_tools/cli.py, tools/specdev_tools/canonical/lint.py
  action: |
    **cli.py** (function `_derive_step_names` at ~line 87):
    - Update the docstring to reference the new URI format `vc:NN-name` instead of `https://specdev.local/schema/NN_name.schema.json`
    - Replace the regex `r"/(\d{2}[a-z]?)_([^.]+)\.schema\.json$"` with `r"^vc:(\d{2}[a-z]?)-(.+)$"` to match the new `vc:NN-name` format
    - Update the `raw_name` derivation: change `.replace("_", " ")` to `.replace("-", " ")` since names now use hyphens
    - The regex must NOT match `vc:core:...`, `vc:canon:...`, `vc:seed-manifest`, or `vc:step-order` — only step schemas like `vc:00-charter`

    **canonical/lint.py** (lines 28-30):
    - `CANON_ALIASES_SCHEMA_URI = "vc:canon:aliases"`
    - `CANON_KIND_SCHEMA_URI = "vc:canon:kind"`
    - `CANON_MANIFEST_SCHEMA_URI = "vc:core:canon"`
  verify: cli.py regex matches `vc:00-charter` and extracts group(1)="00", group(2)="charter". cli.py regex does NOT match `vc:core:atoms`. lint.py contains no `specdev.local` strings. All 3 URI constants start with `vc:`.
  test_gate: none
  depends_on: 1
  parallel_group: 2
  source: T-align2-uri-004

### Batch 3 — Tests, prompts, docs (parallel)

#### T-align2-uri-005 — Update all Python test files with hardcoded URIs

Task 005:
  file: tests/unit/test_cli.py, tests/unit/generation/test_prompt_schema_sync.py, tests/unit/generation/test_schema_contracts.py, tests/unit/canonical/test_canonical_integrity.py, tests/unit/canonical/test_canonical_lint.py, tests/unit/canonical/test_canon_schema_alignment.py, tests/unit/validation/test_validate_integration.py, tests/unit/validation/linters/test_invariants.py, tests/unit/validation/linters/test_quality_lint_rules.py, tests/unit/validation/linters/test_r9_quality_lint.py, tests/unit/validation/linters/test_spec_quality_lint.py, tests/unit/validation/linters/test_seed_strict_mode.py, tests/unit/validation/linters/test_fixtures_lint.py, tests/unit/validation/linters/test_seed_path_validation.py, tests/unit/migration/test_migration_templates.py, tests/unit/core/test_errors_submodule.py, tests/unit/core/test_registry_error_handling.py, tests/integration/test_step_02a.py, tests/integration/test_step_10.py, tests/integration/test_step_16.py
  mode: modify
  reads: tools/schema_registry.json
  action: In each test file, replace all hardcoded `https://specdev.local/schema/...` URI strings with the corresponding `vc:` URI per the URI Mapping Table. These appear in mock data, fixture JSON, expected values, and string assertions. Preserve all fragment suffixes. Be especially careful with `test_prompt_schema_sync.py` which has the most occurrences (~30+). Also update any test assertions that check for the old URI format.
  verify: No test file contains the string `specdev.local`. All tests pass: `pytest tests/ -x`.
  test_gate: pytest tests/ -x
  depends_on: 2, 3, 4
  parallel_group: 3
  source: T-align2-uri-005

#### T-align2-uri-006 — Update prompts, migration templates, and documentation

Task 006:
  file: prompts/prompt_00_project_charter.md, prompts/prompt_01_capabilities.md, prompts/prompt_02_system_sketch.md, prompts/prompt_02a_delivery_baseline.md, prompts/prompt_03_glossary.md, prompts/prompt_04_functional_requirements.md, prompts/prompt_05_interface_contracts.md, prompts/prompt_06_invariants.md, prompts/prompt_07_nfrs.md, prompts/prompt_08_fixtures.md, prompts/prompt_09_impl_plan.md, prompts/prompt_10_governance.md, prompts/prompt_11_redteam.md, prompts/prompt_12_ci_gates.md, prompts/prompt_13_extension_generator.md, prompts/prompt_13a_completeness_assessment.md, prompts/prompt_14_roadmap.md, prompts/prompt_15_scaffold.md, prompts/prompt_16_impl_context.md, prompts/prompt_16a_impl_planner.md, prompts/prompt_16b_impl_coder.md, prompts/prompt_16c_impl_reviewer.md, prompts/migration/template_charter.md, prompts/migration/template_capabilities.md, prompts/migration/template_system_sketch.md, prompts/migration/template_delivery_baseline.md, prompts/migration/template_glossary.md, prompts/migration/template_frs.md, prompts/migration/template_interfaces.md, prompts/migration/template_invariants.md, prompts/migration/template_nfrs.md, prompts/migration/template_fixtures.md, prompts/migration/template_impl_plan.md, prompts/migration/template_governance.md, prompts/migration/template_redteam.md, prompts/migration/template_ci_gates.md, prompts/migration/template_extension_generator.md, prompts/migration/template_completeness_assessment.md, prompts/migration/template_roadmap.md, prompts/migration/template_scaffold.md, prompts/migration/template_impl_context.md, tools/README.md, docs/audit/findings/r8_findings.md, docs/plans/phase_0_governance_plan.md, docs/developers/path_conventions.md, docs/developers/extension_schemas.md
  mode: modify
  reads: tools/schema_registry.json
  action: In each markdown file, replace all `https://specdev.local/schema/...` URI strings with the corresponding `vc:` URI per the URI Mapping Table. These appear in `$schema` examples, `$ref` documentation, inline JSON snippets, and prose references. Preserve all surrounding context and formatting.
  verify: No file in prompts/, prompts/migration/, tools/README.md, or docs/ contains the string `specdev.local`.
  test_gate: none
  depends_on: 1
  parallel_group: 3
  source: T-align2-uri-006

## Test Strategy

- Per-task gates: Task 005 runs `pytest tests/ -x` (all 1344 tests)
- Full suite: `pytest tests/`
- Expected test count after implementation: 1344 (current: 1344) — no tests added or removed

## Risks & Assumptions

1. **Assumption: No external consumers of old URIs** — The `https://specdev.local/...` URIs are internal to this toolkit. No external system resolves them. If any host repo spec files use these URIs in `$schema`, they will need updating separately (only 2 spec files found in this repo).
2. **Assumption: `referencing` library handles `vc:` scheme** — JSON Schema's `referencing` library (v0.36.2) treats `$id` as opaque identifiers. Custom URI schemes are valid per RFC 3986. No library changes expected.
3. **Risk: Prompt files are consumed by LLM runners** — Updating URI references in prompts changes what the LLM sees. Since the new URIs are shorter and cleaner, this is a positive change, but any LLM-generated spec artifacts will use the new URIs. Old artifacts with old URIs will still validate if the registry is updated first.
4. **WIP and done directories excluded** — Files under `WIP/` and `WIP/done/` contain stale audit artifacts with old URIs. These are not updated as they are historical records.

## Observations

None.

## Decision Log

None.
