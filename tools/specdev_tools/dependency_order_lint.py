from __future__ import annotations

import json
import os
import re
from pathlib import Path


PROMPT_STEP_RE = re.compile(r"prompt_(\d{2}[a-z]?)_")
STEP_REF_RE = re.compile(
    r"(?:^|[^a-z0-9/])((?:/[^\s\"']+)?spec/(\d{2}[a-z]?)_[a-z0-9_]+\.json)",
    re.IGNORECASE,
)
EXAMPLE_SPEC_RE = re.compile(
    r"example/[^\s\"']*spec/\d{2}[a-z]?_[a-z0-9_]+\.json",
    re.IGNORECASE,
)


def lint_dependency_order(repo_root: str) -> list[str]:
    root = Path(os.path.abspath(repo_root))
    try:
        order, allowed, policy = _load_order(root / "tools" / "step_order.json")
    except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
        return [f"E520 UNRESOLVED_INPUT invalid_step_order {root / 'tools' / 'step_order.json'} {exc}"]
    index = {step: i for i, step in enumerate(order)}
    allow_self = bool(policy.get("allow_self_dependency", False))
    allow_forward = bool(policy.get("allow_forward_dependency", False))
    errors: list[str] = []
    seen_errors: set[tuple[str, int, str, str, str]] = set()

    for prompt_path in sorted((root / "prompts").glob("prompt_*.md")):
        match = PROMPT_STEP_RE.search(prompt_path.name)
        if not match:
            continue
        step = match.group(1)
        current = index.get(step)
        if current is None:
            continue
        with prompt_path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                for ref in _extract_step_refs(line):
                    target = index.get(ref)
                    if target is None:
                        continue
                    if target == current and not allow_self:
                        _add_error(errors, seen_errors, str(prompt_path), line_no, step, ref, "self-edge")
                    elif target > current and not allow_forward:
                        _add_error(errors, seen_errors, str(prompt_path), line_no, step, ref, "forward-edge")
                    elif target < current and ref not in allowed.get(step, []):
                        _add_error(errors, seen_errors, str(prompt_path), line_no, step, ref, "disallowed-upstream")
    return errors


def _load_order(path: Path) -> tuple[list[str], dict[str, list[str]], dict[str, object]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data["steps"], data.get("allowed_upstream_dependencies", {}), data.get("policy", {})


def _extract_step_refs(line: str) -> list[str]:
    sanitized = EXAMPLE_SPEC_RE.sub("", line)
    refs: list[str] = []
    for m in STEP_REF_RE.finditer(sanitized):
        full_path = m.group(1)
        step = m.group(2)
        if any(ch.isspace() for ch in full_path):
            continue
        normalized_path = full_path.lower()
        prefix = sanitized[max(0, m.start(1) - 12):m.start(1)].lower()
        if "/example/" in normalized_path or normalized_path.startswith("example/") or prefix.endswith("example/"):
            continue
        refs.append(step.lower())
    return refs


def _add_error(
    errors: list[str],
    seen_errors: set[tuple[str, int, str, str, str]],
    prompt_path: str,
    line_no: int,
    step: str,
    ref: str,
    violation_type: str,
) -> None:
    key = (prompt_path, line_no, step, ref, violation_type)
    if key in seen_errors:
        return
    seen_errors.add(key)
    errors.append(
        f"E540 SELF_OR_FORWARD_DEPENDENCY {prompt_path}:{line_no} {step}->{ref} {violation_type}"
    )
