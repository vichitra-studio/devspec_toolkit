# Phase 0: Governance Fixes — Deterministic Implementation Plan

**Version**: 2.1.0
**Created**: 2026-03-01
**Revised**: 2026-03-01
**Status**: REVISED (incorporates review findings C1–C3, H1–H2, M1–M3, F1–F6)
**Branch**: `toolkit_agent_optimisation_claude`

---

## 1. Objective

Eliminate hardcoded governance data from Python modules by making the canonical registry (`canon/`) the single source of truth for trace types, and make step_order.json the sole authority for pipeline topology. This removes drift vectors between code, canon, and schema layers.

### Goals (G1–G7)

| ID | Goal | Status |
|----|------|--------|
| G1 | Make `trace_types.py` load from canon | PLANNED |
| G2 | Make `matrix.py` use dynamic entity indexing | PLANNED |
| G3 | New canon-schema enum↔kind alignment linter | PLANNED |
| G4 | Refactor `step_order.json` (remove `step_metadata`) | PLANNED |
| G5 | Prompt sanitization (remove "Context To Ingest") | VERIFIED NO-OP |
| G6 | Documentation updates | PLANNED |
| G7 | Three-tiered enforcement consistency | COVERED BY G1+G3 |

**G5 Verification**: Grep of all 22 prompt files in `prompts/` found zero matches for "Context To Ingest" (case-insensitive). No action required.

**G7 Clarification**: G1 makes hallucination lint fully dynamic (closing the mixed-tier gap). G3 catches canon-schema drift (keeping the schema tier aligned). No separate work item.

---

## 2. Scope Boundaries

### IN SCOPE (Phase 0)
- Canon data: `trace_type.json` alias fix for `inv`→`invariant` + add `threat` trace type
- Core module: `trace_types.py` canon-backed rewrite
- Matrix: `matrix.py` entity indexing — replace hardcoded schema-name matching (Section A only)
- Alignment: New `canon_schema_alignment.py` linter (enum↔canon kind drift detection)
- Step order: `step_order.json` field restructure
- Dependency lint: Remove `step_metadata` functions
- CLI: prompt-context rewrite (remove `step_artifacts` map) + alignment command
- Tests: All affected test files
- Docs: New/updated documentation

### OUT OF SCOPE (Deferred)
> Items below are tracked in `docs/plans/optimisation_backlog.md` with full context.

- **M1 — Extension handling bug** (`matrix.py:333`): `any()` checks all artifact keys, not the current artifact. Bug causes extension indexing to trigger for ALL artifacts if any artifact key starts with `ext_`. Severity: LOW (only affects projects using extensions).
- **H2 — `validate_trace_integrity()` hardcoded strings** (`matrix.py:113,121,207,217,240`): Five hardcoded `"NN_name" in schema` checks inside the generic validation function. These should be refactored to dynamic discovery but are lower priority since the function still works correctly.
- **Category B hardcoded strings** in validators (`step_02.py`, `step_11.py`, `fixtures_lint.py`, `traceability_closure.py`): These are business rules (which trace types are valid in THIS context), not vocabulary checks. Example: `allowed_target_types = {"api", "component"}` in `step_11.py` restricts which types are valid for threat targets — this is semantic, not vocabulary.
- **json_utils.py location**: Deferred to Phase A.
- **Context package build**: Blocked on Phase 0 completion.
- **Skills and Hooks**: Phase B.

---

## 3. File Change Matrix

Every file touched exactly once. No file appears in more than one task.

| File Path | Task | Change Type | Goal |
|-----------|------|-------------|------|
| `canon/kinds/trace_type.json` | T0 | EDIT | G1 prereq |
| `canon/manifest.json` | T0 | EDIT | G1 prereq |
| `tools/step_order.json` | T2 | REWRITE | G4 |
| `tools/specdev_tools/core/trace_types.py` | T1 | REWRITE | G1 |
| `tools/specdev_tools/validation/dependency_order_lint.py` | T3 | EDIT | G4 |
| `tools/specdev_tools/validation/matrix.py` | T4 | EDIT | G2 |
| `tools/specdev_tools/validation/canon_schema_alignment.py` | T5 | NEW | G3 |
| `tools/specdev_tools/cli.py` | T6 | EDIT | G3+G4 |
| `tests/test_trace_types.py` | T7 | REWRITE | G1 |
| `tests/test_dependency_order_lint.py` | T8 | EDIT | G4 |
| `tests/test_cli.py` | T9 | EDIT | G3+G4 |
| `tests/test_canon_schema_alignment.py` | T10 | NEW | G3 |
| `docs/plans/phase_0_governance_plan.md` | — | THIS FILE | — |
| `docs/developers/reference.md` | T11 | EDIT | G6 |

**Files verified as NOT needing changes**:
- `tools/specdev_tools/core/__init__.py` — exports `normalize_trace_type`, `is_valid_trace_type` which stay unchanged
- `tools/specdev_tools/validation/forward_replay_check.py` — only uses `steps` array, not `step_metadata`
- `tools/specdev_tools/migration/planner.py` — only uses `steps` array
- `tools/specdev_tools/validation/validate.py` — uses `policy` field only
- `tools/specdev_tools/generation/schema_differ.py` — calls `validate_trace_integrity()` whose public API is unchanged
- All 6 trace_types.py consumers (Category A) — public API preserved, zero impact

---

## 4. Execution Batches

```
Batch A ─┬─ T0 (canon data fix)
         └─ T2 (step_order.json)          ← parallel, independent

Batch B ─┬─ T1 (trace_types.py)           ← depends on T0
         ├─ T3 (dependency_order_lint.py)  ← depends on T2, parallel with T1
         └─ T5 (canon_schema_alignment)   ← depends on T0 (not T1), parallel with T1

Batch C ─┬─ T4 (matrix.py)               ← depends on T1
         ├─ T6 (cli.py)                   ← depends on T2, T5
         ├─ T7 (test_trace_types.py)      ← depends on T1
         └─ T8 (test_dep_order_lint.py)   ← depends on T3, parallel with above

Batch D ─┬─ T9 (test_cli.py)             ← depends on T6
         └─ T10 (test_alignment.py)       ← depends on T5, parallel with T9

Batch E ──── VERIFICATION (pytest)        ← depends on all

Batch F ──── T11 (documentation)          ← depends on all
```

> **v2.1 changes**: T5 moved to Batch B (depends on T0 only, not T1 — uses CanonicalRegistry directly, not trace_types.py). T6 moved to Batch C (does not depend on T3 — they modify independent files). This shortens the critical path by one batch.

---

## 5. Task Definitions

---

### T0: Canon Data Fix — inv Alias + threat Trace Type

**Goal**: G1 prerequisite
**Files**: `canon/kinds/trace_type.json`, `canon/manifest.json`
**Depends on**: None
**Batch**: A (parallel with T2)
**Review finding**: C2 — `threat` is used in `matrix.py` (line 326) and `step_11.py` but was missing from canon trace types. Adding it prevents silent regression when T1 makes trace types canon-backed.

#### Current State

`canon/kinds/trace_type.json` has 9 separate entries including both:
- `cn:core:trace_type:inv` (preferred_label: "inv", aliases: [])
- `cn:core:trace_type:invariant` (preferred_label: "invariant", aliases: [])

`canon/manifest.json` mirrors the same 9 entries.

The code `trace_types.py` treats "inv" as an alias for "invariant" via `CANONICAL_TRACE_TYPE = {"inv": "invariant"}`. The canon data does not express this relationship.

There is no `cn:core:trace_type:threat` entry, yet `matrix.py` indexes threats via `"11_redteam" in schema` and `step_11.py` validates `target_ids` using `threat_id`.

#### Required Changes

**canon/kinds/trace_type.json**:
1. Remove the entire entry object where `"id": "cn:core:trace_type:inv"`
2. In the entry where `"id": "cn:core:trace_type:invariant"`, change `"aliases": []` to `"aliases": ["inv"]`
3. Add a new entry for `threat`:
   ```json
   {
     "id": "cn:core:trace_type:threat",
     "kind": "trace_type",
     "preferred_label": "threat",
     "definition": "A red-team threat entity from Step 11 (11_redteam.json).",
     "version": "1.0.0",
     "status": "active",
     "owners": ["spec-platform"],
     "aliases": [],
     "tags": ["tracing"],
     "lifecycle": { "introduced_at": "2026-03-01T00:00:00Z" }
   }
   ```
4. Result: 9 entries total (was 9 — removed inv, added threat)

**canon/manifest.json**:
1. Remove the entry object where `"id": "cn:core:trace_type:inv"` from the `"entries"` array
2. In the entry where `"id": "cn:core:trace_type:invariant"`, change `"aliases": []` to `"aliases": ["inv"]`
3. Add the same `threat` entry to the `"entries"` array

#### Verification

```bash
./tools/run_specdev.sh canonical-lint canon --repo-root .
```
Must pass with zero errors. The linter validates that all canon entries have valid structure.

#### Subagent Protocol

```
subagent_type: general-purpose
isolation: none (changes are safe in-place)
prompt: |
  Read these two files:
  1. canon/kinds/trace_type.json
  2. canon/manifest.json

  In BOTH files:
  - Remove the entire entry object where "id" is "cn:core:trace_type:inv"
  - In the entry where "id" is "cn:core:trace_type:invariant", change "aliases": [] to "aliases": ["inv"]
  - Add a new entry for "threat" trace type:
    id: "cn:core:trace_type:threat", kind: "trace_type", preferred_label: "threat",
    definition: "A red-team threat entity from Step 11 (11_redteam.json).",
    version: "1.0.0", status: "active", owners: ["spec-platform"],
    aliases: [], tags: ["tracing"], lifecycle: { introduced_at: "2026-03-01T00:00:00Z" }

  After editing, run: ./tools/run_specdev.sh canonical-lint canon --repo-root .
  Report the result.
```

#### Acceptance Criteria

- [ ] `canon/kinds/trace_type.json` has exactly 9 entries (inv removed, threat added)
- [ ] `cn:core:trace_type:inv` entry does not exist in either file
- [ ] `cn:core:trace_type:invariant` entry has `"aliases": ["inv"]` in both files
- [ ] `cn:core:trace_type:threat` entry exists in both files
- [ ] `canonical-lint` passes

---

### T1: Rewrite trace_types.py — Canon-Backed Loading

**Goal**: G1
**File**: `tools/specdev_tools/core/trace_types.py`
**Depends on**: T0
**Batch**: B (parallel with T3)

#### Current State (36 lines)

```python
# tools/specdev_tools/core/trace_types.py (current)
from __future__ import annotations
from typing import Iterable

TRACE_TYPES = (
    "fr", "api", "nfr", "inv", "invariant", "fixture",
    "doc", "capability", "component",
)

CANONICAL_TRACE_TYPE = {"inv": "invariant"}

def normalize_trace_type(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return normalized
    return CANONICAL_TRACE_TYPE.get(normalized, normalized)

def is_valid_trace_type(value: str) -> bool:
    return normalize_trace_type(value) in TRACE_TYPES

def normalize_trace_types(values: Iterable[str]) -> list[str]:
    return [normalize_trace_type(v) for v in values]
```

#### Required Changes

Replace the entire file with canon-backed loading. The new implementation must:

1. **Import `CanonicalRegistry`** from `..canonical.registry`
2. **Compute `_TOOLKIT_ROOT`** as `str(Path(__file__).resolve().parents[3])` — this resolves to the toolkit root from `tools/specdev_tools/core/trace_types.py` (3 parent directories up)
3. **Define `_load_from_canon()`** that:
   - Loads `CanonicalRegistry.load(_TOOLKIT_ROOT)`
   - Iterates `registry.entries.values()` filtering `entry.kind == "trace_type"`
   - Collects `preferred_label` values into a set (these become `TRACE_TYPES`)
   - Collects `aliases` from each entry: for each alias string, maps `alias → preferred_label` (these become `CANONICAL_TRACE_TYPE`)
   - Returns `(tuple(sorted(types)), aliases_dict)`
   - On any exception, returns fallback values
4. **Define fallback constants**:
   - `_FALLBACK_TYPES = ("api", "capability", "component", "doc", "fixture", "fr", "invariant", "nfr", "threat")` — sorted, "inv" NOT included (it's an alias now), "threat" included (added in T0)
   - `_FALLBACK_ALIASES = {"inv": "invariant"}`
5. **Initialize at module level**: `TRACE_TYPES, CANONICAL_TRACE_TYPE = _load_from_canon()`
6. **Preserve all public functions unchanged**: `normalize_trace_type()`, `is_valid_trace_type()`, `normalize_trace_types()`

#### Circular Import Safety

- `trace_types.py` is in `core/` package
- `CanonicalRegistry` is in `canonical/registry.py`
- `canonical/registry.py` imports only stdlib modules (json, os, re, dataclasses, datetime, pathlib, typing) — no imports from `core/`
- `core/__init__.py` imports from `trace_types` — this triggers `_load_from_canon()` which imports `CanonicalRegistry`
- No circular dependency exists

#### Path Resolution Verification

From `tools/specdev_tools/core/trace_types.py`:
- `parents[0]` = `tools/specdev_tools/core/`
- `parents[1]` = `tools/specdev_tools/`
- `parents[2]` = `tools/`
- `parents[3]` = toolkit root (contains `canon/`)

This holds for both direct repository use and worktree deployments.

#### Expected New File Content

```python
from __future__ import annotations

from pathlib import Path
from typing import Iterable


def _load_from_canon() -> tuple[tuple[str, ...], dict[str, str]]:
    """Load trace types from canon/kinds/trace_type.json via CanonicalRegistry."""
    try:
        from ..canonical.registry import CanonicalRegistry

        toolkit_root = str(Path(__file__).resolve().parents[3])
        registry = CanonicalRegistry.load(toolkit_root)
        types: set[str] = set()
        aliases: dict[str, str] = {}
        for entry in registry.entries.values():
            if entry.kind != "trace_type":
                continue
            label = entry.payload.get("preferred_label", "")
            if label:
                types.add(label)
            for alias in entry.payload.get("aliases", []) or []:
                if isinstance(alias, str) and alias != label:
                    aliases[alias] = label
        if types:
            return tuple(sorted(types)), aliases
    except Exception:
        pass
    return _FALLBACK_TYPES, _FALLBACK_ALIASES


_FALLBACK_TYPES: tuple[str, ...] = (
    "api", "capability", "component", "doc", "fixture",
    "fr", "invariant", "nfr", "threat",
)
_FALLBACK_ALIASES: dict[str, str] = {"inv": "invariant"}

TRACE_TYPES, CANONICAL_TRACE_TYPE = _load_from_canon()


def normalize_trace_type(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return normalized
    return CANONICAL_TRACE_TYPE.get(normalized, normalized)


def is_valid_trace_type(value: str) -> bool:
    return normalize_trace_type(value) in TRACE_TYPES


def normalize_trace_types(values: Iterable[str]) -> list[str]:
    return [normalize_trace_type(v) for v in values]
```

#### Verification

```python
# Quick smoke test (run from toolkit root with venv active)
python -c "from specdev_tools.core.trace_types import TRACE_TYPES, CANONICAL_TRACE_TYPE, normalize_trace_type, is_valid_trace_type; print('TYPES:', TRACE_TYPES); print('ALIASES:', CANONICAL_TRACE_TYPE); assert 'inv' not in TRACE_TYPES; assert 'invariant' in TRACE_TYPES; assert 'threat' in TRACE_TYPES; assert CANONICAL_TRACE_TYPE.get('inv') == 'invariant'; assert is_valid_trace_type('inv'); assert is_valid_trace_type('fr'); assert is_valid_trace_type('threat'); assert not is_valid_trace_type('bogus'); print('OK')"
```

#### Subagent Protocol

```
subagent_type: general-purpose
isolation: none
prompt: |
  TASK: Rewrite tools/specdev_tools/core/trace_types.py to load trace types from the canonical registry.

  Read these files first:
  1. tools/specdev_tools/core/trace_types.py (current implementation)
  2. tools/specdev_tools/canonical/registry.py (CanonicalRegistry class)
  3. canon/kinds/trace_type.json (the canon data — should already have inv alias on invariant entry from T0)

  Write the new file content exactly as specified in the plan section "Expected New File Content" for T1.
  The public API (TRACE_TYPES, CANONICAL_TRACE_TYPE, normalize_trace_type, is_valid_trace_type, normalize_trace_types)
  must be preserved exactly.

  After writing, run the smoke test command from the plan to verify.
```

#### Acceptance Criteria

- [ ] `TRACE_TYPES` loaded from canon at import time (not hardcoded)
- [ ] `CANONICAL_TRACE_TYPE` derived from canon entry aliases (not hardcoded)
- [ ] Fallback to `_FALLBACK_TYPES` / `_FALLBACK_ALIASES` on any canon load failure
- [ ] `normalize_trace_type("inv")` returns `"invariant"`
- [ ] `is_valid_trace_type("inv")` returns `True`
- [ ] `is_valid_trace_type("bogus")` returns `False`
- [ ] `"inv"` is NOT in `TRACE_TYPES` (it's an alias, not a primary type)
- [ ] No circular imports
- [ ] All 6 consumer files work without modification

---

### T2: Refactor step_order.json — Replace step_metadata with downstream_consumers

**Goal**: G4
**File**: `tools/step_order.json`
**Depends on**: None
**Batch**: A (parallel with T0)

#### Current State (509 lines)

Contains: `version`, `policy`, `steps`, `allowed_upstream_dependencies`, `step_metadata`.

`step_metadata` maps each step to `required_spec_inputs`, `required_seed_inputs`, `extraction_intent`. This data is consumed by `cli.py` (prompt-context command) and `dependency_order_lint.py`.

#### Required Changes

1. **Remove** the entire `"step_metadata"` key and its value
2. **Add** a new `"downstream_consumers"` key containing a computed inversion of the `required_spec_inputs` data

The `downstream_consumers` maps each step ID to the list of step IDs that consume its output artifact. Computed from the existing `step_metadata.required_spec_inputs` using this mapping:

| Artifact | Step ID |
|----------|---------|
| `00_charter.json` | `00` |
| `01_capabilities.json` | `01` |
| `02_system_sketch.json` | `02` |
| `02a_delivery_baseline.json` | `02a` |
| `03_glossary.json` | `03` |
| `04_functional_requirements.json` | `04` |
| `05_interface_contracts.json` | `05` |
| `06_invariants.json` | `06` |
| `07_nfrs.json` | `07` |
| `08_fixtures.json` | `08` |
| `09_impl_plan.json` | `09` |
| `10_governance.json` | `10` |
| `11_redteam.json` | `11` |
| `12_ci_gates.json` | `12` |
| `13_extension_generator.json` | `13` |
| `13a_completeness_assessment.json` | `13a` |
| `14_roadmap.json` | `14` |
| `15_scaffold.json` | `15` |
| `16_impl_context.json` | `16` |
| `16a_impl_planner.json` | `16a` |
| `16b_impl_coder.json` | `16b` |
| `16c_impl_reviewer.json` | `16c` |

#### Pre-computed downstream_consumers

```json
"downstream_consumers": {
  "00": ["01", "03", "04", "07", "09", "10", "13a", "14"],
  "01": ["02", "03", "04", "09", "13", "13a"],
  "02": ["02a", "05", "09", "11", "13", "15"],
  "02a": ["12"],
  "03": ["04", "05", "07"],
  "04": ["05", "06", "07", "08", "09", "11", "13", "13a", "14", "15", "16", "16a", "16c"],
  "05": ["06", "08", "09", "11", "13", "13a", "15", "16", "16a"],
  "06": ["08", "11", "16a"],
  "07": ["08", "09", "11", "13"],
  "08": [],
  "09": ["10", "14", "16"],
  "10": ["12"],
  "11": [],
  "12": [],
  "13": ["13a", "14"],
  "13a": ["14"],
  "14": ["16", "16a", "16b", "16c"],
  "15": [],
  "16": ["16a", "16b", "16c"],
  "16a": [],
  "16b": [],
  "16c": []
}
```

#### Final File Structure

```json
{
  "version": "1.0.0",
  "policy": { ... },           // unchanged
  "steps": [ ... ],            // unchanged (22 entries)
  "allowed_upstream_dependencies": { ... },  // unchanged
  "downstream_consumers": { ... }           // NEW (replaces step_metadata)
}
```

#### Verification

```bash
# Verify JSON is valid
python3 -c "import json; d=json.load(open('tools/step_order.json')); assert 'step_metadata' not in d; assert 'downstream_consumers' in d; assert len(d['downstream_consumers']) == 22; print('OK')"
```

#### Subagent Protocol

```
subagent_type: general-purpose
isolation: none
prompt: |
  TASK: Rewrite tools/step_order.json to replace step_metadata with downstream_consumers.

  Read tools/step_order.json first.

  Changes:
  1. Keep "version", "policy", "steps", "allowed_upstream_dependencies" exactly as-is
  2. Remove the entire "step_metadata" key and value
  3. Add "downstream_consumers" with the exact data from the plan (pre-computed values provided)

  Write the complete file using the Write tool.
  After writing, run the verification command from the plan.
```

#### Acceptance Criteria

- [ ] `step_metadata` key does not exist in the file
- [ ] `downstream_consumers` key exists with 22 entries
- [ ] Each entry lists the correct downstream step IDs (verified against pre-computed table)
- [ ] `version`, `policy`, `steps`, `allowed_upstream_dependencies` are unchanged
- [ ] JSON is valid and well-formatted

---

### T3: Remove step_metadata Functions from dependency_order_lint.py

**Goal**: G4
**File**: `tools/specdev_tools/validation/dependency_order_lint.py`
**Depends on**: T2
**Batch**: B (parallel with T1)

#### Current State (179 lines)

Contains three functional sections:
1. **Lines 20–54**: `lint_dependency_order()` — core DAG enforcement (KEEP)
2. **Lines 57–95**: Helper functions `_load_order`, `_extract_step_refs`, `_add_error` (KEEP)
3. **Lines 97–136**: `_check_required_spec_inputs()` — validates prompts reference `step_metadata.required_spec_inputs` (REMOVE)
4. **Lines 139–178**: `_check_required_seed_inputs()` — validates prompts reference `step_metadata.required_seed_inputs` (REMOVE)

In `lint_dependency_order()`, lines 52–53 call the removed functions:
```python
errors.extend(_check_required_spec_inputs(root))
errors.extend(_check_required_seed_inputs(root))
```

#### Required Changes

1. **Remove lines 52–53** (the two `errors.extend(...)` calls in `lint_dependency_order()`)
2. **Remove lines 97–178** (both `_check_required_spec_inputs` and `_check_required_seed_inputs` functions entirely)
3. The resulting file should have only: imports, regex constants, `lint_dependency_order()`, `_load_order()`, `_extract_step_refs()`, `_add_error()`

#### Verification

```bash
# Module imports without error
python3 -c "from specdev_tools.validation.dependency_order_lint import lint_dependency_order; print('OK')"
```

#### Subagent Protocol

```
subagent_type: general-purpose
isolation: none
prompt: |
  TASK: Remove step_metadata-dependent functions from dependency_order_lint.py.

  Read tools/specdev_tools/validation/dependency_order_lint.py.

  Make these exact edits:
  1. In the lint_dependency_order() function, remove the two lines:
     errors.extend(_check_required_spec_inputs(root))
     errors.extend(_check_required_seed_inputs(root))
  2. Delete the entire _check_required_spec_inputs() function (lines 97-136)
  3. Delete the entire _check_required_seed_inputs() function (lines 139-178)

  Do NOT modify any other code. The core DAG enforcement logic and helper functions must remain unchanged.

  After editing, verify the module imports: python3 -c "from specdev_tools.validation.dependency_order_lint import lint_dependency_order; print('OK')"
```

#### Acceptance Criteria

- [ ] `lint_dependency_order()` no longer calls `_check_required_spec_inputs` or `_check_required_seed_inputs`
- [ ] Both removed functions do not exist in the file
- [ ] Core DAG enforcement (forward-edge, self-edge, disallowed-upstream detection) is unchanged
- [ ] `_load_order()`, `_extract_step_refs()`, `_add_error()` are unchanged
- [ ] Module imports successfully

---

### T4: Refactor matrix.py — Dynamic Entity Indexing (Section A Only)

**Goal**: G2
**File**: `tools/specdev_tools/validation/matrix.py`
**Depends on**: T1
**Batch**: C (parallel with T5, T7, T8)
**Review findings**: C1 — original plan was overscoped (tried to dynamize all 5 sections). H1 — link topology has no dynamic discovery mechanism. User chose **Option A**: replace only Section A (entity indexing), keep Sections C/D/E hardcoded.

#### Current State (411 lines)

`build_trace_matrix()` (lines 288–411) has 5 sections:

| Section | Lines | Content | Phase 0 Action |
|---------|-------|---------|----------------|
| A — Entity indexing | 306–336 | 5 hardcoded `if "NN_name" in schema:` blocks | **REPLACE** with dynamic discovery |
| B — Extension handling | 328–336 | `"extension_generator"` string + M1 bug | **KEEP** (M1 deferred, see backlog) |
| C — Link building | 338–366 | Hardcoded topology: FR→API, API→Fixture, etc. | **KEEP** (business logic, not vocabulary) |
| D — Matrix emission | 368–388 | FR as primary axis, hardcoded field names | **KEEP** (structural) |
| E — Coverage metrics | 390–398 | Hardcoded `"15_scaffold"` + metric keys | **KEEP** (presentation) |

**Also NOT changed**: `collect_definitions_and_references()` (lines 10–79), `validate_trace_integrity()` (lines 82–286). The latter has 5 hardcoded schema strings (H2, deferred — see backlog).

#### Required Changes

**1. Add import** at top of file:
```python
from ..core.trace_types import normalize_trace_type, is_valid_trace_type
```

**2. Replace Section A** (lines 306–336) with dynamic entity discovery:

Current code:
```python
# Lines 306-326 — HARDCODED
frs = []
apis = {}
fixtures = []
nfrs = []
threats = []

for data in artifacts.values():
    schema = data.get("$schema", "")
    if "04_fr_list" in schema:
        frs.extend(data.get("functional_requirements", []))
    if "05_interface_contracts" in schema:
        for a in data.get("apis", []):
            apis[a.get("api_id")] = a
    if "08_fixtures" in schema:
        fixtures.extend(data.get("fixtures", []))
    if "07_nfrs" in schema:
        nfrs.extend(data.get("nfrs", []))
    if "11_redteam" in schema:
        threats.extend(data.get("threats", []))
```

Replacement — dynamic entity indexing:
```python
# Dynamic entity indexing: discover entities by _id fields + canon trace type validation
entity_index = collections.defaultdict(list)  # normalized_trace_type → [entity_objects]

for data in artifacts.values():
    for key, value in data.items():
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            for field in item:
                if not field.endswith("_id") or not isinstance(item[field], str):
                    continue
                prefix = field[:-3]  # strip "_id"
                normalized = normalize_trace_type(prefix)
                if is_valid_trace_type(normalized):
                    entity_index[normalized].append(item)
                    break  # one entity type per object

# Bridge to existing variable names (Sections C/D/E unchanged)
frs = entity_index.get("fr", [])
apis = {a.get("api_id"): a for a in entity_index.get("api", []) if a.get("api_id")}
fixtures = entity_index.get("fixture", [])
nfrs = entity_index.get("nfr", [])
threats = entity_index.get("threat", [])
```

**Key design decisions**:
- `break` after first matching `_id` field prevents double-indexing objects with multiple `_id` fields
- `normalize_trace_type(prefix)` handles aliases (e.g., `inv_id` → `invariant`)
- Variable names `frs`, `apis`, `fixtures`, `nfrs`, `threats` are preserved as the bridge between dynamic indexing and the hardcoded link-building topology in Section C
- `apis` dict is rebuilt from the entity list using `api_id` as key (matching current behavior)

**3. Keep Sections B–E unchanged**. The extension handling (Section B) has a known bug (M1) but is deferred to the backlog.

#### Public API Preservation

- `build_trace_matrix(repo_root, spec_dir) -> dict` — same signature, same return structure
- `validate_trace_integrity(repo_root, spec_dir) -> list[str]` — unchanged
- `collect_definitions_and_references(artifacts) -> tuple[set, list]` — unchanged
- Return dict keys: `matrix`, `coverage`, optionally `extensions`, `integrity_errors` — unchanged

#### Verification

```bash
# Generate matrix from existing spec dir
./tools/run_specdev.sh matrix spec --repo-root . --out /tmp/test_matrix.json
python3 -c "import json; d=json.load(open('/tmp/test_matrix.json')); print('matrix rows:', len(d.get('matrix',[])), 'coverage:', d.get('coverage',{})); print('OK')"
```

#### Subagent Protocol

```
subagent_type: general-purpose
isolation: none
prompt: |
  TASK: Refactor Section A of build_trace_matrix() in tools/specdev_tools/validation/matrix.py
  to use dynamic entity indexing instead of hardcoded schema-name matching.

  Read these files first:
  1. tools/specdev_tools/validation/matrix.py (full file)
  2. tools/specdev_tools/core/trace_types.py (already rewritten in T1)

  SCOPE: Only replace the entity indexing section (lines ~306-336). Keep ALL other
  sections (extension handling, link building, matrix emission, coverage metrics) UNCHANGED.

  CHANGES:
  - Add import at top: from ..core.trace_types import normalize_trace_type, is_valid_trace_type
  - Replace the 5 hardcoded "if 'NN_name' in schema:" blocks with dynamic discovery
  - Discovery algorithm: for each artifact, walk top-level array properties, find objects
    with _id-suffixed fields, strip "_id", validate via is_valid_trace_type(), index by type
  - Bridge to existing variables: frs, apis, fixtures, nfrs, threats = entity_index lookups
  - apis dict must be rebuilt from entity list using api_id as key

  DO NOT CHANGE:
  - collect_definitions_and_references() function
  - validate_trace_integrity() function
  - Extension handling (Section B, lines ~328-336)
  - Link building (Section C, lines ~338-366)
  - Matrix emission (Section D, lines ~368-388)
  - Coverage metrics (Section E, lines ~390-398)

  The public API (function signatures and return shapes) must NOT change.

  After refactoring, verify: ./tools/run_specdev.sh matrix spec --repo-root . --out /tmp/test_matrix.json
```

#### Acceptance Criteria

- [ ] No hardcoded schema name strings (`"04_fr_list"`, `"05_interface_contracts"`, etc.) in entity indexing
- [ ] Entity discovery is driven by `_id` field detection + `is_valid_trace_type()` validation
- [ ] Bridge variables (`frs`, `apis`, `fixtures`, `nfrs`, `threats`) preserve downstream compatibility
- [ ] Link building (Section C) is UNCHANGED — still uses hardcoded `"api"`, `"fr"` type strings
- [ ] Extension handling (Section B) is UNCHANGED — M1 bug noted but deferred
- [ ] `validate_trace_integrity()` is UNCHANGED — H2 tech debt noted but deferred
- [ ] Return dict structure unchanged
- [ ] Matrix generation produces equivalent output for existing specs
- [ ] `from ..core.trace_types import ...` is present

---

### T5: New Canon-Schema Alignment Linter (Redesigned)

**Goal**: G3
**File**: `tools/specdev_tools/validation/canon_schema_alignment.py` (NEW)
**Depends on**: T0 (uses CanonicalRegistry directly, not trace_types.py)
**Batch**: B (parallel with T1, T3)
**Review findings**: C3 — original `_id`-prefix approach produced 17 false E550 errors (most `_id` fields are local entity IDs like `term_id`, `milestone_id`, not trace types) and had a recursion bug in `_extract_id_prefixes`. User chose holistic redesign.

#### Purpose

Detects drift between canon kind registries and JSON Schema `enum` constraints. When a schema enum is clearly paired with a canon kind (e.g., `environmentName` enum ↔ `environment` kind), the linter verifies they stay in sync.

**Why enums, not `_id` fields?** Schema `_id` fields define local entity identifiers — 18 of 25 prefixes (`term_id`, `milestone_id`, `job_id`, etc.) are NOT trace types and should not be flagged. Schema `enum` arrays, on the other hand, are explicit vocabulary constraints that SHOULD match their canon kind counterparts.

#### Design: Two-Phase Approach

**Phase 1 — Explicit pairing check** (zero false positives):
A declarative `_ENUM_CANON_PAIRINGS` config maps known schema enum locations to their canon kind. The linter checks these pairings for drift in both directions.

**Phase 2 — Discovery scan** (advisory warnings):
The linter scans all schema enums and looks for high overlap with any canon kind. Unregistered enums with >= 80% value overlap with a canon kind generate a W552 advisory, helping maintainers discover new pairings to register.

#### Known Enum↔Canon Pairings

Discovered by surveying all `enum` arrays in `schema/`:

| Schema File | JSON Path | Canon Kind | Enum Values |
|-------------|-----------|------------|-------------|
| `core/collections.schema.json` | `$defs/environmentName/enum` | `environment` | dev, ci, staging, prod |
| `core/collections.schema.json` | `$defs/stageName/enum` | `stage` | dev, ci, staging, prod |
| `07_nfrs.schema.json` | (nfrs items category enum) | `nfr_category` | latency, throughput, ... (11 values) |

**Intentionally excluded** from pairings (Category B — business rule subsets):
- `11_redteam.schema.json` mitigations type enum — subset of trace types (7/9), intentionally excludes `component`, `threat`
- `16_impl_context.schema.json` specRef type enum — includes non-trace value `code`, intentionally mixed

#### Algorithm

```python
from __future__ import annotations

import json
import os
from collections import defaultdict
from glob import glob

from ..canonical.registry import CanonicalRegistry


# Declarative enum↔canon pairings: (schema_rel_path, json_path_segments, canon_kind)
# Add a new line whenever a schema enum should track a canon kind.
_ENUM_CANON_PAIRINGS = [
    ("core/collections.schema.json", ["$defs", "environmentName", "enum"], "environment"),
    ("core/collections.schema.json", ["$defs", "stageName", "enum"], "stage"),
    ("07_nfrs.schema.json", ["properties", "nfrs", "items", "properties", "category", "enum"], "nfr_category"),
]


def lint_canon_schema_alignment(repo_root: str) -> list[str]:
    """Check alignment between canon kinds and JSON Schema enum constraints."""
    errors: list[str] = []
    schema_dir = os.path.join(repo_root, "schema")

    # Load canon kinds → {kind: set_of_preferred_labels}
    registry = CanonicalRegistry.load(repo_root)
    canon_kinds: dict[str, set[str]] = defaultdict(set)
    for entry in registry.entries.values():
        label = entry.payload.get("preferred_label", "")
        if label:
            canon_kinds[entry.kind].add(label)

    # Phase 1: Check explicit pairings
    registered_keys: set[tuple[str, str]] = set()
    for schema_rel, json_path, kind in _ENUM_CANON_PAIRINGS:
        path_str = "/".join(json_path)
        registered_keys.add((schema_rel, path_str))

        schema_path = os.path.join(schema_dir, schema_rel)
        if not os.path.exists(schema_path):
            errors.append(f"E552 MISSING_PAIRED_SCHEMA {schema_rel}")
            continue

        with open(schema_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        enum_values = _resolve_json_path(data, json_path)
        if enum_values is None:
            errors.append(f"E553 MISSING_ENUM_PATH {schema_rel}:{path_str}")
            continue

        enum_set = set(enum_values)
        canon_labels = canon_kinds.get(kind, set())

        missing = sorted(canon_labels - enum_set)
        extra = sorted(enum_set - canon_labels)

        if missing:
            errors.append(
                f"E550 CANON_ENUM_DRIFT {schema_rel}:{path_str} "
                f"missing canon {kind} entries: {missing}"
            )
        if extra:
            errors.append(
                f"E551 SCHEMA_ENUM_EXTRA {schema_rel}:{path_str} "
                f"has values not in canon {kind}: {extra}"
            )

    # Category B exclusions: enums that are intentional subsets of a canon kind
    # (business-rule scoping, not vocabulary drift). These would otherwise
    # trigger W552 false positives because they overlap ≥80% with a canon kind
    # but deliberately omit/alias entries for domain reasons.
    _EXCLUDED_DISCOVERY_ENUMS = {
        # 11_redteam mitigations.type — uses "inv" alias + omits "component"/"threat"
        ("11_redteam.schema.json", "properties/threats/items/properties/mitigations/items/properties/type/enum"),
        # 16_impl_context specRef.type — uses "inv" alias + includes "code" (not a trace type)
        ("16_impl_context.schema.json", "$defs/specRef/properties/type/enum"),
    }

    # Phase 2: Discovery scan (advisory)
    for schema_path in sorted(glob(os.path.join(schema_dir, "**", "*.json"), recursive=True)):
        rel = os.path.relpath(schema_path, schema_dir)
        with open(schema_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for path_str, values in _extract_enums(data):
            if (rel, path_str) in registered_keys:
                continue
            if (rel, path_str) in _EXCLUDED_DISCOVERY_ENUMS:
                continue
            enum_set = set(values)
            if len(enum_set) < 3:
                continue
            for kind, labels in canon_kinds.items():
                overlap = len(enum_set & labels)
                if overlap >= 3 and overlap / len(enum_set) >= 0.8:
                    errors.append(
                        f"W552 POTENTIAL_UNREGISTERED_PAIRING {rel}:{path_str} "
                        f"overlaps {overlap}/{len(enum_set)} with canon kind '{kind}'"
                    )
    return errors


def _resolve_json_path(data: dict, path: list[str]):
    """Walk a JSON object by path segments, return the final value or None."""
    current = data
    for segment in path:
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        else:
            return None
    return current if isinstance(current, list) else None


def _extract_enums(schema: dict, path: str = "") -> list[tuple[str, list[str]]]:
    """Recursively extract all enum arrays from a JSON Schema."""
    results: list[tuple[str, list[str]]] = []
    if not isinstance(schema, dict):
        return results
    if "enum" in schema and isinstance(schema["enum"], list):
        values = [v for v in schema["enum"] if isinstance(v, str)]
        if values:
            results.append((path + "/enum" if path else "enum", values))
    for key, value in schema.items():
        if key.startswith("$") and key != "$defs":
            continue
        child_path = f"{path}/{key}" if path else key
        if isinstance(value, dict):
            results.extend(_extract_enums(value, child_path))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    results.extend(_extract_enums(item, f"{child_path}/{i}"))
    return results
```

#### Error Codes

| Code | Level | Meaning |
|------|-------|---------|
| E550 | ERROR | Canon kind has entries missing from a paired schema enum |
| E551 | ERROR | Schema enum has values not present in the paired canon kind |
| E552 | ERROR | Schema file referenced in pairing config not found |
| E553 | ERROR | JSON path referenced in pairing config not found in schema |
| W552 | WARN | Unregistered enum has high overlap with a canon kind (may need pairing) |

#### Verification

```bash
python3 -c "from specdev_tools.validation.canon_schema_alignment import lint_canon_schema_alignment; errs = lint_canon_schema_alignment('.'); print(f'{len(errs)} issues'); [print(e) for e in errs]; print('OK' if not any(e.startswith('E5') for e in errs) else 'FAIL')"
```

#### Subagent Protocol

```
subagent_type: general-purpose
isolation: none
prompt: |
  TASK: Create a new file tools/specdev_tools/validation/canon_schema_alignment.py

  This is a NEW linter that checks alignment between canon kind entries and JSON Schema
  enum constraints. It uses a two-phase approach:
  Phase 1: Check explicit enum↔canon pairings for drift (E550/E551 errors)
  Phase 2: Discover unregistered enums with high canon overlap (W552 warnings)

  Read these files for context:
  1. tools/specdev_tools/canonical/registry.py (CanonicalRegistry class)
  2. schema/core/collections.schema.json (see environmentName and stageName enums)
  3. schema/07_nfrs.schema.json (see nfrs category enum)
  4. canon/kinds/environment.json (canon kind entries for comparison)

  Write the file with the EXACT structure from the plan:
  - _ENUM_CANON_PAIRINGS config list (3 entries)
  - lint_canon_schema_alignment(repo_root) -> list[str]
  - _resolve_json_path(data, path) -> list | None
  - _extract_enums(schema, path) -> list[tuple[str, list[str]]]

  Error codes: E550 (canon entries missing from enum), E551 (enum values not in canon),
  E552 (missing schema file), E553 (missing enum path), W552 (potential unregistered pairing)

  After writing, verify: python3 -c "from specdev_tools.validation.canon_schema_alignment import lint_canon_schema_alignment; print('OK')"
```

#### Acceptance Criteria

- [ ] New file exists at `tools/specdev_tools/validation/canon_schema_alignment.py`
- [ ] `_ENUM_CANON_PAIRINGS` has 3 entries (environment, stage, nfr_category)
- [ ] Phase 1 checks produce E550/E551 for drift in paired enums
- [ ] Phase 2 produces W552 for unregistered high-overlap enums
- [ ] Zero false positives on clean codebase (no `_id`-prefix scanning)
- [ ] Error codes E552/E553 for broken pairing config
- [ ] `_extract_enums` recursively walks JSON Schema structure
- [ ] `_resolve_json_path` navigates nested schema objects by path segments

---

### T6: Update cli.py — prompt-context Rewrite + Alignment Command

**Goal**: G3 + G4
**File**: `tools/specdev_tools/cli.py`
**Depends on**: T2, T3, T5
**Batch**: D
**Review finding**: M2 — the hardcoded `step_artifacts` map (lines 656–678) must be explicitly removed, not just bypassed.

#### Current State

**prompt-context command** (lines 630–758):
- Reads `step_metadata` from step_order.json (line 652)
- Has hardcoded `step_artifacts` map (lines 656–678) — **REMOVE entirely** (M2)
- Iterates `step_metadata` to find downstream steps by scanning `required_spec_inputs` (lines 684–687)
- Has hardcoded `step_name` if/elif chain (lines 702–745)
- Outputs markdown table with columns: Step, Name, Extraction Intent (lines 693–758)

#### Required Changes

**1. Rewrite prompt-context command** (replace lines 630–758):

After T2, `step_order.json` has `downstream_consumers` instead of `step_metadata`. The new prompt-context:
- Reads `downstream_consumers` from step_order.json
- Looks up `downstream_consumers[normalized_step]` directly (no scanning)
- Outputs markdown table with columns: Step, Name (Extraction Intent column removed)
- `step_name` mapping can stay as a hardcoded dict (it's presentation logic)

New implementation:
```python
elif args.cmd == "prompt-context":
    repo_root = os.path.abspath(args.repo_root)
    step_order_path = os.path.join(repo_root, "tools", "step_order.json")
    if not os.path.exists(step_order_path):
        print(f"E520 UNRESOLVED_INPUT missing_step_order {step_order_path}", file=sys.stderr)
        sys.exit(1)

    with open(step_order_path, "r", encoding="utf-8") as f:
        step_order = json.load(f)

    normalized_step = args.step.zfill(2) if args.step.isdigit() else args.step

    if normalized_step not in step_order.get("allowed_upstream_dependencies", {}):
        print(f"Error: Unknown step '{args.step}'", file=sys.stderr)
        sys.exit(1)

    downstream_consumers = step_order.get("downstream_consumers", {})
    consumer_ids = downstream_consumers.get(normalized_step, [])

    STEP_NAMES = {
        "00": "Project Charter", "01": "Capabilities", "02": "System Sketch",
        "02a": "Delivery Baseline", "03": "Glossary", "04": "Functional Requirements",
        "05": "Interface Contracts", "06": "Invariants", "07": "NFRs",
        "08": "Fixtures", "09": "Implementation Plan", "10": "Governance",
        "11": "Red Team", "12": "CI Gates", "13": "Extension Generator",
        "13a": "Completeness Assessment", "14": "Roadmap", "15": "Scaffold",
        "16": "Impl Context", "16a": "Impl Planner", "16b": "Impl Coder",
        "16c": "Impl Reviewer",
    }

    print("| Step | Name |")
    print("|------|------|")
    for cid in consumer_ids:
        name = STEP_NAMES.get(cid, f"Step {cid}")
        print(f"| {cid} | {name} |")
```

**2. Add alignment lint command**:

Add a new subcommand `canon-schema-alignment` (or similar) that runs the linter from T5.

In the argparse setup section, add:
```python
sp_alignment = subparsers.add_parser("canon-schema-alignment", help="Check canon/schema alignment for trace types")
sp_alignment.add_argument("--repo-root", default=".")
```

In the command dispatch section, add:
```python
elif args.cmd == "canon-schema-alignment":
    from .validation.canon_schema_alignment import lint_canon_schema_alignment
    repo_root = os.path.abspath(args.repo_root)
    errors = lint_canon_schema_alignment(repo_root)
    _print_and_exit_if_errors(errors)
```

#### Verification

```bash
# Test prompt-context still works
./tools/run_specdev.sh prompt-context 04 --repo-root .
# Test new alignment command
./tools/run_specdev.sh canon-schema-alignment --repo-root .
```

#### Subagent Protocol

```
subagent_type: general-purpose
isolation: none
prompt: |
  TASK: Update tools/specdev_tools/cli.py with two changes:
  1. Rewrite the prompt-context command (lines 630-758) to use downstream_consumers from step_order.json
  2. Add a new canon-schema-alignment subcommand

  Read these files first:
  1. tools/specdev_tools/cli.py (full file — focus on lines 1-50 for argparse setup, and lines 630-758 for prompt-context)
  2. tools/step_order.json (already refactored in T2 — has downstream_consumers)
  3. tools/specdev_tools/validation/canon_schema_alignment.py (created in T5 — for import path)

  CHANGE 1 — prompt-context rewrite:
  - Replace lines 630-758 with new implementation from the plan
  - Use downstream_consumers instead of step_metadata
  - Remove Extraction Intent column from the table (now just Step and Name)
  - Keep the step existence check using allowed_upstream_dependencies

  CHANGE 2 — new alignment command:
  - Add "canon-schema-alignment" to argparse subparsers (near other lint commands)
  - Add dispatch logic using standard error reporting pattern (match canonical-lint command pattern)
  - Import from .validation.canon_schema_alignment import lint_canon_schema_alignment

  After editing, verify both commands work:
  - ./tools/run_specdev.sh prompt-context 04 --repo-root .
  - ./tools/run_specdev.sh canon-schema-alignment --repo-root .
```

#### Acceptance Criteria

- [ ] prompt-context uses `downstream_consumers` from step_order.json (not `step_metadata`)
- [ ] prompt-context table has 2 columns: Step, Name (no Extraction Intent)
- [ ] prompt-context still errors on unknown steps
- [ ] `canon-schema-alignment` subcommand exists and is callable
- [ ] `canon-schema-alignment` reports errors/warnings in standard format
- [ ] No references to `step_metadata`, `required_spec_inputs`, `required_seed_inputs`, or `extraction_intent` remain in cli.py
- [ ] Hardcoded `step_artifacts` map (lines 656–678) is removed entirely (M2)

---

### T7: Extend test_trace_types.py

**Goal**: G1 tests
**File**: `tests/test_trace_types.py`
**Depends on**: T1
**Batch**: C (parallel with T4, T5, T8)

#### Current State (17 lines)

```python
import unittest
from specdev_tools.core.trace_types import normalize_trace_type, is_valid_trace_type

class TraceTypesTests(unittest.TestCase):
    def test_normalize_inv_alias(self):
        self.assertEqual(normalize_trace_type("inv"), "invariant")

    def test_accepts_invariant_and_component(self):
        self.assertTrue(is_valid_trace_type("invariant"))
        self.assertTrue(is_valid_trace_type("component"))

if __name__ == "__main__":
    unittest.main()
```

#### Required Changes

Keep existing tests (they still pass with the canon-backed implementation). Add new tests:

1. **test_trace_types_loaded_from_canon**: Verify `TRACE_TYPES` is a tuple of strings, contains expected core types (`fr`, `api`, `nfr`, `invariant`, `fixture`, `doc`, `capability`, `component`, `threat`), and does NOT contain `inv` (it's an alias, not a primary type)
2. **test_canonical_trace_type_from_canon**: Verify `CANONICAL_TRACE_TYPE` is a dict, has `inv` → `invariant` mapping
3. **test_all_canon_types_are_valid**: Iterate `TRACE_TYPES` and assert `is_valid_trace_type(t)` for each
4. **test_invalid_type_rejected**: Verify `is_valid_trace_type("bogus")` returns `False`
5. **test_normalize_empty_and_whitespace**: Verify `normalize_trace_type("")` → `""`, `normalize_trace_type("  ")` → `""`
6. **test_normalize_types_batch**: Verify `normalize_trace_types(["inv", "fr", "api"])` → `["invariant", "fr", "api"]`
7. **test_fallback_types_are_sorted**: Verify `_FALLBACK_TYPES` is sorted (import guard)
8. **test_threat_is_valid_trace_type**: Verify `is_valid_trace_type("threat")` returns `True` (added in T0)

#### Subagent Protocol

```
subagent_type: general-purpose
isolation: none
prompt: |
  TASK: Extend tests/test_trace_types.py with new test cases for canon-backed trace types.

  Read tests/test_trace_types.py first.

  Keep the existing 2 test methods unchanged. Add 8 new test methods as specified in the plan:
  1. test_trace_types_loaded_from_canon — TRACE_TYPES is tuple, contains core types incl "threat", no "inv"
  2. test_canonical_trace_type_from_canon — dict with inv→invariant
  3. test_all_canon_types_are_valid — all TRACE_TYPES pass is_valid_trace_type
  4. test_invalid_type_rejected — "bogus" returns False
  5. test_normalize_empty_and_whitespace — edge cases
  6. test_normalize_types_batch — batch normalization
  7. test_fallback_types_are_sorted — _FALLBACK_TYPES is sorted
  8. test_threat_is_valid_trace_type — "threat" returns True

  Import additionally: TRACE_TYPES, CANONICAL_TRACE_TYPE, normalize_trace_types
  Also import _FALLBACK_TYPES from specdev_tools.core.trace_types for fallback test.

  After writing, run: pytest tests/test_trace_types.py -v
```

#### Acceptance Criteria

- [ ] Existing 2 tests still pass
- [ ] 8 new tests added and passing (including `threat` trace type test)
- [ ] Tests verify canon loading behavior (not just function signatures)
- [ ] `pytest tests/test_trace_types.py -v` passes with 10 tests

---

### T8: Update test_dependency_order_lint.py

**Goal**: G4 tests
**File**: `tests/test_dependency_order_lint.py`
**Depends on**: T3
**Batch**: C (parallel with T4, T5, T7)

#### Current State (147 lines)

7 test methods. None of the tests create `step_metadata` in their fixtures — they only test the core DAG enforcement. The step_order.json fixtures in these tests only include `steps`, `policy`, and `allowed_upstream_dependencies`.

#### Required Changes

**No test removals needed** — none of the existing tests test `_check_required_spec_inputs` or `_check_required_seed_inputs`.

**Add 1 new test**: Verify that step_order.json with `downstream_consumers` (and no `step_metadata`) still works correctly:

```python
def test_works_with_downstream_consumers_format(self):
    """Verify lint works with new step_order.json format (downstream_consumers, no step_metadata)."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "tools").mkdir()
        (root / "prompts").mkdir()
        (root / "tools" / "step_order.json").write_text(
            json.dumps({
                "steps": ["00", "01", "02"],
                "allowed_upstream_dependencies": {"00": [], "01": ["00"], "02": ["00", "01"]},
                "downstream_consumers": {"00": ["01", "02"], "01": ["02"], "02": []},
            }),
            encoding="utf-8",
        )
        (root / "prompts" / "prompt_01_test.md").write_text(
            "Use spec/00_charter.json",
            encoding="utf-8",
        )
        errs = lint_dependency_order(str(root))
        self.assertEqual([], errs)
```

#### Subagent Protocol

```
subagent_type: general-purpose
isolation: none
prompt: |
  TASK: Add one new test to tests/test_dependency_order_lint.py.

  Read tests/test_dependency_order_lint.py first.

  Add the test_works_with_downstream_consumers_format test method (from plan) to the existing
  DependencyOrderLintTests class. Place it after the existing tests, before the if __name__ block.

  Do NOT modify any existing tests.

  After editing, run: pytest tests/test_dependency_order_lint.py -v
```

#### Acceptance Criteria

- [ ] All 7 existing tests still pass
- [ ] 1 new test added and passing
- [ ] New test uses `downstream_consumers` in fixture (no `step_metadata`)
- [ ] `pytest tests/test_dependency_order_lint.py -v` passes with 8 tests

---

### T9: Update test_cli.py — prompt-context Tests + Alignment Tests

**Goal**: G3 + G4 tests
**File**: `tests/test_cli.py`
**Depends on**: T6
**Batch**: E (parallel with T10)

#### Current State

4 prompt-context tests (lines 1540–1758):
- `test_prompt_context_step04` — checks >= 13 data rows, uses `step_metadata`
- `test_prompt_context_step00` — checks >= 8 data rows, uses `step_metadata`
- `test_prompt_context_unknown_step` — checks error on unknown step, uses `step_metadata`
- `test_prompt_context_output_format` — checks table format including "Extraction Intent" header, uses `step_metadata`

#### Required Changes
**Review finding**: M3 — test fixtures need exact `downstream_consumers` values, not hand-waved "compute from step_metadata".

**1. Update all 4 prompt-context test fixtures**: Replace `step_metadata` with `downstream_consumers` in the step_order.json fixture data. Use these exact test fixture values (pre-computed from each test's `step_metadata.required_spec_inputs`):

For tests using step 04 as the target (test_prompt_context_step04):
```json
"downstream_consumers": {
  "00": ["01", "03", "04", "07", "09", "10", "13a", "14"],
  "01": ["02", "03", "04", "09", "13", "13a"],
  "02": ["02a", "05", "09", "11", "13", "15"],
  "03": ["04", "05", "07"],
  "04": ["05", "06", "07", "08", "09", "11", "13", "13a", "14", "15", "16", "16a", "16c"]
}
```
The test should assert `>= 13` data rows for step 04 (same count as before — downstream of 04 has 13 consumers).

For tests using step 00 as the target (test_prompt_context_step00):
```json
"downstream_consumers": {
  "00": ["01", "03", "04", "07", "09", "10", "13a", "14"]
}
```
The test should assert `>= 8` data rows for step 00 (same count as before).

**2. Update test assertions**:
- Remove checks for "Extraction Intent" column header (test_prompt_context_output_format line 1748)
- Update header checks to match new 2-column format: "Step" and "Name"
- Data row count assertions should remain the same (downstream relationships preserved)

**3. Add alignment lint test**: Add at least one test for the new `canon-schema-alignment` command:
```python
def test_canon_schema_alignment_runs(self):
    """Test that canon-schema-alignment command runs and returns results."""
    ...
```

#### Subagent Protocol

```
subagent_type: general-purpose
isolation: none
prompt: |
  TASK: Update tests/test_cli.py for prompt-context and alignment changes.

  Read tests/test_cli.py (focus on lines 1540-1762 for prompt-context tests).
  Also read tools/step_order.json (to see the new downstream_consumers format).

  CHANGES:

  1. In all 4 prompt-context tests, replace "step_metadata" fixture data with "downstream_consumers".
     Compute downstream_consumers by inverting the step_metadata.required_spec_inputs data:
     - For each step that has required_spec_inputs, find which step produces that artifact
     - Group by producer step to get the consumer list

  2. Update test_prompt_context_output_format assertions:
     - Remove the assertion: self.assertIn("Extraction Intent", lines[0])
     - The table now has 2 columns: Step, Name (not 3)

  3. In test_prompt_context_unknown_step, replace step_metadata with downstream_consumers.
     The step_order fixture only needs allowed_upstream_dependencies and downstream_consumers.

  4. Add test_canon_schema_alignment_runs test that:
     - Creates a temp dir with canon/kinds/trace_type.json and a schema file
     - Runs ["canon-schema-alignment", "--repo-root", str(repo_root)]
     - Checks exit code 0

  Do NOT modify any tests outside the prompt-context section and the new alignment test.

  After editing, run: pytest tests/test_cli.py -v -k "prompt_context or canon_schema_alignment"
```

#### Acceptance Criteria

- [ ] All 4 prompt-context tests pass with `downstream_consumers` fixtures
- [ ] No references to `step_metadata`, `required_spec_inputs`, or `extraction_intent` in test fixtures
- [ ] "Extraction Intent" assertion removed from output format test
- [ ] New `canon-schema-alignment` test passes
- [ ] All other test_cli.py tests unaffected

---

### T10: New test_canon_schema_alignment.py

**Goal**: G3 tests
**File**: `tests/test_canon_schema_alignment.py` (NEW)
**Depends on**: T5
**Batch**: E (parallel with T9)

#### Purpose

Dedicated test suite for the redesigned canon-schema alignment linter (enum↔canon kind drift detection).

#### Required Test Cases

1. **test_aligned_enum_and_canon**: Paired enum matches canon kind exactly → zero errors
2. **test_canon_enum_drift**: Canon kind has label missing from paired schema enum → E550
3. **test_schema_enum_extra**: Paired schema enum has value not in canon kind → E551
4. **test_missing_paired_schema**: Pairing references schema file that doesn't exist → E552
5. **test_missing_enum_path**: Pairing references JSON path that doesn't exist in schema → E553
6. **test_discovery_scan_warns**: Unregistered enum with high overlap to canon kind → W552
7. **test_no_false_positives_on_subset_enum**: Enum that's a subset of a canon kind but below overlap threshold → no warning

#### Fixture Strategy

Each test creates a minimal temp directory with:
- `canon/manifest.json` — minimal manifest
- `canon/kinds/<kind>.json` — minimal canon kind with test entries
- `schema/NN_test.schema.json` — minimal schema with test enums

The linter must be called with a custom `_ENUM_CANON_PAIRINGS` or the test must create fixtures matching the default pairings. Preferred: create test fixtures matching the default pairing paths.

#### Subagent Protocol

```
subagent_type: general-purpose
isolation: none
prompt: |
  TASK: Create tests/test_canon_schema_alignment.py with 7 test cases.

  Read tools/specdev_tools/validation/canon_schema_alignment.py first (created in T5).

  Create a unittest test class CanonSchemaAlignmentTests with these test methods:
  1. test_aligned_enum_and_canon — paired enum matches kind, zero errors
  2. test_canon_enum_drift — kind has extra label vs enum → E550
  3. test_schema_enum_extra — enum has extra value vs kind → E551
  4. test_missing_paired_schema — pairing refs missing file → E552
  5. test_missing_enum_path — pairing refs missing JSON path → E553
  6. test_discovery_scan_warns — unregistered enum overlaps canon kind → W552
  7. test_no_false_positives_on_subset_enum — subset enum below threshold → no warning

  Each test should create a temp directory with:
  - canon/manifest.json (minimal)
  - canon/kinds/<kind>.json with test entries
  - schema/ files with test enums

  For testing pairings, either:
  a) Monkey-patch _ENUM_CANON_PAIRINGS for controlled testing, OR
  b) Create schema files at the exact paths referenced by default pairings

  Canon kind fixture format (minimal):
  {
    "$schema": "https://specdev.local/schema/canon/kind/1",
    "registry_version": "1.0.0",
    "kind": "environment",
    "entries": [
      {"id": "cn:core:environment:dev", "kind": "environment", "preferred_label": "dev",
       "definition": "...", "version": "1.0.0", "status": "active",
       "owners": ["spec-platform"], "aliases": [], "tags": [],
       "lifecycle": {"introduced_at": "2026-03-01T00:00:00Z"}}
    ]
  }

  After writing, run: pytest tests/test_canon_schema_alignment.py -v
```

#### Acceptance Criteria

- [ ] New file with 7 test methods
- [ ] All 7 tests pass
- [ ] Tests use temp directories (no side effects)
- [ ] All 5 error codes tested (E550, E551, E552, E553, W552)
- [ ] False positive protection tested (subset enum case)
- [ ] Discovery scan threshold tested

---

### T11: Documentation Updates

**Goal**: G6
**Files**: `docs/developers/reference.md`
**Depends on**: All previous tasks
**Batch**: G

#### Required Changes

Update `docs/developers/reference.md` to document:

1. **New command**: `canon-schema-alignment` — purpose, usage, error codes (E550, E551, E552, E553, W552)
2. **Changed command**: `prompt-context` — now uses `downstream_consumers`, table format changed (2 columns)
3. **Changed file**: `step_order.json` — new `downstream_consumers` field, `step_metadata` removed
4. **Architecture note**: trace_types.py is now canon-backed, loads from `canon/kinds/trace_type.json`

#### Subagent Protocol

```
subagent_type: general-purpose
isolation: none
prompt: |
  TASK: Update docs/developers/reference.md with Phase 0 changes.

  Read docs/developers/reference.md first.

  Add/update documentation for:
  1. New CLI command: canon-schema-alignment (--repo-root)
     - E550 CANON_ENUM_DRIFT: canon kind has entries missing from paired schema enum
     - E551 SCHEMA_ENUM_EXTRA: schema enum has values not present in paired canon kind
     - E552: schema file referenced in pairing config not found
     - E553: JSON path referenced in pairing config not found in schema
     - W552 POTENTIAL_UNREGISTERED_PAIRING: unregistered enum has high overlap with a canon kind
  2. Changed CLI command: prompt-context now outputs 2-column table (Step, Name)
  3. Architecture: trace_types.py loads from canon/kinds/trace_type.json (fallback to hardcoded)
  4. step_order.json: step_metadata removed, downstream_consumers added

  Keep documentation concise. Follow the existing style and formatting.
```

#### Acceptance Criteria

- [ ] `canon-schema-alignment` command documented with error codes
- [ ] `prompt-context` output format change noted
- [ ] `step_order.json` structure change documented
- [ ] `trace_types.py` architecture change documented

---

## 6. Verification Protocol

After all tasks complete, run the full verification suite:

```bash
# 1. Full test suite
pytest tests/ -v

# 2. Validate all specs
./tools/run_specdev.sh validate-all spec --repo-root .

# 3. Canon integrity
./tools/run_specdev.sh canonical-lint canon --repo-root .
./tools/run_specdev.sh canonical-integrity spec --repo-root .

# 4. Hallucination lint (now fully dynamic via G1)
./tools/run_specdev.sh hallucination-lint spec --repo-root .

# 5. Dependency order lint (updated in G4)
./tools/run_specdev.sh dependency-order-lint --repo-root .

# 6. New alignment linter (G3)
./tools/run_specdev.sh canon-schema-alignment --repo-root .

# 7. Matrix generation (updated in G2)
./tools/run_specdev.sh matrix spec --repo-root . --out tools/trace_matrix.json

# 8. Fixtures lint
./tools/run_specdev.sh fixtures-lint spec --repo-root .

# 9. Spec quality
./tools/run_specdev.sh spec-quality-lint spec --repo-root .
```

All 9 checks must pass with zero errors.

---

## 7. Risk Register

| Risk | Mitigation | Severity |
|------|-----------|----------|
| Circular import: trace_types ↔ canonical.registry | Verified: registry.py has no core/ imports | LOW |
| Path resolution fails in worktrees | `parents[3]` tested for both direct and worktree layouts | LOW |
| Canon unavailable at import time | Fallback to hardcoded `_FALLBACK_TYPES` (includes `threat`) | LOW |
| Dynamic indexing misses entities | Only Section A replaced; bridge variables preserve exact downstream behavior; matrix test validates | MEDIUM |
| step_order.json consumers break | 5 consumers verified: 2 unaffected (forward_replay, planner), 3 updated (cli, dep_lint, tests) | LOW |
| Test count regression | Each task specifies exact expected test counts | LOW |
| Prompt-context data row counts change | downstream_consumers computed from same data, counts verified identical | LOW |
| Alignment linter false positives | Explicit pairing config (not heuristic); overlap threshold for discovery scan | LOW |
| validate_trace_integrity() tech debt (H2) | Acknowledged, deferred — 5 hardcoded schema strings still work correctly | LOW |
| Extension handling bug (M1) | Acknowledged, deferred — only affects projects using extension files | LOW |

---

## 8. Rollback Plan

Each batch is independently revertable via git:

```bash
# Revert specific batch
git revert <batch-commit-hash>

# Full rollback
git reset --soft HEAD~<number-of-commits>
```

The `_FALLBACK_TYPES` in trace_types.py ensures the system degrades gracefully if canon is corrupted or missing.

---

## 9. Post-Phase 0 Verification Checklist

After all tasks and verification pass:

- [ ] No hardcoded `TRACE_TYPES` tuple in any Python file (only fallback)
- [ ] No `step_metadata` key in `step_order.json`
- [ ] No `required_spec_inputs` reference in any Python file
- [ ] No `extraction_intent` reference in any Python file
- [ ] No `step_artifacts` map in `cli.py`
- [ ] `canon-schema-alignment` command exists and passes with zero E-level errors
- [ ] All existing CLI commands still work
- [ ] All existing tests pass + new tests pass
- [ ] `inv` is an alias of `invariant` in canon (not a separate entry)
- [ ] `threat` exists as a canon trace type entry
- [ ] Matrix output structure unchanged (backward compatible)
- [ ] Zero regressions in existing spec validation
- [ ] Deferred items documented in `docs/plans/optimisation_backlog.md`

---

## 10. Review Findings Log

Findings from the v1.0 plan audit. Each finding has a disposition and the task it affected.

### CRITICAL

| ID | Finding | Disposition | Task |
|----|---------|-------------|------|
| C1 | T4 underscoped — only addressed entity indexing (Section A), missed link building (C), emission (D), coverage (E) | **Narrowed scope**: Option A — replace only Section A, keep C/D/E hardcoded | T4 |
| C2 | `threat` not in canon trace types — dynamic discovery would silently drop threats from matrix | **Fixed**: Add `threat` to canon in T0; add to `_FALLBACK_TYPES` in T1 | T0, T1 |
| C3 | T5 `_id`-prefix approach produces 17 false E550 errors (18 of 25 prefixes are local entity IDs); `_extract_id_prefixes` recursion bug misses nested `_id` fields | **Redesigned**: Replaced `_id`-prefix scanning with enum↔canon kind drift detection using explicit pairings + discovery scan | T5, T10 |

### HIGH

| ID | Finding | Disposition | Task |
|----|---------|-------------|------|
| H1 | Link-building topology in matrix.py has no dynamic discovery mechanism — hardcoded FR→API, API→Fixture, etc. | **Deferred**: Keep hardcoded (Option A) — these are business logic, not vocabulary | T4 (kept) |
| H2 | `validate_trace_integrity()` has 5 hardcoded schema strings at lines 113, 121, 207, 217, 240 | **Deferred**: Acknowledged as tech debt; function still works correctly | Backlog |

### MODERATE

| ID | Finding | Disposition | Task |
|----|---------|-------------|------|
| M1 | Extension handling bug at `matrix.py:333` — `any()` checks all artifact keys, not current artifact | **Deferred**: Noted in backlog; only affects projects using extensions | Backlog |
| M2 | `step_artifacts` map in `cli.py` (lines 656-678) should be explicitly removed, not just bypassed | **Fixed**: Added explicit removal note to T6 | T6 |
| M3 | Test fixtures in T9 need exact `downstream_consumers` values, not hand-waved computation | **Fixed**: Pre-computed exact test fixture values added to T9 | T9 |

### LOW / INFO

| ID | Finding | Disposition |
|----|---------|-------------|
| L1 | T0 must update both `trace_type.json` AND `manifest.json` (merge logic verified) | Confirmed — already in plan |
| L2 | T1 consumer safety requires T0→T1 ordering (step_11, fixtures_lint break otherwise) | Confirmed — T0→T1 dependency in batch ordering |
| L3 | forward_replay_check.py only uses `steps` array | Confirmed — not affected by step_metadata removal |
| L4 | migration/planner.py only uses `steps` array | Confirmed — not affected |
| I1 | downstream_consumers data verified 100% correct (22 entries, zero discrepancies) | Confirmed |
| I2 | No circular import risk between core/trace_types.py and canonical/registry.py | Confirmed |
