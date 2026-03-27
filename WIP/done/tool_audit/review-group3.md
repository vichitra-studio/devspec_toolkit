# Review: Group 3 (P1-C + P1-D)

Reviewed: 2026-03-17
Ground truth: `WIP/tool_audit/p0-ground-truth-FINAL.md`

---

## p1-prompt-hardcoding.md

### Issues Found

1. **MINOR** — Line 27: "Do NOT read all 134 Python files sequentially." The sum of source + test Python files is 61 + 73 = 134, which is correct, but this is ambiguous because it could be read as "134 files in scope" when the scope section (lines 12-14) already separately states 61 source + 73 test files. A reader might wonder where 134 comes from. Add a parenthetical: "(61 source + 73 test)".

2. **MINOR** — Line 19: Lists `.pre-commit-config.yaml (2 hooks)` in scope. Ground truth section 2.13 confirms 2 hooks, so fact is correct. However, the CI configuration file (`.github/workflows/ci.yml`) is not listed in the config scope even though question 7 asks about pre-commit hooks and CI env vars are mentioned in Known Context (line 68). If the agent encounters CI-related hardcoding it may not know whether to report it. Consider explicitly including or excluding CI config.

3. **MINOR** — Line 55: Error code family description says "1xx (canonical integrity), 2xx (cross-artifact drift), 3xx (proof/review closure), 4xx (canonical registry), 5xx (spec content quality)." Ground truth section 6.1 matches exactly. Clean.

4. **MINOR** — Line 71: "tools/UNKNOWN.egg-info/ exists (orphaned/stale)". This is accurate per ground truth section 13 but sits in "Known Context" rather than being framed as something to investigate. The agent may or may not flag this as hardcoding. Acceptable as-is since it is context not a directive.

### Clean

- **File counts**: 61 source files, 13,228 LOC, 73 test files, 17,709 LOC — all match ground truth exactly.
- **Schema registry**: 29 entries — matches ground truth (and correctly notes both P0 agents miscounted as 30).
- **Step count**: 22 steps — matches.
- **Canon system**: 29 files, 25 kind files — matches ground truth section 2.6.
- **Error system**: 77 total (52 E + 25 W), 18 PROMOTABLE_PAIRS, 7 non-promotable — all match ground truth section 6.1 exactly.
- **Version mismatch**: Correctly flagged CLAUDE.md 0.3.0 vs pyproject.toml 0.4.0.
- **Pre-commit hooks**: 2 hooks, correct trigger patterns — matches ground truth section 2.13.
- **CI jobs**: 4 jobs, correct env vars — matches ground truth section 2.14.
- **Step list**: All 22 steps enumerated correctly including substeps (02a, 13a, 16a-c).
- **Validator facts**: 21 files, 21 DEEP_VALIDATORS, 21 validate_step_* entries, 23 _load_* functions — all match ground truth sections 4.1-4.3.
- **Schema breakdown**: "24 schema files total (19 step + 4 core + 1 seed_manifest)" — matches ground truth section 2.3.
- **Grep-first strategy**: Provides specific patterns to search for (step numbers, schema URIs, magic numbers, version strings, path literals). Sufficiently actionable.
- **Questions**: 19 questions are well-scoped to hardcoding/assumptions/hallucinations. No bleed into test quality (P1-D) or DRY (P1-B) territory.
- **Exclusions**: Lines 129-133 explicitly exclude DRY violations (P1-B), test quality (P1-D), separation of concerns (P1-B2), test fixture data, and schema $id values in schema files. Non-contradictory and complete.
- **Output format**: Consistent with the series pattern. 200-line limit stated.

---

## p1-prompt-test-quality.md

### Issues Found

1. **MUST_FIX** — Line 14: "Unit test files (tests/test_*.py): 50 files, 14,690 LOC". Ground truth section 2.2 confirms 50 unit test files at 14,690 LOC. However, line 15 says "Integration test files (tests/integration/test_*.py): 21 files, 2,933 LOC". Ground truth confirms 21 integration test files at 2,933 LOC. The LOC sum is 14,690 + 2,933 + 46 + 40 = 17,709. All match. **Actually clean on re-check.** Downgrading — no issue here.

2. **SHOULD_FIX** — Line 27: "22 fixture directories + 1 top-level file (tests/fixtures/14_roadmap.json)". Ground truth section 2.10 says "133 total fixture files across 22 directories + 1 top-level file" and separately "130 JSON + 3 non-JSON in dependency_order/". P1-D line 16 says "133 files across 22 directories + 1 top-level file" which is correct. But P1-D line 26 says "130 JSON + 3 non-JSON in dependency_order/" — this is stated accurately. However, P1-D **never mentions the fixture count breakdown per directory** (the detailed table in ground truth section 2.10). An agent doing fixture analysis would benefit from knowing which step directories have the most fixtures (step_02 has 24, step_14 has 17, step_16 has 16). Consider adding at least the top 3 by count to help the agent prioritize.

3. **SHOULD_FIX** — Line 57: Shared fixtures listed as "(5): repo_root, schema_root, spec_root, canon_root, fixtures_root". Ground truth section 8 confirms the top-level conftest has **6** fixtures (repo_root, schema_root, spec_root, canon_root, fixtures_root, migration_prompts_root), while the integration conftest has **5** (same minus migration_prompts_root). The "(5)" count is for the **shared** fixtures (common to both), which is correct. And line 58 separately calls out migration_prompts_root as only in tests/conftest.py. So the data is accurate, but the phrasing "Shared fixtures (5)" could confuse an agent into thinking the top-level conftest only has 5 fixtures total. Rephrase to: "Shared fixtures (common to both conftest files, 5 of 6 top-level fixtures):" for clarity.

4. **SHOULD_FIX** — Lines 78-85: Source module coverage reference lists modules with LOC counts. Cross-checking against ground truth section 2.1:
   - `errors.py (186)` — matches ground truth (186 LOC). Correct.
   - `registry.py (85)` — matches. `trace_types.py (53)` — matches. `changelog_parser.py (394)` — matches.
   - `validation/: 18 modules` — ground truth lists 18 non-validator .py files in validation/ (validate.py, hallucination_lint.py, spec_quality_lint.py, forward_replay_check.py, matrix.py, seed_lint.py, cross_artifact_checks.py, fixtures_lint.py, docs_lint.py, invariants.py, governance.py, dependency_order_lint.py, extraction_intent_check.py, _extraction_intent_parser.py, canon_schema_alignment.py, dag_lint.py, traceability_closure.py, __init__.py). That is 18 files. Correct.
   - `canonical/: autofix.py (397), integrity.py (640), lint.py (472), registry.py (318)` — all match ground truth.
   - `generation/: prompt_generator.py (813), prompt_schema_sync.py (501), schema_differ.py (1331)` — all match.
   - `migration/: planner.py (335), runner.py (385), scripts/strip_generation_quality.py (66)` — all match.
   - `cli.py (757)` — matches.
   - `tools/core/json_utils.py (345)` — matches.
   - **Missing**: The list does not include `__init__.py` files from subpackages (canonical/__init__.py at 1 LOC, generation/__init__.py at 1 LOC, migration/__init__.py at 18 LOC, migration/scripts/__init__.py at 0 LOC, validation/__init__.py at 1 LOC, validators/__init__.py at 11 LOC, specdev_tools/__init__.py at 45 LOC). These are unlikely to need test coverage, so omission is acceptable, but the agent might miscount "modules that need coverage" if it cross-references against the total 61 source files. Add a note: "(__init__.py files excluded — 7 files, 77 LOC combined)".

5. **MINOR** — Line 50: R9 task descriptions say "R9 added new CLI commands (dag-lint, extraction-intent-check, env-check) and the 59x error code family (E590-E599, W590-W597)." Ground truth section 11 confirms: 59x family in errors.py, and new CLI commands dag-lint (line 170), extraction-intent-check (line 173), env-check (line 167) in cli.py. Accurate.

6. **MINOR** — Lines 119-126: R9 test overlap pairs listed. The prompt lists 6 pairs to check. This is reasonable but the prompt does not mention `test_r9_error_codes.py` (84 LOC) or `test_r9_cross_step.py` (1047 LOC) in the pairing analysis. These two R9 test files have no obvious pre-existing counterpart named in the list. The agent should still discover them via the question, but explicitly noting "test_r9_cross_step.py and test_r9_error_codes.py have no obvious pre-existing counterpart — confirm or find indirect overlap" would reduce ambiguity.

7. **MINOR** — Line 75: "Most of these spec files do NOT exist in the repo. Only spec/05_interface_contracts.json exists." This is accurate per ground truth section 2.9 (3 files: .gitkeep, 05_interface_contracts.json, common/seed_manifest.json). The statement also correctly addresses review criterion #4 — the prompt acknowledges this is the expected situation, not a hallucination.

8. **MINOR** — Line 85: `tools/core/json_utils.py (345 -- standalone, outside specdev_tools package)`. Ground truth section 13 confirms this is standalone. Correctly noted.

### Clean

- **Test counts**: 830 tests, 50 unit + 21 integration + 2 conftest = 73 total — all match ground truth.
- **LOC**: 17,709 total, 14,690 unit, 2,933 integration, 46 + 40 conftest — all match.
- **Fixture files**: 133 total, 130 JSON + 3 non-JSON — matches ground truth section 2.10.
- **Spec directory contents**: 3 files correctly listed — matches ground truth section 2.9.
- **R9 file list**: 10 files with correct LOC for each — all match ground truth section 2.2.
- **Conftest details**: REPO_ROOT resolution via parents[1] vs parents[2], migration_prompts_root difference — matches ground truth section 8 exactly.
- **test_step_11.py file I/O**: 7 load_json_file calls with correct line numbers — matches ground truth section 12.1.
- **spec/ three-way distinction** (lines 87-95): Actual I/O vs mock string literals vs spec_root fixture. Clear and actionable for an agent.
- **Questions**: 22 questions well-organized into 6 categories. No bleed into P1-B (DRY in source) or P1-C (hardcoding in source) territory. Test-focused throughout.
- **Exclusions**: Lines 161-165 exclude DRY in source (P1-B), hardcoding in source (P1-C), separation of concerns (P1-B2), and known-good facts (830 passing, 0 skips). Non-contradictory and complete.
- **Scope boundary**: P1-D correctly limits itself to tests/ and spec/ usage by tests. No bleed into source code analysis.
- **Output format**: Consistent with series pattern. Category enum includes TOKEN_WASTE which is test-specific and appropriate.

---

## Summary

- Total issues: 8 (MUST_FIX: 0, SHOULD_FIX: 3, MINOR: 5)

### SHOULD_FIX items

| # | File | Issue |
|---|------|-------|
| 1 | p1-prompt-test-quality.md | Add per-directory fixture count breakdown (top 3) to help agent prioritize fixture analysis |
| 2 | p1-prompt-test-quality.md | Clarify shared fixture count phrasing — "5 of 6 top-level fixtures" to avoid ambiguity |
| 3 | p1-prompt-test-quality.md | Note that __init__.py files (7 files, 77 LOC) are excluded from coverage reference to prevent agent miscount |

### MINOR items

| # | File | Issue |
|---|------|-------|
| 1 | p1-prompt-hardcoding.md | Add "(61 source + 73 test)" parenthetical to the "134 Python files" reference |
| 2 | p1-prompt-hardcoding.md | Consider explicitly including or excluding CI config file in scope list |
| 3 | p1-prompt-test-quality.md | Note that test_r9_cross_step.py and test_r9_error_codes.py lack obvious pre-existing counterparts |
| 4 | p1-prompt-test-quality.md | R9 and spec/ details are factually accurate (no hallucinations found) |
| 5 | p1-prompt-hardcoding.md | UNKNOWN.egg-info context note is informational, not actionable — acceptable |

### Verdict

Both prompts are factually accurate against the ground truth. No hallucinations detected. No MUST_FIX issues. The 3 SHOULD_FIX items are clarity improvements that would reduce agent ambiguity but would not cause incorrect results. Scope boundaries between P1-C and P1-D are clean with no overlap.
