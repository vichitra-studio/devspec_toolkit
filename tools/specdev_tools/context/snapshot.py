"""Workspace snapshot and diff utilities for the DevSpec Toolkit context package.

Provides ``save_snapshot`` and ``diff_snapshot`` to enable in-workspace diffing
of spec artifacts without requiring git commits.

Snapshots are stored in ``.specdev/snapshots/`` relative to the git root (or
spec_dir parent when git root is unavailable). Each snapshot is a JSON copy of
the artifact at the time of the call.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from typing import Any

from ._utils import find_spec_file, load_json


# ---------------------------------------------------------------------------
# Snapshot storage resolution
# ---------------------------------------------------------------------------

def _snapshot_dir(spec_dir: str) -> str:
    """Return the .specdev/snapshots/ directory path, creating it if needed."""
    # Prefer placing snapshots at the git root level; fall back to the highest
    # ancestor reached within 4 levels (which may be spec_dir itself if no .git is found).
    candidate = spec_dir
    for _ in range(4):
        if os.path.isdir(os.path.join(candidate, ".git")):
            break
        parent = os.path.dirname(candidate)
        if parent == candidate:
            break
        candidate = parent
    snap_dir = os.path.join(candidate, ".specdev", "snapshots")
    os.makedirs(snap_dir, exist_ok=True)
    return snap_dir


def _snapshot_path(step_id: str, spec_dir: str) -> str:
    """Return the snapshot file path for a given step."""
    return os.path.join(_snapshot_dir(spec_dir), f"{step_id}.snapshot.json")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_snapshot(step_id: str, spec_dir: str, _repo_root: str) -> dict[str, Any]:
    """Copy the current step artifact to the workspace snapshot store.

    Parameters
    ----------
    step_id:
        Pipeline step identifier (e.g. ``"03"``).
    spec_dir:
        Absolute path to the spec directory containing the artifact.
    _repo_root:
        Toolkit repo root (unused; accepted for CLI consistency).

    Returns
    -------
    dict with keys: step, artifact_path, snapshot_path, status
    """
    artifact_path = find_spec_file(step_id, spec_dir)
    if not artifact_path or not os.path.isfile(artifact_path):
        return {
            "step": step_id,
            "status": "not_found",
            "error": f"No artifact found for step {step_id} in {spec_dir}",
        }

    snap_path = _snapshot_path(step_id, spec_dir)
    # Atomic write: copy to temp then rename so a concurrent read never sees a partial file.
    snap_dir = os.path.dirname(snap_path)
    with tempfile.NamedTemporaryFile("w", dir=snap_dir, delete=False, suffix=".tmp") as tf:
        with open(artifact_path, "r", encoding="utf-8") as src:
            shutil.copyfileobj(src, tf)
        tmp_name = tf.name
    os.replace(tmp_name, snap_path)

    return {
        "step": step_id,
        "status": "saved",
        "artifact_path": artifact_path,
        "snapshot_path": snap_path,
    }


def diff_snapshot(step_id: str, spec_dir: str, _repo_root: str) -> dict[str, Any]:
    """Compare the current step artifact against its workspace snapshot.

    Parameters
    ----------
    step_id:
        Pipeline step identifier (e.g. ``"03"``).
    spec_dir:
        Absolute path to the spec directory.
    _repo_root:
        Toolkit repo root (unused; accepted for CLI consistency).

    Returns
    -------
    dict with keys: step, status, changes (list of change records)

    Change record structure
    -----------------------
    Each record has:
      - ``path``: dot-notation path to the changed location
      - ``kind``: "added" | "removed" | "modified"
      - ``before``: previous value (None for added)
      - ``after``: current value (None for removed)
    """
    snap_path = _snapshot_path(step_id, spec_dir)
    if not os.path.isfile(snap_path):
        return {
            "step": step_id,
            "status": "no_snapshot",
            "error": (
                f"No snapshot found for step {step_id}. "
                "Run 'context snapshot <spec_dir> --step <NN>' first."
            ),
        }

    artifact_path = find_spec_file(step_id, spec_dir)
    if not artifact_path or not os.path.isfile(artifact_path):
        return {
            "step": step_id,
            "status": "artifact_not_found",
            "error": f"No artifact found for step {step_id} in {spec_dir}",
        }

    try:
        before = load_json(snap_path)
        after = load_json(artifact_path)
    except (OSError, json.JSONDecodeError) as exc:
        return {"step": step_id, "status": "error", "error": str(exc)}

    changes = _diff_json(before, after, path="")

    return {
        "step": step_id,
        "status": "ok",
        "artifact_path": artifact_path,
        "snapshot_path": snap_path,
        "change_count": len(changes),
        "changes": changes,
    }


# ---------------------------------------------------------------------------
# JSON diff helpers
# ---------------------------------------------------------------------------

def _diff_json(
    before: Any,
    after: Any,
    path: str,
    max_depth: int = 6,
    _depth: int = 0,
) -> list[dict[str, Any]]:
    """Recursively diff two JSON values. Returns a flat list of change records."""
    changes: list[dict[str, Any]] = []

    if _depth > max_depth:
        if before != after:
            changes.append({"path": path or ".", "kind": "modified", "before": before, "after": after})
        return changes

    if type(before) != type(after):  # noqa: E721
        changes.append({"path": path or ".", "kind": "modified", "before": before, "after": after})
        return changes

    if isinstance(before, dict):
        all_keys = set(before) | set(after)
        for key in sorted(all_keys):
            child_path = f"{path}.{key}" if path else key
            if key not in before:
                changes.append({"path": child_path, "kind": "added", "before": None, "after": after[key]})
            elif key not in after:
                changes.append({"path": child_path, "kind": "removed", "before": before[key], "after": None})
            else:
                changes.extend(_diff_json(before[key], after[key], child_path, max_depth, _depth + 1))

    elif isinstance(before, list):
        # For id-keyed arrays (items with *_id field), diff by ID.
        # Otherwise diff by position.
        id_key = _detect_id_key(before, after)
        if id_key:
            changes.extend(_diff_id_keyed_list(before, after, path, id_key, max_depth, _depth))
        else:
            changes.extend(_diff_positional_list(before, after, path, max_depth, _depth))
    else:
        if before != after:
            # Trim long string diffs to keep output readable
            b_repr = _trim(before)
            a_repr = _trim(after)
            changes.append({"path": path or ".", "kind": "modified", "before": b_repr, "after": a_repr})

    return changes


def _detect_id_key(before: list, after: list) -> str | None:
    """Return the id-key name if list items are dicts with a consistent *_id field."""
    sample = next((x for x in (before + after) if isinstance(x, dict)), None)
    if not sample:
        return None
    id_fields = [k for k in sample if k.endswith("_id")]
    return id_fields[0] if len(id_fields) == 1 else None


def _diff_id_keyed_list(
    before: list, after: list, path: str, id_key: str,
    max_depth: int, depth: int,
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    before_map = {item[id_key]: item for item in before if isinstance(item, dict) and id_key in item}
    after_map = {item[id_key]: item for item in after if isinstance(item, dict) and id_key in item}
    all_ids = list(before_map) + [i for i in after_map if i not in before_map]
    for item_id in all_ids:
        child_path = f"{path}[{item_id}]"
        if item_id not in before_map:
            changes.append({"path": child_path, "kind": "added", "before": None, "after": after_map[item_id]})
        elif item_id not in after_map:
            changes.append({"path": child_path, "kind": "removed", "before": before_map[item_id], "after": None})
        else:
            changes.extend(_diff_json(before_map[item_id], after_map[item_id], child_path, max_depth, depth + 1))
    return changes


def _diff_positional_list(
    before: list, after: list, path: str,
    max_depth: int, depth: int,
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    max_len = max(len(before), len(after))
    for i in range(max_len):
        child_path = f"{path}[{i}]"
        if i >= len(before):
            changes.append({"path": child_path, "kind": "added", "before": None, "after": after[i]})
        elif i >= len(after):
            changes.append({"path": child_path, "kind": "removed", "before": before[i], "after": None})
        else:
            changes.extend(_diff_json(before[i], after[i], child_path, max_depth, depth + 1))
    return changes


def _trim(value: Any, max_len: int = 200) -> Any:
    """Trim long strings for readable diff output."""
    if isinstance(value, str) and len(value) > max_len:
        return value[:max_len] + f"… [{len(value) - max_len} chars omitted]"
    return value
