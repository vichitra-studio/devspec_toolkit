from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

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
            canonical_errors = validate_canonical_integrity_file(repo_root, path)
            if canonical_errors:
                enhanced_errors.extend(canonical_errors)

        return enhanced_errors
    except FileNotFoundError as e:
        return [f"E520 UNRESOLVED_INPUT {path}: input_file_not_found detail={str(e)}"]
    except (OSError, json.JSONDecodeError, ValueError, KeyError, AttributeError, TypeError) as e:
        return [f"E520 UNRESOLVED_INPUT {path}: validation_input_error {type(e).__name__}: {str(e)}"]

def validate_dir(repo_root: str, spec_dir: str) -> list[str]:
    failures = []

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
    failures.extend(lint_hallucinations(spec_dir, repo_root=repo_root))
    failures.extend(validate_canonical_integrity(repo_root, spec_dir))

    root = Path(os.path.abspath(repo_root))
    failures.extend(lint_canon_dir(repo_root))
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

    return failures


def _load_component_ids(repo_root: str, file_path: str) -> set[str] | None:
    sketch_path = os.path.join(os.path.dirname(file_path), "02_system_sketch.json")
    if not os.path.exists(sketch_path):
        sketch_path = os.path.join(repo_root, "spec", "02_system_sketch.json")
    if not os.path.exists(sketch_path):
        return None
    try:
        with open(sketch_path, "r", encoding="utf-8") as f:
            cid_data = json.load(f)
        return {c.get("component_id") for c in cid_data.get("components", []) if c.get("component_id")}
    except (OSError, json.JSONDecodeError, ValueError, TypeError, AttributeError):
        return None


def _run_deep_validation(step: str, data: dict, repo_root: str, path: str) -> list[str]:
    try:
        if step == "01":
            return step_01.validate_step_01(data, repo_root, _load_component_ids(repo_root, path))
        if step == "02":
            return step_02.validate_step_02(data, repo_root)
        if step == "02a":
            return step_02a.validate_step_02a(data, repo_root)
        if step == "03":
            return step_03.validate_step_03(data, repo_root)
        if step == "04":
            return step_04.validate_step_04(data, repo_root)
        if step == "05":
            return step_05.validate_step_05(data, repo_root)
        if step == "06":
            return step_06.validate_step_06(data, repo_root)
        if step == "07":
            return step_07.validate_step_07(data, repo_root)
        if step == "08":
            return step_08.validate_step_08(data, repo_root)
        if step == "09":
            return step_09.validate_step_09(data, repo_root)
        if step == "10":
            return step_10.validate_step_10(data, repo_root)
        if step == "11":
            return step_11.validate_step_11(data, repo_root)
        if step == "12":
            return step_12.validate_step_12(data, repo_root)
        if step == "13":
            return step_13.validate_step_13(data, repo_root)
        if step == "13a":
            return step_13a.validate_step_13a(data, repo_root)
        if step == "14":
            return step_14.validate_step_14(data, repo_root, path)
        if step == "15":
            return step_15.validate_step_15(data, repo_root)
        if step == "16":
            return step_16.validate_step_16(data, repo_root, path)
    except Exception as e:
        return [f"Deep Validation Critical Error: {str(e)}"]
    return []


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
