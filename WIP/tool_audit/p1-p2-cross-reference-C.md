# P1+P2 Cross-Reference Report (Agent C)

**Date**: 2026-03-18
**Agent**: Cross-Reference Agent C
**Inputs**: 8 file pairs (A vs B) + 2 orchestration reports
**Methodology**: Read all 18 files, matched findings across runs, verified discrepancies against live codebase

## Summary
- Container A total findings: 76
- Container B total findings: 73
- Corroborated (both found): 52
- A-only (B missed): 11 -- of which 8 verified genuine
- B-only (A missed): 10 -- of which 8 verified genuine
- Contradictions: 2 (severity-only; no factual disagreements)
- **Net unique findings after cross-reference**: 68

The two runs show strong convergence on the most important findings. All HIGH and CRITICAL issues were identified by both (though sometimes in different dimensions). The unique-to-one-run findings are mostly lower-severity observations. Two severity disagreements are significant: unregistered error codes (A=CRITICAL, B=MEDIUM) and layer violation (A=HIGH, B=MEDIUM). A was more thorough on error codes (caught E320 which B missed). B was more thorough on code health (governance.py file leak, json_utils.py untested).

---

## Per-Dimension Analysis

### P1-A: Structure & Wiring

A: 10 findings (S1-S10). B: 10 findings (S1-S10).

#### Corroborated
| A Finding | B Finding | Description | Severity Agreement |
|-----------|-----------|-------------|-------------------|
| S1 (high) | S1 (high) | Version mismatch 0.3.0 vs 0.4.0 across CLAUDE.md, pyproject.toml, README | YES |
| S2 (medium) | S1-partial | No `__version__` in package (A explicit, B folds into S1) | YES |
| S3 (low) | S4 (low) | Orphaned UNKNOWN.egg-info directory | YES |
| S4 (low) | S5 (low) | Stale trace_matrix.json checked in | YES |
| S5 (medium) | S9 (medium) | step_01/step_02 duplicate schema validation | YES |
| S6 (medium) | S7 (medium) | validate.py cross-package import from generation/ | YES |
| S7 (low) | S8 (info) | Lazy import shim (A: 23 entries, B: 22 entries) | MINOR (low vs info) |
| S8 (medium) | S10 (medium) | CLAUDE.md missing CLI subcommands | YES |
| S9 (low) | S2 (medium) | STEP_NAMES dict hardcoded in cli.py | NO (low vs medium) |

#### A-only
- **S10 (info)**: Pre-commit hooks use `python -m` instead of entry point. B lists this under PASS as correct behavior. VERDICT: **FALSE_POSITIVE** -- using `python -m` is more reliable in pre-commit contexts.

#### B-only
- **S3 (low)**: validators/__init__.py only re-exports 3 of 21 modules. Verified: __init__.py imports only step_16a/16b/16c. VERDICT: **GENUINE** -- legitimate structural observation.
- **S6 (info)**: Empty tools/context/ directory. Verified: exists and is empty. VERDICT: **GENUINE** -- cleanup item.

#### Contradictions
None factual. STEP_NAMES severity: recommend MEDIUM (B's assessment) -- drift risk justifies it.

---

### P1-B1: DRY Validators

A: 9 findings (DV1-DV9). B: 9 findings (DV1-DV9).

#### Corroborated
| A Finding | B Finding | Description | Severity Agreement |
|-----------|-----------|-------------|-------------------|
| DV1 (high) | DV1 (high) | _load_fr_ids duplicated 6 times, ~120 LOC | YES |
| DV2 (high) | DV2 (high) | _load_api_ids duplicated 5 times, ~100 LOC | YES |
| DV3 (medium) | DV3 (medium) | _load_capability_ids duplicated 2 times | YES |
| DV4 (medium) | DV4 (medium) | _load_nfr_ids duplicated 2 times | YES |
| DV5 (medium) | DV5 (medium) | step_14 loaders have different signature (artifact_path) | YES |
| DV6 (medium) | DV7 (medium) | upstream_map pattern duplicated 3 times | YES |
| DV7 (low) | DV6 (medium) | Kebab-case regex duplicated across files | NO (low vs medium) |
| DV8 (low) | DV8 (low) | Import pattern inconsistency (type hints, __future__) | YES |
| DV9 (medium) | DV9 (info) | validate.py also has _load_* functions | NO (medium vs info) |

#### A-only
None.

#### B-only
None.

#### Contradictions
- Kebab regex severity: recommend LOW (A) -- ~16 LOC, low drift risk.
- validate.py _load_* severity: recommend MEDIUM (A) -- unifying with shared loaders is part of the DV1-DV5 fix.

Both runs estimate ~300-350 LOC reduction. Strong agreement.

---

### P1-B2: DRY & SoC (Linters, Canonical, Generation, Migration)

A: 9 findings (SL1-SL9). B: 9 findings (SL1-SL9).

#### Corroborated
| A Finding | B Finding | Description | Severity Agreement |
|-----------|-----------|-------------|-------------------|
| SL1 (high) | SL1 (high) | validate.py mega-orchestrator (537 LOC, 6+ responsibilities) | YES |
| SL2 (high) | SL2 (medium) | Layer violation: validation/ imports from generation/ | NO |
| SL6 (medium) | SL5 (low) | canonical/lint.py and integrity.py coupling | NO |
| SL7 (medium) | SL4 (medium) | schema_differ.py oversized (1331 LOC), should split | YES |

#### A-only
- **SL3 (medium)**: _collect_ids_and_refs duplicated between hallucination_lint.py:138 and spec_quality_lint.py:215. Verified via grep: both files define identical functions. VERDICT: **GENUINE**.
- **SL4 (low)**: _iter_json duplicated between same two linters. Verified: 5-line identical functions. VERDICT: **GENUINE** (trivial).
- **SL5 (low)**: _is_reference_context / _in_ref_context duplicated. Verified: different implementations, same semantics. VERDICT: **GENUINE**.
- **SL8 (info)**: governance.py is undersized (37 LOC). Observation only. VERDICT: **FALSE_POSITIVE** -- not a problem.
- **SL9 (low)**: KNOWN_STAGES duplicated in hallucination_lint and step_07. B captures this partially under SL3. VERDICT: **GENUINE** (partially captured by B).

#### B-only
- **SL6 (low)**: governance.py file handle leak (`json.load(open(...))`). Verified at line 11: confirmed unclosed file handle. VERDICT: **GENUINE** -- real resource leak.
- **SL8 (medium)**: validate.py has _load_* helpers duplicating validator patterns. Same as A's DV9 but surfaced in SoC context. VERDICT: **GENUINE** (cross-dimension match).
- **SL9 (info)**: core/trace_types.py imports from canonical/ (core -> canonical reverse dependency). Verified at trace_types.py:10. VERDICT: **GENUINE** -- architecturally notable, mitigated by try/except.
- **SL7 (info)**: _extraction_intent_parser.py is correctly private. Verification finding. VERDICT: PASS (not a problem).

#### Contradictions
- Layer violation severity: recommend **HIGH** (A) -- this is a genuine layer inversion.
- Canonical boundary severity: recommend **LOW** (B) -- the coupling is justified.

---

### P1-C: Hardcoding, Assumptions & Magic Values

A: 14 findings (H1-H14). B: 11 findings (H1-H11).

#### Corroborated
| A Finding | B Finding | Description | Severity Agreement |
|-----------|-----------|-------------|-------------------|
| H1 (high) | H2 (medium) | Schema URIs hardcoded in step_01/step_02 | NO |
| H2 (medium) | H3 (low) | Schema URIs in canonical/lint.py | NO |
| H3 (medium) | H1 (high) | Step file prefixes hardcoded in all loaders | NO (inverted) |
| H4 (medium) | H6 (medium) | KNOWN_STAGES hardcoded | YES |
| H5 (low) | H9 (low) | DEFAULT_COMMAND_PREFIXES hardcoded | YES |
| H7 (high) | H7 (high) | Version strings inconsistent | YES |
| H10 (medium) | H5 (medium) | VALID_CHECKLIST_TYPES/LAYERS in step_16 | YES |
| H11 (medium) | H10 (low) | Filesystem path assumptions | NO |

#### A-only
- **H6 (medium)**: allowed_pr_rules hardcoded in hallucination_lint (14 values). VERDICT: **GENUINE** -- B missed this.
- **H8 (low)**: ASSUMPTION_THRESHOLD magic number in spec_quality_lint. VERDICT: **GENUINE** (trivial).
- **H9 (low)**: Content derivation threshold default=5. VERDICT: **GENUINE** (trivial).
- **H12 (high)**: E142 not in errors.py. B captures in P1-F as G3. VERDICT: **GENUINE** (cross-dimension).
- **H13 (high)**: E141 not in errors.py. B captures in P1-F as G3. VERDICT: **GENUINE** (cross-dimension).
- **H14 (high)**: E320 not in errors.py. B misses entirely. VERDICT: **GENUINE** -- critical miss by B.

#### B-only
- **H4 (medium)**: STEP_NAMES hardcoded in cli.py. A captures in P1-A as S9. VERDICT: **GENUINE** (cross-dimension).
- **H8 (low)**: Hardcoded spec field names acceptable. VERDICT: **FALSE_POSITIVE** -- B correctly marks as acceptable.
- **H11 (low)**: Vague quantifier regex subjective word list. VERDICT: **GENUINE** -- valid observation.

#### Contradictions
- Schema URIs in canonical/lint.py: A=MEDIUM, B=LOW. Recommend **LOW** (B) -- these ARE the source of truth.
- Filesystem path assumptions: A=MEDIUM, B=LOW. Recommend **LOW** -- structural constants.

---

### P1-D: Test Quality, Fixtures & Coverage

A: 9 findings (T1-T9). B: 9 findings (T1-T9).

#### Corroborated
| A Finding | B Finding | Description | Severity Agreement |
|-----------|-----------|-------------|-------------------|
| T1 (high) | T1 (high) | test_step_11.py reads live spec/ files (6 nonexistent) | YES |
| T2 (medium) | T2 (medium) | Conftest fixtures duplicated | YES |
| T3 (low) | T3 (low) | migration_prompts_root fixture unused | YES |
| T4 (medium) | T4 (medium) | test_r9_* overlap with pre-existing tests | YES |
| T5 (medium) | T6 (low) | No dedicated test for governance.py | NO |
| T7 (medium) | T5 (medium) | generation/ package test coverage sparse | YES |

#### A-only
- **T6 (medium)**: invariants.py test coverage needs review. B contradicts: T7 confirms 35 test functions, well-covered. VERDICT: **FALSE_POSITIVE** -- A's concern resolved by B's verification.
- **T8 (low)**: canon_schema_alignment test adequacy. VERDICT: **NEEDS_VERIFICATION**.
- **T9 (low)**: Inline JSON blobs vs fixture files (token waste). VERDICT: **GENUINE** (stylistic).

#### B-only
- **T8 (medium)**: tools/core/json_utils.py (499 LOC per wc -l) has no tests. Verified: file exists outside specdev_tools package. VERDICT: **GENUINE** -- A missed this.
- **T9 (low)**: Integration test count low relative to source complexity. VERDICT: **GENUINE**.

#### Contradictions
- invariants.py coverage: A says "review needed", B says "well-covered with 35 tests". RESOLUTION: B is correct.

---

### P1-E: Error Collection & Reporting Pipeline

A: 8 findings (E1-E8). B: 8 findings (E1-E8).

#### Corroborated
| A Finding | B Finding | Description | Severity Agreement |
|-----------|-----------|-------------|-------------------|
| E1 (high) | E1 (high) | Flat string errors, not structured SpecError | YES |
| E2 (high) | E2 (medium) | Inconsistent error format across sources | NO |
| E4 (info) | E3 (info) | validate_file continues after schema errors | YES |
| E5 (medium) | E4 (medium) | Only 2/25 commands support --json | YES |
| E6 (low) | E6 (low) | _is_warning_message regex matching | YES |

#### A-only
- **E3 (medium)**: W->E promotion only works in validate_dir, not validate_file. VERDICT: **GENUINE** -- real behavioral gap.
- **E7 (medium)**: Deep validator errors lack JSON field path for LLM self-correction. VERDICT: **GENUINE**.
- **E8 (high)**: Unregistered error codes (E141, E142, E320). B captures E141/E142 in P1-F G3 but misses E320. VERDICT: **GENUINE** (cross-dimension, E320 unique).

#### B-only
- **E5 (medium)**: W->E promotion uses string prefix replacement. Complements A's E3 (scope gap). VERDICT: **GENUINE** -- fragile mechanism.
- **E7 (low)**: Error deduplication loses ordering context. VERDICT: **GENUINE** (minor).
- **E8 (low)**: No global exception handler in cli.py. VERDICT: **GENUINE** -- raw tracebacks on unexpected errors.

#### Contradictions
- Error format inconsistency: A=HIGH, B=MEDIUM. Recommend **HIGH** -- affects all consumers.

---

### P1-F: Gaps, Misses, Bugs & Regressions

A: 7 findings (G1-G7). B: 8 findings (G1-G8).

#### Corroborated
| A Finding | B Finding | Description | Severity Agreement |
|-----------|-----------|-------------|-------------------|
| G1 (critical) | G3 (medium) | Unregistered error codes (A: E141+E142+E320; B: E141+E142 only) | **NO** |
| G2 (high) | G1 (high) | step_01/02 duplicate schema validation | YES |
| G3 (medium) | G2 (medium) | step_16a/b/c run full step_16 validator | YES |
| G4 (low) | G4 (low) | Step 00 no deep validator (acceptable) | YES |
| G7 (low) | G6 (low) | Module-load-time warnings.warn | YES |

#### A-only
- **G5 (medium)**: hallucination_lint `_load_nfr_ids` uses `n["id"]` instead of `n["nfr_id"]`. Verified at hallucination_lint.py:277: uses `n["id"]` while schema field is `nfr_id`. VERDICT: **GENUINE BUG** -- B completely missed this. Can cause false E530 errors.
- **G6 (low)**: Empty spec dir edge case. VERDICT: **GENUINE** (minor UX).

#### B-only
- **G5 (info)**: Code health confirmed clean (zero TODOs). Positive confirmation, not a finding.
- **G7 (info)**: step_08 DAG consistency confirmed. Positive confirmation.
- **G8 (info)**: step_14 DAG consistency confirmed. Positive confirmation.

#### Contradictions
- Unregistered error codes severity: A=CRITICAL, B=MEDIUM. Recommend **CRITICAL** (A). B also missed E320 entirely. These codes bypass the centralized error system.

**Critical miss by B**: B's G3 only identifies E141 and E142, omitting E320 in step_13.py (lines 32, 40, 50). Verified: E320 is absent from errors.py.

---

### P2: Research Alignment

A: 10 alignment items. B: 9 alignment items.

#### Corroborated
| A Finding | B Finding | Description | Gap Agreement |
|-----------|-----------|-------------|--------------|
| ALIGNMENT-1 | ALIGNMENT-1 | $ref/$defs DRY authoring | YES (MEDIUM) |
| ALIGNMENT-2 | ALIGNMENT-2 | $id URL vs URN | NO (A=LARGE, B=MEDIUM) |
| ALIGNMENT-3 | ALIGNMENT-3 | Structured error objects | YES (LARGE) |
| ALIGNMENT-5 | ALIGNMENT-4 | Nesting depth (step_16=19 levels) | MINOR (FUNDAMENTAL vs LARGE) |
| ALIGNMENT-6 | ALIGNMENT-5 | Property descriptions (~5% coverage) | YES (LARGE, quick win) |
| ALIGNMENT-8 | ALIGNMENT-8 | WriteValidatedJSON MCP tool | YES (LARGE) |
| ALIGNMENT-9 | ALIGNMENT-9 | Pre-commit hook coverage | YES (SMALL, quick win) |
| ALIGNMENT-10 | ALIGNMENT-6 | Build pipeline (src/dist) | MINOR (LARGE vs FUNDAMENTAL) |
| ALIGNMENT-7 | (in ALIGN-3) | --json output coverage | A standalone, B folds in |

#### A-only
- **ALIGNMENT-4**: additionalProperties:false -- NONE gap (already achieved). B confirms implicitly but does not list as separate item. VERDICT: **GENUINE** positive finding.

#### B-only
- **ALIGNMENT-7**: Enum usage vs free-form strings -- canon/kinds/ should constrain schema enums. VERDICT: **GENUINE** -- valid alignment gap not separately surfaced by A.

#### Contradictions
- $id migration: A=LARGE (month), B=MEDIUM (1-2 weeks). Recommend **LARGE** -- touches all schemas, registry, and existing spec files.

---

## New Findings from Cross-Reference

These issues were identified during cross-referencing that merit special attention:

1. **E320 missed by B entirely**: Container B's P1-F (G3) mentions only E141 and E142. E320 in step_13.py (3 occurrences) was never flagged by B in any dimension. Verified unregistered in errors.py.

2. **hallucination_lint NFR key bug missed by B**: The `n["id"]` vs `nfr_id` discrepancy at hallucination_lint.py:277 is a genuine semantic bug that B did not detect in any dimension. If NFR artifacts use the schema-correct `nfr_id` field, hallucination lint will silently fail to load NFR IDs.

3. **governance.py file handle leak missed by A**: The `json.load(open(...))` pattern at governance.py:11 is a resource leak that A did not flag in any dimension. Verified in live codebase.

4. **tools/core/json_utils.py untested -- missed by A**: A 499-LOC module outside the specdev_tools package has zero test coverage. Only B flagged this.

5. **_collect_ids_and_refs duplication missed by B**: The identical function definitions in hallucination_lint.py:138 and spec_quality_lint.py:215 were only flagged by A (SL3). Verified via grep.

---

## Recommendations for P3 Consolidation

### Definitely Include -- Highest Confidence (corroborated by both)

1. Register E141, E142, E320 in errors.py -- CRITICAL, 5-min fix
2. Remove duplicate schema validation from step_01/step_02 -- HIGH, 30-min fix
3. Update version strings to 0.4.0 -- HIGH, trivial fix
4. Extract shared _load_ids helper -- HIGH, ~300 LOC reduction
5. Split validate.py orchestrator -- HIGH, architectural improvement
6. Resolve validate.py -> generation/ layer violation -- HIGH
7. Migrate to structured errors (SpecError) -- HIGH, phased
8. Refactor test_step_11.py to use test fixtures -- HIGH
9. Merge test_r9_* into pre-existing test files -- MEDIUM, 4740 LOC consolidation
10. Add --json to all validation commands -- MEDIUM
11. Add property descriptions to schemas -- MEDIUM, quick win
12. Add pre-commit hooks (validate-all, canonical-lint) -- SMALL, quick win

### Definitely Include -- Single-Run Verified Genuine

13. Fix hallucination_lint `n["id"]` -> `n["nfr_id"]` -- HIGH BUG, 5-min fix (A-only)
14. Fix governance.py file handle leak -- LOW, trivial fix (B-only)
15. Move W->E promotion to also apply in validate_file -- MEDIUM (A-only)
16. Extract _collect_ids_and_refs to shared utility -- MEDIUM (A-only)
17. Add deep validator JSON field paths in error messages -- MEDIUM (A-only)
18. Add tests for tools/core/json_utils.py -- MEDIUM (B-only)
19. Add enum constraints from canon/kinds to schemas -- MEDIUM (B-only)
20. Fix allowed_pr_rules hardcoding in hallucination_lint -- MEDIUM (A-only)

### Drop (false positives or resolved)

- A:S10 Pre-commit using `python -m` -- acceptable pattern
- A:T6 invariants.py coverage concern -- B confirmed 35 tests, well-covered
- A:SL8 governance.py undersized -- observation, not a problem
- B:H8 hardcoded spec field names -- acceptable by design
- B:G5/G7/G8 positive confirmations -- not findings

### Needs Further Investigation

- A:T8 canon_schema_alignment test adequacy -- neither agent verified depth
- tools/core/json_utils.py ownership -- is this part of the toolkit or external?
- step_16a/b/c triple execution -- needs performance data to decide caching vs restructuring

### Severity Adjustments for P3

| Finding | A Severity | B Severity | P3 Recommendation |
|---------|-----------|-----------|-------------------|
| Unregistered error codes | CRITICAL | MEDIUM | **CRITICAL** |
| Layer violation (validation -> generation) | HIGH | MEDIUM | **HIGH** |
| Inconsistent error format | HIGH | MEDIUM | **HIGH** |
| Schema $id migration gap | LARGE | MEDIUM | **LARGE** |
| Canonical lint.py URI constants | MEDIUM | LOW | **LOW** |
| Filesystem path assumptions | MEDIUM | LOW | **LOW** |
| STEP_NAMES hardcoded | LOW | MEDIUM | **MEDIUM** |
