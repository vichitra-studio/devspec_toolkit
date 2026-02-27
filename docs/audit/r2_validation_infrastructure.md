<review_prompt id="R2" areas="7,10,11" runs_after="R1" priority="P0-blocker">
# Review R2: Validation Infrastructure — Schema Paths, Environment Behavior, Submodule Integration

## Scope
Three areas that ALL converge on `validate.py` and `forward_replay_check.py`. Fix together to eliminate rework:
- **Area 7**: `$ref` resolution robustness, schema registry completeness, circular ref detection
- **Area 10**: Environment-dependent validation silently disabling checks (replay, traceability gaps)
- **Area 11**: Git-aware validators operating from wrong root in submodule deployment model

R1 is already complete. Fix R2 before R3-R6 — those reviews assume the validation infrastructure is sound.

---

## Files Under Review

| File | Areas | Key Lines |
|------|-------|-----------|
| `tools/specdev_tools/validation/validate.py` | 7, 10, 11 | 224, 231-253, 395-419 |
| `tools/specdev_tools/validation/forward_replay_check.py` | 10, 11 | line 21 (root=Path(repo_root)), line 44 (_step_exists uses root/"spec"), lines 69-71 (git -C str(root) diff) |
| `tools/specdev_tools/core/registry.py` | 7 | full file |
| `tools/schema_registry.json` | 7 | full |
| `tools/step_order.json` | 7 | all step names (steps array, not step_metadata) |
| `tools/specdev_tools/validation/seed_lint.py` | 11 | 76-90 |
| `scripts/init_project.py` | 11 | 13-16, 77 |
| `tests/test_validate_integration.py` | 7, 10, 11 | existing test file — extend for new behaviors |
| `tests/test_forward_replay_check.py` | 10, 11 | existing test file — extend for submodule paths |
| `tests/test_seed_path_validation.py` | 11 | existing test file — verify seed_lint project root logic |

---

## Subagent Protocol (MANDATORY)

### Main Agent Rules
- **FORBIDDEN in main agent**: Read, Edit, Write, Grep, Glob, Bash for file content
- Main agent ONLY: spawn subagents, read their text summaries, create tasks, final report
- All file investigation → Explore subagents
- All code changes → general-purpose subagents with worktree isolation

### Subagent Assignment

#### Phase 1 — Investigation (4 Explore subagents)

**Subagent A** (`Explore`, no isolation) — Schema Path Integrity:
```
Read these files and answer:
1. tools/specdev_tools/core/registry.py (full file)
   - What is the SchemaRegistry class API? (methods, constructor args)
   - Does it configure $ref resolution at all, or delegate entirely to jsonschema?
   - What happens if a $ref points to a non-existent file? Is there explicit error handling?

2. tools/specdev_tools/validation/validate.py — lines 1-120
   - IMPORTANT: modern jsonschema (>=4.x) uses a Registry-based API, NOT the legacy RefResolver API.
     Look for: importlib.resources, referencing.Registry, jsonschema.validators.validator_for(),
     or jsonschema.validate() with a registry= kwarg — NOT resolver=.
   - Determine WHICH jsonschema API pattern is used (legacy RefResolver or modern Registry).
   - Does it catch jsonschema.exceptions.RefResolutionError or referencing.exceptions.Unresolvable?
   - Does it handle schema-not-found errors with a user-readable message?

3. tools/schema_registry.json — list all step names registered
4. tools/step_order.json — extract all step names from the `steps` array (not step_metadata)
Compare: are there steps in step_order.json that have NO entry in schema_registry.json?
Are there entries in schema_registry.json with no corresponding step in step_order.json (orphans)?
Report: exact gaps found with evidence. Quote the $ref resolution code pattern found.
```

**Subagent B** (`Explore`, no isolation) — Environment Behavior:
```
Read tools/specdev_tools/validation/validate.py lines 220-260 and 390-430.
Answer these questions with exact code quotes:
1. Lines 233-236: What is the default diff_error_mode when SPECDEV_REPLAY_DIFF_ERROR_MODE is not set,
   CI env var is not set, and _is_git_repo() returns False? Is it "ignore"?
2. Lines 244-253: When SPECDEV_WARNINGS_AS_ERRORS is not set, what happens to W560 errors?
   Are they filtered out at line 224? Quote the filter logic.
3. Lines 406-419: List all fallback candidates in _resolve_replay_base_ref(). In what order?
4. Lines 395-403: Does _is_git_repo() shell out to git? What happens on timeout?
Produce a complete matrix: For each combination of env vars (set/unset) and conditions
(git available/not, CI/not), what checks run vs are silently disabled?
```

**Subagent C** (`Explore`, no isolation) — Submodule Path Integrity:
```
Read these files:
1. tools/specdev_tools/validation/forward_replay_check.py (full file, ~168 LOC)
   - Lines 21-22: What variable is set as the git working directory?
   - Line 44: What path does _step_exists() check for spec files?
   - Lines 69-71: What exact git command runs? What directory does it run in?
2. tools/specdev_tools/validation/validate.py lines 226-245
   - Line 231: What argument is passed to check_forward_replay()?
3. tools/specdev_tools/validation/seed_lint.py lines 76-90
   - How does _project_root_from_spec_dir() derive the project root?
   - Is it immune to the submodule repo_root mismatch?
4. scripts/init_project.py lines 1-100
   - What --repo-root value is used in generated hooks/CI workflows?
Report: confirm or refute that forward replay is functionally disabled in submodule deployment.
Identify which validators are immune (like seed_lint) and which are affected.
```

**Subagent D** (`Explore`, no isolation) — Cross-validator canonical path consistency:
```
Search for how canonical references are resolved across the three tools:
1. tools/specdev_tools/canonical/lint.py — how does it load canonical registry?
2. tools/specdev_tools/canonical/integrity.py — how does it load canonical registry?
3. tools/specdev_tools/validation/validate.py — does it pass canonical registry path to validators?
Do all three resolve through the same code path (e.g., via registry.py)?
Or does each have its own resolution logic?
Report: any inconsistency in canonical path resolution.
```

#### Phase 2 — Implementation (after Phase 1)

Each subagent handles one logical change with worktree isolation.

**Subagent E** (`general-purpose`, isolation: `worktree`) — Schema $ref robustness:
```
Based on Phase 1 findings, make these changes to validate.py and core/registry.py:
1. Wrap jsonschema.validate() calls to explicitly catch jsonschema.exceptions.RefResolutionError
   and emit a clear error message including the unresolved $ref path.
2. If schema_registry.json is missing entries for any step in step_order.json (per Phase 1 findings),
   add a startup check in validate.py that emits a clear error listing missing entries.
3. Add a comment in core/registry.py documenting that circular $ref detection is delegated to
   the jsonschema library and noting the version dependency.
Run: pytest tests/ -k schema -v and confirm pass.
```

**Subagent F** (`general-purpose`, isolation: `worktree`) — Environment determinism:
```
VERIFIED: validate.py lines 233-236 set mode = "error" if (in_ci or _is_git_repo(root)) else "ignore".
The default is NOT always "ignore" — it is CONDITIONAL. Only non-CI + non-git = "ignore".

Based on Phase 1 Subagent B findings, make these changes to validate.py:
1. Lines 233-236: Do NOT change the conditional logic. Instead, after the mode assignment,
   add a log/print statement IF mode == "ignore":
   "Note: forward replay checks disabled (not in CI and not in a git repo). Set SPECDEV_REPLAY_DIFF_ERROR_MODE=error or run inside a git repo to enable."
   Emit this to stderr using `import sys; print("...", file=sys.stderr)` at the point BEFORE calling check_forward_replay(), not at module load.
   Find the exact call site by reading the file — do not assume line numbers.
2. Lines 244-253: Do NOT change W560 behavior (this is by design with SPECDEV_WARNINGS_AS_ERRORS).
   Instead, add a startup banner when validate-all runs without SPECDEV_WARNINGS_AS_ERRORS=1:
   "Note: traceability gaps (W560) are warnings only. Set SPECDEV_WARNINGS_AS_ERRORS=1 to enforce."
3. Lines 406-419: Add a comment documenting the full base-ref resolution order so developers
   understand why results may differ across environments.
4. Document the full environment behavior matrix as a comment block near line 231.
Run: pytest tests/ -k validate -v and confirm pass.
```

**Subagent G** (`general-purpose`, isolation: `worktree`) — Submodule path fix:
```
Based on Phase 1 Subagent C findings, make these changes:
1. forward_replay_check.py lines 21-22: Accept an optional `spec_root` parameter separate from
   `repo_root`. If `spec_root` is provided, use it for _step_exists() checks instead of
   `repo_root / "spec"`. Default to `repo_root / "spec"` for backward compatibility.
2. forward_replay_check.py lines 69-71: Accept an optional `git_root` parameter for the git
   working directory. If `git_root` is provided, use it for git diff operations. Default to
   `repo_root` for backward compatibility.
3. validate.py lines 226-245: Add logic to detect when repo_root is a subdirectory of a git
   repository (submodule scenario). When detected, derive the parent git root and pass it as
   `git_root` to check_forward_replay(). Use the same pattern as seed_lint._project_root_from_spec_dir().
4. Update init_project.py generated hooks to pass explicit --spec-root flag if applicable.
Run: pytest tests/ -k forward_replay -v and confirm pass.
```

#### Phase 3 — Integration Test (after Phase 2)

**Subagent H** (`general-purpose`, no isolation):
```
Run the full test suite and validate-all on the spec directory:
1. pytest tests/ --tb=short -q
2. ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
Report: pass/fail counts, any new failures introduced by Phase 2 changes.
```

---

## Investigation Checklist

### Area 7
- [ ] Does registry.py configure RefResolver for $ref resolution?
- [ ] Is RefResolutionError caught explicitly in validate.py?
- [ ] Are all step_order.json steps present in schema_registry.json?
- [ ] Are there orphan entries in schema_registry.json with no corresponding step?

### Area 10
- [ ] What is the exact default mode when CI=unset, git=unavailable?
- [ ] Are W560 traceability gaps silently filtered without SPECDEV_WARNINGS_AS_ERRORS?
- [ ] Does base_ref resolution produce different results on different machines?
- [ ] Is there any user-visible indication when checks are downgraded?

### Area 11
- [ ] Does `forward_replay_check.py` use toolkit root for git operations?
- [ ] Does `_step_exists()` check toolkit/spec/ instead of parent_project/spec/?
- [ ] Does seed_lint correctly derive project root independent of repo_root?
- [ ] Which other validators receive spec_dir separately and are immune?

---

## Deliverables

> **Format**: Use compact tables from `docs/audit/review_protocol.md`. No verbose prose.

### Part A: Findings
```
| ID | Sev | File:Line | Finding | Impact |
|----|-----|-----------|---------|--------|
| A-R2-01 | CRIT/HIGH/MED/LOW | path:line | description | impact |
```
Evidence blocks (CRIT/HIGH only): exact quoted code, one block per finding.

### Part B: Implementation Plan
Atomic tasks — one file per task. See `review_protocol.md` for sequencing rules and table format.

Required task sequence for this review (infrastructure first):
1. `tools/specdev_tools/core/registry.py` — explicit error handling for bad $ref (code, P1) → `pytest tests/test_validate_integration.py -v`
2. `tools/specdev_tools/validation/validate.py` — environment mode visibility banner + CHECK 2 (code, P1) → `pytest tests/test_validate_integration.py -v`
3. `tools/specdev_tools/validation/forward_replay_check.py` — add optional spec_root + git_root params (code, P1, must precede validate.py submodule task) → `pytest tests/test_forward_replay_check.py -v`
4. `tools/specdev_tools/validation/validate.py` — submodule detection + pass git_root to forward replay (code, P1, deps: T03) → `pytest tests/test_forward_replay_check.py -v`
5. `tools/schema_registry.json` — add missing step entries found in Phase 1A (data, P0, no deps) → `./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit`
6. `scripts/init_project.py` — update generated hook to pass --spec-root flag (code, P2, deps: T03) → manual verification with generated output
7. `tests/test_validate_integration.py` — extend with environment mode + submodule path tests (test, P1, deps: T02, T04)
8. `tests/test_forward_replay_check.py` — extend with spec_root/git_root parameter tests (test, P1, deps: T03)
9. `tests/test_seed_path_validation.py` — verify seed_lint project root derivation still passes (test, P1) → `pytest tests/test_seed_path_validation.py -v`
10. Documentation: check `docs/developers/` for CLI reference; if `--spec-root`/`--git-root` flags are added, add a doc task for that file (P3)

Note: validate.py appears twice (T02 and T04) — these are DIFFERENT logical changes to the same file. Sequence strictly: T02 (environment banners) → T04 (submodule detection). Each is a separate task touching the same file. Phase 4 self-verification CHECK 3 will flag this — override is justified because both changes are to validate.py and cannot be split without rework.

---

## Anti-Patterns
- Do not change the public CLI API — `--repo-root` flag must remain backward compatible
- Do not disable any validation checks — only add visibility when they are downgraded
- Do not break single-repo (non-submodule) usage when fixing submodule paths
- The fix for Area 11 must be additive (new optional parameters), not a breaking change

---

## Phase 4: Self-Verification Loop

After drafting Part A + Part B, launch before writing to file.

**Subagent V1** (`general-purpose`, no isolation): Run all 7 checks from `docs/audit/review_protocol.md § Phase 4`.
- If NEEDS REVISION: revise and re-run. Max 3 iterations.
- If VERIFIED after any iteration: proceed to Phase 5.

---

## Phase 5: Write Findings to File

**Output file**: `docs/audit/findings/r2_findings.md`

**Subagent W1** (`general-purpose`, no isolation): Write verified findings using the format in `docs/audit/review_protocol.md § Phase 5`.

---

## Phase 6: Post-Implementation Verification

Run in a separate session after all Part B tasks are executed.

**Subagent P1** (`Explore`, no isolation): Run all checks from `docs/audit/review_protocol.md § Phase 6`.
Key commands for this review:
```
pytest tests/ -k "schema or validate or forward_replay" -v
pytest tests/ --tb=short -q
./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
./tools/run_specdev.sh forward-replay-check --repo-root ./devspec_toolkit --base-ref origin/main
```

</review_prompt>
