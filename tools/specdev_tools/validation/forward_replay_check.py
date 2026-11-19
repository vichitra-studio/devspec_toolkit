from __future__ import annotations

import copy
import json
import os
import re
import subprocess
from pathlib import Path

from ..core.errors import SpecError, make_error
from ._legacy_shim import removed_paths
from .linter_utils import build_lint_graph
from .spec_check import lock_link_findings
from .traceability_closure import check_traceability_closure

SPEC_FILE_RE = re.compile(r"spec/(\d{2}[a-z]?)_[a-z0-9_]+\.json$")
ID_MATCH_RE = re.compile(r"[a-z]+-[a-z0-9-]+")
_PATH_SEGMENT_RE = re.compile(r"^([^\[\]{}]+)((?:\[\]|\{\})*)$")
_FILE_STEP_RE = re.compile(r"^(\d{2}[a-z]?)_")
_PER_FILE_CODES = frozenset({"E555", "W598", "W550"})


def check_forward_replay(
    repo_root: str,
    base_ref: str = "origin/main",
    diff_error_mode: str = "error",
    git_root: str | None = None,
    spec_root: str | None = None,
) -> list[SpecError]:
    """Report id regressions of the steps a branch changed (E555, W598, W550), plus the traceability closure.

    File-level forward replay (E550 for an unknown step or a missing downstream step, the W595 token staleness check
    and the status-write exemptions) is retired: ``specdev stale`` and the trace lock replace it.  What stays is the
    id-regression check, which needs the changed-file list of ``git diff <base_ref>...HEAD``.

    Args:
        repo_root: Path to the devspec toolkit root directory.
        base_ref: Git ref to diff against (e.g. ``origin/main``).
        diff_error_mode: ``"error"`` to fail (E550) when the diff cannot be computed, ``"ignore"`` to skip.
            Any other value is itself an E550.
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
                make_error("E550", f"FORWARD_REPLAY_MISSING invalid_diff_error_mode={diff_error_mode} expected=error|ignore")
            ]
        return [make_error("E550", f"FORWARD_REPLAY_MISSING unable_to_compute_diff base_ref={base_ref} reason={diff_error}")]
    steps = _load_steps(root / "tools" / "step_order.json")
    idx = {s: i for i, s in enumerate(steps)}
    changed_steps = {m.group(1) for p in changed if (m := SPEC_FILE_RE.search(p))}
    known_changed = sorted([s for s in changed_steps if s in idx], key=lambda x: idx[x])
    errors: list[SpecError] = []

    semantic_errors = _check_semantic_coverage(
        effective_git_root, set(known_changed), base_ref, effective_spec_root, repo_root=root,
    )

    errors.extend(_semantic_findings(semantic_errors))

    tc_errors = check_traceability_closure(str(effective_spec_root), str(root))
    for tc_err in tc_errors:
        if tc_err.code == "E560":
            errors.append(SpecError(code="W560", message=tc_err.message, path=tc_err.path))
        else:
            errors.append(tc_err)

    return errors


def _semantic_findings(semantic_errors: list[dict]) -> list[SpecError]:
    """E555, W598 and W550 for the results of ``_check_semantic_coverage``; each names its file (``file=``) so ``--step`` can filter it."""
    findings: list[SpecError] = []
    for err in semantic_errors:
        path = err["path"]
        if err["type"] == "skip":
            findings.append(make_error(
                "W550", f"SEMANTIC_COVERAGE_SKIP unable_to_read_base base_ref={err['base_ref']} path={path}", file=path
            ))
        elif err["type"] == "regression":
            dropped_str = ",".join(err["dropped_ids"])
            findings.append(make_error("E555", f"SEMANTIC_COVERAGE_REGRESSION path={path} dropped_ids={dropped_str}", file=path))
            # W598: warn individually for each removed ID to surface renames early
            findings.extend(
                make_error("W598", f"ID_STABILITY_REMOVAL path={path} removed_id={removed_id}", file=path) for removed_id in err["dropped_ids"]
            )
    return findings


def check_forward_replay_alias(
    repo_root: str,
    base_ref: str,
    diff_error_mode: str = "error",
    git_root: str | None = None,
    spec_root: str | None = None,
    step: str | None = None,
) -> list[SpecError]:
    """The findings of the deprecated ``specdev forward-replay-check``: ``check_forward_replay`` plus the suspect links of the trace lock.

    The suspect findings are those of ``lock_link_findings`` (E760 to E763, E778, E882, W720).  *step* limits the suspect
    findings to links held by that step's nodes (the slice of ``specdev stale --step``) and the per-file findings
    (E555, W598, W550) to that step's file; findings that name no file pass through.
    """
    errors = check_forward_replay(
        repo_root, base_ref=base_ref, diff_error_mode=diff_error_mode, git_root=git_root, spec_root=spec_root
    )
    if step is not None:
        errors = [e for e in errors if e.code not in _PER_FILE_CODES or _step_of_path(e.file or e.path) == step]
    spec_dir = os.path.abspath(spec_root) if spec_root else os.path.join(os.path.abspath(repo_root), "spec")
    graph = build_lint_graph(spec_dir, os.path.abspath(repo_root))
    host_root = os.path.abspath(git_root) if git_root else os.path.abspath(repo_root)
    return [*errors, *lock_link_findings(graph, spec_dir, os.path.abspath(repo_root), host_root, step=step)]


def _step_of_path(path: str | None) -> str | None:
    """The step id in the file name of *path* (``spec/03_glossary.json`` gives ``03``), or ``None``."""
    match = _FILE_STEP_RE.match(Path(path).name) if path else None
    return match.group(1) if match else None


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


def _load_steps(path: Path) -> list[str]:
    """The step ids of ``step_order.json`` in waterfall order."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)["steps"]


def _fan_out(nodes: list[object], marker: str) -> list[object]:
    """The items of every list in *nodes* (marker ``[]``) or the values of every dict in them (``{}``)."""
    if marker == "[]":
        return [item for node in nodes if isinstance(node, list) for item in node]
    return [value for node in nodes if isinstance(node, dict) for value in node.values()]


def _prune_node(node: object, segments: list[tuple[str, str]]) -> None:
    """Delete the subtree that *segments* (``(key, fan-out markers)``) name below *node*, in place."""
    if not segments or not isinstance(node, dict):
        return
    (key, fanout), rest = segments[0], segments[1:]
    if key not in node:
        return
    if not rest:
        if not fanout:
            del node[key]
        return
    children = [node[key]]
    for i in range(0, len(fanout), 2):
        children = _fan_out(children, fanout[i:i + 2])
    for child in children:
        _prune_node(child, rest)


def _prune_removed_paths(doc: object, paths: list[str]) -> object:
    """Return a copy of *doc* without the subtrees at *paths* (``a[].b``, ``m{}``; a glob or core path is ignored).

    A path whose last segment fans out (``a[]``) is not a subtree and is ignored. Never raises on a
    document or path of an unexpected shape.
    """
    pruned = copy.deepcopy(doc)
    for path in paths:
        segments = [_PATH_SEGMENT_RE.match(part) for part in path.split(".")]
        if all(segments) and not path.startswith("$"):
            _prune_node(pruned, [(m.group(1), m.group(2)) for m in segments if m])
    return pruned


def _extract_ids_from_spec(path: str) -> set[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
    except (OSError, json.JSONDecodeError):
        return set()
    return _extract_ids(obj)


def _extract_ids(obj: object) -> set[str]:
    ids: set[str] = set()

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
    repo_root: Path | None = None,
) -> list[dict]:
    errors = []
    spec_dir = spec_root if spec_root else git_root / "spec"

    for step in changed_steps:
        removed = removed_paths(step, repo_root)  # read once per step, not once per changed file
        for new_path in spec_dir.glob(f"{step}_*.json"):
            try:
                # realpath on both sides: a spec root spelled through a symlink (macOS /tmp) is still inside the repository
                rel_path = (Path(os.path.realpath(spec_dir)) / new_path.name).relative_to(os.path.realpath(git_root)).as_posix()
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
                
            # Legacy (M6c deletes): a field removed from the schema that a legacy reader still reads is
            # not an id the new file dropped, so its subtree leaves the base document before the diff.
            try:
                old_doc = _prune_removed_paths(json.loads(result.stdout), removed)
            except json.JSONDecodeError:
                old_doc = None
            old_ids = _extract_ids(old_doc)

            new_ids = _extract_ids_from_spec(str(new_path))
                
            dropped = sorted(old_ids - new_ids)
            if dropped:
                errors.append({
                    "type": "regression",
                    "path": rel_path,
                    "dropped_ids": dropped
                })

    return errors
