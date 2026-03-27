# Review: Group 5 (P3 + P4 + P5 + P6)

Reviewed against: `WIP/tool_audit/p0-ground-truth-FINAL.md`

---

## p3-prompt-consolidation.md

### Issues Found

1. **MUST_FIX**: P3 references `WIP/tool_audit/p0-baseline.md` as a baseline input (line 51), but this file does not exist. The actual ground truth file is `WIP/tool_audit/p0-ground-truth-FINAL.md`. P0's output template (in `p0-prompt-baseline.md`) directs writing to `p0-baseline.md`, but it was never generated -- the final consolidated file is `p0-ground-truth-FINAL.md`. An agent running P3 will fail or hallucinate when it cannot find `p0-baseline.md`.

2. **SHOULD_FIX**: P3 says "Runs AFTER P1 (7 agents) and P2 (1 agent) complete" (line 17). This states 7 P1 agents, but the P1 input list on lines 23-30 shows exactly 7 P1 output files + 1 P2 output file = 8 files total. The "7 agents" count is consistent with the 7 `p1-out-*` files, so this is correct. No issue here -- retracted.

3. **SHOULD_FIX**: The cross-check instruction "match by topic/description" (line 77) is vague. WIP files are unstructured prose with no IDs. The prompt gives no heuristic for matching granularity -- should an agent match at the level of individual bullet points, sections, or entire files? Two agents could produce wildly different match counts. Add guidance such as: "Match at the individual finding level. A WIP finding is a distinct recommendation or observation, typically one bullet or paragraph."

4. **MINOR**: The baseline numbers on lines 53-61 are all correct per ground truth: 830 tests, 61 source files, 13228 LOC, 73 test files, 17709 LOC, 23 `_load_*` functions, 21 step validator files, 21 DEEP_VALIDATORS entries, 77 error codes (52 E + 25 W), 29 registry entries, 22 steps, 25 CLI subcommands, 133 fixture files, 22 fixture directories. All match.

5. **MINOR**: The P1/P2 input file list (8 files, lines 23-30) and WIP file list (10 files, lines 36-45) both match the review criteria counts. Complete.

### Clean

- All baseline numbers are factually accurate against ground truth.
- Output format is well-structured with AUDIT-NNN IDs, severity ranking, and target-file grouping.
- The "Findings by Target File" table (line 127-132) correctly anticipates P4's need for per-file grouping.

---

## p4-prompt-fix-plan.md

### Issues Found

1. **MUST_FIX**: P4 references `WIP/tool_audit/p0-baseline.md` as an input (line 24), which does not exist. Same issue as P3. Must be changed to `p0-ground-truth-FINAL.md` or the P0 prompt must be updated to actually produce `p0-baseline.md`.

2. **SHOULD_FIX**: The batch gate protocol (lines 86-100) says to revert with `git checkout -- <file>` on failure. However, the batch may contain multiple tasks that modified different files. The protocol only identifies the single failing file and reverts it. If a Batch 1 CREATE task is reverted, Batch 2 IMPORT tasks depending on it will all fail. The protocol should specify: "After reverting a Batch N task, check whether any tasks in Batch N+1 depend on the reverted task. If so, mark those downstream tasks as BLOCKED."

3. **SHOULD_FIX**: The prompt does not address the scenario where a single finding from P3 affects multiple files (e.g., a DRY violation spanning 10 validators). Rule 1 says "one task = one file," and Rule 3 says "multi-finding files: ONE task." But what about multi-file findings? The prompt should explicitly state: "A single AUDIT-NNN that spans multiple files becomes multiple FIX-NNN tasks, one per file, with explicit cross-references."

4. **SHOULD_FIX**: The "Conflict Check" at line 158 says "no two tasks in the same batch share a target file." This is a final verification step, but there is no instruction on what to do if a conflict is found beyond "merge into a single task or move one to a later batch." Moving a task to a later batch could break dependency ordering. Add: "If moving to a later batch, verify all of its dependencies are still satisfied in the earlier batches."

5. **SHOULD_FIX**: The prompt includes no handling for when a finding from multiple P1/P2 agents disagrees on the recommended fix. P3 deduplicates by keeping "the version with the most detail," but P4 has no guidance for when the P3 consolidated description contains contradictory recommendations for the same file.

6. **MINOR**: Baseline numbers on lines 27-31 are all correct: 830 tests, 23 `_load_*` functions, 21 step validators, 61 source files, 13228 LOC, 73 test files, 17709 LOC. All match ground truth.

7. **MINOR**: The FIX-NNN template (lines 67-79) covers CREATE/MODIFY/DELETE/MOVE change types and includes test gate, dependencies, and LOC estimate. Complete.

8. **MINOR**: The test gate commands include `source devspec_env/bin/activate` in the batch gate (line 89). Good. However, individual task test gates (line 77) show only `pytest tests/test_specific_file.py -x --tb=short` without venv activation. The P5 template adds it, so this is acceptable as P4 is a planning doc, not an execution doc.

### Clean

- Batch ordering logic (Foundation -> Consumer -> Tests -> Cleanup -> Research) is sound and dependency-correct.
- Severity filter (CRITICAL/HIGH/MEDIUM only, LOW/INFO to appendix) is well-defined.
- FIX-NNN template is thorough.
- Output structure cleanly chains from P3's AUDIT-NNN IDs.

---

## p5-prompt-fix-execution.md

### Issues Found

1. **MUST_FIX**: There is no escalation protocol for when a P5 agent discovers the fix plan is wrong. For example, if FIX-003 says "remove function X from file Y" but function X does not exist in file Y (because P3/P4 had stale information), the agent has no instructions beyond the 3-attempt retry. The retry protocol (lines 58-62) assumes the failure is in the agent's implementation, not in the plan itself. Add: "If the target file does not match the description (function does not exist, file structure differs from expected), report status as PLAN_ERROR with details. Do not attempt to improvise a different fix."

2. **MUST_FIX**: The per-task template (lines 24-72) constrains agents to "Modify ONLY the target file" (line 46), but for MOVE operations (line 50), the agent must "handle both source removal and destination creation" -- that is two files. The constraint on line 46 contradicts the MOVE instruction on line 50. Clarify: "For MOVE operations, both the source and destination files are in scope."

3. **SHOULD_FIX**: The failure protocol (lines 91-99) says to revert with `git checkout -- <target-file>`. But if the task's change type was CREATE (new file), `git checkout` will not remove a newly created file. It should say: "For CREATE tasks, use `rm <target-file>` instead of `git checkout`."

4. **SHOULD_FIX**: Cross-task conflict prevention (lines 101-105) says "If you discover two tasks in the same batch targeting the same file, STOP and merge them." But P5 agents are independent parallel agents -- they cannot coordinate a merge mid-execution. This instruction is only actionable by the orchestrator launching the batch, not by the individual task agents. Clarify who is responsible: "The orchestrator MUST verify no file conflicts exist before launching a batch. If a task agent discovers a conflict at runtime (e.g., file already modified), it should STOP and report CONFLICT."

5. **SHOULD_FIX**: The template's test gate (line 55) says `source devspec_env/bin/activate && {exact pytest command from P4}`. Good -- venv activation is present. However, the "Read the target file in full" instruction (line 41) does not account for CREATE tasks where the file does not yet exist. Add: "For CREATE tasks, skip step 1 (the file does not exist yet). For MODIFY, read the full file first."

6. **MINOR**: The final gate (lines 113-117) correctly expects "830+ tests passing" and uses `pytest tests/ -v` with venv activation. Matches the P4 final gate.

7. **MINOR**: The output report template (lines 129-163) is well-structured with per-batch tables, gate results, and deferred task tracking.

### Clean

- Batch execution order (sequential batches, parallel within batch) is correct.
- 3-attempt retry protocol is reasonable.
- Venv activation is consistently included in test commands.
- Report structure captures all necessary data for P6 consumption.

---

## p6-prompt-verification.md

### Issues Found

1. **MUST_FIX**: P6's "After Metrics" commands (lines 91-103) are NOT identical to P0's baseline commands. Differences:
   - P6 uses `pytest tests/ --collect-only -q` but P0 used `pytest tests/ --co -q` (equivalent, `--co` is short for `--collect-only`, so this is actually fine).
   - P6 is **missing** several P0 commands: source file count (`find tools/specdev_tools -name '*.py' | wc -l`), test file count (`find tests -name '*.py' | wc -l`), unit test file count, integration test file count, conftest count, schema registry entry count, CLI subcommand count, error code count, test fixture count, schema file count, and version check. P6 only runs 4 of P0's 15 commands but its output table (lines 162-167) expects 6 "After" metrics (source files, source LOC, test files, test LOC, `_load_*` functions, error codes). The commands to collect source file count, test file count, and error code count are missing from Task 5.

2. **MUST_FIX**: P6's "Baseline Numbers" table (line 29-44) references `p0-ground-truth-FINAL.md` in the heading, which is correct. However, the inputs table (line 23-27) references `WIP/tool_audit/p0-baseline.md` which does not exist. Same broken reference as P3 and P4.

3. **SHOULD_FIX**: P6 Task 2 (lines 62-70) says "If count decreased, identify which tests were removed and whether that was intentional." But it provides no criteria for determining intentionality. An agent cannot read the developer's mind. Provide guidance: "If tests were removed, check whether the removed tests correspond to deleted source code (from DELETE tasks in P5). If so, mark as EXPECTED. If tests were removed without corresponding source deletion, mark as UNEXPECTED_REGRESSION."

4. **SHOULD_FIX**: P6 Task 3 (lines 74-79) uses `grep -rn "def _load_" tools/specdev_tools/validation/validators/ | wc -l` which matches the P0 command exactly. Good. However, Task 5 (line 102) repeats the same command. This redundancy should be acknowledged or deduplicated.

5. **SHOULD_FIX**: P6's output structure (lines 113-171) includes a "Regression Report" section (line 143) but provides no template for what to include. Other sections have detailed table formats. Add a template: "For each regression, include: test name, file, traceback summary, likely cause (FIX-NNN reference)."

6. **MINOR**: All baseline numbers in the table (lines 33-44) are correct: 830 tests, 61 source files, 13228 LOC, 73 test files, 17709 LOC, 23 `_load_*` functions, 77 error codes (52 E + 25 W), 29 registry entries, 25 CLI subcommands, version 0.4.0 (pyproject.toml) and 0.3.0 mismatch (CLAUDE.md). All match ground truth.

7. **MINOR**: The "Research Alignment Progress" task (Task 4, lines 82-85) references `p2-out-research-alignment.md` which is consistent with P1/P2 output naming.

### Clean

- Finding-to-fix verification taxonomy (RESOLVED/PARTIALLY_RESOLVED/NOT_RESOLVED/REGRESSED) is clear and complete.
- Before/after metrics table format is well-designed.
- DRY verification is specific and measurable.
- Research alignment cross-reference is a good completeness check.

---

## Cross-Prompt Chain Validation

### P3 output -> P4 input

- **P3 output**: `WIP/tool_audit/p3-out-master-findings.md` with AUDIT-NNN IDs, severity ranking, and "Findings by Target File" table.
- **P4 input**: Expects `WIP/tool_audit/p3-out-master-findings.md` with AUDIT-NNN IDs. P4 references "AUDIT-001, AUDIT-005" in its FIX template.
- **Verdict**: CHAINS CORRECTLY. P3's AUDIT-NNN format matches what P4 consumes. P3's target-file grouping directly supports P4's one-task-per-file rule.

### P4 output -> P5 input

- **P4 output**: `WIP/tool_audit/p4-out-fix-plan.md` with FIX-NNN tasks containing target file, change type, description, test gate, dependencies, LOC estimate.
- **P5 input**: Per-task template expects FIX-NNN with all the same fields (task ID, target file, change type, audit reference, dependencies, description, test gate).
- **Verdict**: CHAINS CORRECTLY. Every field in P5's template has a direct source in P4's FIX-NNN template.

### P5 output -> P6 input

- **P5 output**: `WIP/tool_audit/p5-out-execution-report.md` with per-task status (PASS/FAIL/DEFERRED), LOC deltas, test gate results, and final test count.
- **P6 input**: Expects `WIP/tool_audit/p5-out-execution-report.md`. P6 Task 1 reads target files to verify fixes. P6 references p3 (AUDIT-NNN) and p4 (FIX-NNN) for cross-referencing.
- **Verdict**: CHAINS CORRECTLY. P6 has all four upstream files (p0, p3, p4, p5) in its inputs table.

### Broken Reference Chain

- **MUST_FIX**: P3, P4, and P6 all reference `WIP/tool_audit/p0-baseline.md` which does not exist. The P0 prompt (`p0-prompt-baseline.md`) instructs writing to `p0-baseline.md`, but the actual consolidated ground truth is `p0-ground-truth-FINAL.md`. Either:
  - (a) Run P0 to produce `p0-baseline.md`, or
  - (b) Update P3/P4/P6 to reference `p0-ground-truth-FINAL.md`.

### Missing Escalation Path

- **SHOULD_FIX**: There is no reverse-flow protocol across the chain. If P5 discovers the plan is wrong (target file does not match description), it cannot signal back to P4. If P6 discovers a fix does not address its finding, it cannot re-trigger P5. The chain is strictly forward-only with no error recovery across phases. At minimum, P5 should have a PLAN_ERROR status that P6 can interpret as "needs re-planning."

---

## Summary

- **Total issues: 18** (MUST_FIX: 5, SHOULD_FIX: 9, MINOR: 4)

| Severity | Count | Key Themes |
|----------|-------|------------|
| MUST_FIX | 5 | Broken `p0-baseline.md` reference (x3 across P3/P4/P6), P5 MODIFY-only constraint contradicts MOVE, P6 missing metric collection commands |
| SHOULD_FIX | 9 | Vague matching heuristic (P3), no downstream-blocking awareness in batch revert (P4), no escalation from P5 to P4, CREATE revert needs `rm` not `git checkout`, missing intentionality criteria for test removal (P6) |
| MINOR | 4 | Baseline numbers all verified correct, redundant `_load_*` count command in P6, template completeness |
