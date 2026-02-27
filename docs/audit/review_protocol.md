# Review Protocol — DevSpec Toolkit Audit Series

Shared protocol for all reviews (R1–R6). Every review MUST implement all phases defined here.

---

## Subagent Protocol

### Main Agent Rules (ALL REVIEWS)
- **FORBIDDEN**: Read, Edit, Write, Grep, Glob, Bash for file content in main agent
- **ALLOWED**: Spawn subagents, read text summaries, create TaskList, final report
- **Token budget**: < 5K tokens per review session in main agent
- All file reads → `Explore` subagent (fast, no isolation)
- All code/schema/prompt changes → `general-purpose` subagent with `isolation: "worktree"`
- All integration test runs → `general-purpose` subagent (no isolation)
- No nested subagents (Task tool forbidden within subagent tasks)
- Within each phase, independent subagents can launch together in a single message
- Reviews execute sequentially (R1→R2→R3→R4→R5→R6) — each review assumes all prior reviews are complete
- **Decision gates** (choosing between implementation options after investigation) are main-agent
  work. Example: R5 requires main agent to select option (a/b/c) after Phase 1 before launching Phase 2.
- **Shared files**: When a file was modified by a prior review, subagent instructions must include
  "read current state first" to build on prior changes, not overwrite them.

---

## Compact Output Format

Use these formats. Verbose prose wastes tokens.

### Part A: Findings Table

```
| ID | Sev | File:Line | Finding | Impact |
|----|-----|-----------|---------|--------|
| A-RN-01 | CRIT | path/file.py:42 | one-line description | one-line impact |
| A-RN-02 | HIGH | path/file.py:88 | one-line description | one-line impact |
```

Severity codes: `CRIT` | `HIGH` | `MED` | `LOW`

**Evidence block** — required for CRIT and HIGH only:
```
### Evidence
A-RN-01:
  "exact quoted code from the file"
```

### Part B: Atomic Implementation Plan

**Atomic Task Rules (strictly enforced):**
1. One task = one file changed (no exceptions — even if two files are trivially related)
2. Each code task → immediately followed by a test task (`T` prefix) or confirmation command
3. Each public API/error-code/schema-version change → followed by a doc task (`D` prefix)
4. Sequencing order within a review:
   - New error codes (`errors.py`) first — everything else may reference them
   - Core/registry modules second
   - Validators and linters third
   - Schemas fourth (after validators that reference them are fixed)
   - Prompts fifth (after schemas they reference are finalized)
   - Tests sixth (after all code targets are stable)
   - Docs/CHANGELOG last
5. No task may modify a file already modified by an earlier task in the same review
6. Every task must have a machine-verifiable acceptance criterion (a command, not prose)

**Task table format:**
```
| ID  | Pri | Deps    | File                        | Change summary         | Acceptance command              | Findings    |
|-----|-----|---------|-----------------------------|------------------------|---------------------------------|-------------|
| T01 | P0  | —       | tools/core/errors.py        | Add E561, E562, E563   | python -c "from specdev_tools.core.errors import *" | A-R4-01 |
| T02 | P0  | T01     | tests/test_errors.py        | Tests for E561-E563    | pytest tests/test_errors.py -v  | A-R4-01 |
| T03 | P1  | T01     | validation/traceability.py  | Add E561 check         | pytest tests/ -k traceability   | A-R4-02 |
| T04 | P1  | T03     | tests/test_traceability.py  | Tests for new check    | pytest tests/test_traceability.py -v | A-R4-02 |
| D01 | P3  | T01     | CHANGELOG.md                | Add entry for E561-563 | —                               | —           |
```

Priority codes: `P0` (blocker) | `P1` (high) | `P2` (medium) | `P3` (low/docs)

---

## Phase 4: Self-Verification Loop

Run AFTER completing Part A and Part B drafts, BEFORE writing findings to file.

**Subagent V1** (`general-purpose`, no isolation):
```
Read the draft Part A findings table and Part B task table.
Run all 7 checks. Report PASS or FAIL for each.

CHECK 1 — No assumptions:
  FAIL if any finding contains: "likely", "probably", "may", "could", "appears to", "seems to"
  Each must be replaced with verified evidence or removed entirely.

CHECK 2 — Verified references:
  FAIL if any finding's File:Line was not confirmed by a Phase 1 Explore subagent.
  Verification means: the Phase 1 subagent READ that file and QUOTED code from that exact line.
  A finding is NOT verified if Phase 1 only said "the file exists" without quoting the line.
  For each CRIT/HIGH finding, spot-check: does the evidence block contain a direct quote?
  If a finding references a line number that Phase 1 never quoted, mark it FAIL.
  ⚠️ ALSO CHECK PART B TASKS: Part B task descriptions include assumed line numbers drafted
  before Phase 1 ran. If Phase 1 evidence contradicts a task's line number (e.g., task says
  "Fix line 40" but Phase 1 shows the bug is on line 45), mark CHECK 2 FAIL and revise the
  task line number to match Phase 1's actual quoted evidence. Part B tasks are TEMPLATES
  until Phase 4 verifies them — Phase 4 is the source of truth for final line numbers.

CHECK 3 — Atomic tasks:
  FAIL if any task in Part B modifies more than one file.
  Split multi-file tasks into separate tasks with explicit dependencies.

CHECK 4 — Test coverage:
  FAIL if any task that modifies code (validators, linters, core modules) has no
  immediately following test task (T-prefix) in the table.
  Add the missing test task.

CHECK 5 — Documentation coverage:
  FAIL if any task that: (a) adds/removes error codes, (b) changes CLI commands,
  (c) bumps schema version, or (d) changes public function signatures — has no
  corresponding D-prefix documentation task.
  Add the missing doc task.

CHECK 6 — Dependency resolution:
  FAIL if any task's "Deps" column references a task ID that appears AFTER it
  in the table, or references a task from a different review without noting it.
  Reorder or add missing prerequisites.

CHECK 7 — Orphan findings:
  FAIL if any finding in Part A has no corresponding task in Part B.
  Add a task or mark the finding as "Documentation Only" with reason.

Output format:
CHECK 1: PASS | FAIL — [issue description if FAIL]
CHECK 2: PASS | FAIL — [issue description if FAIL]
...
CHECK 7: PASS | FAIL — [issue description if FAIL]

OVERALL: VERIFIED | NEEDS REVISION
If NEEDS REVISION: list the exact changes required to each failing section.
```

**If NEEDS REVISION**: revise Part A/B and re-run Subagent V1. Repeat until VERIFIED.
**Maximum iterations**: 3. If not VERIFIED after 3 iterations, flag remaining issues explicitly and proceed.

---

## Phase 5: Write Findings to File

Only after Phase 4 returns VERIFIED.

**Subagent W1** (`general-purpose`, no isolation):
```
First, ensure the output directory exists:
  mkdir -p docs/audit/findings

Then write the verified findings to the output file path specified in the review.
Use EXACTLY the compact format from review_protocol.md.

File structure:
---
# Review RN Findings — [Area Titles]
Generated: [date]
Status: VERIFIED (Phase 4 passed N/3 iterations)

## Part A: Findings
[compact table]

### Evidence
[evidence blocks for CRIT/HIGH only]

## Part B: Implementation Plan
[atomic task table]

## Verification Status
- CHECK 1 Assumptions: PASS
- CHECK 2 References: PASS
- CHECK 3 Atomic: PASS
- CHECK 4 Tests: PASS
- CHECK 5 Docs: PASS
- CHECK 6 Deps: PASS
- CHECK 7 Orphans: PASS
- Total findings: N (C crit, H high, M med, L low)
- Total tasks: N code + N test + N doc
---
```

---

## Phase 6: Post-Implementation Verification

Run AFTER all Part B tasks are executed (separate session from the review).

**Subagent P1** (`Explore`, no isolation):
```
Read the findings file. For each task in Part B:
1. Confirm the file was modified as described (read the file, check the change)
2. Note whether the acceptance command was run and passed

Then run the full verification suite:
1. pytest tests/ --tb=short -q
2. ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
3. SPECDEV_WARNINGS_AS_ERRORS=1 ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit

Check for regressions:
- Any new test failures not present before the review?
- Any new validation errors not in the pre-review baseline?
- Any finding in Part A with status UNRESOLVED?

Output format:
TASKS VERIFIED: N/N
FINDINGS ADDRESSED: N/N
TEST STATUS: PASS (N tests) | FAIL (list)
REGRESSIONS: NONE | [list]
OVERALL: IMPLEMENTATION VERIFIED | GAPS FOUND

If GAPS FOUND: produce a remediation task table using the same atomic format.
```

---

## Documentation Task Triggers

A `D`-prefix documentation task is REQUIRED for:

| Trigger | Target File | Content |
|---------|-------------|---------|
| New error code (Exxx/Wxxx) | `docs/developers/error-codes.md` or equivalent | Add code, message, trigger |
| New CLI command/flag | `docs/developers/cli-reference.md` or equivalent | Add command with usage example |
| Schema version bump | `CHANGELOG.md` | Add migration notes |
| New validator added | `docs/developers/validation.md` or equivalent | Add validator description |
| Error code deprecated/removed | `docs/developers/error-codes.md` or equivalent | Add deprecation notice, replacement |
| Breaking change to public API | `README.md` or equivalent | Update usage examples |

**BEFORE assigning doc tasks**: run an Explore subagent to list `docs/developers/` and identify the actual file names. The known structure includes:
- `docs/developers/tools/` — tool-specific guides (schema_differ.md, changelog_parser.md, align.md, etc.)
- `docs/developers/workflows/` — workflow guides
- `docs/developers/reference.md` — general reference

If the target documentation file does not exist, create it as part of the doc task.
Do NOT assign a doc task to a file that doesn't exist without also adding `(create)` to the task description.
