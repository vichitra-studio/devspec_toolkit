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
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator
from jsonschema.exceptions import _WrappedReferencingError  # type: ignore[attr-defined]
from ..canonical.integrity import validate_canonical_integrity, validate_canonical_integrity_file
from ..canonical.lint import lint_canon_dirs
from .dependency_order_lint import lint_dependency_order
from .forward_replay_check import check_forward_replay
from .extraction_intent_check import check_extraction_intent
from .hallucination_lint import lint_hallucinations
from ..generation.prompt_schema_sync import run_prompt_schema_sync
from ..core.config import get_config, reset_config
from ..core.errors import PROMOTABLE_PAIRS, SpecError, make_error
from ..core.loaders import iter_spec_artifacts, load_json_artifact, load_sibling_artifact
from ..core.registry import SchemaRegistry
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


STEP_FILE_RE = re.compile(r"^(\d{2}[a-z]?)_")
STEP_DIR_RE = re.compile(r"^step_(\d{2}[a-z]?)$")
IMPL_CONTEXT_DIR_RE = re.compile(r"^impl_context$")

def _get_step_from_path(path: str) -> str:
    """Extract step number from file path.

    Handles standard ``NN_name.json`` filenames, ``step_NN/`` directories,
    and ``impl_context/`` directories.

    Routing rules for Step 16 artifacts:
    - ``16_impl_context.json`` NOT inside ``impl_context/`` → step ``"16"``
      (Trinity Anchor; dispatches to validate_step_16_anchor).
    - Any ``.json`` inside an ``impl_context/`` directory → step ``"16a"``
      by default.  ``_refine_impl_context_substep`` promotes to ``"16b"`` or
      ``"16c"`` based on artifact content (presence of ``execution.execution_results``
      or ``review.verdict``).  All three sub-step validators now chain up through
      their predecessors, so dispatching to the highest-phase validator runs
      every earlier phase's checks as well.
    """
    filename = os.path.basename(path)

    # Anchor: 16_impl_context.json NOT inside impl_context/ → step "16"
    # Check this before the generic STEP_FILE_RE so the specific filename
    # takes priority over the numeric-prefix pattern.
    dirname_full = os.path.dirname(path)
    if filename == "16_impl_context.json" and os.path.basename(dirname_full) != "impl_context":
        return "16"

    match = STEP_FILE_RE.match(filename)
    if match:
        return match.group(1)

    dirname = os.path.basename(dirname_full) if dirname_full else ""
    if dirname:
        match = STEP_DIR_RE.match(dirname)
        if match:
            return match.group(1)
        if IMPL_CONTEXT_DIR_RE.match(dirname):
            # Default to "16a" for impl_context/ artifacts.  Content-based
            # refinement (see _refine_impl_context_substep) promotes to
            # "16b"/"16c" once the artifact is loaded.
            return "16a"

    return "unknown"


def _refine_impl_context_substep(step: str, data: Any) -> str:
    """Promote/demote ``impl_context/`` dispatch by artifact content.

    All three Trinity sub-step artifacts share ``spec/impl_context/`` and the
    ``vc:16-impl-context`` schema, so path alone cannot distinguish them.
    Content signals the highest phase present:

    - ``artifact_role == "anchor"``                      → ``"16"`` (misfiled anchor)
    - ``review.verdict`` present (non-empty string)      → ``"16c"`` (reviewer output)
    - ``execution.execution_results`` populated (len>0)  → ``"16b"`` (coder output)
    - otherwise                                          → ``"16a"`` (planner output)

    ``validate_step_16c`` chains through ``validate_step_16b`` → ``validate_step_16a``,
    so routing to the highest phase runs every earlier phase's checks as well.
    Non-``"16a"`` inputs are returned unchanged — this function is a no-op for
    charter artifacts, scaffold artifacts, etc.

    Anchor demotion rationale: when an author drops the anchor file inside
    ``spec/impl_context/`` by mistake, ``_get_step_from_path`` classifies it as
    ``"16a"`` by directory.  Without this demotion the file would be deep-validated
    by ``validate_step_16a`` and emit confusing 16a-specific errors (missing
    ``plan.status``, missing ``spec_alignment.checklist``) instead of being
    routed to the anchor validator.  The anchor validator's ``_is_anchor`` + W586
    signal then surfaces the real problem — wrong location for this artifact_role.

    Note on invalid verdicts: promotion triggers on *any* non-empty string in
    ``review.verdict`` — including values outside the ``VALID_VERDICTS`` enum
    (e.g. ``"TOTALLY_INVALID"``).  This is intentional: the enum check lives
    inside ``validate_step_16c``, so routing must reach it *first* for the
    E520 signal to fire.  Demoting unknown verdicts back to 16a would silence
    that diagnostic.
    """
    if step != "16a" or not isinstance(data, dict):
        return step
    # ``.strip()`` for consistency with the verdict check below — schema enforces
    # the const ``"anchor"`` exactly, but defensive normalisation keeps routing
    # symmetric (a stray trailing space in either field shouldn't break dispatch
    # silently while the schema validator separately complains).
    artifact_role = data.get("artifact_role")
    if isinstance(artifact_role, str) and artifact_role.strip() == "anchor":
        return "16"
    review = data.get("review")
    if isinstance(review, dict) and isinstance(review.get("verdict"), str) and review["verdict"].strip():
        return "16c"
    execution = data.get("execution")
    if isinstance(execution, dict):
        results = execution.get("execution_results")
        if isinstance(results, list) and len(results) > 0:
            return "16b"
    return "16a"

def validate_file(
    repo_root: str,
    path: str,
    include_quality_lint: bool = True,
    include_canonical_integrity: bool = True,
    project_canon_dir: str | None = None,
    git_root: str | None = None,
    spec_root: str | None = None,
) -> list[SpecError]:
    # Clear the step-16 chain-up cache so long-lived processes that call
    # validate_file repeatedly do not accumulate cached entries.  The cache's
    # only role is deduplicating the 16c→16b→16a→base chain inside ONE
    # artifact; entries from prior artifacts are never queried again because
    # the cache key includes spec_path.  validate_dir already clears it once
    # per run; this clear protects single-file callers (CLI ``validate``, IDE
    # integrations, daemon-mode hosts).
    from .validators.step_16 import _step16_cache
    _step16_cache.clear()

    try:
        registry = SchemaRegistry(repo_root)
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
            schema = registry.load(schema_uri)
        except FileNotFoundError as e:
            return [make_error("E520", f"{path}: schema_not_found uri={schema_uri} detail={str(e)}")]
        except json.JSONDecodeError as e:
            return [make_error("E520", f"{path}: schema_json_decode_failed uri={schema_uri} detail={str(e)}")]

        # Exclude $schema from validation payload because many step schemas disallow unknown keys
        data_for_validation = dict(data)
        data_for_validation.pop("$schema", None)

        # Build a resolver store
        reg = registry.to_referencing_registry()
        v = Draft202012Validator(
            schema,
            registry=reg,
            format_checker=Draft202012Validator.FORMAT_CHECKER
        )
        try:
            errors = sorted(v.iter_errors(data_for_validation), key=lambda e: e.path)
        except _WrappedReferencingError as e:
            return [make_error("E520", f"{path}: schema_reference_resolution_failed {str(e)}")]
        except Exception as e:
            return [make_error("E521", f"{path}: schema_validation_runtime_error {type(e).__name__}: {str(e)}")]

        # Resolve step once — use content-based refinement for impl_context/
        # artifacts so 16b/16c sub-step validators actually run during
        # validate_file (path-only routing always yielded "16a").
        step = _refine_impl_context_substep(_get_step_from_path(path), data)

        # Enhance error messages with context
        enhanced_errors: list[SpecError] = []
        for e in errors:
            error_msg = f"{path}:{'/'.join(map(str, e.path))}: {e.message}"

            # Add context about what to do next
            if step != "unknown":
                prompt_path = f"prompts/prompt_{step}*.md"
                error_msg += f"\n  See: {prompt_path} for guidance on requirements"

            enhanced_errors.append(make_error("E520", error_msg))

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
    # Clear the step-16 content-hash cache so long-lived processes do not
    # accumulate entries across successive validate_dir invocations.  The cache
    # is a correctness-neutral optimisation for chain-up (16c→16b→16a→base);
    # keeping it across runs would leak memory without benefit because each
    # validate_dir walks a fresh set of artifacts.
    from .validators.step_16 import _step16_cache
    _step16_cache.clear()

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

    failures.extend(lint_spec_quality(spec_dir))
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
                git_root = _detect_git_root(root)
                base_ref = _resolve_replay_base_ref(git_root)
                failures.extend(
                    check_forward_replay(
                        repo_root,
                        base_ref=base_ref,
                        diff_error_mode=mode,
                        git_root=str(git_root),
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
            promoted.append(SpecError(code=new_code, message=err.message, path=err.path))
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


def _load_component_ids(repo_root: str, file_path: str) -> set[str] | None:
    """Thin wrapper around ``load_sibling_artifact``.

    ``load_sibling_artifact`` now distinguishes "file absent" (``None``) from
    "file present but empty" (``set()``); this wrapper simply propagates that
    contract so ``_build_validation_context`` consumers can run cross-ref
    validation against a present-but-empty upstream and still flag stray refs.
    """
    return load_sibling_artifact(file_path, "02", "components", "component_id", fallback_root=repo_root)


def _load_capability_ids(repo_root: str, file_path: str) -> set[str] | None:
    """Thin wrapper: see ``_load_component_ids`` rationale."""
    return load_sibling_artifact(file_path, "01", "capabilities", "capability_id", fallback_root=repo_root)


def _load_nfrs_data(repo_root: str, file_path: str) -> dict[str, Any] | None:
    """Load full NFR data dict (not just IDs) for step_03 cross-ref validation.

    Cannot use ``load_upstream_ids`` because step_03 needs the entire JSON dict,
    not a set of IDs (AUDIT-019)."""
    # Try sibling first, then fallback to spec/
    for prefix in ("07",):
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
        "component_ids": _load_component_ids(repo_root, path),
        "capability_ids": _load_capability_ids(repo_root, path),
        "nfrs_data": _load_nfrs_data(repo_root, path),
        "monitoring_data": _load_monitoring_data(repo_root, path),
    }


DeepValidator = Callable[[dict[str, Any], str, dict[str, Any]], list[SpecError]]


# Hardcoded step→validator mapping.  A future enhancement could auto-discover
# validators via an entry-point or a naming convention scan of the validators/
# package, but the explicit dict keeps startup predictable and avoids import
# side-effects.  See AUDIT-043 for the auto-discovery proposal.
DEEP_VALIDATORS: dict[str, DeepValidator] = {
    "01": lambda instance, root, ctx: step_01.validate_step_01(instance, root, ctx.get("component_ids")),
    "02": lambda instance, root, ctx: step_02.validate_step_02(instance, root, ctx.get("capability_ids")),
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
    #   via path regex. _refine_impl_context_substep(step, data) then promotes the step
    #   based on content:  non-empty review.verdict → "16c",  non-empty
    #   execution.execution_results → "16b",  else stays at "16a". Chain-up inside the
    #   validators (16c→16b→16a→base) preserves downstream checks; _step16_cache
    #   deduplicates the base pass so chain-up is O(1) in base work.
    "16": lambda instance, root, ctx: step_16_anchor.validate_step_16_anchor(instance, root, ctx.get("artifact_path")),
    "16a": lambda instance, root, ctx: step_16a.validate_step_16a(instance, root, ctx.get("artifact_path")),
    "16b": lambda instance, root, ctx: step_16b.validate_step_16b(instance, root, ctx.get("artifact_path")),
    "16c": lambda instance, root, ctx: step_16c.validate_step_16c(instance, root, ctx.get("artifact_path")),
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
    if validator is None:
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
    the host repo root.  This function walks up looking for a non-bare
    ``.git`` directory (or file, as submodules use ``.git`` files).
    Falls back to *repo_root* if detection fails.
    """
    cmd = ["git", "-C", str(repo_root), "rev-parse", "--show-toplevel"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=10)
        if result.returncode == 0:
            detected = Path(result.stdout.strip())
            if detected.exists():
                return detected
    except (subprocess.TimeoutExpired, OSError, ValueError):
        pass
    return repo_root


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
    for candidate in ("origin/main", "origin/master", "main", "master"):
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
