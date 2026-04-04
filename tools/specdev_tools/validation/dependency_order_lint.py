from __future__ import annotations

import json
import os
import re
from pathlib import Path

from ..core.errors import SpecError, make_error


PROMPT_STEP_RE = re.compile(r"prompt_(\d{2}[a-z]?)_")
STEP_REF_RE = re.compile(
    r"(?:^|[^a-z0-9/])((?:/[^\s\"']+)?spec/(\d{2}[a-z]?)_[a-z0-9_]+\.json)",
    re.IGNORECASE,
)
EXAMPLE_SPEC_RE = re.compile(
    r"example/[^\s\"']*spec/\d{2}[a-z]?_[a-z0-9_]+\.json",
    re.IGNORECASE,
)
# Conditional qualifiers that mark a reference as optional (not a hard dependency).
CONDITIONAL_RE = re.compile(
    r"\(\s*if\s+(?:present|updating|available|exists)\s*\)",
    re.IGNORECASE,
)
# Patterns indicating a self-reference is an emit/write/output instruction.
EMIT_RE = re.compile(
    r"\b(?:emit|write|output|produce|generate)\b.*\bspec/",
    re.IGNORECASE,
)


def lint_dependency_order(repo_root: str) -> list[SpecError]:
    root = Path(os.path.abspath(repo_root))
    try:
        order, policy = _load_order(root / "tools" / "step_order.json")
    except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
        return [make_error("E520", f"UNRESOLVED_INPUT invalid_step_order {root / 'tools' / 'step_order.json'} {exc}")]
    index = {step: i for i, step in enumerate(order)}
    allow_self = bool(policy.get("allow_self_dependency", False))
    allow_forward = bool(policy.get("allow_forward_dependency", False))
    errors: list[SpecError] = []
    seen_errors: set[tuple[str, int, str, str, str]] = set()

    for prompt_path in sorted((root / "prompts").glob("prompt_*.md")):
        match = PROMPT_STEP_RE.search(prompt_path.name)
        if not match:
            continue
        step = match.group(1)
        current = index.get(step)
        if current is None:
            continue
        in_code_block = False
        with prompt_path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                stripped = line.strip()
                if stripped.startswith("```"):
                    in_code_block = not in_code_block
                for ref in _extract_step_refs(line):
                    target = index.get(ref)
                    if target is None:
                        continue
                    if target == current and not allow_self:
                        # Self-references are expected when a step references its
                        # own output in code blocks (validate/canon-accept commands),
                        # emit instructions ("Emit the artifact to spec/..."),
                        # inline code (backtick-wrapped commands), or conditional
                        # qualifiers like "(if updating)".
                        if in_code_block or EMIT_RE.search(line) or _is_conditional_ref(line, ref) or _is_inline_code_ref(line, ref):
                            continue
                        _add_error(errors, seen_errors, str(prompt_path), line_no, step, ref, "self-edge")
                    elif target > current and not allow_forward:
                        # Forward references are excluded when they appear in
                        # code blocks (tool command examples), inline code, or
                        # are qualified with "(if present)" etc.
                        if in_code_block or _is_conditional_ref(line, ref) or _is_inline_code_ref(line, ref):
                            continue
                        _add_error(errors, seen_errors, str(prompt_path), line_no, step, ref, "forward-edge")
    return errors


def _load_order(path: Path) -> tuple[list[str], dict[str, object]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    steps = data["steps"]
    return steps, data.get("policy", {})


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


def _is_conditional_ref(line: str, step: str) -> bool:
    """Return True if the spec ref for *step* is qualified by a conditional like '(if present)'.

    Handles two patterns:
    - Single ref: ``spec/03.json (if present)`` — qualifier immediately follows the ref.
    - Comma list: ``spec/03.json, spec/07.json (if present)`` — qualifier at end
      modifies all refs in the list (the bullet point is conditional as a whole).
    - Mixed: ``spec/02.json (if present) and spec/03.json`` — only 02 is conditional.
    """
    if not CONDITIONAL_RE.search(line):
        return False

    # Find where spec/NN_ appears in the line
    pattern = re.compile(rf"spec/{re.escape(step)}_[a-z0-9_]+\.json", re.IGNORECASE)
    m = pattern.search(line)
    if not m:
        return False

    # Check for a conditional qualifier in the text following this ref
    after = line[m.end():]
    # Look for the next spec/ ref — if there is one, the qualifier must appear
    # between this ref and the next one for it to apply to this ref.
    next_ref = re.search(r"spec/\d{2}", after)
    if next_ref:
        region = after[:next_ref.start()]
        # Direct qualifier: "(if present)" appears between this ref and the next
        if CONDITIONAL_RE.search(region):
            return True
        # Comma-separated list: check if this ref and the next are separated by
        # only comma/whitespace/markdown (no prose connectors like "and", "or",
        # "but", "using", "as"). In a comma list, a trailing qualifier applies
        # to all items.
        separator = region.strip().rstrip(",").strip()
        if not separator or separator in (",", "**"):
            # Refs are in a list — check if qualifier appears later on the line
            return True
        return False
    else:
        # No next ref — qualifier is after this ref (trailing position)
        return bool(CONDITIONAL_RE.search(after))


def _is_inline_code_ref(line: str, step: str) -> bool:
    """Return True if the spec reference for *step* appears inside backtick-delimited inline code."""
    # Find all backtick-delimited spans and check if any contain a spec/NN_ path.
    in_tick = False
    buf: list[str] = []
    for ch in line:
        if ch == "`":
            if in_tick:
                span = "".join(buf)
                if re.search(rf"spec/{re.escape(step)}_", span):
                    return True
                buf.clear()
            in_tick = not in_tick
            continue
        if in_tick:
            buf.append(ch)
    return False


def _add_error(
    errors: list[SpecError],
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
    errors.append(make_error(
        "E540", f"SELF_OR_FORWARD_DEPENDENCY {prompt_path}:{line_no} {step}->{ref} {violation_type}"
    ))


