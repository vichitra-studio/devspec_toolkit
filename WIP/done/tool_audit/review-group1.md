> **ARCHIVE NOTE (2026-05-16):** Canonical trace_matrix path is now `spec/extras/trace_matrix.json`. The `tools/trace_matrix.json` references below reflect the state at the time of writing.

# Review: Group 1 (Plan + Baseline + P1-A)

Reviewed against: `WIP/tool_audit/p0-ground-truth-FINAL.md`
Reviewer: Claude Opus 4.6
Date: 2026-03-17

---

## 00-AUDIT-PLAN.md

### Issues Found

1. **MUST_FIX** -- P1-A agent count includes 8 `__init__.py` files but ground truth lists only 8 init files (including `migration/scripts/__init__.py` at 0 LOC). The plan line "All 6 `__init__.py` files" in the P1-A scope description says 6, but the P1-A prompt (p1-prompt-structure.md) correctly lists 8. The plan's P1-A scope description is inconsistent with the actual init file count of 8.

2. **SHOULD_FIX** -- P1-B2 scope says "All non-validator files in `validation/` (14 files)". Ground truth shows validation/ contains: `__init__.py`, `_extraction_intent_parser.py`, `canon_schema_alignment.py`, `cross_artifact_checks.py`, `dag_lint.py`, `dependency_order_lint.py`, `docs_lint.py`, `extraction_intent_check.py`, `fixtures_lint.py`, `forward_replay_check.py`, `governance.py`, `hallucination_lint.py`, `invariants.py`, `matrix.py`, `seed_lint.py`, `spec_quality_lint.py`, `traceability_closure.py`, `validate.py`, plus `validators/` subpackage. Excluding the `validators/` subpackage (21 step files + 1 `__init__.py` = 22 files), the remaining validation/ files total 18 (not 14). The "14 files" claim is incorrect.

3. **SHOULD_FIX** -- P1-B2 scope says "all files in ... `generation/` (3 files), `migration/` (5 files including scripts/)". Ground truth shows generation/ has 4 files (`__init__.py`, `prompt_generator.py`, `prompt_schema_sync.py`, `schema_differ.py`) and migration/ has 5 files (`__init__.py`, `planner.py`, `runner.py`, `scripts/__init__.py`, `scripts/strip_generation_quality.py`). The generation count of 3 is wrong (should be 4).

4. **SHOULD_FIX** -- P1-B2 scope says "all files in ... `canonical/` (4 files)". Ground truth shows canonical/ has 5 files (`__init__.py`, `autofix.py`, `integrity.py`, `lint.py`, `registry.py`). The count of 4 is wrong (should be 5).

5. **MINOR** -- Phase table says "P1: 7 agents (P1-A through P1-F)" but agents listed in the scope table are P1-A, P1-B1, P1-B2, P1-C, P1-D, P1-E, P1-F -- that is 7 agents, but the range "P1-A through P1-F" implies 6. The naming (with B1/B2 split) makes the "through P1-F" shorthand misleading.

6. **MINOR** -- The plan references "approximately 1550 lines total" for existing WIP files. This is unverified and could cause agents to set wrong expectations, but it is explicitly labeled "unverified" so the risk is low.

### Clean

- Test suite metrics (830 collected, 830 passed, 0 failed/skipped/xfail, 36.16s) match ground truth exactly.
- File counts for source files (61), source LOC (13,228), test .py files (73), test LOC (17,709), unit test files (50), integration test files (21), conftest files (2), schema files (24), schema registry entries (29), steps (22), canon files (29), prompt files (41), script files (6), spec files (3), test fixture files (133), test fixture directories (22) all match ground truth.
- CLI metrics (25 subcommands, 7 align sub-actions, 2 --json flag commands) match.
- Validator metrics (21 step validator files, 21 DEEP_VALIDATORS entries, 23 _load_* functions, 21 validate_step_* entry points) match.
- Error system metrics (186 LOC, 77 total codes, 52 E-codes, 25 W-codes, 18 PROMOTABLE_PAIRS, 7 non-promotable W-codes, 12 warnings.warn, 3 exception classes) match.
- Version mismatch correctly noted (CLAUDE.md 0.3.0 vs pyproject.toml 0.4.0).
- Code health metrics (0 TODO in specdev_tools, 1 TODO in tools/core, 1 noqa, 2 pre-commit hooks, 4 CI jobs) match.
- R9 metrics match ground truth.
- Conftest comparison matches ground truth.
- Import dependency direction matches ground truth.
- `_load_fr_ids` implementation differences match ground truth.
- P1 agent scope assignments are generally well-partitioned with clear non-overlap boundaries.

---

## p0-prompt-baseline.md

### Issues Found

1. **SHOULD_FIX** -- Command #11 (`grep -c 'sub.add_parser' tools/specdev_tools/cli.py`) counts CLI subcommands by grepping for `sub.add_parser`. This may not be robust if the variable name differs (e.g., `align` uses its own subparser). The ground truth confirms 25 via `sub.add_parser()` calls so it happens to work, but the prompt should note this caveat or use the more reliable method from the ground truth derivation.

2. **SHOULD_FIX** -- Command #12 counts error codes via regex `"[EW]\d{3}"` in errors.py. The ground truth verifies 77 codes this way, so the result will match. However, the regex `\"[EW]\d{3}\"` in the prompt's Python string has escaped double quotes that look correct for a shell-embedded Python script. The string escaping is fragile -- if an agent copies this with slightly different quoting, it could fail silently. Consider noting the expected output (77 total, 52 E, 25 W, 18 pairs) more prominently.

3. **MINOR** -- The prompt does not include commands for: canon file count, prompt file count, script file count, spec file count, step count (step_order.json), align sub-actions, --json flag commands, DEEP_VALIDATORS count, validate_step_* count, warnings.warn count, CI job count, pre-commit hook count, or any of the other metrics in the ground truth. This is acceptable since P0 is labeled "Baseline Capture" and the expected-value table covers the key metrics, but an executing agent might wonder why the template expects values (like "pyproject.toml version") that don't have a corresponding command. Command #15 covers version but the template also lists `_load_*` functions (command #9 covers this) which is good.

4. **MINOR** -- The output template includes `pyproject.toml version | 0.4.0` but the prompt command #15 is `grep 'version' tools/pyproject.toml | head -1` which will output something like `version = "0.4.0"`, not just `0.4.0`. A literal comparison might confuse an agent. Minor since any reasonable agent will extract the version number.

### Clean

- All 15 commands are syntactically correct bash that will run from the repo root.
- The output template's "Expected (from ground truth)" column matches the ground truth document exactly for all listed metrics.
- The "Drift from Ground Truth" section is a good safeguard against stale baselines.
- The prompt correctly specifies `devspec_env` (not `dev_env`) as the virtualenv name, matching the memory note.
- The template correctly expects 29 schema registry entries (not 30).
- All expected values in the template are factually correct per ground truth.

---

## p1-prompt-structure.md

### Issues Found

1. **MUST_FIX** -- Lists "All `__init__.py` files" with 8 entries but the list actually contains 8 items (including `validation/__init__.py` and `validation/validators/__init__.py`), which is correct. However, the `core/__init__.py` is listed as "12 LOC" -- ground truth confirms 12 LOC. The `migration/__init__.py` is listed as "18 LOC" -- ground truth confirms 18 LOC. The `validators/__init__.py` is listed as "11 LOC" -- ground truth confirms 11 LOC. **Actually, no issue here -- all LOC counts match.** Reclassifying: NOT an issue.

2. **MUST_FIX** -- The prompt says `tools/core/json_utils.py` has "345 LOC". Ground truth confirms 345 LOC. However, the prompt lists `core/` as having "4 files: `errors.py` (186 LOC), `registry.py` (85 LOC), `trace_types.py` (53 LOC), `changelog_parser.py` (394 LOC)". This refers to `tools/specdev_tools/core/`, which per ground truth has exactly these 4 files plus `__init__.py` (12 LOC). The prompt separately lists `__init__.py` in the init files section, so the "4 files" count for core/ excludes `__init__.py`. This is **ambiguous** -- an agent could think core/ only has 4 files total, missing the `__init__.py`. Should say "4 non-init files" or "5 files including __init__.py".

3. **SHOULD_FIX** -- The prompt says `tools/requirements.txt` lists "4 deps: jsonschema, pyyaml, jsonschema-specifications, pyjwt". Ground truth confirms the 4 deps with specific version constraints (`jsonschema>=4.21.1`, `pyyaml>=6.0.1`, `jsonschema-specifications>=2023.12.1`, `pyjwt>=2.8.0`). Omitting version constraints is acceptable since this prompt focuses on structure, but listing bare names could cause an agent to miss version-constraint issues.

4. **SHOULD_FIX** -- Question 16 asks "Are all 25 canon kinds referenced by at least one schema or validator? Are there unused kinds?" But ground truth shows 25 kind files in `canon/kinds/`. The question is well-formed, but the prompt does not list the 25 kind file names anywhere for the agent to reference. The agent would need to discover them independently. Consider adding the list or referencing the ground truth section.

5. **SHOULD_FIX** -- The prompt tells the agent to read `tools/trace_matrix.json` and notes it has "all-zero counters" and "last modified 2025-02-22". Ground truth confirms this. However, the prompt does not mention whether this file is gitignored or checked in. Since question 21 asks exactly this, the prompt should avoid pre-answering by stating "last modified 2025-02-22" (which implies it is tracked). The date is a fact from ground truth so it is acceptable as context, but it slightly biases the answer.

6. **SHOULD_FIX** -- The prompt says the agent should read `docs/` directory with "(extensive subdirectory tree: README.md, agents/, architecture/, audit/, developers/, ops/, plans/, prompts/)". Ground truth confirms this structure. But reading the entire docs/ tree (which has dozens of files per ground truth section 2.12) is potentially a huge amount of content for an agent with a 200-line output limit. The prompt should clarify whether to skim or exhaustively read every docs file.

7. **MINOR** -- The prompt says `tools/specdev_tools.egg-info/` has "6 files" and `tools/UNKNOWN.egg-info/` has "4 files". Ground truth confirms these counts. No issue.

8. **MINOR** -- The prompt says ".pre-commit-config.yaml (only 2 hooks: dag-lint and extraction-intent-check)". Ground truth confirms. No issue.

9. **MINOR** -- Question 15 asks about "22 prompt file names" but ground truth shows 22 step prompts (plus 19 migration templates = 41 total). The question specifically says "prompt file names" in context of step mapping, so 22 is correct. No issue, but could be clearer by saying "22 step prompt files".

10. **MUST_FIX** -- The prompt instructs the agent to read `tools/specdev_tools/cli.py` and states it is "757 LOC". Ground truth confirms 757 LOC. However, the prompt also says to read "all 25 subcommand registrations" but does not provide the line numbers for the subcommands. Ground truth lists all 25 with specific line numbers (line 49 through 173). Providing these line numbers would significantly help the agent. This is a **completeness gap** -- the ground truth has this data and it is directly relevant to the P1-A scope.

11. **SHOULD_FIX** -- The "Known Context from Ground Truth" section says "Schema registry maps 16a/16b/16c all to the same `schema/16_impl_context.schema.json`". This is correct per ground truth (section 2.4). However, this fact is relevant to question 2 (schema registry resolution) and the agent might not connect it. Consider cross-referencing it in the question.

12. **MINOR** -- Output limit "200 lines" is quite restrictive given 22 questions spanning wiring, structure, imports, packaging, and documentation. An agent may be forced to superficially answer questions to stay within the limit.

### Clean

- Repo root path is correct.
- All 25 CLI subcommand count matches ground truth.
- 7 align sub-actions correctly listed (status, diff, plan, apply, prompts, rollback, validate).
- 29 schema registry entries correctly stated (with note about agents' original miscount of 30).
- 22 steps in step_order.json correctly stated with complete step list.
- Version mismatch correctly flagged (CLAUDE.md 0.3.0 vs pyproject.toml 0.4.0).
- 2 --json flag subcommands correctly identified (validate, traceability-check).
- No step_00 validator correctly noted.
- CI configuration (4 jobs, env vars) correctly stated.
- tools/core/json_utils.py correctly identified as outside specdev_tools package.
- No __version__ in __init__.py correctly noted.
- tools/README.md title correctly quoted.
- Import dependency direction in "Known Context" matches ground truth exactly.
- 21 DEEP_VALIDATORS entries correctly stated.
- The question set is comprehensive and well-organized by category.
- Finding format template is clear and actionable.
- Exclusive scope boundaries are clearly delineated ("Does NOT audit...").
- 6 script files correctly listed with paths matching ground truth section 2.8.
- 29 canon files breakdown (1 manifest + 1 aliases.json + 2 schemas + 25 kind files) matches ground truth.
- 41 prompt files breakdown (22 step + 19 migration) matches ground truth.

---

## Summary

- Total issues: 14 (MUST_FIX: 2, SHOULD_FIX: 8, MINOR: 4)

### MUST_FIX (2)

| # | File | Issue |
|---|------|-------|
| 1 | 00-AUDIT-PLAN.md | P1-A scope says "6 `__init__.py` files" but there are 8 |
| 2 | p1-prompt-structure.md | core/ listed as "4 files" is ambiguous -- excludes `__init__.py` without saying so |

### SHOULD_FIX (8)

| # | File | Issue |
|---|------|-------|
| 1 | 00-AUDIT-PLAN.md | P1-B2 scope says "14 files" in validation/ (non-validator) but actual count is 18 |
| 2 | 00-AUDIT-PLAN.md | P1-B2 scope says generation/ has "3 files" but it has 4 |
| 3 | 00-AUDIT-PLAN.md | P1-B2 scope says canonical/ has "4 files" but it has 5 |
| 4 | p0-prompt-baseline.md | CLI subcommand grep may not be robust (happens to work but fragile) |
| 5 | p0-prompt-baseline.md | Error code regex command has fragile string escaping |
| 6 | p1-prompt-structure.md | Question 16 references "25 canon kinds" but doesn't provide the kind names |
| 7 | p1-prompt-structure.md | docs/ reading scope is unbounded for a 200-line output limit |
| 8 | p1-prompt-structure.md | CLI subcommand line numbers from ground truth not provided to agent |

### MINOR (4)

| # | File | Issue |
|---|------|-------|
| 1 | 00-AUDIT-PLAN.md | "P1-A through P1-F" implies 6 agents but B1/B2 split makes 7 |
| 2 | p0-prompt-baseline.md | Template expects some values without corresponding capture commands |
| 3 | p0-prompt-baseline.md | grep output format vs template format mismatch for version |
| 4 | p1-prompt-structure.md | 200-line output limit may be too restrictive for 22 questions |
