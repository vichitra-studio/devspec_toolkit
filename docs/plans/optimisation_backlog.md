# Optimisation Backlog

**Created**: 2026-03-01
**Source**: Phase 0 governance plan review (v2.0.0)
**Status**: ACTIVE

Items deferred from Phase 0 with full context for future implementation.

---

## Prioritised Backlog

### OPT-001: Extension Handling Bug in matrix.py (M1) -- COMPLETED

**Severity**: LOW
**File**: `tools/specdev_tools/validation/matrix.py:333`
**Origin**: Phase 0 review finding M1
**Phase**: Post-Phase 0
**Status**: COMPLETED (2026-03-01)

#### Problem

The extension indexing code uses `any()` across all artifact keys, not just the current artifact:

```python
# Line 333 — BUG
if "extension_generator" in schema or any(fn.startswith("ext_") for fn in artifacts.keys() if fn.endswith(".json")):
```

The `any(fn.startswith("ext_") ...)` iterates `artifacts.keys()` (all loaded artifacts), not just the current one. This means if ANY artifact key starts with `ext_`, the extension indexing triggers for ALL artifacts — causing false extension entries.

#### Impact

Only affects projects that use extension files (`ext_*.json`). The bug causes spurious entries in the extensions list but does not corrupt the main matrix or integrity checks.

#### Fix

Replace the `any()` check with a check against the current artifact path:

```python
# Correct: check current artifact, not all artifacts
artifact_key = path  # or however the current artifact is referenced
if "extension_generator" in schema or artifact_key.startswith("ext_"):
```

#### Resolution

Fixed by checking the current artifact key instead of iterating all artifacts with `any()`. No regressions. 578 tests pass.

#### Dependencies

None — can be fixed independently.

---

### OPT-002: validate_trace_integrity() Hardcoded Schema Strings (H2) -- COMPLETED

**Severity**: MEDIUM
**File**: `tools/specdev_tools/validation/matrix.py:113,121,207,217,240`
**Origin**: Phase 0 review finding H2
**Phase**: Post-Phase 0 (recommended before Phase A)
**Status**: COMPLETED (2026-03-01)

#### Problem

`validate_trace_integrity()` (lines 82–286) claims to be "generic" but contains 5 hardcoded schema-name checks:

| Line | Hardcoded String | Purpose |
|------|------------------|---------|
| 113 | `"01_capabilities"` | Index capability IDs for coverage check |
| 121 | `"02_system_sketch"` | Trigger system sketch integrity checks |
| 207 | `"03_glossary"` | Index glossary term IDs |
| 217 | `"04_fr_list"` | Trigger FR coverage checks against glossary |
| 240 | `"03_glossary"` | Trigger glossary integrity checks |

These perform step-specific structural validation (duplicate detection, cross-step coverage) beyond generic trace reference checking.

#### Impact

The function works correctly for all current steps. The hardcoding means:
- New steps with similar structural patterns won't automatically get integrity checks
- Adding/renaming schema files requires updating this function

#### Recommended Fix

Extract step-specific validation into per-step validator functions (similar to the `validators/step_*.py` pattern). The generic `validate_trace_integrity()` should only do generic trace reference checking. Step-specific checks should live in their respective validators.

This is a larger refactor and should be paired with the Category B cleanup (OPT-003).

#### Resolution

Extracted step-specific checks into `cross_artifact_checks.py` with 5 exported functions. `validate_trace_integrity()` reduced from ~200 to ~40 lines. Error message format preserved. 578 tests pass.

#### Dependencies

- OPT-003 (should be done together)
- Phase 0 must complete first (T4 dynamic indexing provides the pattern)

---

### OPT-003: Category B Hardcoded Business Rule Strings -- COMPLETED

**Severity**: LOW
**File(s)**:
- `tools/specdev_tools/validation/validators/step_02.py`
- `tools/specdev_tools/validation/validators/step_11.py`
- `tools/specdev_tools/validation/fixtures_lint.py`
- `tools/specdev_tools/validation/traceability_closure.py`
**Origin**: Phase 0 scope boundary decision
**Phase**: Post-Phase 0
**Status**: COMPLETED (2026-03-01)

#### Problem

These validators contain hardcoded trace type strings that define business rules (which trace types are valid in a specific context), not vocabulary definitions:

| File | Hardcoded Set | Purpose |
|------|---------------|---------|
| `step_11.py` | `{"api", "component"}` | Valid target types for threats |
| `step_11.py` | `{"fr", "api", "nfr", "invariant", "fixture", "doc", "capability"}` | Valid mitigation types |
| `fixtures_lint.py` | `normalize_trace_type(ttype) == "invariant"` | Special handling for invariant fixtures |
| `traceability_closure.py` | Various trace type checks | Closure validation |

#### Why Deferred

These are NOT vocabulary duplication — they're semantic rules about which trace types are valid in specific contexts. Changing them requires domain knowledge about each step's business logic.

Phase 0's G1 (canon-backed trace_types.py) ensures the vocabulary layer is DRY. The business rule layer is a separate concern.

#### Recommended Fix

Move these sets into step-specific schema validation rules or a configuration registry. Each set would be:
1. Documented with its business justification
2. Validated against canon trace types (all values must be valid trace types)
3. Discoverable via tooling

#### Resolution

7 files updated. 12+ hardcoded strings replaced with named frozenset constants, each with business rule documentation and canon drift detection via `warnings.warn()`. Runtime assertion added in `fixtures_lint.py` for pool/frozenset sync. `normalize_trace_type` added to `step_02.py` for consistency. Canon gaps closed: `charter-goal` and `glossary` added to `canon/kinds/trace_type.json` and `canon/manifest.json`.

#### Dependencies

- Phase 0 must complete first (canon-backed trace types provide the vocabulary)
- Should be paired with OPT-002 (validate_trace_integrity refactor)

---

### OPT-004: json_utils.py Location

**Severity**: LOW
**Origin**: Phase A scope
**Phase**: Phase A

#### Problem

`json_utils.py` may need to be relocated for better module organisation. Current location works but doesn't follow the package structure convention.

#### Dependencies

- Phase 0 must complete first

---

### OPT-005: Context Package Build

**Severity**: HIGH (blocks automation)
**Origin**: Primary automation objective
**Phase**: Phase A (blocked on Phase 0)

#### Problem

The context package builder needs Phase 0's governance fixes to be complete before it can:
- Use `downstream_consumers` from `step_order.json` for dependency-aware context assembly
- Use canon-backed trace types for dynamic entity resolution
- Use the alignment linter to validate context package integrity

#### Dependencies

- Phase 0 complete (all G1–G7 goals met)
- OPT-002 and OPT-003 recommended but not strictly blocking

---

### OPT-006: Skills and Hooks

**Severity**: MEDIUM
**Origin**: Automation architecture
**Phase**: Phase B

#### Problem

Claude Code skills and hooks for:
- Auto-validation after spec edits
- Governance-compliant commit message generation
- Matrix regeneration triggers
- Prompt-context integration

#### Dependencies

- Phase 0 complete
- OPT-005 context package (recommended before skills)

---

## Priority Matrix

| Item | Severity | Effort | Blocks | Recommended Order | Status |
|------|----------|--------|--------|-------------------|--------|
| OPT-005 | HIGH | LARGE | Automation | 1 (Phase A) | OPEN |
| OPT-002 | MEDIUM | MEDIUM | OPT-003 | 2 | COMPLETED (2026-03-01) |
| OPT-003 | LOW | MEDIUM | — | 3 (with OPT-002) | COMPLETED (2026-03-01) |
| OPT-006 | MEDIUM | LARGE | — | 4 (Phase B) | OPEN |
| OPT-001 | LOW | SMALL | — | Any time | COMPLETED (2026-03-01) |
| OPT-004 | LOW | SMALL | — | Any time | OPEN (deferred to Phase A) |

**Note**: Phase 0 governance goals G5 (prompt sanitization) and G6 (documentation) are also COMPLETED as of 2026-03-01. G5 removed "Context To Ingest" and "Extraction Intent" from 16 prompt files (05-16c). G6 created `docs/architecture/governance_architecture.md` with full coverage of the governance system.
