# P1-B2: Linters, Canonical, Generation & Migration — SoC Analysis

Agent Type: Explore (very thorough)
Repo Root: /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/

### Objective

Audit separation of concerns and DRY compliance across all non-validator tool modules. Identify layer violations, duplicated logic between linters, and modules doing too much.

### Exclusive Scope

Do NOT audit `validators/*.py` — P1-B1 covers those exclusively.
Do NOT assess error flow or error code consistency — P1-E covers that.
Do NOT assess registry consistency or CLI wiring — P1-A covers those.

Read every file listed below with LOC:

**validation/ (non-validator files)**

| LOC | File |
|-----|------|
| 537 | `validation/validate.py` |
| 124 | `validation/_extraction_intent_parser.py` |
| 128 | `validation/canon_schema_alignment.py` |
| 307 | `validation/cross_artifact_checks.py` |
| 195 | `validation/dag_lint.py` |
| 94 | `validation/dependency_order_lint.py` |
| 119 | `validation/docs_lint.py` |
| 118 | `validation/extraction_intent_check.py` |
| 109 | `validation/fixtures_lint.py` |
| 385 | `validation/forward_replay_check.py` |
| 37 | `validation/governance.py` |
| 440 | `validation/hallucination_lint.py` |
| 86 | `validation/invariants.py` |
| 353 | `validation/matrix.py` |
| 310 | `validation/seed_lint.py` |
| 257 | `validation/spec_quality_lint.py` |
| 152 | `validation/traceability_closure.py` |

**canonical/**

| LOC | File |
|-----|------|
| 397 | `canonical/autofix.py` |
| 640 | `canonical/integrity.py` |
| 472 | `canonical/lint.py` |
| 318 | `canonical/registry.py` |

**generation/**

| LOC | File |
|-----|------|
| 813 | `generation/prompt_generator.py` |
| 501 | `generation/prompt_schema_sync.py` |
| 1331 | `generation/schema_differ.py` (largest module in the entire codebase) |

**migration/**

| LOC | File |
|-----|------|
| 335 | `migration/planner.py` |
| 385 | `migration/runner.py` |
| 66 | `migration/scripts/strip_generation_quality.py` |
| 18 | `migration/__init__.py` (re-exports public API: MigrationPlan, MigrationStep, etc.) |

### Known Context from Ground Truth

**Import graph (validation/ -> other packages)**:
```
canon_schema_alignment.py   -> canonical.registry.CanonicalRegistry
cross_artifact_checks.py    -> core.trace_types (is_valid_trace_type, normalize_trace_type)
fixtures_lint.py            -> core.trace_types (is_valid_trace_type, normalize_trace_type)
hallucination_lint.py       -> canonical.lint.lint_canon_dir
                            -> canonical.registry.CanonicalRegistry
                            -> core.trace_types.is_valid_trace_type
matrix.py                   -> core.trace_types (normalize_trace_type, is_valid_trace_type)
traceability_closure.py     -> core.trace_types (is_valid_trace_type, normalize_trace_type)
matrix.py                   -> validation.cross_artifact_checks (intra-package)
validate.py                 -> canonical.integrity (validate_canonical_integrity, validate_canonical_integrity_file)
                            -> canonical.lint.lint_canon_dir
                            -> generation.prompt_schema_sync.run_prompt_schema_sync
                            -> core.errors.PROMOTABLE_PAIRS
                            -> core.registry.SchemaRegistry
                            -> (intra-package) dependency_order_lint, forward_replay_check,
                               extraction_intent_check, hallucination_lint,
                               spec_quality_lint, traceability_closure, validators
```

**canonical/ -> core/**:
```
autofix.py     -> core.registry.SchemaRegistry
integrity.py   -> core.registry.SchemaRegistry
lint.py        -> core.registry.SchemaRegistry
```

**generation/ -> core/ and intra-package**:
```
prompt_generator.py     -> core.changelog_parser
prompt_generator.py     -> generation.schema_differ (intra-package)
prompt_schema_sync.py   -> core.registry.SchemaRegistry
schema_differ.py        -> core.changelog_parser
schema_differ.py        -> validation.validate.validate_dir (lazy import, line 1256)
schema_differ.py        -> validation.matrix.validate_trace_integrity (lazy import, line 1267)
```

**WARNING**: `schema_differ.py` contains lazy imports back into `validation/`, creating a circular dependency path at the package level: `validation/ -> generation.prompt_schema_sync` AND `generation.schema_differ -> validation/`. These are deferred at runtime via local imports but represent a significant SoC concern.

**migration/ -> other packages and intra-package**:
```
planner.py -> generation.schema_differ, core.changelog_parser
runner.py  -> generation.schema_differ
runner.py  -> migration.planner (intra-package: MigrationPlan, MigrationStep)
```

**Layer direction**:
```
core/ <- canonical/
core/ <- generation/
core/, canonical/, generation/ <- validation/
core/, generation/ <- migration/
generation/ <- validation/ (via schema_differ.py lazy imports — CIRCULAR at package level)
```
The key cross-cutting imports are: (1) `validate.py -> generation.prompt_schema_sync` (validation depends on generation), and (2) `schema_differ.py -> validation.validate` and `schema_differ.py -> validation.matrix` (generation depends back on validation, creating a circular dependency path deferred via lazy imports).

### Questions

**Separation of Concerns (7 questions)**

1. `validate.py` (537 LOC) orchestrates schema validation, deep validation, canonical integrity, canonical lint, prompt-schema sync, and W->E promotion. Is it doing too much? Should any of these responsibilities be extracted?
2. `validate.py` imports from `generation.prompt_schema_sync` — this means validation/ depends on generation/. Is this a layer violation? Should prompt-schema sync be moved to validation/ or extracted to a shared location?
3. Is there validation logic that has leaked into `cli.py` (757 LOC) instead of living in the validation package?
4. `canonical/lint.py` (472 LOC) and `canonical/integrity.py` (640 LOC) — do these have overlapping responsibilities? Where is the boundary between "lint" and "integrity"?
5. `core/trace_types.py` (53 LOC) — is this correctly placed in core/? It's imported by 5 validation modules (also imported by 4 validator modules in P1-B1 scope — 9 total consumers). Could it belong in validation/ instead?
6. Are error codes centralized in `core/errors.py` or scattered across individual modules? Do any linters define their own error codes inline?
7. `validation/_extraction_intent_parser.py` (124 LOC) — the leading underscore suggests it's private. Is it only used by `extraction_intent_check.py`, or is it imported elsewhere?

**DRY Between Linters (5 questions)**

8. `hallucination_lint.py` (440 LOC) and `spec_quality_lint.py` (257 LOC) — both check content quality. Do they share patterns (e.g., vague language detection, placeholder detection, field scanning)? Is there duplicated logic?
9. `cross_artifact_checks.py` (307 LOC) and `traceability_closure.py` (152 LOC) — both deal with cross-artifact references. Is there overlap in how they load and check references?
10. `governance.py` (37 LOC) and `invariants.py` (86 LOC) — these are unusually small. Do they duplicate `_load` patterns from the validators, or do they have their own approach?
11. Do multiple linters independently load and parse JSON schema files, duplicating what `core/registry.py` provides?
12. Do any linters re-implement jsonschema validation instead of delegating to validate.py's schema validation?

**Generation Package (2 questions)**

13. `schema_differ.py` (1331 LOC) is the largest module in the codebase. Does its size indicate it should be split? What are its main responsibilities?
14. `prompt_schema_sync.py` (501 LOC) — does it duplicate registry-loading logic that already exists in `core/registry.py`?

**Migration Package (2 questions)**

15. `migration/runner.py` (385 LOC) — does it duplicate validation logic that should be delegated to the validation package?
16. `migration/planner.py` (335 LOC) — does it duplicate registry or schema-loading logic from core/ or generation/?

### Output Format

Write to: `WIP/tool_audit/p1-out-soc-linters.md`

Use finding format:

```
### FINDING-SL{N}: {Title}
- **Severity**: critical | high | medium | low | info
- **Category**: SOC_BREACH | DRY_VIOLATION | LAYER_VIOLATION | ABSTRACTION_MISSING
- **Locations**: {file path(s) with LOC}
- **Description**: {what is wrong or suboptimal}
- **Evidence**: {specific imports, duplicated functions, or shared patterns}
- **Recommendation**: {proposed refactoring}
```

End with a `## PASS` section listing things that are well-separated and properly factored.

Limit: 200 lines.
