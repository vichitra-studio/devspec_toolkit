from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


SPEC_FILE_RE = re.compile(r"spec/(\d{2}[a-z]?)_[a-z0-9_]+\.json$")


def check_forward_replay(
    repo_root: str,
    base_ref: str = "origin/main",
    diff_error_mode: str = "error",
) -> list[str]:
    root = Path(os.path.abspath(repo_root))
    changed, diff_error = _changed_files(root, base_ref)
    if diff_error:
        if diff_error_mode == "ignore":
            return []
        if diff_error_mode != "error":
            return [
                f"E550 FORWARD_REPLAY_MISSING invalid_diff_error_mode={diff_error_mode} expected=error|ignore"
            ]
        return [f"E550 FORWARD_REPLAY_MISSING unable_to_compute_diff base_ref={base_ref} reason={diff_error}"]
    steps = _load_steps(root / "tools" / "step_order.json")
    idx = {s: i for i, s in enumerate(steps)}
    changed_steps = {m.group(1) for p in changed if (m := SPEC_FILE_RE.search(p))}
    known_changed = sorted([s for s in changed_steps if s in idx], key=lambda x: idx[x])
    changed_set = set(known_changed)
    errors: list[str] = []

    for step in sorted(changed_steps - changed_set):
        errors.append(f"E550 FORWARD_REPLAY_MISSING unknown_step_in_diff={step}")

    for step in known_changed:
        start = idx[step] + 1
        for downstream in steps[start:]:
            if _step_exists(root / "spec", downstream) and downstream not in changed_set:
                errors.append(
                    f"E550 FORWARD_REPLAY_MISSING changed={step} missing_downstream={downstream}"
                )
                break
    return errors


def _changed_files(root: Path, base_ref: str) -> tuple[list[str], str | None]:
    cmd = ["git", "-C", str(root), "diff", "--name-only", f"{base_ref}...HEAD"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
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
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)["steps"]


def _step_exists(spec_dir: Path, step: str) -> bool:
    return any(spec_dir.glob(f"{step}_*.json"))
