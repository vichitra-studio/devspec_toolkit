from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from .traceability_closure import check_traceability_closure

SPEC_FILE_RE = re.compile(r"spec/(\d{2}[a-z]?)_[a-z0-9_]+\.json$")
ID_MATCH_RE = re.compile(r"[a-z]+-[a-z0-9-]+")


def check_forward_replay(
    repo_root: str,
    base_ref: str = "origin/main",
    diff_error_mode: str = "error",
    git_root: str | None = None,
    spec_root: str | None = None,
) -> list[str]:
    """Check that all downstream steps are replayed when an upstream step changes.

    Args:
        repo_root: Path to the devspec toolkit root directory.
        base_ref: Git ref to diff against (e.g. ``origin/main``).
        diff_error_mode: ``"error"`` to fail on diff errors, ``"ignore"`` to skip.
        git_root: Host repo git root for ``git diff``. In submodule deployments
            this differs from *repo_root*. Defaults to *repo_root*.
        spec_root: Path to the spec directory. In submodule deployments this
            may be outside *repo_root*. Defaults to ``repo_root/spec``.
    """
    root = Path(os.path.abspath(repo_root))
    effective_git_root = Path(os.path.abspath(git_root)) if git_root else root
    effective_spec_root = Path(os.path.abspath(spec_root)) if spec_root else root / "spec"
    changed, diff_error = _changed_files(effective_git_root, base_ref)
    if diff_error:
        if diff_error_mode == "ignore":
            return []
        if diff_error_mode != "error":
            return [
                f"E550 FORWARD_REPLAY_MISSING invalid_diff_error_mode={diff_error_mode} expected=error|ignore"
            ]
        return [f"E550 FORWARD_REPLAY_MISSING unable_to_compute_diff base_ref={base_ref} reason={diff_error}"]
    steps, exemptions = _load_steps_and_exemptions(root / "tools" / "step_order.json")
    idx = {s: i for i, s in enumerate(steps)}
    changed_steps = {m.group(1) for p in changed if (m := SPEC_FILE_RE.search(p))}

    # Filter out steps where ALL changed files are status-only
    if exemptions:
        step_to_files: dict[str, list[str]] = {}
        for p in changed:
            m = SPEC_FILE_RE.search(p)
            if m:
                step_to_files.setdefault(m.group(1), []).append(p)
        for step_id, files in step_to_files.items():
            if step_id in exemptions:
                all_exempt = all(
                    _is_status_only_change(
                        effective_git_root, effective_spec_root / Path(f).name,
                        base_ref, exemptions[step_id]
                    )
                    for f in files
                )
                if all_exempt:
                    changed_steps.discard(step_id)

    known_changed = sorted([s for s in changed_steps if s in idx], key=lambda x: idx[x])
    changed_set = set(known_changed)
    errors: list[str] = []

    for step in sorted(changed_steps - changed_set):
        errors.append(f"E550 FORWARD_REPLAY_MISSING unknown_step_in_diff={step}")

    for step in known_changed:
        start = idx[step] + 1
        for downstream in steps[start:]:
            if _step_exists(effective_spec_root, downstream) and downstream not in changed_set:
                errors.append(
                    f"E550 FORWARD_REPLAY_MISSING changed={step} missing_downstream={downstream}"
                )
                break

    semantic_errors = _check_semantic_coverage(effective_git_root, set(known_changed), base_ref, effective_spec_root)
    
    for err in semantic_errors:
        if err["type"] == "skip":
            errors.append(f"W550 SEMANTIC_COVERAGE_SKIP unable_to_read_base base_ref={err['base_ref']} path={err['path']}")
        elif err["type"] == "regression":
            dropped_str = ",".join(err["dropped_ids"])
            errors.append(f"E550 SEMANTIC_COVERAGE_REGRESSION path={err['path']} dropped_ids={dropped_str}")

    tc_errors = check_traceability_closure(str(effective_spec_root), str(root))
    for err in tc_errors:
        if err.startswith("E560"):
            errors.append(err.replace("E560", "W560", 1))
        else:
            errors.append(err)

    return errors


def _changed_files(root: Path, base_ref: str) -> tuple[list[str], str | None]:
    cmd = ["git", "-C", str(root), "diff", "--name-only", f"{base_ref}...HEAD"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
    except subprocess.TimeoutExpired:
        return [], "git-diff-timeout"
    if result.returncode != 0:
        reason = (result.stderr or result.stdout or "").strip().replace("\n", " ")
        reason_lower = reason.lower()
        if "not a git repository" in reason_lower:
            return [], "not-a-git-repository"
        if "bad revision" in reason_lower:
            return [], "bad-revision"
        if len(reason) > 240:
            reason = reason[:240].rstrip() + "..."
        return [], reason or "git-diff-failed"
    return [line.strip() for line in result.stdout.splitlines() if line.strip()], None


def _load_steps_and_exemptions(path: Path) -> tuple[list[str], dict[str, list[str]]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    exemptions = data.get("policy", {}).get("status_write_exemptions", {})
    return data["steps"], exemptions


def _zero_recursive(obj: object, parts: list[str], depth: int) -> None:
    if depth >= len(parts) or not isinstance(obj, dict):
        return
    key = parts[depth]
    if key not in obj:
        return
    if depth == len(parts) - 1:
        obj[key] = None
    elif isinstance(obj[key], list):
        for item in obj[key]:
            if isinstance(item, dict):
                _zero_recursive(item, parts, depth + 1)
    elif isinstance(obj[key], dict):
        _zero_recursive(obj[key], parts, depth + 1)


def _zero_exempt_fields(obj: object, paths: list[str]) -> object:
    out = copy.deepcopy(obj)
    for path in paths:
        parts = path.replace("[]", "").split(".")
        _zero_recursive(out, parts, 0)
    return out


def _is_status_only_change(
    git_root: Path, spec_file: Path, base_ref: str, exempt_paths: list[str]
) -> bool:
    """Return True if the only changes in *spec_file* are in *exempt_paths*."""
    try:
        with spec_file.open("r", encoding="utf-8") as f:
            new_obj = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False

    try:
        rel_path = spec_file.relative_to(git_root).as_posix()
    except ValueError:
        return False
    cmd = ["git", "-C", str(git_root), "show", f"{base_ref}:{rel_path}"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
    except subprocess.TimeoutExpired:
        return False
    if result.returncode != 0:
        return False

    try:
        old_obj = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False

    old_zeroed = _zero_exempt_fields(old_obj, exempt_paths)
    new_zeroed = _zero_exempt_fields(new_obj, exempt_paths)
    return old_zeroed == new_zeroed


def _step_exists(spec_dir: Path, step: str) -> bool:
    return any(spec_dir.glob(f"{step}_*.json"))


def _extract_ids_from_spec(path: str) -> set[str]:
    ids = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
    except (OSError, json.JSONDecodeError):
        return ids

    def _crawl(data):
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, str) and (k == "id" or k.endswith("_id") or k.endswith("_ref")):
                    for match in ID_MATCH_RE.findall(v):
                        ids.add(match)
                elif isinstance(v, list) and k.endswith("_refs"):
                    for item in v:
                        if isinstance(item, str):
                            for match in ID_MATCH_RE.findall(item):
                                ids.add(match)
                if isinstance(v, (dict, list)):
                    _crawl(v)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    _crawl(item)

    _crawl(obj)
    return ids


def _check_semantic_coverage(
    git_root: Path,
    changed_steps: set[str],
    base_ref: str,
    spec_root: Path | None = None,
) -> list[dict]:
    errors = []
    spec_dir = spec_root if spec_root else git_root / "spec"

    for step in changed_steps:
        for new_path in spec_dir.glob(f"{step}_*.json"):
            try:
                rel_path = new_path.relative_to(git_root).as_posix()
            except ValueError:
                errors.append({
                    "type": "skip",
                    "path": str(new_path),
                    "base_ref": base_ref,
                })
                continue

            cmd = ["git", "-C", str(git_root), "show", f"{base_ref}:{rel_path}"]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
            except subprocess.TimeoutExpired:
                errors.append({
                    "type": "skip",
                    "path": rel_path,
                    "base_ref": base_ref,
                })
                continue
            if result.returncode != 0:
                stderr_lower = result.stderr.lower()
                if "does not exist in" not in stderr_lower and "exists on disk, but not in" not in stderr_lower:
                    errors.append({
                        "type": "skip",
                        "path": rel_path,
                        "base_ref": base_ref
                    })
                continue
                
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".json")
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as tmp:
                    tmp.write(result.stdout)
                old_ids = _extract_ids_from_spec(tmp_path)
            finally:
                os.remove(tmp_path)
                
            new_ids = _extract_ids_from_spec(str(new_path))
                
            dropped = sorted(old_ids - new_ids)
            if dropped:
                errors.append({
                    "type": "regression",
                    "path": rel_path,
                    "dropped_ids": dropped
                })
                
    return errors
