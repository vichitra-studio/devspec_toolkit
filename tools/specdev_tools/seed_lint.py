from __future__ import annotations

import json
import os
from typing import Dict, List, Set

from .validate import validate_file


def _project_root_from_spec_dir(spec_dir: str) -> str:
    return os.path.abspath(os.path.join(spec_dir, os.pardir))


def _load_manifest(repo_root: str, project_root: str, errors: List[str]) -> Dict:
    manifest_path = os.path.join(project_root, "spec", "common", "seed_manifest.json")
    if not os.path.exists(manifest_path):
        errors.append(f"Missing seed manifest: {manifest_path}")
        return {}

    schema_errors = validate_file(repo_root, manifest_path)
    if schema_errors:
        errors.extend(schema_errors)

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        errors.append(f"Failed to read seed manifest: {manifest_path} ({e})")
        return {}


def _step_from_path(path: str) -> str:
    if os.sep + "impl_context" + os.sep in path:
        return "16"
    filename = os.path.basename(path)
    if "_" in filename:
        return filename.split("_", 1)[0]
    return "unknown"


def _collect_required_seeds(manifest: Dict, step_id: str) -> Set[str]:
    global_required = set(manifest.get("global_seed_order", []))
    step_requirements = manifest.get("step_requirements", {})
    if step_id == "16":
        required = set()
        for key in ("16a", "16b", "16c"):
            required.update(step_requirements.get(key, []))
        required.update(global_required)
        return required
    required = set(step_requirements.get(step_id, []))
    required.update(global_required)
    return required


def _lint_prompt_manifest_refs(repo_root: str, errors: List[str]) -> None:
    prompts_dir = os.path.join(repo_root, "prompts")
    if not os.path.isdir(prompts_dir):
        errors.append(f"Missing prompts directory: {prompts_dir}")
        return

    for fn in os.listdir(prompts_dir):
        if not fn.startswith("prompt_") or not fn.endswith(".md"):
            continue
        path = os.path.join(prompts_dir, fn)
        try:
            text = open(path, "r", encoding="utf-8").read()
        except Exception as e:
            errors.append(f"Failed to read prompt: {path} ({e})")
            continue
        if "Seed Order & Mandatory Sources" not in text:
            errors.append(f"{path}: missing 'Seed Order & Mandatory Sources' section")
        if "spec/common/seed_manifest.json" not in text:
            errors.append(f"{path}: missing reference to spec/common/seed_manifest.json")


def lint_seeds(repo_root: str, spec_dir: str) -> List[str]:
    errors: List[str] = []
    project_root = _project_root_from_spec_dir(spec_dir)
    manifest = _load_manifest(repo_root, project_root, errors)
    if not manifest:
        return errors

    seed_ids = [s.get("seed_id") for s in manifest.get("seeds", []) if isinstance(s, dict)]
    if len(seed_ids) != len(set(seed_ids)):
        errors.append("Seed manifest has duplicate seed_id values.")

    seed_id_set = set(seed_ids)
    for sid in manifest.get("global_seed_order", []):
        if sid not in seed_id_set:
            errors.append(f"global_seed_order references unknown seed_id: {sid}")

    for layer in manifest.get("nested_order", []):
        for sid in layer.get("seed_ids", []):
            if sid not in seed_id_set:
                errors.append(f"nested_order references unknown seed_id: {sid}")

    for step_id, reqs in manifest.get("step_requirements", {}).items():
        for sid in reqs:
            if sid not in seed_id_set:
                errors.append(f"step_requirements[{step_id}] references unknown seed_id: {sid}")

    _lint_prompt_manifest_refs(repo_root, errors)

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
                instance = json.load(open(file_path, "r", encoding="utf-8"))
            except Exception:
                continue

            seed_refs = instance.get("seed_refs", [])
            if not isinstance(seed_refs, list):
                errors.append(f"{file_path}: seed_refs must be an array")
                continue

            used_seed_ids = {ref.get("seed_id") for ref in seed_refs if isinstance(ref, dict)}
            missing_seed_ids = {sid for sid in used_seed_ids if sid not in seed_id_set}
            for sid in missing_seed_ids:
                errors.append(f"{file_path}: seed_refs includes unknown seed_id '{sid}'")

            required = _collect_required_seeds(manifest, step_id)
            missing_required = sorted(required - used_seed_ids)
            if missing_required:
                errors.append(
                    f"{file_path}: missing required seed_refs for step {step_id}: {', '.join(missing_required)}"
                )

    return errors
