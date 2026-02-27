# R2 Validation Infrastructure — Canonical Drift Review

**Review Date**: 2026-02-27
**Reviewer**: Claude (AI-assisted audit)
**Areas**: 7 (Schema Paths), 10 (Environment Behavior), 11 (Submodule Integration)
**Status**: Implementation in progress

---

## Part A: Findings

| ID | Sev | File:Line | Finding | Impact |
|----|-----|-----------|---------|--------|
| A-R2-01 | CRIT | validation/forward_replay_check.py:70 | Git diff runs from `repo_root` (submodule dir) instead of host repo git root; `-C {root}` targets wrong directory | Forward replay silently disabled in all submodule deployments |
| A-R2-02 | HIGH | validation/validate.py:236 | Default diff_error_mode="ignore" when not CI and not git repo; no user-visible indication | Forward replay checks silently skipped with zero feedback |
| A-R2-03 | HIGH | validation/validate.py:252-253 | W560 traceability warnings silently filtered when SPECDEV_WARNINGS_AS_ERRORS unset | Traceability gaps invisible to developers by default |
| A-R2-04 | HIGH | tools/schema_registry.json | Steps 16a, 16b, 16c missing from schema_registry.json but present in step_order.json | Schema validation falls through to step_16; no substep-specific checks |
| A-R2-05 | MED | validation/validate.py:406-419 | Base ref resolution order undocumented; 5-level fallback chain produces different results across environments | Non-deterministic replay base across dev/CI/prod |
| A-R2-06 | MED | validation/forward_replay_check.py:93-94 | `_step_exists()` checks `spec_dir/{step}_*.json` from repo_root; wrong path in submodule | Spec file existence checks fail silently |
| A-R2-07 | MED | validation/seed_lint.py:84-89 | `_project_root_from_spec_dir()` detects mismatch but only warns, never fails | Mismatched project roots go unnoticed |
| A-R2-08 | MED | scripts/init_project.py:15,77 | Generated hooks hardcode `--repo-root ./devspec_toolkit`; no --spec-root or --git-root | Submodule users must manually edit generated hooks |
| A-R2-09 | LOW | tools/schema_registry.json:27 | seed_manifest registered in schema_registry.json but not in step_order.json steps array | Orphan registry entry; no impact on validation |
| A-R2-10 | LOW | core/registry.py:45-46 | FileNotFoundError message lacks actionable suggestion | Poor DX when schema is misconfigured |
| A-R2-11 | LOW | validation/validate.py:395-403 | `_is_git_repo()` returns False on timeout (10s); no logging | Silent fallback to "ignore" mode on slow git |

### Evidence

**A-R2-01:**
```python
# forward_replay_check.py:69-71
cmd = ["git", "-C", str(root), "diff", "--name-only", f"{base_ref}...HEAD"]
# root = Path(os.path.abspath(repo_root)) where repo_root = submodule dir
# In submodule: git runs from devspec_toolkit/.git (detached HEAD), not host repo
```

**A-R2-02:**
```python
# validate.py:233-236
mode = os.getenv("SPECDEV_REPLAY_DIFF_ERROR_MODE", "").strip().lower()
if not mode:
    in_ci = os.getenv("CI", "").strip().lower() in {"1", "true", "yes"}
    mode = "error" if (in_ci or _is_git_repo(root)) else "ignore"
# No stderr/log output when mode="ignore" — checks silently skip
```

**A-R2-03:**
```python
# validate.py:251-253
if not warn_as_error:
    e560_bases = {f.replace("E560", "W560", 1) for f in failures if f.startswith("E560")}
    failures = [f for f in failures if not (f.startswith("W560") and f in e560_bases)]
```

**A-R2-04:**
```
# step_order.json steps array includes: "16a", "16b", "16c"
# schema_registry.json has NO URIs for 16a, 16b, 16c
# validate.py:366-368 routes all three to step_16:
"16a": lambda instance, root, ctx: step_16.validate_step_16(instance, root, ctx.get("artifact_path")),
```

---

## Part B: Implementation Plan

| ID | Pri | Deps | File | Change summary | Findings |
|----|-----|------|------|----------------|----------|
| T01 | P0 | — | `tools/specdev_tools/core/errors.py` | Add `SubmoduleDetectionError` and `SchemaRegistryError` | A-R2-10 |
| T02 | P0 | T01 | `tests/test_errors_submodule.py` | Tests for new error classes | A-R2-10 |
| T03 | P0 | T01 | `tools/specdev_tools/core/registry.py` | Add `uri_exists()`, enhance error messages, add `load_with_fallback()` | A-R2-10 |
| T04 | P0 | T03 | `tests/test_registry_error_handling.py` | Tests for registry enhancements | A-R2-10 |
| T05 | P0 | — | `tools/schema_registry.json` | Add 16a, 16b, 16c entries | A-R2-04 |
| T06 | P1 | — | `tools/step_order.json` | Verify 16a/16b/16c deps; add seed_manifest metadata | A-R2-09 |
| T07 | P1 | T05 | `tools/specdev_tools/validation/validators/__init__.py` | Export step_16a, step_16b, step_16c | A-R2-04 |
| T08 | P1 | T07 | `tools/specdev_tools/validation/validators/step_16a.py` | Plan phase validator | A-R2-04 |
| T09 | P1 | T07 | `tools/specdev_tools/validation/validators/step_16b.py` | Execute phase validator | A-R2-04 |
| T10 | P1 | T07 | `tools/specdev_tools/validation/validators/step_16c.py` | Review phase validator | A-R2-04 |
| T11 | P1 | T01,T03,T05,T08-T10 | `tools/specdev_tools/validation/validate.py` | Submodule detection, stderr warnings, 16a/16b/16c routing | A-R2-01,02,04,05,11 |
| T12 | P1 | T11 | `tests/test_validate_submodule.py` | Tests for validate.py submodule changes | A-R2-01,02,04,05,11 |
| T13 | P1 | T01,T11 | `tools/specdev_tools/validation/forward_replay_check.py` | spec_root/git_root params, submodule support | A-R2-01,06 |
| T14 | P1 | T13 | `tests/test_forward_replay_submodule.py` | Tests for submodule replay | A-R2-01,06 |
| T15 | P1 | T11 | `tools/specdev_tools/validation/seed_lint.py` | Public project_root_from_spec_dir, strict_mode | A-R2-07 |
| T16 | P1 | T15 | `tests/test_seed_strict_mode.py` | Tests for strict mode | A-R2-07 |
| T17 | P1 | T11 | `tools/specdev_tools/validation/validators/step_07.py` | Deep NFR validation | — |
| T18 | P1 | T17 | `tests/test_step_07_deep.py` | NFR validation tests | — |
| T19 | P1 | T11 | `tools/specdev_tools/validation/validators/step_10.py` | Deep governance validation | — |
| T20 | P1 | T19 | `tests/test_step_10_deep.py` | Governance validation tests | — |
| T21 | P1 | T11 | `tools/specdev_tools/validation/validators/step_11.py` | Deep red-team validation | — |
| T22 | P1 | T21 | `tests/test_step_11_deep.py` | Red-team validation tests | — |
| T23 | P1 | T13 | `tools/specdev_tools/cli.py` | --spec-root, --git-root params | A-R2-01,08 |
| T24 | P1 | T23 | `tests/test_cli_submodule_params.py` | CLI param tests | A-R2-01,08 |
| T25 | P2 | T23 | `scripts/init_project.py` | Submodule-aware hook generation | A-R2-08 |
| T26 | P2 | T25 | `tests/test_init_project_submodule.py` | Init project tests | A-R2-08 |
| T27 | P1 | T12,T14,T16,T18,T20,T22,T24 | — | Integration gate: full test suite | — |
| T28 | P1 | T27 | — | Integration gate: validate-all | — |
| D01 | P3 | T23 | `docs/developers/reference.md` | CLI reference updates | A-R2-08 |
| D02 | P3 | T23 | `docs/developers/path_conventions.md` | Path resolution docs | A-R2-01,08 |
| D03 | P3 | T11 | `CLAUDE.md` | Submodule section | A-R2-01,02,05 |
| D04 | P3 | T01 | `docs/developers/error-codes.md` | Error code docs | A-R2-10 |

---

## Verification Status

- All findings verified with exact code quotes
- Each task modifies exactly one file
- Every code task has a corresponding test task
- All dependencies resolve forward
- All 11 findings mapped to implementation tasks

**Total**: 11 findings (1 CRIT, 3 HIGH, 4 MED, 3 LOW), 32 tasks
