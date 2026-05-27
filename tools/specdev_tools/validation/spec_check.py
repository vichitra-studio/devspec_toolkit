"""Unified spec-check: runs all applicable validation and lint checks in one pass.

Wraps validate-all as the core, then adds checks that validate-all doesn't run
(seed-lint, fixtures-lint, completeness-check, canon-schema-alignment).
Reports per-check breakdown with PASS/WARN/FAIL/SKIP status.
"""

from __future__ import annotations

import os
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any

from ..core.config import reset_config
from ..core.errors import SpecError
from ..core.json_output import error_to_dict
from ..core.loaders import iter_spec_artifacts


def _classify(errors: list[SpecError]) -> dict[str, Any]:
    """Return status/counts for a list of errors."""
    e_count = sum(1 for e in errors if not e.code.startswith("W"))
    w_count = sum(1 for e in errors if e.code.startswith("W"))
    if e_count:
        status = "FAIL"
    elif w_count:
        status = "WARN"
    else:
        status = "PASS"
    return {"status": status, "error_count": e_count, "warning_count": w_count}


def _check_toolkit_version(repo_root: str, spec_dir: str) -> list[SpecError]:
    """Return [] if versions match, or [E608] on any error condition.

    Error cases:
    - ``spec/specdev_version`` does not exist (project must always have a recorded version).
    - Toolkit version is unreadable (missing pyproject.toml).
    - Version mismatch between recorded and active toolkit.
    """
    import os as _os
    from pathlib import Path as _Path
    from ..generation.schema_differ import get_user_version
    from ..core.changelog_parser import get_toolkit_version
    from ..core.errors import make_error

    host_version = get_user_version(_Path(_os.path.abspath(spec_dir)))
    if host_version is None:
        _sv_file = _Path(_os.path.abspath(spec_dir)) / "specdev_version"
        if _sv_file.exists():
            return [
                make_error(
                    "E608",
                    "spec/specdev_version exists but is malformed or missing the `toolkit_version` key. "
                    "Re-stamp it (run `specdev align`) or fix the file.",
                )
            ]
        return [
            make_error(
                "E608",
                "No toolkit version recorded in spec/specdev_version. Run `specdev align` to stamp the project's toolkit version.",
            )
        ]

    toolkit_version = get_toolkit_version(_Path(_os.path.abspath(repo_root)))
    if toolkit_version is None:
        return [
            make_error(
                "E608",
                f"Could not determine the active toolkit version from {_os.path.abspath(repo_root)}/tools/pyproject.toml.",
            )
        ]

    if host_version == toolkit_version:
        return []

    return [
        make_error(
            "E608",
            (
                f"Spec was built against toolkit v{host_version}, but the active "
                f"toolkit is v{toolkit_version}. Run `specdev align` to migrate before editing specs."
            ),
        )
    ]


def _run_checks(
    repo_root: str,
    spec_dir: str,
    include_forward_replay: bool = False,
    git_root: str | None = None,
    spec_root: str | None = None,
    project_canon_dir: str | None = None,
) -> OrderedDict[str, dict[str, Any]]:
    """Run all applicable checks and return per-check results.

    Each value is either:
    - ``{"status": "SKIP", "reason": "..."}`` for skipped checks, or
    - ``{"status": "PASS"|"WARN"|"FAIL", "error_count": int, "warning_count": int, "errors": list}``
    """
    root = Path(os.path.abspath(repo_root))
    checks: OrderedDict[str, dict[str, Any]] = OrderedDict()

    # --- 1. Schema validation (validate each file) ---
    from .validate import validate_file

    schema_errs: list[SpecError] = []
    if os.path.isdir(spec_dir):
        for file_path in iter_spec_artifacts(spec_dir):
            schema_errs.extend(
                validate_file(
                    repo_root,
                    file_path,
                    include_quality_lint=False,
                    include_canonical_integrity=False,
                    git_root=git_root,
                    spec_root=spec_root,
                )
            )
    checks["schema-validation"] = {**_classify(schema_errs), "errors": schema_errs}

    # --- 1b. Toolkit version gate ---
    tv_result = _check_toolkit_version(repo_root, spec_dir)
    checks["toolkit-version"] = {**_classify(tv_result), "errors": tv_result}

    # --- 2. Spec quality lint ---
    from .spec_quality_lint import lint_spec_quality

    quality_errs = lint_spec_quality(spec_dir)
    checks["spec-quality-lint"] = {**_classify(quality_errs), "errors": quality_errs}

    # --- 3. Canonical preflight ---
    from ..canonical.lint import lint_canon_dirs

    canon_errs = list(
        dict.fromkeys(
            lint_canon_dirs(
                repo_root,
                project_canon_dir=project_canon_dir,
                require_manifest_schema_registration=True,
            )
        )
    )
    checks["canonical-lint"] = {**_classify(canon_errs), "errors": canon_errs}

    # If canonical bootstrap failed, skip canon-dependent checks
    canon_ok = not any(not e.code.startswith("W") for e in canon_errs)

    # --- 4. Canonical integrity ---
    if canon_ok:
        from ..canonical.integrity import validate_canonical_integrity

        integrity_errs = validate_canonical_integrity(
            repo_root, spec_dir,
            require_manifest_schema_registration=True,
            project_canon_dir=project_canon_dir,
        )
        checks["canonical-integrity"] = {
            **_classify(integrity_errs),
            "errors": integrity_errs,
        }
    else:
        checks["canonical-integrity"] = {
            "status": "SKIP",
            "reason": "canonical preflight failed",
        }

    # --- 5. Hallucination lint ---
    if canon_ok:
        from .hallucination_lint import lint_hallucinations

        hall_errs = lint_hallucinations(
            spec_dir,
            repo_root=repo_root,
            require_canon_dir=True,
            require_manifest_schema_registration=True,
            project_canon_dir=project_canon_dir,
            git_root=git_root,
        )
        checks["hallucination-lint"] = {**_classify(hall_errs), "errors": hall_errs}
    else:
        checks["hallucination-lint"] = {
            "status": "SKIP",
            "reason": "canonical preflight failed",
        }

    # --- 6. Traceability closure ---
    from .traceability_closure import check_traceability_closure

    tc_errs = check_traceability_closure(spec_dir, repo_root)
    checks["traceability-closure"] = {**_classify(tc_errs), "errors": tc_errs}

    # --- 7. Completeness check (W564-W568) ---
    _completeness_codes = frozenset({
        "W564", "W565", "W566", "W567", "W568",
        "E564", "E565", "E566", "E567", "E568",
    })
    completeness_errs = [
        e for e in tc_errs
        if isinstance(e, SpecError) and e.code in _completeness_codes
    ]
    checks["completeness-check"] = {
        **_classify(completeness_errs),
        "errors": completeness_errs,
    }

    # --- 8. Seed lint ---
    # project_root must be computed before the gate so the manifest-existence
    # check can use it.  It is also passed to lint_seeds when the gate is True.
    project_root = os.path.dirname(spec_dir) if git_root is None else git_root
    seed_applicable = os.path.exists(
        os.path.join(project_root, "spec", "common", "seed_manifest.json")
    )
    if seed_applicable:
        from .seed_lint import lint_seeds

        # For submodule deployments, seed docs are in the host repo (git_root),
        # not in the toolkit root. Pass project_root so seeds resolve correctly.
        seed_errs = lint_seeds(repo_root, spec_dir, project_root=project_root)
        checks["seed-lint"] = {**_classify(seed_errs), "errors": seed_errs}
    else:
        checks["seed-lint"] = {
            "status": "SKIP",
            "reason": "seed_manifest.json not present",
        }

    # --- 9. Fixtures lint ---
    fixtures_file = os.path.join(spec_dir, "08_fixtures.json")
    if os.path.isfile(fixtures_file):
        from .fixtures_lint import lint_fixtures

        fix_errs = lint_fixtures(spec_dir)
        checks["fixtures-lint"] = {**_classify(fix_errs), "errors": fix_errs}
    else:
        checks["fixtures-lint"] = {
            "status": "SKIP",
            "reason": "step 08 not present",
        }

    # --- 10. Dependency order lint ---
    if (root / "tools" / "step_order.json").exists():
        from .dependency_order_lint import lint_dependency_order

        dep_errs = lint_dependency_order(repo_root)
        checks["dependency-order-lint"] = {
            **_classify(dep_errs),
            "errors": dep_errs,
        }
    else:
        checks["dependency-order-lint"] = {
            "status": "SKIP",
            "reason": "step_order.json not found",
        }

    # --- 11. Registry check (R001-R003) ---
    # Registry now lives toolkit-side at <repo_root>/tools/entry_key_registry.json
    registry_file = os.path.join(repo_root, "tools", "entry_key_registry.json")
    if os.path.isfile(registry_file):
        from .registry_check import run_registry_check

        effective_spec_root = spec_root or spec_dir
        reg_errs = run_registry_check(
            spec_root=effective_spec_root,
            repo_root=repo_root,
            git_root=git_root,
        )
        checks["registry-check"] = {**_classify(reg_errs), "errors": reg_errs}
    else:
        checks["registry-check"] = {
            "status": "SKIP",
            "reason": "entry_key_registry.json not present",
        }

    # --- 12. Hardcoded seed reference check (W554) ---
    # Always runs when a prompts/ directory exists under repo_root.
    prompts_dir = os.path.join(repo_root, "prompts")
    if os.path.isdir(prompts_dir):
        from .seed_lint import check_hardcoded_seed_reference

        hsr_errs = check_hardcoded_seed_reference(repo_root, git_root=git_root)
        checks["hardcoded-seed-check"] = {**_classify(hsr_errs), "errors": hsr_errs}
    else:
        checks["hardcoded-seed-check"] = {
            "status": "SKIP",
            "reason": "prompts/ directory not present",
        }

    # --- 13. Glossary drift ---
    glossary_file = os.path.join(spec_dir, "03_glossary.json")
    if os.path.isfile(glossary_file):
        from .glossary_drift_lint import lint_glossary_drift
        gd_errs = lint_glossary_drift(
            spec_dir,
            repo_root=repo_root,
            project_canon_dir=project_canon_dir,
        )
        checks["glossary-drift-check"] = {**_classify(gd_errs), "errors": gd_errs}
    else:
        checks["glossary-drift-check"] = {
            "status": "SKIP",
            "reason": "03_glossary.json not present",
        }

    # --- 14. Forward replay (opt-in) ---
    if include_forward_replay:
        from .forward_replay_check import check_forward_replay
        from .validate import _resolve_replay_base_ref, _detect_git_root

        effective_git_root = git_root or str(_detect_git_root(root))
        base_ref = _resolve_replay_base_ref(Path(effective_git_root))
        replay_errs = check_forward_replay(
            repo_root,
            base_ref=base_ref,
            diff_error_mode="error",
            git_root=effective_git_root,
            spec_root=spec_root or str(root / "spec"),
        )
        checks["forward-replay-check"] = {
            **_classify(replay_errs),
            "errors": replay_errs,
        }
    else:
        checks["forward-replay-check"] = {
            "status": "SKIP",
            "reason": "use --include-forward-replay to enable",
        }

    return checks


def _collect_errors(checks: OrderedDict[str, dict[str, Any]]) -> list[SpecError]:
    """Collect and deduplicate all errors across checks."""
    combined: list[SpecError] = []
    seen: set[tuple[str, str]] = set()
    # Completeness errors are a subset of traceability-closure errors;
    # skip them to avoid double-counting in the combined list.
    skip_checks = {"completeness-check"}
    for name, info in checks.items():
        if name in skip_checks:
            continue
        for e in info.get("errors", []):
            key = (e.code, e.message)
            if key not in seen:
                seen.add(key)
                combined.append(e)
    return combined


def run_spec_check(
    repo_root: str,
    spec_dir: str,
    include_forward_replay: bool = False,
    git_root: str | None = None,
    spec_root: str | None = None,
    project_canon_dir: str | None = None,
) -> list[SpecError]:
    """Run all applicable checks and return combined deduplicated errors.

    Prints a per-check summary to stderr before returning.
    """
    reset_config()
    checks = _run_checks(repo_root, spec_dir, include_forward_replay, git_root, spec_root, project_canon_dir=project_canon_dir)
    _print_summary(checks)
    return _collect_errors(checks)


def run_spec_check_json(
    repo_root: str,
    spec_dir: str,
    include_forward_replay: bool = False,
    git_root: str | None = None,
    spec_root: str | None = None,
    project_canon_dir: str | None = None,
) -> tuple[list[SpecError], dict[str, Any]]:
    """Run all checks and return (errors, json_context) for ``_json_exit``."""
    reset_config()
    checks = _run_checks(repo_root, spec_dir, include_forward_replay, git_root, spec_root, project_canon_dir=project_canon_dir)
    checks_summary: dict[str, Any] = {}
    for name, info in checks.items():
        if info.get("status") == "SKIP":
            checks_summary[name] = {"status": "SKIP", "reason": info.get("reason", "")}
        else:
            checks_summary[name] = {
                "status": info["status"],
                "error_count": info["error_count"],
                "warning_count": info["warning_count"],
                "findings": [error_to_dict(e) for e in info.get("errors", [])],
            }
    return _collect_errors(checks), {"checks": checks_summary}


def _print_summary(checks: OrderedDict[str, dict[str, Any]]) -> None:
    """Print per-check breakdown to stderr."""
    run_count = 0
    total_e = 0
    total_w = 0
    lines: list[str] = []
    for name, info in checks.items():
        if info.get("status") == "SKIP":
            lines.append(f"  [SKIP] {name:<30s} ({info.get('reason', '')})")
        else:
            run_count += 1
            ec = info["error_count"]
            wc = info["warning_count"]
            total_e += ec
            total_w += wc
            tag = info["status"]
            lines.append(f"  [{tag:4s}] {name:<30s} {ec} errors  {wc} warnings")

    print(f"spec-check: {run_count} checks run, {total_e} errors, {total_w} warnings\n", file=sys.stderr)
    for line in lines:
        print(line, file=sys.stderr)
    print(file=sys.stderr)
