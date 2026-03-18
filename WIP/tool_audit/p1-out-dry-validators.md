# P1-B1: Validators DRY Analysis — Findings

## Executive Summary
23 `_load_*` functions across 21 validator files represent ~400 LOC of duplicated logic. The `_load_fr_ids` pattern is copied 6 times with cosmetic differences. A single shared helper could eliminate ~300 LOC. Beyond loaders, the `upstream_map` pattern is duplicated 3 times.

---

### FINDING-DV1: _load_fr_ids Duplicated 6 Times
- **Severity**: high
- **Category**: DRY_VIOLATION
- **Locations**: step_05.py:85, step_06.py:117, step_07.py:83, step_08.py:86, step_12.py:122, step_13a.py:101
- **Duplicate LOC**: ~120 (6 x ~20 lines)
- **Common Pattern**: Scan spec/ for 04_*.json, json.load, extract fr_id from functional_requirements array
- **Differences**: (a) Guard style: step_05/step_07 use inline conditional `os.listdir(spec_dir) if os.path.isdir(spec_dir) else []`; step_06/step_08/step_12/step_13a use separate `if not os.path.isdir: return None` guard. (b) Variable names: `fr` vs `item` vs `req`. (c) Type hints: `Optional[Set[str]]` vs `set[str] | None`
- **Recommendation**: Extract to `core/loaders.py::load_ids(toolkit_root, step_prefix, json_key, id_field) -> set[str] | None`

### FINDING-DV2: _load_api_ids Duplicated 5 Times
- **Severity**: high
- **Category**: DRY_VIOLATION
- **Locations**: step_06.py:139, step_08.py:108, step_11.py:135, step_13a.py:123, step_15.py:81
- **Duplicate LOC**: ~100 (5 x ~20 lines)
- **Common Pattern**: Scan spec/ for 05_*.json, extract api_id from apis array
- **Differences**: step_11.py also checks `endpoints` key and `endpoint_id` field (backward compat). step_15.py also checks `contracts` key. Others only check `apis`/`api_id`.
- **Recommendation**: Shared helper with optional fallback keys parameter

### FINDING-DV3: _load_capability_ids Duplicated 2 Times
- **Severity**: medium
- **Category**: DRY_VIOLATION
- **Locations**: step_04.py:63, step_09.py:52
- **Duplicate LOC**: ~40 (2 x ~20 lines)
- **Common Pattern**: Scan spec/ for 01_*.json, extract capability_id from capabilities array
- **Differences**: Identical logic, only variable naming differs
- **Recommendation**: Same shared helper

### FINDING-DV4: _load_nfr_ids Duplicated 2 Times
- **Severity**: medium
- **Category**: DRY_VIOLATION
- **Locations**: step_08.py:152, step_12.py:145
- **Duplicate LOC**: ~40 (2 x ~20 lines)
- **Common Pattern**: Scan spec/ for 07_*.json, extract nfr_id from nfrs array
- **Differences**: Identical logic
- **Recommendation**: Same shared helper

### FINDING-DV5: step_14 Loaders Use Different Signature
- **Severity**: medium
- **Category**: ABSTRACTION_MISSING
- **Locations**: step_14.py:152, step_14.py:184, step_14.py:203, step_14.py:228
- **Duplicate LOC**: ~100 (4 functions, ~25 lines each)
- **Common Pattern**: Build candidates list from artifact_path parent + toolkit_root/spec/, try each
- **Differences**: Takes (toolkit_root, artifact_path) instead of (toolkit_root). Uses Path objects. Resolves sibling files relative to artifact.
- **Recommendation**: Shared helper with optional artifact_path parameter: `load_ids(toolkit_root, step_prefix, json_key, id_field, artifact_path=None)`

### FINDING-DV6: upstream_map Pattern Duplicated 3 Times
- **Severity**: medium
- **Category**: DRY_VIOLATION
- **Locations**: step_08.py:41-56, step_12.py:42-55, step_13a.py:35-48
- **Duplicate LOC**: ~45 (3 x ~15 lines)
- **Common Pattern**: Build dict mapping prefix -> (id_set, filename, type_label), emit W590 once per missing upstream, then validate targets against the map
- **Differences**: Different prefix sets (step_08 has fr/api/inv/nfr; step_12 has fr/nfr; step_13a has fr/api)
- **Recommendation**: Extract `check_upstream_refs(targets, upstream_map, errors)` helper

### FINDING-DV7: Kebab-case ID Regex Duplicated Across Files
- **Severity**: low
- **Category**: DRY_VIOLATION
- **Locations**: step_04.py:6, step_06.py:8-9, step_07.py:10, step_08.py:8-9, step_12.py:10-11, step_13a.py:8, step_14.py:10-12, step_15.py:44
- **Duplicate LOC**: ~20
- **Common Pattern**: `re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")` with various prefixes (fr-, inv-, nfr-, fix-)
- **Differences**: Different prefix constraints but identical base pattern
- **Recommendation**: Central KEBAB_ID_RE in core/ with a factory: `kebab_id_re(prefix="fr")`

### FINDING-DV8: Import Pattern Inconsistency
- **Severity**: low
- **Category**: DRY_VIOLATION
- **Locations**: All 21 validator files
- **Duplicate LOC**: N/A (style issue)
- **Common Pattern**: All import json, os. Some use `from __future__ import annotations`, some don't. Type hints vary: `Optional[Set[str]]` vs `set[str] | None`, `List[str]` vs `list[str]`, `Dict[str, Any]` vs `dict[str, Any]`
- **Differences**: step_01, step_04, step_15 use old-style typing (List, Dict). Others use modern syntax.
- **Recommendation**: Standardize on `from __future__ import annotations` + modern syntax

### FINDING-DV9: validate.py Also Has _load_* Functions
- **Severity**: medium
- **Category**: DRY_VIOLATION
- **Locations**: validate.py:327-370 (_load_component_ids, _load_capability_ids, _load_nfrs_data, _load_monitoring_data)
- **Duplicate LOC**: ~50
- **Common Pattern**: Same loader pattern as validators but using _load_json_artifact helper. validate.py has its own shared abstraction but validators don't use it.
- **Differences**: validate.py uses a more generic _load_json_artifact(repo_root, file_path, filename) that checks both artifact sibling dir and spec/
- **Recommendation**: Unify: move _load_json_artifact to core/loaders.py, have all validators use it

## PASS

- step_16a/16b/16c correctly delegate to step_16 base validator (no duplication)
- Error message format is consistent within each file (E590/W590 codes)
- Cross-step reference checking logic is consistent (warn if upstream missing, error if ID not found)
- step_14's 4 loaders correctly handle artifact_path for sibling resolution
- _check_task_dependency_cycles (step_14) and _has_cycle (step_12) implement different cycle detection for different structures — NOT duplicates

**Estimated LOC reduction from deduplication: ~300 LOC (from ~400 duplicated to ~100 shared helpers)**
