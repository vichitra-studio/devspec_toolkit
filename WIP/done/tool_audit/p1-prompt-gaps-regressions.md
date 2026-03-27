# P1-F: Gaps, Misses, Bugs & Regressions Analysis

Agent Type: Explore (very thorough)
Repo Root: /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/

## Objective

Find functional bugs, missing coverage, edge cases, regressions. Focus on schema-to-validator field-level consistency and edge cases. Do NOT report DRY issues (P1-B covers those), test quality (P1-D covers that), registry-to-filesystem consistency (P1-A covers that), or style issues.

## Scope

- `tools/specdev_tools/validation/validators/*.py` (spot-check against corresponding schemas)
- `schema/*.schema.json` (cross-reference fields against validator checks)
- `tests/` (look for skipped tests, xfail markers, TODOs)
- `tools/step_order.json` (dependency DAG vs validator load assumptions)

## Known Context (from ground truth — DO NOT re-verify these)

- 21 step validators (step_01 through step_16c), NO step_00 validator
- Validator dispatch dict is named `DEEP_VALIDATORS` (21 entries, exact lambdas listed in ground truth section 4.2)
- 22 steps in step_order.json: 00, 01, 02, 02a, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 13a, 14, 15, 16, 16a, 16b, 16c
- Schema registry: 29 entries. Steps 16a/16b/16c all map to `schema/16_impl_context.schema.json`
- 24 schema files total (19 step + 4 core + 1 seed_manifest)
- Step 16 schema: 1868 lines, max nesting depth 19, has 4 $defs
- Step 00 schema: 202 lines, max nesting depth 8, 21 top-level properties
- 23 `_load_*` functions across validators (full list in ground truth section 4.3)
- _load_fr_ids exists in step_05, step_06, step_07 with functionally equivalent but stylistically different implementations
- Code health: zero TODOs in specdev_tools/, zero skips/xfails in tests, one noqa in validators/__init__.py line 7
- 1 TODO in tools/core/json_utils.py (outside specdev_tools package)
- 12 warnings.warn call sites (listed in ground truth section 10.4)
- R9 task IDs: T18, T20, T22, T24, T26, T28
- R9 markers in 12 source locations (listed in ground truth section 11)
- R9 scope: vague language scan (T18), content derivation (T20), staleness detection (T22), coverage thresholds (T24), extraction intent + W->E promotion (T26), env-check diagnostic (T28)
- R9 new CLI commands: dag-lint, extraction-intent-check, env-check
- R9 test files: test_r9_cli.py (286 LOC), test_r9_cross_step.py (1047), test_r9_dag_lint.py (461), test_r9_error_codes.py (84), test_r9_extraction_intent.py (459), test_r9_forward_replay.py (648), test_r9_hallucination.py (584), test_r9_matrix.py (263), test_r9_quality_lint.py (433), test_r9_validate.py (475) — 10 files, 4,740 LOC total
- Version mismatch: CLAUDE.md says 0.3.0, pyproject.toml has 0.4.0

## Questions

### Schema-to-Validator Field Consistency (4 questions)

Q1. Spot-check step_05 (interface_contracts): does the validator check fields that actually exist in `schema/05_interface_contracts.schema.json`? Are there schema-defined fields the validator ignores? Are there validator checks on fields not in the schema?

Q2. Spot-check step_08 (fixtures): same cross-reference. The validator loads FR IDs, API IDs, invariant IDs, and NFR IDs via 4 `_load_*` functions — do the schema fields for target references match what the validator checks?

Q3. Spot-check step_14 (roadmap): this validator has 4 `_load_*` functions (milestone IDs, tech stack names, FR IDs, capability IDs from different upstream steps). Do the schema fields match the validator's cross-reference checks?

Q4. Steps 16a/16b/16c share `16_impl_context.schema.json` (1868 lines, 17 top-level properties) but have separate small validators (46/45/47 LOC). Do the validators check the right subset of fields for each sub-step? What fields does each sub-step validator actually validate vs what the shared schema defines?

### Validator-to-step_order Dependencies (2 questions)

Q5. Cross-reference the 23 `_load_*` functions (ground truth section 4.3) against `step_order.json` dependencies. Do any validators load data from steps that aren't listed as upstream in the DAG? Check at least step_08 (loads from 04, 05, 06, 07) and step_14 (loads from 01, 04, 09).

Q6. Step 00 has no deep validator — is the charter schema rich enough that JSON Schema validation alone is sufficient? Or are there semantic checks (like unique IDs, cross-references) that should exist?

### Edge Cases (4 questions)

Q7. What happens when a spec directory is empty? Does `validate-all` handle this gracefully, or does it crash/give misleading output?

Q8. What happens with malformed JSON (truncated file, BOM, encoding issues)? Is there a try/except around JSON parsing?

Q9. What happens when schema_registry.json references a schema file that doesn't exist on disk?

Q10. Unicode handling — do validators handle non-ASCII characters in field values (e.g., glossary terms in non-Latin scripts)?

### Code Health (4 questions — most already answered, verify quickly)

Q11. (VERIFIED: zero TODOs in specdev_tools/, one in tools/core/json_utils.py) — just confirm no new ones have appeared.

Q12. (VERIFIED: one noqa in validators/__init__.py:7) — read that line and confirm it's justified.

Q13. (VERIFIED: zero skip/xfail) — just confirm.

Q14. The 12 `warnings.warn` call sites — are any of these indicating known bugs or incomplete implementations? Spot-check 3-4 of them for context.

### R9 Feature Round Coverage (2 questions)

Q15. The 10 `test_r9_*` files total 4,740 LOC. Cross-reference against the 12 R9 marker locations in source code and the 6 R9 task IDs (T18: vague language scan, T20: content derivation, T22: staleness detection, T24: coverage thresholds, T26: extraction intent + W->E promotion, T28: env-check diagnostic) — is every R9 feature exercised by at least one test? Are there R9 features without dedicated test coverage?

Q16. Are all R9-added checks registered in DEEP_VALIDATORS and reachable via CLI? Specifically: dag-lint, extraction-intent-check, and env-check are CLI commands — verify they're wired through cli.py (lines 166-174 per ground truth).

## Output Format

Write to: `WIP/tool_audit/p1-out-gaps-regressions.md`

### Finding Format

```
### FINDING-G{N}: {title}

- **Severity**: Critical | High | Medium | Low
- **Category**: SCHEMA_VALIDATOR_MISMATCH | REGISTRY_INCONSISTENCY | EDGE_CASE | CODE_HEALTH | REGRESSION
- **Location**: {file}:{line}
- **Description**: {what's missing/broken}
- **Evidence**: {code reference, failing scenario, or missing check}
- **Impact**: {what breaks or is missed because of this}
- **Recommendation**: {specific fix}
```

### Output Structure

1. Executive summary (5 lines max)
2. Findings (numbered FINDING-G1 through FINDING-GN)
3. R9 coverage matrix (R9 task ID vs test file — small table)
4. Summary table of all findings with severity and category

**Hard limit: 200 lines.**
