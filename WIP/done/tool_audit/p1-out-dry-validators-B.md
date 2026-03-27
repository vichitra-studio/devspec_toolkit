# P1-B1: Validators DRY Analysis (Run B)

## Executive Summary

23 `_load_*` functions confirmed across 21 validator files. The `_load_fr_ids` pattern is duplicated 6 times, `_load_api_ids` 5 times, `_load_capability_ids` 2 times, `_load_nfr_ids` 2 times. Total duplicated LOC: ~350. A single shared helper could replace all 15 non-step14 loaders. Step 14's 4 loaders need a separate abstraction due to their `artifact_path` parameter.

## Findings

### FINDING-DV1: _load_fr_ids duplicated 6 times
- **Severity**: high
- **Category**: DRY_VIOLATION
- **Locations**: step_05.py:85, step_06.py:117, step_07.py:83, step_08.py:86, step_12.py:122, step_13a.py:101
- **Duplicate LOC**: ~120 (6 copies x ~20 lines each)
- **Common Pattern**: Scan spec_dir for `04_*.json`, parse JSON, extract `fr_id` from `functional_requirements` array, return `set[str] | None`.
- **Differences**: (a) Guard style: step_05/step_07 use inline conditional `os.listdir(spec_dir) if os.path.isdir(spec_dir) else []`; step_06/step_08/step_12/step_13a use separate `if not os.path.isdir: return None` guard. (b) Variable names: `fr` vs `item` vs `req`. (c) Type hints: `Optional[Set[str]]` vs `set[str] | None`. (d) Intermediate variables: step_06 uses `items = data.get(...)`. All are functionally equivalent.
- **Recommendation**: Extract to `validation/validators/_loaders.py` as `load_upstream_ids(toolkit_root, step_prefix, array_key, id_field) -> set[str] | None`.

### FINDING-DV2: _load_api_ids duplicated 5 times
- **Severity**: high
- **Category**: DRY_VIOLATION
- **Locations**: step_06.py:139, step_08.py:108, step_11.py:135, step_13a.py:123, step_15.py:81
- **Duplicate LOC**: ~100 (5 copies x ~20 lines each)
- **Common Pattern**: Scan spec_dir for `05_*.json`, parse JSON, extract `api_id` from `apis` array.
- **Differences**: step_11.py uses fallback `data.get("apis", data.get("endpoints", []))` and extracts `a.get("api_id", a.get("endpoint_id", ""))`. step_15.py uses fallback `data.get("apis", data.get("contracts", []))`. Other 3 copies are simple.
- **Recommendation**: Same shared helper with optional fallback_key parameter.

### FINDING-DV3: _load_capability_ids duplicated 2 times
- **Severity**: medium
- **Category**: DRY_VIOLATION
- **Locations**: step_04.py:63, step_09.py:52
- **Duplicate LOC**: ~40
- **Common Pattern**: Scan spec_dir for `01_*.json`, extract `capability_id` from `capabilities` array.
- **Differences**: Identical logic, same guard style.
- **Recommendation**: Extract to shared helper.

### FINDING-DV4: _load_nfr_ids duplicated 2 times
- **Severity**: medium
- **Category**: DRY_VIOLATION
- **Locations**: step_08.py:152, step_12.py:145
- **Duplicate LOC**: ~40
- **Common Pattern**: Scan spec_dir for `07_*.json`, extract `nfr_id` from `nfrs` array.
- **Differences**: Identical logic.
- **Recommendation**: Extract to shared helper.

### FINDING-DV5: step_14 has 4 unique loaders with artifact_path signature
- **Severity**: medium
- **Category**: ABSTRACTION_MISSING
- **Locations**: step_14.py:152 (_load_step09_milestone_ids), step_14.py:184 (_load_step09_tech_stack_names), step_14.py:203 (_load_step04_fr_ids), step_14.py:228 (_load_step01_cap_ids)
- **Duplicate LOC**: ~100
- **Common Pattern**: Build candidate paths from `artifact_path` parent + toolkit_root fallback, load first existing candidate, extract IDs.
- **Differences**: Each loads different data from different step files. Signature takes `(toolkit_root, artifact_path)` instead of just `(toolkit_root)`.
- **Recommendation**: Extract a `load_sibling_artifact(toolkit_root, artifact_path, filename) -> dict | None` helper. Keep extraction logic per-caller.

### FINDING-DV6: Repeated kebab-case regex patterns across validators
- **Severity**: medium
- **Category**: DRY_VIOLATION
- **Locations**: step_04.py:6, step_06.py:8-9, step_07.py:10, step_08.py:8-9, step_12.py:10-11, step_13a.py:8, step_14.py:10-12, step_15.py:44
- **Duplicate LOC**: ~16
- **Common Pattern**: `re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")` or prefixed variants like `^fr-[a-z0-9]+(?:-[a-z0-9]+)*$`.
- **Differences**: Some are module-level constants, some are inline. Prefix varies by entity type.
- **Recommendation**: Extract `KEBAB_RE` and a `make_prefixed_kebab_re(prefix)` factory to shared module.

### FINDING-DV7: upstream_map pattern duplicated in step_08, step_12, step_13a
- **Severity**: medium
- **Category**: DRY_VIOLATION
- **Locations**: step_08.py:41-46, step_12.py:42-45, step_13a.py:35-38
- **Duplicate LOC**: ~30
- **Common Pattern**: Build `upstream_map: dict[str, tuple[set|None, str, str]]` mapping prefix -> (id_set, filename, label), then emit W590 once per missing upstream, then iterate targets to check E590.
- **Differences**: Different prefixes included per step. Otherwise identical pattern.
- **Recommendation**: Extract the upstream_map validation loop to a shared `check_cross_step_refs(targets, upstream_map, errors, context_label)` function.

### FINDING-DV8: Import patterns inconsistent across validators
- **Severity**: low
- **Category**: DRY_VIOLATION
- **Locations**: All 21 validator files
- **Duplicate LOC**: N/A (style issue)
- **Common Pattern**: All import `json`, `os`. Most import `re`, `typing`. Some use `from __future__ import annotations`, others don't.
- **Differences**: step_01/step_02 import `jsonschema`, `SchemaRegistry`, `trace_types`. step_11 imports `warnings`, `trace_types`. Others are self-contained. Type hint style varies: `Optional[Set[str]]` vs `set[str] | None`.
- **Recommendation**: Standardize on `from __future__ import annotations` + modern type hints everywhere.

### FINDING-DV9: Estimated LOC reduction from deduplication
- **Severity**: info
- **Category**: DRY_VIOLATION
- **Locations**: All validator files with _load_* functions
- **Duplicate LOC**: ~350 total across all _load_* functions
- **Common Pattern**: With a shared `_loaders.py` module (~60 LOC for generic helper + per-step config), net reduction would be ~290 LOC (350 removed, 60 added).
- **Recommendation**: Create `tools/specdev_tools/validation/validators/_loaders.py` with: `load_upstream_ids(toolkit_root, step_prefix, array_key, id_field)`, `load_sibling_artifact(toolkit_root, artifact_path, filename)`, `KEBAB_RE`, `make_prefixed_kebab_re()`, `check_cross_step_refs()`.

## PASS

- Error message formatting is reasonably consistent across validators (E590/W590 codes used correctly).
- All validators return `list[str]` consistently (no mixed return types).
- Cross-step reference checking logic is correct in all validators examined.
- step_16a/16b/16c properly delegate to step_16 base validator via composition.
- trace_refs validation is handled by individual validators appropriate to their step context.
