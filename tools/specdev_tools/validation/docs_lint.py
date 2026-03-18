from __future__ import annotations

import json
import os
from typing import Dict, List

from ..core.errors import SpecError, make_error


def _project_root_from_spec_dir(spec_dir: str) -> str:
    return os.path.abspath(os.path.join(spec_dir, os.pardir))


def _load_manifest(project_root: str, errors: List[SpecError]) -> Dict:
    manifest_path = os.path.join(project_root, "spec", "common", "seed_manifest.json")
    if not os.path.exists(manifest_path):
        errors.append(make_error("E520", f"Missing seed manifest: {manifest_path}"))
        return {}
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        errors.append(make_error("E520", f"Failed to read seed manifest: {manifest_path} ({e})"))
        return {}


def _normalize_path(path: str) -> str:
    return os.path.normpath(path).replace(os.sep, "/").rstrip("/") + "/"


def _is_excluded(rel_path: str, exclusions: List[str]) -> bool:
    rel = _normalize_path(rel_path)
    for exc in exclusions:
        if rel.startswith(_normalize_path(exc)):
            return True
    return False


def lint_docs(spec_dir: str) -> List[SpecError]:
    errors: List[SpecError] = []
    project_root = _project_root_from_spec_dir(spec_dir)
    manifest = _load_manifest(project_root, errors)
    if not manifest:
        return errors

    docs_policy = manifest.get("docs_policy", {})
    readme_required = docs_policy.get("readme_required", False)
    root_readme_required = docs_policy.get("root_readme_required", False)
    readme_depth_default = docs_policy.get("readme_depth_default", 1)
    readme_depth_by_scope = docs_policy.get("readme_depth_by_scope", {})
    scope = docs_policy.get("scope", [])
    exclusions = docs_policy.get("exclusions", [])
    if os.path.basename(project_root) == "devspec_toolkit":
        for exc in list(exclusions):
            if exc.startswith("devspec_toolkit/"):
                exclusions.append(exc[len("devspec_toolkit/"):])

    if root_readme_required:
        root_readme = os.path.join(project_root, "README.md")
        if not os.path.exists(root_readme):
            errors.append(make_error("E520", f"Missing root README.md at {root_readme}"))

    if not readme_required:
        return errors

    def _normalize_scope(path: str) -> str:
        return path.replace("\\", "/").rstrip("/") + "/"

    normalized_depth_map = {}
    for key, value in readme_depth_by_scope.items():
        if isinstance(key, str) and isinstance(value, int):
            norm_key = _normalize_scope(key)
            normalized_depth_map[norm_key] = value
            if os.path.basename(project_root) == "devspec_toolkit" and norm_key.startswith("devspec_toolkit/"):
                normalized_depth_map[_normalize_scope(norm_key[len("devspec_toolkit/"):])] = value

    def _depth_limit_for(rel_path: str) -> tuple[str, int]:
        rel = _normalize_scope(rel_path)
        best_key = ""
        best_depth = readme_depth_default
        for key, depth in normalized_depth_map.items():
            if rel.startswith(key) and len(key) > len(best_key):
                best_key = key
                best_depth = depth
        return best_key, best_depth

    for scope_entry in scope:
        scope_path = os.path.join(project_root, scope_entry)
        if not os.path.isdir(scope_path):
            if scope_entry.rstrip("/") == "devspec_toolkit" and os.path.basename(project_root) == "devspec_toolkit":
                scope_path = project_root
            else:
                errors.append(make_error("E520", f"Docs scope not found: {scope_path}"))
                continue

        for root, dirs, files in os.walk(scope_path):
            rel_root = os.path.relpath(root, project_root).replace(os.sep, "/")
            if _is_excluded(rel_root, exclusions):
                dirs[:] = []
                continue

            base_key, depth_limit = _depth_limit_for(rel_root)
            base_rel = base_key.rstrip("/") if base_key else _normalize_scope(scope_entry).rstrip("/")
            if base_rel and rel_root.startswith(base_rel):
                suffix = rel_root[len(base_rel):].lstrip("/")
            else:
                suffix = rel_root
            depth = 0 if suffix == "" else len([p for p in suffix.split("/") if p])

            if depth <= depth_limit and "README.md" not in files:
                errors.append(make_error("E520", f"Missing README.md in {root}"))

            # Prune excluded subdirectories from traversal
            pruned = []
            for d in dirs:
                rel_child = os.path.relpath(os.path.join(root, d), project_root).replace(os.sep, "/")
                if not _is_excluded(rel_child, exclusions):
                    pruned.append(d)
            dirs[:] = pruned

    return errors
