# R3: Canonical System — Alias Lifecycle + Cross-Artifact Drift Detection

**Review Date**: 2026-02-27
**Reviewer**: Claude (AI-assisted audit)
**Areas**: 5 (Alias Lifecycle), 3 (Cross-Artifact Drift Detection)
**Status**: Implementation complete

---

## Context

R3 addresses two gaps found in the canonical module:
- **Area 5**: `aliases.json` has no lifecycle fields (no `deprecated_since`, `sunset_date`, `replaced_by`). `alias_is_deprecated()` returns only `bool`. W110/W120 never escalate. `autofix.py` silently resolves deprecated aliases with no warning.
- **Area 3**: `_collect_observed_semantics()` groups by term only (`set[str]`), so E210 fires but cannot pinpoint which artifact has a stale canonical ID. E211 (partial drift) does not exist. Thin validators (step_04/06/07/08/12/13a) lack semantic checks.

**Goal**: Add alias lifecycle enforcement (Area 5), partial drift detection with artifact-level precision (Area 3), and strengthen thin validators.

---

## Part A: Findings

| ID | Sev | File:Line | Finding | Impact |
|----|-----|-----------|---------|--------|
| A-R3-01 | HIGH | canon/aliases.json:full | No lifecycle fields (deprecated_since, sunset_date, replaced_by) on any alias entry; only `status` field exists | Deprecated aliases have no sunset enforcement or replacement guidance |
| A-R3-02 | HIGH | canonical/registry.py:107-108 | `alias_is_deprecated()` returns `bool` only; no metadata (sunset_date, replaced_by) exposed | Callers cannot distinguish sunset-expired from merely deprecated |
| A-R3-03 | HIGH | canonical/registry.py:128-135 | W110/W120 never escalated to errors; no E-code for sunset-expired aliases | Deprecated/sunset aliases produce warnings only, never block CI |
| A-R3-04 | HIGH | canonical/autofix.py:129 | `_try_infer_ref()` calls `resolve_alias()` but never checks `alias_is_deprecated()`; no warning emitted | Autofix silently injects refs pointing to deprecated canonical entries |
| A-R3-05 | HIGH | canonical/integrity.py:214-236 | `_collect_observed_semantics()` returns `dict[(kind,val), set[cid]]`; no artifact path tracking | E210 cannot identify which artifact has the stale canonical ID |
| A-R3-06 | MED | canonical/integrity.py:62-66 | Semantic collision emits E210 but cannot report partial drift (N-1 updated, 1 stale) | Developers get "drift exists" but not "fix file X" |
| A-R3-07 | MED | validators/step_04.py:full | Only checks duplicate fr_id; no format convention or downstream reference check | Malformed FR IDs and orphan FRs go undetected |
| A-R3-08 | MED | validators/step_06.py:full | Checks duplicate inv_id + trace presence; no trace target format or expression validity check | Invalid trace targets and malformed expressions pass silently |
| A-R3-09 | LOW | validators/step_07.py:full | No nfr_id format check; no threshold numeric validation | Non-numeric thresholds and malformed NFR IDs undetected |
| A-R3-10 | LOW | validators/step_08.py:full | No target ID format validation; only checks targets non-empty | Invalid target references pass validation |
| A-R3-11 | LOW | validators/step_12.py:full | No DAG cycle detection in job `requires` graph | Circular job dependencies pass validation |
| A-R3-12 | LOW | validators/step_13a.py:full | No element_id format check; no consistency between completeness < 100 and missing_elements | Inconsistent assessments pass validation |

### Evidence

**A-R3-02:**
```python
# registry.py:107-108
def alias_is_deprecated(self, kind: str, value: str) -> bool:
    return self.alias_status.get((kind, _norm(value))) == "deprecated"
```

**A-R3-03:**
```python
# registry.py:128-129, 134-135
if entry.status == "deprecated":
    errs.append(f"W110 DEPRECATED_CANONICAL_USED {cid}")
# ...
elif self.alias_is_deprecated(kind, alias_used):
    errs.append(f"W120 ALIAS_DEPRECATED kind={kind} alias={alias_used}")
```

**A-R3-04:**
```python
# autofix.py:129
resolved = registry.resolve_alias(kind, value)
if not resolved:
    return
# No call to alias_is_deprecated() — proceeds to inject ref silently
```

**A-R3-05:**
```python
# integrity.py:214, 236
def _collect_observed_semantics(obj: Any, observed: dict[tuple[str, str], set[str]]) -> None:
    # ...
    observed.setdefault((kind, normalized), set()).add(cid)
    # No artifact path stored — set contains only cid strings
```

---

## Part B: Implementation Plan

### Task Table

| ID | Pri | Deps | File | Change summary | Acceptance command | Findings |
|----|-----|------|------|----------------|--------------------|----------|
| T00 | P0 | — | `docs/audit/findings/r3_findings.md` | Write the complete findings plan (Part A + Part B + verification status) from this document to the findings file as the implementation reference | `test -f docs/audit/findings/r3_findings.md` | All |
| T01 | P0 | T00 | `tools/specdev_tools/core/errors.py` | Add `"E125": "ALIAS_SUNSET_EXPIRED"` after E120, `"E211": "PARTIAL_DRIFT"` after E210 | `python -c "from specdev_tools.core.errors import ERROR_CODES; assert 'E125' in ERROR_CODES; assert 'E211' in ERROR_CODES"` | A-R3-03, A-R3-06 |
| T02 | P0 | T01 | `tests/test_error_code_coverage.py` | Add `"E125"` and `"E211"` to the `expected` set (lines 11-47) | `pytest tests/test_error_code_coverage.py -v` | A-R3-03, A-R3-06 |
| T03 | P0 | — | `canon/aliases.json` | Add 3 new deprecated alias entries with `lifecycle` blocks: (1) kind=term normalized="java web token" target=cn:core:term:jwt, sunset_date=2026-06-01 (future), (2) kind=unit normalized="millis" target=cn:core:unit:ms, no sunset, (3) kind=unit normalized="millisec" target=cn:core:unit:ms, sunset_date=2025-12-31 (past, for E125 testing). All have status="deprecated", deprecated_since, replaced_by | `python -c "import json; d=json.load(open('canon/aliases.json')); dep=[a for a in d if a.get('status')=='deprecated']; assert len(dep)==3; assert all('lifecycle' in a for a in dep)"` | A-R3-01 |
| T04 | P1 | T01, T03 | `tools/specdev_tools/canonical/registry.py` | (a) Add `alias_lifecycle: dict[tuple[str,str], dict] \| None = None` param to `__init__` (line 21-31); store as `self.alias_lifecycle = alias_lifecycle or {}`, (b) populate in `from_manifest()` (line 82-91): read `alias.get("lifecycle")` and store keyed by `(kind, _norm(normalized))`, pass to constructor, (c) add `alias_is_sunset(kind, value) -> bool` method: check `sunset_date` against `datetime.now(timezone.utc)`, use `.replace("Z", "+00:00")` for py<3.11, (d) in `validate_ref()` line 134: if deprecated AND sunset → emit `E125 ALIAS_SUNSET_EXPIRED kind={kind} alias={alias_used} replaced_by={...}`; elif deprecated AND not sunset → emit `W120 ALIAS_DEPRECATED kind={kind} alias={alias_used} replaced_by={...}` | `pytest tests/test_canonical_registry.py -v` | A-R3-02, A-R3-03 |
| T05 | P1 | T04 | `tests/test_canonical_registry.py` | Add 3 tests using `from_manifest()` inline dict pattern: (1) `test_alias_lifecycle_stored` — manifest with alias having lifecycle block → assert `reg.alias_lifecycle` contains expected dict, (2) `test_sunset_expired_emits_E125` — alias with past sunset_date → `validate_ref()` returns E125, (3) `test_deprecated_not_sunset_emits_W120_with_replaced_by` — alias with future sunset_date → returns W120 with replaced_by, no E125 | `pytest tests/test_canonical_registry.py -v` | A-R3-02, A-R3-03 |
| T06 | P1 | T04 | `tools/specdev_tools/canonical/autofix.py` | In `_try_infer_ref()` after `resolved = registry.resolve_alias(kind, value)` (line 129): add deprecation guard — if `registry.alias_is_deprecated(kind, value)` is True, get lifecycle via `registry.alias_lifecycle.get((kind, <normalized>), {})`, extract `replaced_by`, append WARN message to `file_changes`, return early (skip autofix). Normalize value inline with `" ".join(re.split(r"[\s_-]+", value.lower().strip()))` to avoid importing private `_norm` | `pytest tests/ -k autofix -v` | A-R3-04 |
| T07 | P1 | T01 | `tools/specdev_tools/canonical/integrity.py` | (a) Line 35: change `observed` type to `dict[tuple[str,str], dict[str, list[str]]]`, (b) Line 60: pass `rel` to `_collect_observed_semantics(data, observed, rel)`, (c) Line 214: add `rel: str = ""` param to function signature, update type annotation, (d) Line 236: change `observed.setdefault((kind, normalized), set()).add(cid)` to `observed.setdefault((kind, normalized), {}).setdefault(cid, []).append(rel)`, (e) Lines 238-239: pass `rel` to recursive calls, (f) Lines 62-66: emit `E211 PARTIAL_DRIFT` instead of `E210` with per-cid artifact paths: `f"E211 PARTIAL_DRIFT kind={kind} value='{value}' {detail}"` where detail = `cid@[paths] \| cid@[paths]` | `pytest tests/test_canonical_integrity.py -v` | A-R3-05, A-R3-06 |
| T08 | P1 | T07 | `tests/test_canonical_integrity.py` | (a) Add `test_partial_drift_emits_E211_with_artifact_paths` — two spec files, same term, different cids → assert E211 present with both file paths, (b) Add `test_single_cid_no_E211` — same cid across files → no E211, (c) Update any existing test asserting E210 for semantic collision to assert E211 instead (the E210 code is now only emitted for missing/extra canonical_refs, not semantic collision) | `pytest tests/test_canonical_integrity.py -v` | A-R3-05, A-R3-06 |
| T09 | P2 | — | `tools/specdev_tools/validation/validators/step_04.py` | Add `import re`; add `FR_ID_PATTERN = re.compile(r"^fr-[a-z0-9]+(?:-[a-z0-9]+)*$")`; in loop: check `fr_id` matches pattern, check title/description non-empty | `pytest tests/test_step_validators_core.py tests/integration/test_step_04.py -v` | A-R3-07 |
| T09a | P2 | T09 | `tests/test_step_validators_core.py` | Add `from specdev_tools.validation.validators import step_04` to imports; add `test_step_04_bad_fr_id_format` — pass `{"functional_requirements": [{"fr_id": "BAD_ID"}]}` → assert error contains "convention"; add `test_step_04_valid_fr_id` — pass `{"functional_requirements": [{"fr_id": "fr-login", "title": "User login"}]}` → no format errors | `pytest tests/test_step_validators_core.py -v` | A-R3-07 |
| T10 | P2 | — | `tools/specdev_tools/validation/validators/step_06.py` | Add `import re`; add `INV_ID_PATTERN` and `TRACE_TARGET_PATTERN` regexes; in loop: check inv_id format, check trace targets match `(fr\|api\|nfr\|inv)-*` pattern | `pytest tests/test_step_validators_core.py -v` | A-R3-08 |
| T10a | P2 | T10 | `tests/test_step_validators_core.py` | Add `test_step_06_bad_inv_id_format` — inv_id="BAD" → error; add `test_step_06_bad_trace_target` — trace="not-a-valid-id" → error | `pytest tests/test_step_validators_core.py -v` | A-R3-08 |
| T11 | P2 | — | `tools/specdev_tools/validation/validators/step_07.py` | Add `import re`; add `NFR_ID_PATTERN`; in loop: check nfr_id matches `nfr-*` pattern, check threshold is numeric when present | `pytest tests/test_step_validators_core.py -v` | A-R3-09 |
| T11a | P2 | T11 | `tests/test_step_validators_core.py` | Add `test_step_07_bad_nfr_id_format` — nfr_id="BAD" → error; add `test_step_07_non_numeric_threshold` — threshold="high" → error | `pytest tests/test_step_validators_core.py -v` | A-R3-09 |
| T12 | P2 | — | `tools/specdev_tools/validation/validators/step_08.py` | Add `import re`; add `FIXTURE_ID_PATTERN` and `TARGET_ID_PATTERN`; in loop: check fixture_id format, check each target matches `(fr\|api\|nfr\|inv)-*` | `pytest tests/test_step_validators_core.py -v` | A-R3-10 |
| T12a | P2 | T12 | `tests/test_step_validators_core.py` | Add `test_step_08_bad_fixture_id` — fixture_id="BAD" → error; add `test_step_08_bad_target_format` — target="not-valid" → error | `pytest tests/test_step_validators_core.py -v` | A-R3-10 |
| T13 | P2 | — | `tools/specdev_tools/validation/validators/step_12.py` | Add `_has_cycle(graph)` helper using DFS (WHITE/GRAY/BLACK coloring); after existing `requires` check: build graph from jobs, call `_has_cycle`, emit error on circular dependency | `pytest tests/test_step_validators_core.py -v` | A-R3-11 |
| T13a | P2 | T13 | `tests/test_step_validators_core.py` | Add `test_step_12_circular_dependency` — two jobs that require each other → error contains "Circular"; add `test_step_12_valid_dag` — linear dependency → no cycle error | `pytest tests/test_step_validators_core.py -v` | A-R3-11 |
| T14 | P2 | — | `tools/specdev_tools/validation/validators/step_13a.py` | Add `import re`; add `ELEMENT_ID_PATTERN`; in loop: check element_id format; after summary check: if completeness < 100 and missing_elements is empty → emit error | `pytest tests/test_step_validators_core.py -v` | A-R3-12 |
| T14a | P2 | T14 | `tests/test_step_validators_core.py` | Add `test_step_13a_bad_element_id` — element_id="BAD" → error; add `test_step_13a_incomplete_but_no_missing` — completeness=50 with empty missing_elements → error | `pytest tests/test_step_validators_core.py -v` | A-R3-12 |
| D01 | P3 | T01 | `docs/developers/error-codes.md` | Add E125 ALIAS_SUNSET_EXPIRED (trigger: alias with past sunset_date used in spec; resolution: replace with canonical term from replaced_by) and E211 PARTIAL_DRIFT (trigger: same term maps to different canonical IDs across artifacts; resolution: update stale artifacts to use current canonical ID) | — | A-R3-03, A-R3-06 |

**Note on test_step_validators_core.py**: Tasks T09a, T10a, T11a, T12a, T13a, T14a all modify this same file. They MUST execute sequentially (each appends new test methods). The sequencing is: T09a → T10a → T11a → T12a → T13a → T14a. Alternatively, these can be consolidated into a single task T15 that adds all 12 test methods at once after all validator code tasks (T09-T14) are complete.

### Batch Execution Plan (token-optimized)

```
Batch 0 (first step): T00
  └── Write this entire findings plan to docs/audit/findings/r3_findings.md
      This serves as the reference document for reviewing implementation.

Batch 1 (parallel, 8 subagents): T01, T03, T09, T10, T11, T12, T13, T14
  └── All independent, no deps. Worktree-isolated.

Batch 2 (parallel, 3 subagents): T02, T04, T07
  └── T02 deps T01; T04 deps T01+T03; T07 deps T01

Batch 3 (parallel, 3 subagents): T05, T06, T08
  └── T05 deps T04; T06 deps T04; T08 deps T07

Batch 4 (single subagent): T15 (consolidated validator tests)
  └── Deps: T09-T14. One task adds all 12 test methods to test_step_validators_core.py

Batch 5 (single subagent): D01
  └── Deps: T01. Adds error code documentation.
```

### Key Implementation Details

**T04 — registry.py changes (exact locations verified):**
- `__init__` (lines 21-31): Add `alias_lifecycle: dict[tuple[str,str], dict] | None = None` parameter; store as `self.alias_lifecycle = alias_lifecycle or {}`
- `load()` (line 38): Pass through to `from_manifest()` — no change needed (alias_lifecycle comes from manifest)
- `from_manifest()` (lines 82-91): In the `for alias in manifest.get("aliases", []):` loop, after line 90 (`register_alias()`), add: `lc = alias.get("lifecycle"); if isinstance(lc, dict): alias_lifecycle[(kind, _norm(normalized))] = lc`. Initialize local `alias_lifecycle: dict = {}` before the loop. Pass to constructor at line 92
- New method `alias_is_sunset(kind, value) -> bool` after line 108: parse `sunset_date` with `datetime.fromisoformat(sd.replace("Z", "+00:00"))`, compare to `datetime.now(timezone.utc)`
- `validate_ref()` (lines 134-135): Replace single `elif` with nested if/else for sunset vs deprecated

**T07 — integrity.py changes (exact locations verified):**
- Line 35: `observed: dict[tuple[str, str], dict[str, list[str]]] = {}`
- Line 60: `_collect_observed_semantics(data, observed, rel)`
- Line 214: `def _collect_observed_semantics(obj: Any, observed: dict[tuple[str, str], dict[str, list[str]]], rel: str = "") -> None:`
- Line 236: `observed.setdefault((kind, normalized), {}).setdefault(cid, []).append(rel)`
- Line 238: `_collect_observed_semantics(v, observed, rel)` (and same for list branch at ~line 240)
- Lines 62-66: Change E210 to E211 with detail string: `cid@[comma-separated paths]` for each cid

**T06 — autofix.py deprecation guard (~8 LOC):**
- After line 129 (`resolved = registry.resolve_alias(kind, value)`), before constructing `candidate_ref`:
- Check `registry.alias_is_deprecated(kind, value)` → if True, normalize value inline, look up `registry.alias_lifecycle`, extract `replaced_by`, append warning to `file_changes`, return early

### Verification

After all tasks complete, run:
```bash
source devspec_env/bin/activate
pytest tests/ --tb=short -q
pytest tests/test_error_code_coverage.py -v
pytest tests/test_canonical_registry.py -v
pytest tests/test_canonical_integrity.py -v
pytest tests/test_step_validators_core.py -v
./tools/run_specdev.sh canonical-lint canon --repo-root ./devspec_toolkit
./tools/run_specdev.sh canonical-integrity spec --repo-root ./devspec_toolkit
```

---

## Phase 4: Self-Verification Status

- CHECK 1 Assumptions: PASS — No speculative language in findings
- CHECK 2 References: PASS — All line numbers verified via direct file reads (registry.py:107-108, 128-135, 134; integrity.py:35, 60, 62-66, 214, 236; autofix.py:129)
- CHECK 3 Atomic: PASS — Each task modifies exactly one file
- CHECK 4 Tests: PASS — Every code task has a corresponding test task (T01→T02, T04→T05, T06→acceptance cmd, T07→T08, T09→T09a through T14→T14a)
- CHECK 5 Docs: PASS — D01 covers new error codes E125 and E211
- CHECK 6 Deps: PASS — All deps reference earlier tasks; no forward references
- CHECK 7 Orphans: PASS — All 12 findings mapped to tasks
- Total findings: 12 (0 CRIT, 5 HIGH, 2 MED, 5 LOW)
- Total tasks: 14 code + 8 test + 1 doc = 23 tasks

## Phase 5: Findings File

T00 writes the complete findings plan to `docs/audit/findings/r3_findings.md` **before any implementation begins**. This file serves as the reference for reviewing each implementation task. It contains Part A (findings table + evidence), Part B (task table with acceptance commands), and verification status.

---

## Post-Implementation Review Corrections

**Date**: 2026-02-27

### A-R3-09 / T11 + T11a — `step_07.py` field name and validation logic

**Problem**: The validator checked `nfr.get("threshold")` but the schema field is `target` (`schema/07_nfrs.schema.json`). Additionally, the validation used `float()` parsability, but the schema's `target` field accepts strings matching `^.*\d+.*$` (e.g. `"< 200ms"`), so numeric parsing is incorrect.

**Correction**:
- Changed `nfr.get("threshold")` → `nfr.get("target")`
- Replaced `float()` check with `re.search(r"\d", target)` to match the schema pattern
- Updated error message from `"non-numeric threshold"` → `"target string contains no digit"`
- Updated test `test_step_07_non_numeric_threshold` → `test_step_07_target_no_digit` with corrected field name and assertion

### A-R3-04 / T06 — `autofix.py` inline normalization empty-token filter

**Problem**: The inline normalization at line 134 (`" ".join(re.split(r"[\s_-]+", value.lower().strip()))`) did not filter empty tokens from the split result. The canonical `_norm()` function in `registry.py` includes `[part for part in ... if part]`. Edge-case values starting or ending with separators could produce mismatched lookup keys.

**Correction**: Added empty-token filter: `" ".join(p for p in re.split(...) if p)`

### Staging gap — `test_schema_contracts.py`

**Problem**: `tests/test_schema_contracts.py` contained unstaged changes (autofix deprecation guard test) that would have been excluded from the commit.

**Correction**: File staged via `git add`.
