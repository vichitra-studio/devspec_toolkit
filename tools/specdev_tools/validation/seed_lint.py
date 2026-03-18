from __future__ import annotations

import json
import os
import re as _re
from typing import Dict, List, Set

from ..core.errors import SpecError, ensure_spec_errors, make_error
from .validate import validate_file


def project_root_from_spec_dir(spec_dir: str) -> str:
    """Derive the project root from a spec directory path (one level up)."""
    return os.path.abspath(os.path.join(spec_dir, os.pardir))


# Keep private alias for backward compatibility within this module
_project_root_from_spec_dir = project_root_from_spec_dir


def _load_manifest(repo_root: str, project_root: str, errors: List[SpecError]) -> Dict:
    manifest_path = os.path.join(project_root, "spec", "common", "seed_manifest.json")
    if not os.path.exists(manifest_path):
        errors.append(make_error("E520", f"Missing seed manifest: {manifest_path}"))
        return {}

    schema_errors = validate_file(repo_root, manifest_path)
    if schema_errors:
        errors.extend(ensure_spec_errors(schema_errors))

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        errors.append(make_error("E520", f"Failed to read seed manifest: {manifest_path} ({e})"))
        return {}


def _step_from_path(path: str) -> str:
    if os.sep + "impl_context" + os.sep in path:
        return "16"
    filename = os.path.basename(path)
    if "_" in filename:
        return filename.split("_", 1)[0]
    return "unknown"


def _collect_required_seeds(manifest: Dict, step_id: str) -> Set[str]:
    step_requirements = manifest.get("step_requirements", {})
    if step_id == "16":
        sub_keys = ("16a", "16b", "16c")
        if not any(k in step_requirements for k in sub_keys):
            return set()
        required = set()
        for key in sub_keys:
            required.update(step_requirements.get(key, []))
    else:
        if step_id not in step_requirements:
            return set()
        required = set(step_requirements.get(step_id, []))
    global_required = set(manifest.get("global_seed_order", []))
    required.update(global_required)
    return required


def _extract_step_from_prompt_filename(filename: str) -> str:
    """Extract step ID from a prompt filename like 'prompt_05_interface_contracts.md' → '05'."""
    match = _re.match(r"prompt_(\d{2}[a-z]?)_", filename)
    return match.group(1) if match else "unknown"


def _lint_prompt_manifest_refs(
    repo_root: str, errors: List[SpecError], manifest: Dict | None = None
) -> None:
    prompts_dir = os.path.join(repo_root, "prompts")
    if not os.path.isdir(prompts_dir):
        errors.append(make_error("E520", f"Missing prompts directory: {prompts_dir}"))
        return

    # Determine which steps require seeds
    step_requirements = {}
    if manifest:
        step_requirements = manifest.get("step_requirements", {})
    else:
        errors.append(make_error("W150", "seed_manifest not provided — skipping prompt seed-section checks"))

    for fn in os.listdir(prompts_dir):
        if not fn.startswith("prompt_") or not fn.endswith(".md"):
            continue

        step_id = _extract_step_from_prompt_filename(fn)

        # Only enforce seed sections for steps that have entries in step_requirements
        requires_seeds = step_id in step_requirements
        if step_id == "16":
            requires_seeds = any(
                k in step_requirements for k in ("16a", "16b", "16c")
            )

        if not requires_seeds:
            continue

        path = os.path.join(prompts_dir, fn)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except Exception as e:
            errors.append(make_error("E520", f"Failed to read prompt: {path} ({e})"))
            continue
        if "Seed Order & Mandatory Sources" not in text:
            errors.append(make_error("E520", f"{path}: missing 'Seed Order & Mandatory Sources' section"))
        if "spec/common/seed_manifest.json" not in text:
            errors.append(make_error("E520", f"{path}: missing reference to spec/common/seed_manifest.json"))


_STOP_WORDS = frozenset({
    "the", "this", "that", "with", "from", "have", "will", "been", "each",
    "which", "their", "about", "would", "could", "should", "there", "these",
    "those", "other", "after", "before", "where", "being", "does", "into",
    "over", "only", "than", "them", "then", "they", "when", "also", "more",
    "most", "some", "such", "very", "just", "like", "make", "made", "must",
    "need", "used",
})

def _tokenize(text: str) -> set:
    return {w for w in _re.findall(r"[a-z0-9]{4,}", text.lower()) if w not in _STOP_WORDS}


def _check_seed_content_overlap(
    spec_dir: str, manifest: Dict, project_root: str, errors: List[SpecError]
) -> None:
    seed_paths: Dict[str, str] = {}
    for seed in manifest.get("seeds", []):
        if isinstance(seed, dict) and seed.get("seed_id") and seed.get("path"):
            resolved = os.path.normpath(os.path.join(project_root, seed["path"]))
            if os.path.isfile(resolved):
                seed_paths[seed["seed_id"]] = resolved

    for root_dir, _, files in os.walk(spec_dir):
        for fn in files:
            if not fn.endswith(".json"):
                continue
            file_path = os.path.join(root_dir, fn)
            try:
                with open(file_path, "r", encoding="utf-8") as fh:
                    instance = json.load(fh)
            except Exception:
                continue
            seed_refs = instance.get("seed_refs", [])
            if not isinstance(seed_refs, list):
                continue
            spec_text = json.dumps(instance)
            spec_tokens = _tokenize(spec_text)
            for ref in seed_refs:
                if not isinstance(ref, dict):
                    continue
                sid = ref.get("seed_id")
                if not sid or sid not in seed_paths:
                    continue
                try:
                    with open(seed_paths[sid], "r", encoding="utf-8") as fh:
                        seed_text = fh.read()
                except Exception:
                    continue
                seed_tokens = _tokenize(seed_text)
                shared = len(spec_tokens & seed_tokens)
                if shared < 3:
                    errors.append(make_error(
                        "W140", f"SEED_CONTENT_OVERLAP_LOW seed_id={sid} artifact={fn} shared_tokens={shared}"
                    ))


def lint_seeds(
    repo_root: str,
    spec_dir: str,
    project_root: str | None = None,
    strict_mode: bool = False,
) -> List[SpecError]:
    """Lint seed references across spec artifacts.

    Args:
        strict_mode: When ``True``, a project-root mismatch (spec_dir implies
            a different root than the canonical root) is treated as a hard
            error instead of a warning.
    """
    errors: List[SpecError] = []
    # D20 fix: prefer explicit project_root, then repo_root; warn on spec_dir mismatch
    implicit_root = _project_root_from_spec_dir(spec_dir)
    if project_root is None:
        project_root = os.path.abspath(repo_root)
    else:
        project_root = os.path.abspath(project_root)
    if os.path.abspath(implicit_root) != project_root:
        msg = (
            f"spec_dir scope warning: spec_dir '{spec_dir}' implies project root"
            f" '{implicit_root}' but canonical project root is '{project_root}'."
            f" Using canonical root."
        )
        if strict_mode:
            errors.append(make_error("E520", f"UNRESOLVED_INPUT project_root_mismatch: {msg}"))
            return errors
        errors.append(make_error("W570", f"GRACEFUL_SKIP project_root_mismatch: {msg}"))
    manifest = _load_manifest(repo_root, project_root, errors)
    if not manifest:
        return errors

    seed_ids = [s.get("seed_id") for s in manifest.get("seeds", []) if isinstance(s, dict)]
    if len(seed_ids) != len(set(seed_ids)):
        errors.append(make_error("E410", "CANONICAL_ALIAS_COLLISION Seed manifest has duplicate seed_id values."))

    # D19 fix: validate that each seed path exists on disk and doesn't escape project root
    for seed in manifest.get("seeds", []):
        if not isinstance(seed, dict):
            continue
        seed_id = seed.get("seed_id", "unknown")
        seed_path = seed.get("path")
        if not seed_path:
            errors.append(make_error("E520", f"Seed '{seed_id}' is missing 'path' field."))
            continue
        resolved = os.path.normpath(os.path.join(project_root, seed_path))
        if not os.path.isfile(resolved):
            errors.append(make_error(
                "E520",
                f"Seed '{seed_id}' path '{seed_path}' does not exist or is not readable"
                f" (resolved: {resolved})",
            ))
        try:
            common = os.path.commonpath(
                [os.path.abspath(project_root), os.path.abspath(resolved)]
            )
            if common != os.path.abspath(project_root):
                errors.append(make_error(
                    "E520", f"Seed '{seed_id}' path '{seed_path}' escapes project root"
                ))
        except ValueError:
            errors.append(make_error(
                "E520", f"Seed '{seed_id}' path '{seed_path}' escapes project root (different drive)"
            ))

    # G5: Reverse check — detect on-disk seeds not declared in manifest
    declared_paths = set()
    for seed in manifest.get("seeds", []):
        if isinstance(seed, dict) and seed.get("path"):
            declared_paths.add(os.path.normpath(os.path.join(project_root, seed["path"])))

    seed_directory = manifest.get("seed_directory", "docs/seed")
    seed_dir_abs = os.path.join(project_root, seed_directory)
    if os.path.isdir(seed_dir_abs):
        for fn in os.listdir(seed_dir_abs):
            if not fn.endswith(".md"):
                continue
            on_disk_path = os.path.normpath(os.path.join(seed_dir_abs, fn))
            if on_disk_path not in declared_paths:
                errors.append(make_error(
                    "W551", f"UNDECLARED_SEED on-disk seed '{fn}' not declared in seed_manifest.json"
                ))

    seed_id_set = set(seed_ids)
    for sid in manifest.get("global_seed_order", []):
        if sid not in seed_id_set:
            errors.append(make_error("E520", f"global_seed_order references unknown seed_id: {sid}"))

    for layer in manifest.get("nested_order", []):
        for sid in layer.get("seed_ids", []):
            if sid not in seed_id_set:
                errors.append(make_error("E520", f"nested_order references unknown seed_id: {sid}"))

    for step_id, reqs in manifest.get("step_requirements", {}).items():
        for sid in reqs:
            if sid not in seed_id_set:
                errors.append(make_error("E520", f"step_requirements[{step_id}] references unknown seed_id: {sid}"))

    _lint_prompt_manifest_refs(repo_root, errors, manifest)

    _check_seed_content_overlap(spec_dir, manifest, project_root, errors)

    for root, _, files in os.walk(spec_dir):
        for fn in files:
            if not fn.endswith(".json"):
                continue
            file_path = os.path.join(root, fn)
            if os.path.normpath(file_path).endswith(os.path.normpath(os.path.join("spec", "common", "seed_manifest.json"))):
                continue

            step_id = _step_from_path(file_path)
            if step_id == "unknown":
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as fh:
                    instance = json.load(fh)
            except Exception:
                continue

            seed_refs = instance.get("seed_refs", [])
            if not isinstance(seed_refs, list):
                errors.append(make_error("E520", f"{file_path}: seed_refs must be an array"))
                continue

            used_seed_ids = {ref.get("seed_id") for ref in seed_refs if isinstance(ref, dict) and ref.get("seed_id") is not None}
            missing_seed_ids = {sid for sid in used_seed_ids if sid not in seed_id_set}
            for sid in missing_seed_ids:
                errors.append(make_error("E520", f"{file_path}: seed_refs includes unknown seed_id '{sid}'"))

            required = _collect_required_seeds(manifest, step_id)
            missing_required = sorted(required - used_seed_ids)
            if missing_required:
                errors.append(make_error(
                    "E520",
                    f"{file_path}: missing required seed_refs for step {step_id}: {', '.join(missing_required)}",
                ))

    return errors
