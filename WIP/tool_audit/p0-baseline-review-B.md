# P0 Baseline Review (Agent B)

Reviewed at: 2026-03-17T18:44:05Z
Reviewer: Review Agent B (independent verification)

## Verification Results

All 19 baseline metrics independently verified by running the exact commands from the P0 prompt.

| Metric | Baseline Value | Independently Verified | Match? |
|--------|---------------|----------------------|--------|
| Tests collected | 830 | 830 (`pytest tests/ --co -q` => "830 tests collected in 0.13s") | YES |
| Tests passed | 830 | 830 (`pytest tests/ -q` => "830 passed in 35.89s") | YES |
| Source files (specdev_tools/) | 61 | 61 (`find tools/specdev_tools -name '*.py' \| wc -l`) | YES |
| Source LOC (specdev_tools/) | 13,228 | 13,228 (`find ... \| xargs wc -l \| tail -1` => "13228 total") | YES |
| Test .py files (all) | 73 | 73 (`find tests -name '*.py' \| wc -l`) | YES |
| Test LOC | 17,709 | 17,709 (`find tests -name '*.py' \| xargs wc -l \| tail -1` => "17709 total") | YES |
| Unit test files | 50 | 50 (`find tests -maxdepth 1 -name 'test_*.py' \| wc -l`) | YES |
| Integration test files | 21 | 21 (`find tests/integration -name 'test_*.py' \| wc -l`) | YES |
| Conftest files | 2 | 2 (`find tests -name 'conftest.py' \| wc -l`) | YES |
| _load_* functions | 23 | 23 (`grep -rn 'def _load_' tools/specdev_tools/validation/validators/ \| wc -l`) | YES |
| Schema registry entries | 29 | 29 (`python3 -c "import json; print(len(json.load(open('tools/schema_registry.json'))))"`) | YES |
| CLI subcommands | 25 | 25 (`grep -c 'sub.add_parser' tools/specdev_tools/cli.py`) | YES |
| Error codes total | 77 | 77 (regex count of `"[EW]\d{3}"` in errors.py) | YES |
| E-codes | 52 | 52 | YES |
| W-codes | 25 | 25 | YES |
| PROMOTABLE_PAIRS | 18 | 18 (`len(PROMOTABLE_PAIRS)`) | YES |
| Test fixture files | 133 | 133 (`find tests/fixtures -type f \| wc -l`) | YES |
| Schema files | 24 | 24 (`find schema -name '*.schema.json' \| wc -l`) | YES |
| pyproject.toml version | 0.4.0 | 0.4.0 (`grep 'version' tools/pyproject.toml` => `version = "0.4.0"`) | YES |

**Result: 19/19 metrics match. Zero discrepancies.**

## Ground Truth Cross-Reference (10+ metrics)

Cross-referencing the baseline against `p0-ground-truth-FINAL.md`:

| Metric | Baseline | Ground Truth | Match? |
|--------|----------|-------------|--------|
| Tests collected | 830 | 830 | YES |
| Tests passed | 830 | 830 | YES |
| Source files | 61 | 61 | YES |
| Source LOC | 13,228 | 13,228 | YES |
| Schema registry entries | 29 | 29 | YES |
| CLI subcommands | 25 | 25 | YES |
| _load_* functions | 23 | 23 | YES |
| Error codes total | 77 | 77 | YES |
| PROMOTABLE_PAIRS | 18 | 18 | YES |
| Test fixture files | 133 | 133 | YES |
| Unit test files | 50 | 50 | YES |
| Integration test files | 21 | 21 | YES |

**Result: All 12 cross-referenced metrics match the ground truth.**

## Issues Found

### MUST_FIX

1. **Missing test result detail beyond "830 passed"**: The baseline says "Tests passed: 830" but does not capture 0 failures, 0 skipped, 0 xfail, 0 errors. The ground truth explicitly states "Zero failures, zero skips, zero xfails." P6 (verification phase) has a table with columns for "Tests failed", "Tests skipped" that requires these values. If the baseline is the sole "before" snapshot and does not record these as 0, P6 has to re-derive them. **Impact**: P6 needs explicit before-values for failed/skipped/xfail columns. Without them the delta calculation is ambiguous. **Recommendation**: Add rows for "Tests failed: 0", "Tests skipped: 0", "Tests xfail: 0" or add a note: "830 passed, 0 failed, 0 skipped, 0 xfail."

### SHOULD_FIX

1. **Missing metrics needed by downstream phases**: The ground truth contains many more data points than the 19 captured in the baseline. Several of these are explicitly referenced in downstream prompts (see Missing Metrics Assessment below). Without them, P1 and P6 agents must re-derive values that have already been verified. This creates redundant work and risks inconsistency.

2. **Timestamp accuracy**: The baseline says `2026-03-17T18:42:25Z`. The current UTC time is `2026-03-17T18:44:05Z`, and the branch is still `codex/canonical-drift-review-plan`. Both are plausible for a capture ~2 minutes ago, so the timestamp is reasonable. However, the baseline does not record which commands were run or their raw output. If any metric ever comes into question, there is no audit trail. **Recommendation**: Consider adding a collapsed section with raw command output, or at minimum a note that commands from `p0-prompt-baseline.md` were run verbatim.

3. **Drift section is correct but could be more explicit**: The drift section says "None -- baseline matches ground truth." This is accurate (all 19 Actual values equal their Expected values). However, it does not call out that this was verified for all 19 rows. A more explicit statement like "All 19 metrics verified: Actual equals Expected for every row" would be clearer.

### MINOR

1. **No mention of the ground truth document version/timestamp**: The baseline references "Expected (from ground truth)" but does not cite which ground truth document or its consolidation timestamp (2026-03-17T19:30:00Z from `p0-ground-truth-FINAL.md`). Adding a reference line would improve traceability.

2. **Branch name not linked to expected value**: The branch `codex/canonical-drift-review-plan` is recorded but not compared against any expected value. This is fine since there is no "expected branch" in the ground truth, but noting this is informational.

3. **Markdown formatting**: The baseline is clean and well-formed. No placeholder text remains. The template from `p0-prompt-baseline.md` is fully populated. No issues.

## Missing Metrics Assessment

The ground truth (`p0-ground-truth-FINAL.md`) contains approximately 54 verified facts. The baseline captures 19 of them. The following metrics are **missing from the baseline but referenced by downstream phases**:

### Needed by P1-A (Structure & Wiring)

| Missing Metric | Ground Truth Value | P1-A Reference |
|---------------|-------------------|----------------|
| Step count (step_order.json) | 22 | P1-A question 3: "Does step_order.json's 22-step list match..." |
| DEEP_VALIDATORS entries | 21 | P1-A question 3 and known context section |
| Align sub-actions | 7 | P1-A question 6: "Is the align subcommand's 7-action set..." |
| --json flag subcommands | 2 | P1-A question 7 |
| Canon files | 29 | P1-A known context |
| Prompt files | 41 (22+19) | P1-A known context |
| Script files | 6 | P1-A known context |
| Version mismatch (CLAUDE.md says 0.3.0) | yes | P1-A question 14 and known context |
| Pre-commit hooks | 2 | P1-A known context |
| CI jobs | 4 | P1-A known context |
| validate_step_* entry points | 21 | P1-A context |
| cli.py LOC | 757 | P1-A file listing |
| errors.py LOC | 186 | P1-A file listing |

However, note that P1-A already embeds these values directly in its prompt (the "Known Context from Ground Truth" section). So while the baseline does not contain them, the P1-A prompt does. **This means P1-A will not fail**, but the baseline is not serving as the single source of truth it could be.

### Needed by P1-B1 (DRY Validators)

The P1-B1 prompt already embeds the full `_load_*` function table (all 23 with file:line locations) and per-file LOC. The baseline's `_load_* functions: 23` is sufficient as a count, but the detailed breakdown is in the ground truth and P1-B1 prompt, not the baseline.

### Needed by P6 (Verification)

| Missing Metric | Ground Truth Value | P6 Reference |
|---------------|-------------------|----------------|
| Tests failed | 0 | P6 before/after table has "Tests failed" column |
| Tests skipped | 0 | P6 before/after table has "Tests skipped" column |
| Version (CLAUDE.md) | 0.3.0 (mismatch) | P6 baseline numbers table includes this |

P6's "Baseline Numbers" section lists "Version (CLAUDE.md): 0.3.0 (mismatch)" as a tracked metric. This is not in the P0 baseline. However, P6 also explicitly cites `p0-ground-truth-FINAL.md` as its source, so it can find this value there.

### Assessment

The missing metrics are **not critical blockers** because:
- P1 prompts embed the needed values directly from the ground truth
- P6 references the ground truth document, not just the baseline
- P3 (consolidation) also directly references the ground truth

However, the baseline would be more self-contained and useful as a quick-reference "before" snapshot if it included at least these additional rows:
- Tests failed: 0, Tests skipped: 0, Tests xfail: 0
- Step count: 22
- DEEP_VALIDATORS entries: 21
- validate_step_* entry points: 21
- Version (CLAUDE.md): 0.3.0 (mismatch flag)

## Verdict

**APPROVED_WITH_FIXES**

The baseline is accurate -- all 19 metrics are independently verified and match both live codebase values and the ground truth. The template is fully populated with no placeholders remaining.

One MUST_FIX: add explicit "0 failed, 0 skipped, 0 xfail" to the test results (P6 needs these as before-values).

Two SHOULD_FIX items that would improve downstream utility: (1) add 4-5 additional metrics that P6 tracks, and (2) add a note about raw command output or audit trail.

No accuracy issues were found. No hallucinated values. The drift section correctly reports no drift.
