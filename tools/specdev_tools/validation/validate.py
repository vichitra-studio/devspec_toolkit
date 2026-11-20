"""Central validation orchestrator for the DevSpec Toolkit.

This module is intentionally the single entry point for both single-file
(``validate_file``) and full-directory (``validate_dir``) validation.
``validate_dir`` further orchestrates quality lint, canonical integrity,
forward-replay, dependency-order, extraction-intent, and prompt-schema-sync
checks.  A future refactor could split ``validate_dir`` into a dedicated
``orchestrator.py`` module (see AUDIT-004).
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

# Kept as the patch-target anchor for test_validate_file_runtime_error_is_not_misclassified_as_ref_resolution (patches validate.Draft202012Validator.iter_errors); do not remove.
from jsonschema import Draft202012Validator
from ..core.schema_validate import (
    jq_path_of,
    validate_data_against_schema,
    SchemaBootstrapError,
    SchemaNotFoundError,
    SchemaDecodeError,
    SchemaReferencingError,
    SchemaRuntimeError,
)
from ..canonical.integrity import validate_canonical_integrity, validate_canonical_integrity_file
from ..canonical.lint import lint_canon_dirs
from .dependency_order_lint import lint_dependency_order
from .forward_replay_check import check_forward_replay
from .extraction_intent_check import check_extraction_intent
from .hallucination_lint import lint_hallucinations
from .linter_utils import build_lint_graph
from .check_registry import graph_for_checks
from .spec_check import lock_link_findings
from ..generation.prompt_schema_sync import run_prompt_schema_sync
from ..core.config import get_config, reset_config
from ..core.constants import DEFAULT_BRANCH_CANDIDATES
from ..core.errors import ERROR_CODES, PROMOTABLE_PAIRS, SpecError, make_error
from ..core.loaders import iter_spec_artifacts, load_json_artifact
from ..core.registry import SchemaRegistry, get_shared_registry
from ..graph.build import build_file_graph
from ..graph.gitview import GitViewError, git_top_level, host_root_of
from ..graph.ids import check_unique_ids
from ..graph.kinds import KindRegistryError
from .spec_quality_lint import lint_spec_quality, lint_spec_quality_file
from .validators import (
    step_01,
    step_02,
    step_02a,
    step_03,
    step_04,
    step_05,
    step_06,
    step_07,
    step_08,
    step_09,
    step_10,
    step_11,
    step_12,
    step_13,
    step_13a,
    step_14,
    step_15,
    step_16,
    step_16a,
    step_16b,
    step_16c,
    step_16_anchor,
)


from ..core.step_paths import get_step_from_path, refine_impl_context_substep


def _duplicate_id_errors(repo_root: str, path: str, data: dict[str, Any]) -> list[SpecError]:
    """E704 for an id defined twice inside the file *path*; nothing when the toolkit has no usable registry."""
    try:
        return check_unique_ids(build_file_graph(path, repo_root, data))
    except KindRegistryError:
        return []


def validate_file(
    repo_root: str,
    path: str,
    include_quality_lint: bool = True,
    include_canonical_integrity: bool = True,
    project_canon_dir: str | None = None,
    git_root: str | None = None,
    spec_root: str | None = None,
    include_id_slice: bool = True,
) -> list[SpecError]:
    """Validate one spec file: schema, deep per-step checks and, by default, duplicate ids inside the file (E704).

    ``include_id_slice=False`` drops the duplicate-id check; ``spec-check`` passes it because its ``graph`` check
    covers the same duplicates across all files.
    """
    try:
        get_shared_registry(repo_root)  # bootstrap probe — fires schema_registry_bootstrap_failed before the helper
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as e:
        return [make_error("E520", f"{path}: schema_registry_bootstrap_failed detail={str(e)}")]
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return [
                make_error(
                    "E520",
                    f"{path}: invalid_document_root_type "
                    f"expected=object got={type(data).__name__}",
                )
            ]

        schema_uri = data.get("$schema")
        if schema_uri is None:
            return [make_error("E520", f"{path}: missing_schema_uri")]
        if not isinstance(schema_uri, str):
            return [
                make_error(
                    "E520",
                    f"{path}: invalid_schema_uri_type "
                    f"expected=str got={type(schema_uri).__name__}",
                )
            ]
        schema_uri = schema_uri.strip()
        if not schema_uri:
            return [make_error("E520", f"{path}: missing_schema_uri")]

        try:
            raw_errors = validate_data_against_schema(repo_root, data)
        except SchemaBootstrapError as e:
            # TOCTOU / reordering defence: helper's own bootstrap failed after the
            # probe above succeeded.  Emit the byte-identical message the probe would
            # have emitted so callers see a consistent schema_registry_bootstrap_failed
            # signal regardless of which bootstrap fires.
            return [make_error("E520", f"{path}: schema_registry_bootstrap_failed detail={str(e.original)}")]
        except SchemaNotFoundError as e:
            return [make_error("E520", f"{path}: schema_not_found uri={e.uri} detail={e.detail}")]
        except SchemaDecodeError as e:
            return [make_error("E520", f"{path}: schema_json_decode_failed uri={e.uri} detail={e.detail}")]
        except SchemaReferencingError as e:
            return [make_error("E520", f"{path}: schema_reference_resolution_failed {str(e.original)}")]
        except SchemaRuntimeError as e:
            return [make_error("E521", f"{path}: schema_validation_runtime_error {type(e.original).__name__}: {str(e.original)}")]

        # Sort by path tuple for deterministic ordering (mirrors the original
        # sorted(v.iter_errors(...), key=lambda e: e.path) call).
        errors = sorted(raw_errors, key=lambda t: t[0])

        # Resolve step once — use content-based refinement for impl_context/
        # artifacts so 16b/16c sub-step validators actually run during
        # validate_file (path-only routing always yielded "16a").
        step = refine_impl_context_substep(get_step_from_path(path), data)

        # Enhance error messages with context
        enhanced_errors: list[SpecError] = []
        for path_tuple, message in errors:
            error_msg = f"{path}:{'/'.join(map(str, path_tuple))}: {message}"

            # Add context about what to do next
            if step != "unknown":
                prompt_path = f"prompts/prompt_{step}*.md"
                error_msg += f"\n  See: {prompt_path} for guidance on requirements"

            enhanced_errors.append(make_error("E520", error_msg, jq_path=jq_path_of(path_tuple)))

        deep_errors = _run_deep_validation(step, data, repo_root, path, git_root=git_root, spec_root=spec_root)
        if deep_errors:
            for de in deep_errors:
                enhanced_errors.append(
                    SpecError(code=de.code, message=f"{path}: {de.message}", path=de.path)
                )

        if include_quality_lint:
            quality_errors = lint_spec_quality_file(path, spec_dir=os.path.dirname(path))
            if quality_errors:
                enhanced_errors.extend(quality_errors)
        if include_canonical_integrity:
            canonical_errors = validate_canonical_integrity_file(
                repo_root,
                path,
                enforce_unresolved_semantics=False,
                require_manifest_schema_registration=True,
                project_canon_dir=project_canon_dir,
            )
            if canonical_errors:
                enhanced_errors.extend(canonical_errors)

        if include_id_slice:
            enhanced_errors.extend(_duplicate_id_errors(repo_root, path, data))

        # W->E promotion for single-file validation (mirrors validate_dir logic)
        enhanced_errors = _apply_we_promotion(enhanced_errors)

        return enhanced_errors
    except FileNotFoundError as e:
        return [make_error("E520", f"{path}: input_file_not_found detail={str(e)}")]
    except (OSError, json.JSONDecodeError, ValueError, KeyError, AttributeError, TypeError) as e:
        return [make_error("E520", f"{path}: validation_input_error {type(e).__name__}: {str(e)}")]

def validate_dir(repo_root: str, spec_dir: str, project_canon_dir: str | None = None, git_root: str | None = None, spec_root: str | None = None) -> list[SpecError]:
    # Reset config to pick up any env var changes since last call
    reset_config()
    # Early exit: no JSON spec artifacts anywhere under spec_dir means nothing
    # to validate.  Use ``iter_spec_artifacts`` so the guard matches the main
    # walk's exclusion rules (``samples/``, ``extras/``, ``migration_backups/``)
    # and — critically — recurses into ``impl_context/``.  A flat
    # ``os.listdir`` guard would short-circuit on any host repo whose only
    # spec artifacts are per-milestone plans inside ``impl_context/``.
    if os.path.isdir(spec_dir) and next(iter_spec_artifacts(spec_dir), None) is None:
        import sys as _sys
        print(f"specdev: {spec_dir} contains no .json files; nothing to validate.", file=_sys.stderr)
        return []

    failures: list[SpecError] = []
    # Surface (once per run) any SPECDEV_PROMOTE_CODES entries that will be
    # silently ignored because they are not promotable.
    _warn_ignored_promote_codes()
    canonical_preflight_errors: list[SpecError] = list(
        dict.fromkeys(
            lint_canon_dirs(
                repo_root,
                project_canon_dir=project_canon_dir,
                require_manifest_schema_registration=True,
            )
        )
    )
    if _has_canonical_bootstrap_failure(canonical_preflight_errors):
        return canonical_preflight_errors

    for file_path in iter_spec_artifacts(spec_dir):
        failures.extend(
            validate_file(
                repo_root,
                file_path,
                include_quality_lint=False,
                include_canonical_integrity=False,
                git_root=git_root,
                spec_root=spec_root,
            )
        )

    lint_graph = build_lint_graph(spec_dir, repo_root)
    failures.extend(lint_spec_quality(spec_dir, graph=lint_graph))
    if canonical_preflight_errors:
        failures.extend(canonical_preflight_errors)
    else:
        failures.extend(
            lint_hallucinations(
                spec_dir,
                repo_root=repo_root,
                require_canon_dir=True,
                require_manifest_schema_registration=True,
                project_canon_dir=project_canon_dir,
                git_root=git_root,
                graph=lint_graph,
            )
        )
        failures.extend(
            validate_canonical_integrity(
                repo_root,
                spec_dir,
                require_manifest_schema_registration=True,
                project_canon_dir=project_canon_dir,
            )
        )
        from .traceability_closure import check_traceability_closure
        tc_errors = check_traceability_closure(spec_dir, repo_root)
        # Only propagate hard errors (E-codes); W-codes are informational
        failures.extend(e for e in tc_errors if not e.code.startswith("W"))

    root = Path(os.path.abspath(repo_root))
    failures.extend(
        lock_link_findings(
            graph_for_checks(repo_root, spec_dir, spec_root, lint_graph),
            spec_root or spec_dir,
            repo_root,
            host_root_of(spec_root or spec_dir, git_root),
        )
    )
    if (root / "tools" / "step_order.json").exists() and (root / "prompts").exists():
        step_order = _load_step_order(root / "tools" / "step_order.json")
        dep_errors = lint_dependency_order(repo_root)
        failures.extend(dep_errors)
        if step_order.get("require_full_forward_replay_on_change", True):
            if not any("invalid_step_order" in e.message for e in dep_errors):
                cfg = get_config()
                mode = cfg.replay_diff_error_mode
                if not mode:
                    in_ci = os.getenv("CI", "").strip().lower() in {"1", "true", "yes"}
                    mode = "error" if (in_ci or _is_git_repo(root)) else "ignore"
                if mode == "ignore":
                    import sys as _sys
                    print(
                        "specdev: forward-replay check skipped (not in CI and not a git repo). "
                        "Set SPECDEV_REPLAY_DIFF_ERROR_MODE=error to force.",
                        file=_sys.stderr,
                    )
                detected_git_root = _detect_git_root(root)
                base_ref = _resolve_replay_base_ref(detected_git_root)
                failures.extend(
                    check_forward_replay(
                        repo_root,
                        base_ref=base_ref,
                        diff_error_mode=mode,
                        git_root=str(detected_git_root),
                        spec_root=spec_root or str(root / "spec"),
                    )
                )
    # R9/T26: Extraction intent validation (prompts vs step_order.json)
    if (root / "tools" / "step_order.json").exists() and (root / "prompts").exists():
        failures.extend(check_extraction_intent(repo_root))

    # Prompt-schema sync validation
    failures.extend(run_prompt_schema_sync(repo_root))

    failures = _apply_we_promotion(failures)

    return failures


def _warn_ignored_promote_codes() -> None:
    """Warn (to stderr) when SPECDEV_PROMOTE_CODES lists codes that will be ignored.

    A code in SPECDEV_PROMOTE_CODES that is not in PROMOTABLE_PAIRS is silently
    dropped by the promotion intersection. Surface it so a CI author who, e.g.,
    sets ``SPECDEV_PROMOTE_CODES=W597`` (a valid but non-promotable code) or a
    typo is not left believing a promotion took effect. Only meaningful when
    SPECDEV_WARNINGS_AS_ERRORS is off — when it is on, promote_codes is ignored
    wholesale and a per-code warning would mislead.
    """
    cfg = get_config()
    if cfg.warnings_as_errors or not cfg.promote_codes:
        return
    ignored = set(cfg.promote_codes) - set(PROMOTABLE_PAIRS.keys())
    if not ignored:
        return
    import sys as _sys
    for code in sorted(ignored):
        if code not in ERROR_CODES:
            print(
                f"specdev: SPECDEV_PROMOTE_CODES contains unrecognised code "
                f"{code!r}; it will be ignored.",
                file=_sys.stderr,
            )
        else:
            print(
                f"specdev: SPECDEV_PROMOTE_CODES contains {code} "
                f"({ERROR_CODES[code]}) which is not a promotable code; "
                f"it will be ignored.",
                file=_sys.stderr,
            )


def _apply_we_promotion(failures: list[SpecError]) -> list[SpecError]:
    """Apply W->E code promotion and dedup to a list of SpecError objects.

    Uses field-based code swapping instead of regex, which is both more
    correct and more efficient.
    """
    cfg = get_config()
    warn_as_error = cfg.warnings_as_errors
    promote_codes_cfg = cfg.promote_codes

    if warn_as_error:
        codes_to_promote = set(PROMOTABLE_PAIRS.keys())
    elif promote_codes_cfg:
        codes_to_promote = set(promote_codes_cfg) & set(PROMOTABLE_PAIRS.keys())
    else:
        codes_to_promote = set()

    promoted: list[SpecError] = []
    for err in failures:
        if err.code in codes_to_promote:
            new_code = PROMOTABLE_PAIRS[err.code]
            promoted.append(replace(err, code=new_code))
        else:
            promoted.append(err)

    # Dedup preserving order
    seen: set[tuple[str, str, str | None]] = set()
    deduped: list[SpecError] = []
    for err in promoted:
        key = (err.code, err.message, err.path)
        if key not in seen:
            seen.add(key)
            deduped.append(err)

    # Drop redundant W-codes when NOT in full warn-as-error mode.
    # In partial-promotion mode, non-promoted W-codes that happen to have
    # a matching E-code counterpart already present should still be cleaned up.
    if not warn_as_error:
        e_messages: set[tuple[str, str, str | None]] = {
            (err.code, err.message, err.path)
            for err in deduped
            if err.code.startswith("E")
        }
        deduped = [
            err for err in deduped
            if not (
                err.code.startswith("W")
                and err.code in PROMOTABLE_PAIRS
                and (PROMOTABLE_PAIRS[err.code], err.message, err.path) in e_messages
            )
        ]

    return deduped


def _has_canonical_bootstrap_failure(errors: list[SpecError]) -> bool:
    bootstrap_tokens = (
        "missing_schema_registry",
        "schema_uri_not_registered",
        "schema_registry_bootstrap_failed",
    )
    return any(any(token in e.message for token in bootstrap_tokens) for e in errors)


def _load_nfrs_data(repo_root: str, file_path: str) -> dict[str, Any] | None:
    """Load full NFR data dict (not just IDs) for step_03 cross-ref validation.

    Cannot use ``load_upstream_ids`` because step_03 needs the entire JSON dict,
    not a set of IDs (AUDIT-019).

    Search order mirrors ``_load_roadmap`` / ``_find_seed_manifest``: when the
    artifact lives inside ``impl_context/``, 07_nfrs.json is at the spec root
    (parent), not in the same directory as the plan."""
    artifact_dir = os.path.dirname(file_path) if file_path else ""
    search_dirs = [artifact_dir]
    if os.path.basename(artifact_dir) == "impl_context":
        search_dirs.append(os.path.dirname(artifact_dir))
    search_dirs.append(os.path.join(repo_root, "spec"))
    for d in search_dirs:
        if not d or not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if fn.startswith("07_") and fn.endswith(".json"):
                data = load_json_artifact(os.path.join(d, fn))
                if data:
                    return data
    return None


def _load_monitoring_data(repo_root: str, file_path: str) -> dict[str, Any] | None:
    """Load full monitoring data dict for step_03 cross-ref validation (AUDIT-019)."""
    for prefix in ("16",):
        artifact_dir = os.path.dirname(file_path) if file_path else ""
        for d in (artifact_dir, os.path.join(repo_root, "spec")):
            if not d or not os.path.isdir(d):
                continue
            for fn in os.listdir(d):
                if fn.startswith(f"{prefix}_") and fn.endswith(".json"):
                    data = load_json_artifact(os.path.join(d, fn))
                    if data:
                        return data
    return None


def _build_validation_context(
    repo_root: str,
    path: str,
    git_root: str | None = None,
    spec_root: str | None = None,
) -> dict[str, Any]:
    # Prefer an explicitly supplied spec_root (e.g. from --spec-root CLI arg).
    # Fall back to deriving from git_root so callers that only pass --git-root work.
    effective_spec_root: str | None = spec_root or (os.path.join(git_root, "spec") if git_root else None)
    return {
        "artifact_path": path,
        "spec_root": effective_spec_root,
        "nfrs_data": _load_nfrs_data(repo_root, path),
        "monitoring_data": _load_monitoring_data(repo_root, path),
    }


DeepValidator = Callable[[dict[str, Any], str, dict[str, Any]], list[SpecError]]


# Hardcoded step→validator mapping.  A future enhancement could auto-discover
# validators via an entry-point or a naming convention scan of the validators/
# package, but the explicit dict keeps startup predictable and avoids import
# side-effects.  See AUDIT-043 for the auto-discovery proposal.
DEEP_VALIDATORS: dict[str, DeepValidator] = {
    "01": lambda instance, root, ctx: step_01.validate_step_01(instance, root),
    "02": lambda instance, root, ctx: step_02.validate_step_02(instance, root, ctx.get("spec_root"), ctx.get("artifact_path")),
    "02a": lambda instance, root, ctx: step_02a.validate_step_02a(instance, root),
    "03": lambda instance, root, ctx: step_03.validate_step_03(
        instance,
        root,
        ctx.get("nfrs_data"),
        ctx.get("monitoring_data"),
    ),
    "04": lambda instance, root, ctx: step_04.validate_step_04(instance, root, ctx.get("spec_root")),
    "05": lambda instance, root, ctx: step_05.validate_step_05(instance, root, ctx.get("spec_root")),
    "06": lambda instance, root, ctx: step_06.validate_step_06(instance, root, ctx.get("spec_root")),
    "07": lambda instance, root, ctx: step_07.validate_step_07(instance, root, ctx.get("spec_root")),
    "08": lambda instance, root, ctx: step_08.validate_step_08(instance, root, ctx.get("spec_root")),
    "09": lambda instance, root, ctx: step_09.validate_step_09(instance, root, ctx.get("spec_root")),
    "10": lambda instance, root, ctx: step_10.validate_step_10(instance, root),
    "11": lambda instance, root, ctx: step_11.validate_step_11(instance, root, ctx.get("artifact_path")),
    "12": lambda instance, root, ctx: step_12.validate_step_12(instance, root, ctx.get("spec_root")),
    "13": lambda instance, root, ctx: step_13.validate_step_13(instance, root, ctx.get("spec_root")),
    "13a": lambda instance, root, ctx: step_13a.validate_step_13a(instance, root, ctx.get("spec_root")),
    "14": lambda instance, root, ctx: step_14.validate_step_14(instance, root, ctx.get("artifact_path")),
    "15": lambda instance, root, ctx: step_15.validate_step_15(instance, root, ctx.get("spec_root")),
    # "16" → Trinity Anchor validator (spec/16_impl_context.json, not in impl_context/).
    # "16a" / "16b" / "16c" → all live under spec/impl_context/ and initially land on "16a"
    #   via path regex. refine_impl_context_substep(step, data) (core/step_paths.py) then promotes the step
    #   based on content:  non-empty review.verdict → "16c",  non-empty
    #   execution.execution_results → "16b",  else stays at "16a". Chain-up inside the
    #   validators (16c→16b→16a→base) preserves downstream checks.
    "16": lambda instance, root, ctx: step_16_anchor.validate_step_16_anchor(instance, root, ctx.get("artifact_path")),
    "16a": lambda instance, root, ctx: step_16a.validate_step_16a(instance, root, ctx.get("artifact_path"), ctx.get("spec_root")),
    "16b": lambda instance, root, ctx: step_16b.validate_step_16b(instance, root, ctx.get("artifact_path"), ctx.get("spec_root")),
    "16c": lambda instance, root, ctx: step_16c.validate_step_16c(instance, root, ctx.get("artifact_path"), ctx.get("spec_root")),
}


def _run_deep_validation(
    step: str,
    data: dict,
    repo_root: str,
    path: str,
    git_root: str | None = None,
    spec_root: str | None = None,
) -> list[SpecError]:
    validator = DEEP_VALIDATORS.get(step)
    if validator is None or not isinstance(data, dict):  # a non-object document is reported by the schema
        return []
    context = _build_validation_context(repo_root, path, git_root=git_root, spec_root=spec_root)
    try:
        return validator(data, repo_root, context)
    except Exception as e:
        return [make_error("E521", f"Deep Validation Critical Error: {str(e)}")]


def _load_step_order(path: Path) -> dict[str, object]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        policy = data.get("policy", {})
        if isinstance(policy, dict):
            return policy
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        pass
    return {}


def _detect_git_root(repo_root: Path) -> Path:
    """Detect the host repo git root, which may differ from repo_root in submodule deployments.

    In a submodule layout, ``repo_root`` points to the toolkit directory
    (e.g. ``host_repo/devspec_toolkit/``) but git operations must run from
    the host repo root.  This function asks git for the top of the working
    tree that holds *repo_root* (``gitview.git_top_level``, which also
    resolves the ``.git`` file a submodule has).
    Falls back to *repo_root* when git does not answer or names no folder.
    """
    try:
        top = git_top_level(str(repo_root))
    except GitViewError:
        return repo_root
    return Path(top) if top and Path(top).exists() else repo_root


def _is_git_repo(root: Path) -> bool:
    cmd = ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=10)
    except subprocess.TimeoutExpired:
        import sys as _sys
        print(f"specdev: git rev-parse timed out for {root}; assuming not a git repo", file=_sys.stderr)
        return False
    except (OSError, ValueError):
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def _resolve_replay_base_ref(root: Path) -> str:
    """Resolve the git base ref for forward-replay checks.

    Resolution order (first match wins):
    1. ``SPECDEV_REPLAY_BASE_REF`` environment variable (explicit override)
    2. Current branch's upstream tracking branch (``@{upstream}``)
    3. Well-known remote defaults: ``origin/main``, ``origin/master``
    4. Well-known local defaults: ``main``, ``master``
    5. Current branch name (self-diff — effectively a no-op)
    6. Fallback: ``origin/main`` (may fail if remote is not configured)
    """
    explicit = get_config().replay_base_ref
    if explicit:
        return explicit
    upstream = _git_upstream_branch(root)
    if upstream:
        return upstream
    for candidate in DEFAULT_BRANCH_CANDIDATES:
        if _git_ref_exists(root, candidate):
            return candidate
    current = _git_current_branch(root)
    if current:
        return current
    return "origin/main"


def _git_ref_exists(root: Path, ref: str) -> bool:
    cmd = ["git", "-C", str(root), "rev-parse", "--verify", "--quiet", ref]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=10)
    except subprocess.TimeoutExpired:
        return False
    except (OSError, ValueError):
        return False
    return result.returncode == 0


def _git_upstream_branch(root: Path) -> str | None:
    cmd = ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=10)
    except subprocess.TimeoutExpired:
        return None
    except (OSError, ValueError):
        return None
    if result.returncode != 0:
        return None
    out = result.stdout.strip()
    return out or None


def _git_current_branch(root: Path) -> str | None:
    cmd = ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=10)
    except subprocess.TimeoutExpired:
        return None
    except (OSError, ValueError):
        return None
    if result.returncode != 0:
        return None
    out = result.stdout.strip()
    if out in {"", "HEAD"}:
        return None
    return out
