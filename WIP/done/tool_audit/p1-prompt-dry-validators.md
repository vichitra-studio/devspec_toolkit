# P1-B1: Validators DRY Analysis

Agent Type: Explore (very thorough)
Repo Root: /Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/

### Objective

Find ALL DRY violations within the 21 step validator files exclusively. Identify duplicated patterns that could be extracted into shared helpers.

### Exclusive Scope

ONLY audit files in `tools/specdev_tools/validation/validators/*.py`. Do NOT audit linters, canonical modules, generation modules, migration modules, or test files. Those are covered by P1-B2 and other prompts.

All 21 step validator files (note: no `step_00.py` validator exists — Step 00 has no deep validator):

| LOC | File |
|-----|------|
| 81 | `validators/step_01.py` |
| 167 | `validators/step_02.py` |
| 17 | `validators/step_02a.py` |
| 111 | `validators/step_03.py` |
| 82 | `validators/step_04.py` |
| 105 | `validators/step_05.py` |
| 158 | `validators/step_06.py` |
| 99 | `validators/step_07.py` |
| 171 | `validators/step_08.py` |
| 71 | `validators/step_09.py` |
| 83 | `validators/step_10.py` |
| 154 | `validators/step_11.py` |
| 197 | `validators/step_12.py` |
| 112 | `validators/step_13.py` |
| 142 | `validators/step_13a.py` |
| 250 | `validators/step_14.py` |
| 102 | `validators/step_15.py` |
| 415 | `validators/step_16.py` |
| 46 | `validators/step_16a.py` |
| 45 | `validators/step_16b.py` |
| 47 | `validators/step_16c.py` |

### Known Context — _load_* Functions

There are exactly **23 `_load_*` functions** across these 21 files. Complete table with file:line:

```
step_04.py:63   _load_capability_ids(toolkit_root)
step_05.py:85   _load_fr_ids(toolkit_root)
step_06.py:117  _load_fr_ids(toolkit_root)
step_06.py:139  _load_api_ids(toolkit_root)
step_07.py:67   _load_canonical_stages(toolkit_root)
step_07.py:83   _load_fr_ids(toolkit_root)
step_08.py:86   _load_fr_ids(toolkit_root)
step_08.py:108  _load_api_ids(toolkit_root)
step_08.py:130  _load_inv_ids(toolkit_root)
step_08.py:152  _load_nfr_ids(toolkit_root)
step_09.py:52   _load_capability_ids(toolkit_root)
step_11.py:114  _load_component_ids(toolkit_root)
step_11.py:135  _load_api_ids(toolkit_root)
step_12.py:122  _load_fr_ids(toolkit_root)
step_12.py:145  _load_nfr_ids(toolkit_root)
step_13.py:78   _load_governance_labels(toolkit_root)
step_13a.py:101 _load_fr_ids(toolkit_root)
step_13a.py:123 _load_api_ids(toolkit_root)
step_14.py:152  _load_step09_milestone_ids(toolkit_root, artifact_path)
step_14.py:184  _load_step09_tech_stack_names(toolkit_root, artifact_path)
step_14.py:203  _load_step04_fr_ids(toolkit_root, artifact_path)
step_14.py:228  _load_step01_cap_ids(toolkit_root, artifact_path)
step_15.py:81   _load_api_ids(toolkit_root)
```

Grouped by function name:
- `_load_fr_ids`: 6 copies (step_05, step_06, step_07, step_08, step_12, step_13a)
- `_load_api_ids`: 5 copies (step_06, step_08, step_11, step_13a, step_15)
- `_load_capability_ids`: 2 copies (step_04, step_09)
- `_load_nfr_ids`: 2 copies (step_08, step_12)
- `_load_inv_ids`: 1 (step_08)
- `_load_component_ids`: 1 (step_11)
- `_load_canonical_stages`: 1 (step_07)
- `_load_governance_labels`: 1 (step_13)
- step_14 variants: 4 functions with different signature `(toolkit_root, artifact_path)` — loads from sibling spec files relative to the artifact. Return types also differ: e.g., `_load_step09_milestone_ids` returns `tuple[set[str], str | None]` (a tuple), not `Optional[Set[str]]` like the standard loaders

**IMPORTANT**: step_14's 4 loaders take an extra `artifact_path` parameter and resolve sibling spec files relative to the artifact, unlike all other loaders which use a fixed `spec/` directory. Flag these separately.

### _load_fr_ids Body Comparison (from ground truth section 4.5)

The implementations are **NOT identical** across files. Key differences:

- **step_05** (line 85): Inline conditional `for fn in os.listdir(spec_dir) if os.path.isdir(spec_dir) else []`, variable name `fr`, `Optional[Set[str]]` type hint
- **step_06** (line 117): Separate `if not os.path.isdir(spec_dir): return None` guard, variable name `item`, intermediate `items` variable, `Optional[Set[str]]` type hint
- **step_07** (line 83): Same inline conditional as step_05, variable name `fr`, `set[str] | None` type hint (newer syntax)

The remaining 3 copies (step_08, step_12, step_13a) are not compared here — question 2 asks you to compare all 6.

All six load FR IDs from step 04's `functional_requirements` array. Logic is functionally equivalent but implementations differ in style (guard style, variable names, type hint syntax).

### Questions (12)

**_load_* Deduplication (5 questions)**

1. Confirm all 23 `_load_*` function instances listed above. Read each body and classify as: (a) identical to another copy, (b) functionally equivalent but stylistically different, or (c) genuinely different logic.
2. For each group of same-named functions (`_load_fr_ids`, `_load_api_ids`, `_load_capability_ids`, `_load_nfr_ids`), compare the bodies line by line. Document the exact differences (guard style, variable names, type hints, return types).
3. Design a shared helper signature that could replace the common `_load_*` pattern. Consider: what parameters would it need (toolkit_root, step_number, json_key, id_field)? What return type?
4. The 4 step_14 variant loaders use a different signature `(toolkit_root, artifact_path)`. Can these share the same helper with an optional `artifact_path` parameter, or do they need a separate abstraction?
5. Estimate total LOC reduction if all 23 `_load_*` functions were replaced with calls to a shared helper. Count current duplicated LOC vs proposed.

**Other Patterns (7 questions)**

6. Is there repeated ID format validation (e.g., kebab-case checks, `^[a-z0-9]+(-[a-z0-9]+)*$` regex) across multiple validators? How many files duplicate this?
7. Are there repeated file discovery patterns (scanning `spec/` directory for JSON files matching a step pattern)?
8. Is `trace_refs` validation duplicated across validators? Which files validate trace_refs and how?
9. Is cross-step reference checking (e.g., "does this FR ID exist in step 04?") duplicated beyond just the `_load_*` pattern?
10. Are there repeated JSON parse-and-extract patterns (open file, json.load, navigate to key, extract IDs)?
11. Are error message formatting patterns consistent across validators, or does each file construct error messages differently?
12. Are import patterns consistent across the 21 files? Do they all import the same set of modules, or is there unnecessary variation?

### Output Format

Write to: `WIP/tool_audit/p1-out-dry-validators.md`

Use finding format:

```
### FINDING-DV{N}: {Title}
- **Severity**: critical | high | medium | low | info
- **Category**: DRY_VIOLATION | ABSTRACTION_MISSING
- **Locations**: {list of file:line for each duplicate}
- **Duplicate LOC**: {approximate lines duplicated}
- **Common Pattern**: {describe the shared logic}
- **Differences**: {what varies between copies}
- **Recommendation**: {proposed shared helper or refactoring}
```

End with a `## PASS` section listing patterns that are already well-factored.

Limit: 200 lines.
