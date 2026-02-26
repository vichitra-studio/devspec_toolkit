from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator
from jsonschema.exceptions import _WrappedReferencingError
from referencing import Registry, Resource

from .canonical_integrity import validate_canonical_integrity, validate_canonical_integrity_file
from .canonical_lint import lint_canon_dir
from .dependency_order_lint import lint_dependency_order
from .forward_replay_check import check_forward_replay
from .hallucination_lint import lint_hallucinations
from .prompt_schema_sync import run_prompt_schema_sync
from .registry import SchemaRegistry
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
)

STEP_FILE_RE = re.compile(r"^(\d{2}[a-z]?)_")
STEP_DIR_RE = re.compile(r"^step_(\d{2}[a-z]?)$")

def _registry_for(registry: SchemaRegistry) -> Registry:
    store = {uri: Resource.from_contents(schema) for uri, schema in registry.store.items()}
    return Registry().with_resources(store.items())

def _get_step_from_path(path: str) -> str:
    """Extract step number from file path"""
    filename = os.path.basename(path)

    match = STEP_FILE_RE.match(filename)
    if match:
        return match.group(1)

    dirname = os.path.dirname(path)
    if dirname:
        dirname = os.path.basename(dirname)
        match = STEP_DIR_RE.match(dirname)
        if match:
            return match.group(1)

    return "unknown"

def _get_prompt_path(path: str) -> str:
    """Get corresponding prompt file path"""
    step = _get_step_from_path(path)
    if step != "unknown":
        return f"prompts/prompt_{step}*.md"
    return "prompts/*.md"

def validate_file(
    repo_root: str,
    path: str,
    include_quality_lint: bool = True,
    include_canonical_integrity: bool = True,
) -> list[str]:
    try:
        registry = SchemaRegistry(repo_root)
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as e:
        return [f"E520 UNRESOLVED_INPUT {path}: schema_registry_bootstrap_failed detail={str(e)}"]
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return [
                f"E520 UNRESOLVED_INPUT {path}: invalid_document_root_type "
                f"expected=object got={type(data).__name__}"
            ]

        schema_uri = data.get("$schema")
        if schema_uri is None:
            return [f"E520 UNRESOLVED_INPUT {path}: missing_schema_uri"]
        if not isinstance(schema_uri, str):
            return [
                f"E520 UNRESOLVED_INPUT {path}: invalid_schema_uri_type "
                f"expected=str got={type(schema_uri).__name__}"
            ]
        schema_uri = schema_uri.strip()
        if not schema_uri:
            return [f"E520 UNRESOLVED_INPUT {path}: missing_schema_uri"]

        try:
            schema = registry.load(schema_uri)
        except FileNotFoundError as e:
            return [f"E520 UNRESOLVED_INPUT {path}: schema_not_found uri={schema_uri} detail={str(e)}"]
        except json.JSONDecodeError as e:
            return [f"E520 UNRESOLVED_INPUT {path}: schema_json_decode_failed uri={schema_uri} detail={str(e)}"]

        # Exclude $schema from validation payload because many step schemas disallow unknown keys
        data_for_validation = dict(data)
        data_for_validation.pop("$schema", None)

        # Build a resolver store
        reg = _registry_for(registry)
        v = Draft202012Validator(
            schema,
            registry=reg,
            format_checker=Draft202012Validator.FORMAT_CHECKER
        )
        try:
            errors = sorted(v.iter_errors(data_for_validation), key=lambda e: e.path)
        except _WrappedReferencingError as e:
            return [f"E520 UNRESOLVED_INPUT {path}: schema_reference_resolution_failed {str(e)}"]
        except Exception as e:
            return [f"E521 VALIDATOR_RUNTIME {path}: schema_validation_runtime_error {type(e).__name__}: {str(e)}"]
        
        # Enhance error messages with context
        enhanced_errors = []
        for e in errors:
            error_msg = f"{path}:{'/'.join(map(str, e.path))}: {e.message}"
            
            # Add context about what to do next
            step = _get_step_from_path(path)
            if step != "unknown":
                prompt_path = _get_prompt_path(path)
                error_msg += f"\n  See: {prompt_path} for guidance on requirements"
            
            enhanced_errors.append(error_msg)
            
        step = _get_step_from_path(path)
        deep_errors = _run_deep_validation(step, data, repo_root, path)
        if deep_errors:
            enhanced_errors.extend([f"{path}: {e}" for e in deep_errors])

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
            )
            if canonical_errors:
                enhanced_errors.extend(canonical_errors)

        return enhanced_errors
    except FileNotFoundError as e:
        return [f"E520 UNRESOLVED_INPUT {path}: input_file_not_found detail={str(e)}"]
    except (OSError, json.JSONDecodeError, ValueError, KeyError, AttributeError, TypeError) as e:
        return [f"E520 UNRESOLVED_INPUT {path}: validation_input_error {type(e).__name__}: {str(e)}"]

def validate_dir(repo_root: str, spec_dir: str) -> list[str]:
    failures = []
    canonical_preflight_errors = list(
        dict.fromkeys(
            lint_canon_dir(
                repo_root,
                require_manifest_schema_registration=True,
            )
        )
    )
    if _has_canonical_bootstrap_failure(canonical_preflight_errors):
        return canonical_preflight_errors

    for root, _, files in os.walk(spec_dir):
        for fn in files:
            if fn.endswith(".json"):
                file_path = os.path.join(root, fn)
                failures.extend(
                    validate_file(
                        repo_root,
                        file_path,
                        include_quality_lint=False,
                        include_canonical_integrity=False,
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
            )
        )
        failures.extend(
            validate_canonical_integrity(
                repo_root,
                spec_dir,
                require_manifest_schema_registration=True,
            )
        )
        from .traceability_closure import check_traceability_closure
        tc_errors = check_traceability_closure(spec_dir, repo_root)
        failures.extend(tc_errors)

    root = Path(os.path.abspath(repo_root))
    if (root / "tools" / "step_order.json").exists() and (root / "prompts").exists():
        step_order = _load_step_order(root / "tools" / "step_order.json")
        dep_errors = lint_dependency_order(repo_root)
        failures.extend(dep_errors)
        if step_order.get("require_full_forward_replay_on_change", True):
            if not any("invalid_step_order" in e for e in dep_errors):
                mode = os.getenv("SPECDEV_REPLAY_DIFF_ERROR_MODE", "").strip().lower()
                if not mode:
                    in_ci = os.getenv("CI", "").strip().lower() in {"1", "true", "yes"}
                    mode = "error" if (in_ci or _is_git_repo(root)) else "ignore"
                base_ref = _resolve_replay_base_ref(root)
                failures.extend(check_forward_replay(repo_root, base_ref=base_ref, diff_error_mode=mode))
    if (root / "schema").exists() and (root / "prompts").exists():
        failures.extend(run_prompt_schema_sync(repo_root))

    # Honor SPECDEV_WARNINGS_AS_ERRORS for any W-coded traceability gaps,
    # and deduplicate divergent error signals (duplicate reporting of gaps)
    warn_as_error = os.getenv("SPECDEV_WARNINGS_AS_ERRORS", "").strip().lower() in {"1", "true", "yes"}
    
    if warn_as_error:
        failures = [f.replace("W560", "E560", 1) if f.startswith("W560") else f for f in failures]
        
    failures = list(dict.fromkeys(failures))
    
    if not warn_as_error:
        e560_bases = {f.replace("E560", "W560", 1) for f in failures if f.startswith("E560")}
        failures = [f for f in failures if not (f.startswith("W560") and f in e560_bases)]

    return failures


def _has_canonical_bootstrap_failure(errors: list[str]) -> bool:
    bootstrap_tokens = (
        "missing_schema_registry",
        "schema_uri_not_registered",
        "schema_registry_bootstrap_failed",
    )
    return any(any(token in err for token in bootstrap_tokens) for err in errors)


def _load_json_artifact(repo_root: str, file_path: str, filename: str) -> dict[str, Any] | None:
    candidates: list[str] = []
    if file_path:
        candidates.append(os.path.join(os.path.dirname(file_path), filename))
    candidates.append(os.path.join(repo_root, "spec", filename))

    seen: set[str] = set()
    for candidate in candidates:
        candidate = os.path.abspath(candidate)
        if candidate in seen:
            continue
        seen.add(candidate)
        if not os.path.exists(candidate):
            continue
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                loaded = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            continue
        if isinstance(loaded, dict):
            return loaded
    return None


def _load_component_ids(repo_root: str, file_path: str) -> set[str] | None:
    sketch = _load_json_artifact(repo_root, file_path, "02_system_sketch.json")
    if not isinstance(sketch, dict):
        return None
    components = sketch.get("components", [])
    if not isinstance(components, list):
        return None
    return {c.get("component_id") for c in components if isinstance(c, dict) and c.get("component_id")}


def _load_capability_ids(repo_root: str, file_path: str) -> set[str] | None:
    caps = _load_json_artifact(repo_root, file_path, "01_capabilities.json")
    if not isinstance(caps, dict):
        return None
    capability_items = caps.get("capabilities", [])
    if not isinstance(capability_items, list):
        return None
    return {
        cap.get("capability_id")
        for cap in capability_items
        if isinstance(cap, dict) and cap.get("capability_id")
    }


def _load_nfrs_data(repo_root: str, file_path: str) -> dict[str, Any] | None:
    return _load_json_artifact(repo_root, file_path, "07_nfrs.json")


def _load_monitoring_data(repo_root: str, file_path: str) -> dict[str, Any] | None:
    for filename in ("16_impl_context.json", "16_delivery_monitoring.json"):
        loaded = _load_json_artifact(repo_root, file_path, filename)
        if isinstance(loaded, dict):
            return loaded
    return None


def _build_validation_context(repo_root: str, path: str) -> dict[str, Any]:
    return {
        "artifact_path": path,
        "component_ids": _load_component_ids(repo_root, path),
        "capability_ids": _load_capability_ids(repo_root, path),
        "nfrs_data": _load_nfrs_data(repo_root, path),
        "monitoring_data": _load_monitoring_data(repo_root, path),
    }


DeepValidator = Callable[[dict[str, Any], str, dict[str, Any]], list[str]]


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
    "04": lambda instance, root, ctx: step_04.validate_step_04(instance, root),
    "05": lambda instance, root, ctx: step_05.validate_step_05(instance, root),
    "06": lambda instance, root, ctx: step_06.validate_step_06(instance, root),
    "07": lambda instance, root, ctx: step_07.validate_step_07(instance, root),
    "08": lambda instance, root, ctx: step_08.validate_step_08(instance, root),
    "09": lambda instance, root, ctx: step_09.validate_step_09(instance, root),
    "10": lambda instance, root, ctx: step_10.validate_step_10(instance, root),
    "11": lambda instance, root, ctx: step_11.validate_step_11(instance, root),
    "12": lambda instance, root, ctx: step_12.validate_step_12(instance, root),
    "13": lambda instance, root, ctx: step_13.validate_step_13(instance, root),
    "13a": lambda instance, root, ctx: step_13a.validate_step_13a(instance, root),
    "14": lambda instance, root, ctx: step_14.validate_step_14(instance, root, ctx.get("artifact_path")),
    "15": lambda instance, root, ctx: step_15.validate_step_15(instance, root),
    "16": lambda instance, root, ctx: step_16.validate_step_16(instance, root, ctx.get("artifact_path")),
}


def _run_deep_validation(step: str, data: dict, repo_root: str, path: str) -> list[str]:
    validator = DEEP_VALIDATORS.get(step)
    if validator is None:
        return []
    context = _build_validation_context(repo_root, path)
    try:
        return validator(data, repo_root, context)
    except Exception as e:
        return [f"Deep Validation Critical Error: {str(e)}"]


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


def _is_git_repo(root: Path) -> bool:
    cmd = ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except (OSError, ValueError):
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def _resolve_replay_base_ref(root: Path) -> str:
    explicit = os.getenv("SPECDEV_REPLAY_BASE_REF", "").strip()
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
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except (OSError, ValueError):
        return False
    return result.returncode == 0


def _git_upstream_branch(root: Path) -> str | None:
    cmd = ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except (OSError, ValueError):
        return None
    if result.returncode != 0:
        return None
    out = result.stdout.strip()
    return out or None


def _git_current_branch(root: Path) -> str | None:
    cmd = ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except (OSError, ValueError):
        return None
    if result.returncode != 0:
        return None
    out = result.stdout.strip()
    if out in {"", "HEAD"}:
        return None
    return out
