# Prompt Review: P1-B1 (p1-prompt-dry-validators.md)

## Claims Verified

| Claim | Source Line | Verified Against | Match? |
|-------|-----------|-----------------|--------|
| 21 step validator files | Line 14 | `ls tools/specdev_tools/validation/validators/step_*.py` | YES |
| step_01.py = 81 LOC | Line 18 | `wc -l` | YES |
| step_02.py = 167 LOC | Line 19 | `wc -l` | YES |
| step_02a.py = 17 LOC | Line 20 | `wc -l` | YES |
| step_16.py = 415 LOC | Line 35 | `wc -l` | YES |
| step_16c.py = 47 LOC | Line 38 | `wc -l` | YES |
| step_14.py = 250 LOC | Line 33 | `wc -l` | YES |
| 23 `_load_*` functions total | Line 42 | `grep -n "def _load_" validators/step_*.py` | YES (23 matches) |
| step_04.py:63 `_load_capability_ids` | Line 45 | grep output | YES |
| step_05.py:85 `_load_fr_ids` | Line 46 | grep output | YES |
| step_06.py:117 `_load_fr_ids` | Line 47 | grep output | YES |
| step_06.py:139 `_load_api_ids` | Line 48 | grep output | YES |
| step_07.py:67 `_load_canonical_stages` | Line 49 | grep output | YES |
| step_07.py:83 `_load_fr_ids` | Line 50 | grep output | YES |
| step_08.py:86 `_load_fr_ids` | Line 51 | grep output | YES |
| step_08.py:108 `_load_api_ids` | Line 52 | grep output | YES |
| step_08.py:130 `_load_inv_ids` | Line 53 | grep output | YES |
| step_08.py:152 `_load_nfr_ids` | Line 54 | grep output | YES |
| step_09.py:52 `_load_capability_ids` | Line 55 | grep output | YES |
| step_11.py:114 `_load_component_ids` | Line 56 | grep output | YES |
| step_11.py:135 `_load_api_ids` | Line 57 | grep output | YES |
| step_12.py:122 `_load_fr_ids` | Line 58 | grep output | YES |
| step_12.py:145 `_load_nfr_ids` | Line 59 | grep output | YES |
| step_13.py:78 `_load_governance_labels` | Line 60 | grep output | YES |
| step_13a.py:101 `_load_fr_ids` | Line 61 | grep output | YES |
| step_13a.py:123 `_load_api_ids` | Line 62 | grep output | YES |
| step_14.py:152 `_load_step09_milestone_ids` | Line 63 | grep output | YES |
| step_14.py:184 `_load_step09_tech_stack_names` | Line 64 | grep output | YES |
| step_14.py:203 `_load_step04_fr_ids` | Line 65 | grep output | YES |
| step_14.py:228 `_load_step01_cap_ids` | Line 66 | grep output | YES |
| step_15.py:81 `_load_api_ids` | Line 67 | grep output | YES |
| `_load_fr_ids`: 6 copies | Line 71 | `grep -l "def _load_fr_ids"` | YES (step_05, 06, 07, 08, 12, 13a) |
| `_load_api_ids`: 5 copies | Line 72 | `grep -l "def _load_api_ids"` | YES (step_06, 08, 11, 13a, 15) |
| step_14 loaders take `(toolkit_root, artifact_path)` | Line 79 | Reading step_14.py | YES |
| step_05 `_load_fr_ids` uses inline conditional | Line 87 | Reading step_05.py:85-104 | YES |
| step_06 `_load_fr_ids` uses separate guard | Line 88 | Reading step_06.py:117-136 | YES |
| step_07 `_load_fr_ids` uses `set[str] | None` type hint | Line 89 | Reading step_07.py:83 | YES |
| step_05 uses variable name `fr` | Line 87 | Reading step_05.py:98 | YES |
| step_06 uses variable name `item`, intermediate `items` | Line 88 | Reading step_06.py:128-130 | YES |

**All 23 _load_* entries verified: 23/23 correct (file, line number, signature).**
**All 21 LOC counts verified: 21/21 correct.**

## Issues Found

### MUST_FIX

None.

### SHOULD_FIX

**SF-1: Missing step_00 exclusion note**
The prompt says "All 21 step validator files" but does not note that step_00 has no validator. The ground truth (section 4.1) explicitly states "No `step_00.py` validator exists. Step 00 has no deep validator." An agent unfamiliar with the codebase might wonder why step_00 is absent. Adding a brief note would prevent confusion.

**SF-2: Incomplete _load_fr_ids body comparison -- only 3 of 6 copies compared**
The "Known Context" section (lines 83-91) compares step_05, step_06, and step_07 implementations of `_load_fr_ids`. However, there are 6 copies total (step_05, 06, 07, 08, 12, 13a). The remaining 3 are not described. Question 2 asks the agent to compare all copies, so this is partly mitigated, but the prompt could pre-seed more context to save tokens.

**SF-3: step_14 return types not fully specified**
The prompt notes step_14 has "different signature `(toolkit_root, artifact_path)`" but doesn't mention that the return types also differ from standard loaders. For example, `_load_step09_milestone_ids` returns `tuple[set[str], str | None]` (a tuple, not `Optional[Set[str]]`). This is a meaningful design difference worth flagging.

### MINOR

**M-1: Validators `__init__.py` omitted from file count context**
The prompt scopes "All 21 step validator files" but doesn't mention `validators/__init__.py` (11 LOC) which contains the `noqa: F401` re-export for `validate.py`'s `DEEP_VALIDATORS`. This file is relevant to DRY analysis since it's the glue between validators and the orchestrator.

**M-2: No mention of validators importing from core/**
Four validators (step_01, step_02, step_10, step_11) import from `core.trace_types` and two (step_01, step_02) also import `core.registry.SchemaRegistry`. These cross-package imports from within the validators are relevant to a DRY analysis (are these imports consistent? duplicated? could they be shared?). The prompt's scope says only to audit validators/ but these imports represent a shared pattern across validators.

**M-3: Output limit of 200 lines may be tight**
With 23 _load_* functions, 12 questions, and the required finding format, 200 lines is a challenging constraint. A thorough agent may need to truncate findings.

## Verdict: APPROVED_WITH_FIXES

The prompt is highly accurate. Every single fact claim (23 _load_* entries, all line numbers, all LOC counts, all function groupings, body comparison details) verified as correct against the live codebase. The SHOULD_FIX items are refinements that would improve agent output quality but do not represent errors. No hallucinations detected.
