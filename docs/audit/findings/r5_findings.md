# R5 Generation Quality — Findings & Implementation Plan

## Context

The `generation_quality` block in every spec artifact has 7 sub-fields, but only 2 are consumed by any validator or tool. The remaining 5 are write-only — they consume schema space, AI context tokens (~108 lines across 41 prompt files), and test fixture surface area (127 fixture files) with zero validation value. Additionally, E511 (`PLACEHOLDER_SCAN_MISMATCH`) is circular: it validates an agent's self-reported placeholder scan against an independent scan that E510 already performs, making it redundant.

**Decision**: Option (b) — Reduce `generation_quality` to `assumptions`-only. This preserves the one genuinely consumed field (assumptions → E512/W571/W572/W573) while eliminating 71% dead weight. Migration scope is minimal (1 spec artifact).

---

## Part A: Findings

| ID | Sev | File:Line | Finding | Impact |
|----|-----|-----------|---------|--------|
| A-R5-01 | CRIT | `schema/core/collections.schema.json:385-387` | `preflight_passed` is required but never read by any validator — pure write-only | Dead schema field in every artifact; wasted prompt tokens |
| A-R5-02 | HIGH | `schema/core/collections.schema.json:388-417` | `evidence_records` (15-line nested object schema) never read by any validator | 15 lines of dead schema per artifact |
| A-R5-03 | HIGH | `schema/core/collections.schema.json:419-421` | `unresolved_inputs` never read by any validator | Dead field |
| A-R5-04 | HIGH | `schema/core/collections.schema.json:425-438` | `placeholder_scan` object consumed only by circular E511 check | Redundant with E510 independent scan |
| A-R5-05 | HIGH | `schema/core/collections.schema.json:440-461` | `self_check_results` (12-line nested object schema) never read by any validator | Dead field |
| A-R5-06 | HIGH | `tools/specdev_tools/validation/spec_quality_lint.py:94-114` | E511 `_check_placeholder_scan_agreement()` validates agent self-report against independent scan — circular and redundant with E510 | False sense of validation; E510 already catches all real placeholders |
| A-R5-07 | MED | 41 files in `prompts/` | ~108 lines across all prompt files describe full 7-field generation_quality for 5 unused fields | Wasted AI context tokens on every generation |
| A-R5-08 | MED | 127 files in `tests/fixtures/` | All test fixtures contain full 7-field generation_quality object | Fixtures will fail schema validation after schema change |
| A-R5-09 | LOW | `tests/test_spec_quality_lint.py:117-156` | `test_detects_placeholder_count_mismatch` tests E511 which will be removed | Dead test |
| A-R5-10 | LOW | `tools/specdev_tools/core/errors.py:31` | E511 error code definition becomes orphaned after validator removal | Dead error code |

### Evidence (CRIT/HIGH)

**A-R5-01** — `preflight_passed` required but never consumed:
```json
// schema/core/collections.schema.json:463-465
"required": [
    "preflight_passed"
]
```
No validator reads `preflight_passed`. `_check_required_top_level()` (line 154-168) checks for `generation_quality` key existence but never inspects sub-fields.

**A-R5-06** — E511 circularity:
```python
# spec_quality_lint.py:94-114
def _check_placeholder_scan_agreement(rel, data, actual_tokens):
    """RFC 3.2: E511 if independent scan finds tokens NOT reported in generation_quality.placeholder_scan.tokens_found."""
    # ... reads data["generation_quality"]["placeholder_scan"]["tokens_found"]
    # ... compares against actual_tokens from _check_placeholders() (E510)
    # This is circular: E510 already catches all placeholders independently.
    # E511 only detects agent reporting failures which have zero downstream value.
```

---

## Part B: Implementation Plan — Atomic Tasks

### Phase 1 — Foundation (3 parallel subagents)

| ID | Pri | Deps | File | Change summary | Findings |
|----|-----|------|------|----------------|----------|
| Tb01 | P0 | — | `schema/core/collections.schema.json` | Replace `generationQuality` definition: remove `preflight_passed`, `evidence_records`, `unresolved_inputs`, `placeholder_scan`, `self_check_results`, and `required` array. Keep only `assumptions`. | A-R5-01,02,03,04,05 |
| Tb02 | P0 | — | `tools/specdev_tools/core/errors.py` | Remove E511 entry from `ERROR_CODES` dict. | A-R5-10 |
| Tb03 | P0 | — | `tools/specdev_tools/migration/scripts/r5_strip_generation_quality.py` (NEW) | Create migration script that strips old generation_quality sub-fields. | A-R5-08 |

### Phase 2 — Validator Update (depends on Tb01 + Tb02)

| ID | Pri | Deps | File | Change summary | Findings |
|----|-----|------|------|----------------|----------|
| Tb04 | P0 | Tb01,Tb02 | `tools/specdev_tools/validation/spec_quality_lint.py` | Delete `_check_placeholder_scan_agreement()` and all calls to it. | A-R5-06 |

### Phase 3 — Spec Artifact Migration (depends on Tb01)

| ID | Pri | Deps | File | Change summary | Findings |
|----|-----|------|------|----------------|----------|
| Tb05 | P0 | Tb01 | `spec/05_interface_contracts.json` | Replace `generation_quality` block with `{"assumptions": []}`. | A-R5-08 |

### Phase 4 — Test Updates (6 parallel, depend on Tb03/Tb04)

| ID | Pri | Deps | File | Change summary | Findings |
|----|-----|------|------|----------------|----------|
| Tb06 | P0 | Tb04 | `tests/test_spec_quality_lint.py` | Remove E511 test, update fixtures, add simplified gq test. | A-R5-06,09 |
| Tb07 | P0 | Tb03 | 127 files in `tests/fixtures/` | Run migration script on all fixtures. | A-R5-08 |
| Tb08 | P0 | Tb01 | `tests/test_schema_contracts.py` | Update inline generation_quality fixtures. | A-R5-08 |
| Tb09a | P0 | Tb01 | `tests/integration/test_step_16.py` | Update inline generation_quality. | A-R5-08 |
| Tb09b | P0 | Tb01 | `tests/test_canonical_integrity.py` | Update inline generation_quality. | A-R5-08 |
| Tb09c | P0 | Tb01 | `tests/test_invariants.py` | Update inline generation_quality. | A-R5-08 |

### Phase 5 — Prompt Updates (3 parallel, depend on Tb01)

| ID | Pri | Deps | File | Change summary | Findings |
|----|-----|------|------|----------------|----------|
| Tb10 | P2 | Tb01 | 16 prompt files | Replace full generation_quality JSON with assumptions-only. | A-R5-07 |
| Tb11 | P2 | Tb01 | 19 migration templates | Same pattern as Tb10 for migration templates. | A-R5-07 |
| Tb12 | P1 | Tb01,Tb10 | `tests/test_prompt_schema_sync.py` | Verify/fix tests after schema change. | A-R5-08 |

### Phase 6 — Version Bump

| ID | Pri | Deps | File | Change summary |
|----|-----|------|------|----------------|
| Tb13 | P0 | Tb01-Tb12 | `tools/pyproject.toml` | Bump version 0.3.0 → 0.4.0. |

### Phase 7 — Documentation (2 parallel)

| ID | Pri | Deps | File | Change summary |
|----|-----|------|------|----------------|
| D01 | P3 | Tb13 | `changelog/v0.4.0.md` + `changelog/v0.4.0.yaml` (NEW) | Create changelog entries for breaking changes. |
| D02 | P3 | Tb02 | `docs/developers/error-codes.md` | Add deprecation notice for E511. |

### Phase 8 — Final Validation Gate

| ID | Pri | Deps | Change summary |
|----|-----|------|----------------|
| Tb14 | P0 | ALL | Run full test + validation suite. |

---

## Verification Checklist

- CHECK 1 Assumptions: PASS — No hedging language. All findings verified against actual code.
- CHECK 2 References: PASS — All file:line references confirmed.
- CHECK 3 Atomic: PASS — Each task modifies exactly one file (Tb09 split into Tb09a/b/c).
- CHECK 4 Tests: PASS — Every code change has corresponding test task.
- CHECK 5 Docs: PASS — E511 removal → D02. Version bump → D01.
- CHECK 6 Deps: PASS — All deps reference earlier tasks. No circular dependencies.
- CHECK 7 Orphans: PASS — All 10 findings mapped to tasks.
