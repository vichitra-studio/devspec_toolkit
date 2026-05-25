from __future__ import annotations

import json
import os
import re as _re
from pathlib import Path
from typing import Dict, List

from ..core.errors import SpecError, ensure_spec_errors, make_error
from ..core.loaders import iter_spec_artifacts
from ..core.seed_routing import resolve_seeds_for_step, resolve_seed_paths
from .validate import validate_file


# W554 HARDCODED_SEED_REFERENCE — matches literal seed-doc filenames like
# seed_overview.md, seed_tech_stack.md, etc. that end in .md.
# The pattern seed_\w+\.md cannot match seed_manifest.json because that
# filename ends in .json (not .md), so the \.md suffix acts as the exclusion.
_HARDCODED_SEED_RE = _re.compile(r"\bseed_\w+\.md\b")


def check_hardcoded_seed_reference(repo_root: str) -> List[SpecError]:
    r"""Scan prompt files for literal seed-doc filenames (W554 HARDCODED_SEED_REFERENCE).

    Globs ``prompts/**/*.md`` recursively from *repo_root* and flags any line
    containing a pattern like ``seed_overview.md``, ``seed_tech_stack.md``, etc.
    The pattern ``seed_\w+\.md`` deliberately excludes ``seed_manifest.json``
    (wrong suffix) and the manifest-anchored ``**Seeds**:`` bullets that only
    reference ``seed_manifest.json``.

    Args:
        repo_root: Path to the toolkit (or host-repo) root containing ``prompts/``.

    Returns:
        List of W554 SpecError objects, one per matching line.
    """
    errors: List[SpecError] = []
    prompts_dir = Path(os.path.abspath(repo_root)) / "prompts"
    if not prompts_dir.is_dir():
        return errors

    for prompt_path in sorted(prompts_dir.rglob("*.md")):
        try:
            text = prompt_path.read_text(encoding="utf-8")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            m = _HARDCODED_SEED_RE.search(line)
            if m:
                rel = str(prompt_path.relative_to(Path(os.path.abspath(repo_root))))
                errors.append(make_error(
                    "W554",
                    f"HARDCODED_SEED_REFERENCE {rel}:{lineno}: literal seed filename"
                    f" '{m.group()}' — route seeds via seed_manifest.json instead",
                ))
    return errors


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


def _collect_required_seeds(manifest: Dict, step_id: str) -> List[str]:
    """Return the ordered list of seed IDs required by *step_id*.

    Delegates to ``seed_routing.resolve_seeds_for_step``.  Returns only
    *step_seed_ids* (second element of the tuple) — the seeds required by this
    specific step, ordered by global_seed_order with extras appended.  The
    global_seed_ids (first element) are intentionally discarded to avoid
    widening W140 false-positives across all step–artifact pairs.
    """
    _, step_seed_ids = resolve_seeds_for_step(step_id, manifest)
    return step_seed_ids


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
    # Resolve all seed IDs declared in the manifest to absolute paths.
    # resolve_seed_paths does NOT existence-filter; we keep only paths that
    # exist on disk, matching the prior behaviour.
    all_seed_ids = [
        s.get("seed_id") for s in manifest.get("seeds", [])
        if isinstance(s, dict) and s.get("seed_id")
    ]
    raw_paths = resolve_seed_paths(manifest, all_seed_ids, project_root)
    seed_paths: Dict[str, str] = {
        sid: os.path.normpath(p)
        for sid, p in raw_paths.items()
        if os.path.isfile(os.path.normpath(p))
    }

    for file_path in iter_spec_artifacts(spec_dir):
        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                instance = json.load(fh)
        except Exception:
            continue
        step_id = _step_from_path(file_path)
        required_seeds = _collect_required_seeds(manifest, step_id)
        if not required_seeds:
            continue
        spec_text = json.dumps(instance)
        spec_tokens = _tokenize(spec_text)
        for sid in required_seeds:
            if sid not in seed_paths:
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
                    "W140", f"SEED_CONTENT_OVERLAP_LOW seed_id={sid} artifact={os.path.basename(file_path)} shared_tokens={shared}"
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

    # Derive scan directories from the parent directories of declared seed paths.
    # This avoids the hardcoded "docs/seed" fallback that misfires when the
    # host places seeds elsewhere.  Each unique parent is scanned once.
    scan_dirs: set = set()
    for seed in manifest.get("seeds", []):
        if isinstance(seed, dict) and seed.get("path"):
            seed_abs = os.path.normpath(os.path.join(project_root, seed["path"]))
            scan_dirs.add(os.path.dirname(seed_abs))
    for seed_dir_abs in scan_dirs:
        if not os.path.isdir(seed_dir_abs):
            continue
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

    # Load valid pipeline step IDs from step_order.json (toolkit-side).
    # Inline load to avoid import-time I/O; cached in a local variable.
    _step_order_path = os.path.join(repo_root, "tools", "step_order.json")
    try:
        with open(_step_order_path, "r", encoding="utf-8") as _f:
            _valid_steps: frozenset = frozenset(json.load(_f).get("steps", []))
    except Exception:
        _valid_steps = frozenset()

    for step_id, reqs in manifest.get("step_requirements", {}).items():
        for sid in reqs:
            if sid not in seed_id_set:
                errors.append(make_error("E520", f"step_requirements[{step_id}] references unknown seed_id: {sid}"))
        if _valid_steps and step_id not in _valid_steps:
            errors.append(make_error(
                "W553",
                f"SEED_STEP_UNKNOWN step_requirements[{step_id}] is not a known pipeline step",
            ))

    _check_seed_content_overlap(spec_dir, manifest, project_root, errors)

    return errors
