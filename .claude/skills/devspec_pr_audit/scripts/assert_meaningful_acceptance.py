#!/usr/bin/env python3
"""Lint acceptance_command fields in a fix_plan.json for vacuous (always-exit-0) patterns.

Usage:
    python3 assert_meaningful_acceptance.py --fix-plan <path-to-fix_plan.json>

Exit codes:
    0 — no violations found
    1 — one or more violations found
    2 — input error (file not found, JSON parse error, or invalid 'tasks' type)

Output:
    Violations are written to stderr as:
        VIOLATION task=<id> pattern=<rule_name> description=<desc> command=<truncated-command>
    A one-line summary is written to stdout:
        acceptance lint: N tasks checked, M violations

Rules (9 canonical):
    1. pipe_or_true        — || true masks command failure
    2. grep_v_bare         — bare grep -v not in a pipeline always exits 0
    3. or_true_in_py       — ' or True' in python3 -c body makes assertion vacuous
    4. assert_true         — assert True in python3 -c body is a no-op
    5. subprocess_no_check — subprocess.run without check=True or sys.exit(r.returncode)
    6. empty_command       — acceptance_command is empty or whitespace-only
    7. bash_noop_colon     — ': ' is a Bash no-op
    8. literal_true        — 'true' as the entire command always exits 0
    9. hardcoded_pass      — command echoes success without checking anything
"""
from __future__ import annotations

import argparse
import io
import json
import re
import shlex
import sys
import tokenize
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Module-level verbosity flag (set by main() from --verbose)
# ---------------------------------------------------------------------------

_VERBOSE = False

# ---------------------------------------------------------------------------
# Python comment stripping (tokenize-based, string-literal aware)
# ---------------------------------------------------------------------------


def _strip_python_comments(body: str) -> str:
    """Strip Python line comments while preserving string-literal contents."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(body).readline))
    except (tokenize.TokenError, IndentationError):
        # If body isn't parseable as Python, return unmodified
        return body
    out_lines: list[str] = body.split("\n")
    # tokenize returns COMMENT tokens with (lineno, col_offset)
    # Walk in reverse so positional edits don't shift later positions
    comments = [(t.start, t.end) for t in tokens if t.type == tokenize.COMMENT]
    for (sl, sc), (_, ec) in reversed(comments):
        # tokenize is 1-indexed for lines, 0-indexed for columns
        line_idx = sl - 1
        if line_idx < len(out_lines):
            out_lines[line_idx] = out_lines[line_idx][:sc] + out_lines[line_idx][ec:]
    return "\n".join(out_lines)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMMAND_TRUNCATE = 120  # chars shown in VIOLATION lines

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _truncate(s: str, limit: int = COMMAND_TRUNCATE) -> str:
    s = s.replace("\n", " ")
    if len(s) <= limit:
        return s
    return s[:limit] + "..."


def _extract_python_body(command: str, _depth: int = 0) -> str | None:
    """Extract the body passed to python3 -c '...' or python3 -c \"...\".

    Uses shlex.split so quote-balanced escaping is handled correctly.
    Returns None if no -c body is found.

    Will unwrap one level of 'bash -c \"...\"' wrapping if needed.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        # Unmatched quotes — fall back to regex
        m = re.search(r"""python3?\s+-c\s+(?P<q>['"])(?P<body>.*?)(?P=q)""", command, re.DOTALL)
        return m.group("body") if m else None

    # Find the position of 'python3 -c' or 'python -c' and return the next token
    for i, tok in enumerate(tokens):
        if tok in ("python3", "python") and i + 1 < len(tokens) and tokens[i + 1] == "-c":
            if i + 2 < len(tokens):
                return tokens[i + 2]

    # Fallback: bash -c "..." wrapping — recurse once
    if _depth == 0:
        bash_match = re.match(r"^\s*bash\s+-c\s+(['\"])(.+)\1\s*$", command, re.DOTALL)
        if bash_match:
            inner = bash_match.group(2)
            return _extract_python_body(inner, _depth=1)
    else:
        deeper = re.match(r"^\s*bash\s+-c\s+(['\"])(.+)\1\s*$", command, re.DOTALL)
        if deeper and _VERBOSE:
            print(
                "DEBUG: bash -c unwrap depth limit reached; deeper nesting not analyzed",
                file=sys.stderr,
            )

    return None


def _strip_shell_comments(clause: str) -> str:
    """Strip lines that are pure shell comments from a clause."""
    lines = clause.split("\n")
    out = [line for line in lines if not line.strip().startswith("#")]
    return "\n".join(out).strip()


def _split_shell_clauses(command: str) -> list[tuple[str, int]]:
    """Split a shell command into clauses on &&, ||, ; (NOT on pipes |).

    Returns a list of (clause_text, start_offset) tuples, where start_offset
    is the index in *command* where the clause begins (before stripping).
    Handles quoted strings by skipping quoted sections during tokenisation.
    """
    clauses: list[tuple[str, int]] = []
    current: list[str] = []
    clause_start: int = 0
    i = 0
    while i < len(command):
        c = command[i]
        # Skip quoted sections
        if c in ('"', "'"):
            quote = c
            current.append(c)
            i += 1
            while i < len(command) and command[i] != quote:
                if command[i] == "\\" and i + 1 < len(command):
                    current.append(command[i])
                    current.append(command[i + 1])
                    i += 2
                else:
                    current.append(command[i])
                    i += 1
            if i < len(command):
                current.append(command[i])
            i += 1
            continue
        # Check for two-char operators first
        if i + 1 < len(command):
            two = command[i : i + 2]
            if two in ("&&", "||"):
                clauses.append(("".join(current).strip(), clause_start))
                current = []
                i += 2
                clause_start = i
                continue
        if c == ";":
            clauses.append(("".join(current).strip(), clause_start))
            current = []
            i += 1
            clause_start = i
            continue
        current.append(c)
        i += 1
    if current:
        clauses.append(("".join(current).strip(), clause_start))
    return [(text, offset) for text, offset in clauses if text]


def _clause_is_in_pipeline(offset: int, full_command: str) -> bool:
    """Return True if this clause is preceded by a pipe '|' in the full command.

    Uses the clause's start offset in the full_command to check the character
    immediately before the clause (skipping whitespace). A preceding '|' (but
    not '||') means the clause receives piped input.
    """
    # Walk backward from offset to find the first non-whitespace character
    pos = offset - 1
    while pos >= 0 and full_command[pos] in (" ", "\t", "\n"):
        pos -= 1
    if pos < 0:
        return False
    ch = full_command[pos]
    if ch != "|":
        return False
    # Make sure it's not '||' (logical OR)
    if pos > 0 and full_command[pos - 1] == "|":
        return False
    return True


# ---------------------------------------------------------------------------
# Individual rule checkers
# Each returns a list of (rule_name, description) pairs.
# ---------------------------------------------------------------------------

RuleResult = list[tuple[str, str]]


def _rule_pipe_or_true(command: str) -> RuleResult:
    """Rule 1: || true anywhere in the command masks failures."""
    if re.search(r"\|\|\s*true\b", command):
        return [("pipe_or_true", "|| true masks command failure")]
    return []


def _rule_grep_v_bare(command: str) -> RuleResult:
    """Rule 2: bare 'grep -v X' not in a pipeline — exits 0 whenever any line doesn't match."""
    results: RuleResult = []
    clauses = _split_shell_clauses(command)
    for clause_text, offset in clauses:
        stripped = _strip_shell_comments(clause_text)
        if not re.match(r"grep\s+(?:-[a-zA-Z]*v[a-zA-Z]*\b|--invert-match\b)", stripped):
            continue
        # Does it follow a pipe in the original command?
        if _clause_is_in_pipeline(offset, command):
            continue  # Pipeline usage is meaningful
        results.append(("grep_v_bare", "grep -v not in pipeline always exits 0 on non-trivial files"))
    return results


def _rule_or_true_in_py(command: str) -> RuleResult:
    """Rule 3: ' or True' in a python3 -c body makes assertions vacuous."""
    body = _extract_python_body(command)
    if body is None:
        return []
    if " or True" in body:
        return [("or_true_in_py", "' or True' in python3 -c body makes assertion vacuous")]
    return []


def _rule_assert_true(command: str) -> RuleResult:
    """Rule 4: 'assert True' in a python3 -c body is a no-op assertion."""
    body = _extract_python_body(command)
    if body is None:
        return []
    # Match 'assert True' as a standalone statement (not inside a string)
    if re.search(r"\bassert\s+True\b", body):
        return [("assert_true", "assert True in python3 -c body is a no-op")]
    return []


def _rule_subprocess_no_check(command: str) -> RuleResult:
    """Rule 5: subprocess.run(...) without check=True, r.check_returncode(), or sys.exit(r.returncode)."""
    body = _extract_python_body(command)
    if body is None:
        return []
    if "subprocess.run(" not in body:
        return []
    body = _strip_python_comments(body)  # strip Python line comments (string-literal aware)
    # Acceptable patterns: check=True anywhere in the body, check_returncode(), or sys.exit(r.returncode)
    has_check = (
        bool(re.search(r"check\s*=\s*True", body))
        or bool(re.search(r"\.\s*check_returncode\s*\(\s*\)", body))
    )
    has_exit_returncode = bool(re.search(r"sys\.exit\s*\(\s*\w+\.returncode\s*\)", body))
    if has_check or has_exit_returncode:
        return []
    return [("subprocess_no_check",
             "subprocess.run without check=True or sys.exit(r.returncode) — ignores failure")]


def _rule_empty_command(command: str) -> RuleResult:
    """Rule 6: Empty acceptance_command (just whitespace)."""
    if not command.strip():
        return [("empty_command", "acceptance_command is empty or whitespace-only")]
    return []


def _rule_bash_noop_colon(command: str) -> RuleResult:
    """Rule 7: ': ' (Bash no-op) as a top-level command or clause."""
    clauses = _split_shell_clauses(command)
    for clause_text, _ in clauses:
        stripped = _strip_shell_comments(clause_text)
        # The bare ':' or ': ' (possibly with a comment like ': placeholder')
        if stripped == ":" or stripped.startswith(": ") or re.match(r"^:\s*$", stripped):
            return [("bash_noop_colon", "': ' is a Bash no-op — always exits 0")]
    return []


def _rule_literal_true(command: str) -> RuleResult:
    """Rule 8: 'true' (literal) as the entire command."""
    if command.strip() == "true":
        return [("literal_true", "'true' as the entire command always exits 0")]
    return []


def _rule_hardcoded_pass(command: str) -> RuleResult:
    """Rule 9: entire command is just printf/echo (echoes success without checking anything)."""
    stripped = command.strip()
    if re.match(r"^(printf|echo)\s+", stripped) and not re.search(r"[|&;]", stripped):
        return [("hardcoded_pass", "command echoes success without checking anything")]
    return []


# ---------------------------------------------------------------------------
# All rules in evaluation order
# ---------------------------------------------------------------------------

ALL_RULES = [
    _rule_pipe_or_true,
    _rule_grep_v_bare,
    _rule_or_true_in_py,
    _rule_assert_true,
    _rule_subprocess_no_check,
    _rule_empty_command,
    _rule_bash_noop_colon,
    _rule_literal_true,
    _rule_hardcoded_pass,
]


# ---------------------------------------------------------------------------
# Optional fix_plan schema pre-validation
# ---------------------------------------------------------------------------


def _validate_fix_plan_schema(doc: dict[str, Any]) -> list[str]:
    """Validate doc against schema/infra/pr_audit_fix_plan.schema.json if present."""
    schema_path = Path(__file__).resolve().parents[4] / "schema/infra/pr_audit_fix_plan.schema.json"
    if not schema_path.exists():
        return []
    try:
        import jsonschema  # type: ignore[import-untyped]
        with schema_path.open(encoding="utf-8") as fh:
            s = json.load(fh)
        v = jsonschema.Draft202012Validator(s)
        return [f"{list(e.path)}: {e.message}" for e in v.iter_errors(doc)]
    except ImportError:
        return []


# ---------------------------------------------------------------------------
# Core lint logic
# ---------------------------------------------------------------------------


def lint_fix_plan(fix_plan: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """Lint all task acceptance_command fields.

    Returns a list of (task_id, rule_name, description, truncated_command) tuples.
    Raises TypeError if 'tasks' is not a list.
    """
    violations: list[tuple[str, str, str, str]] = []
    tasks = fix_plan.get("tasks", [])
    if not isinstance(tasks, list):
        raise TypeError(f"'tasks' must be a list, got {type(tasks).__name__}")
    for task in tasks:
        task_id: str = task.get("id", "<unknown>")
        command: str = task.get("acceptance_command") or ""
        # Collect all rule violations for this task, deduplicating by rule_name
        seen_rules: set[str] = set()
        for rule_fn in ALL_RULES:
            results = rule_fn(command)
            for rule_name, description in results:
                if rule_name not in seen_rules:
                    seen_rules.add(rule_name)
                    violations.append((task_id, rule_name, description, _truncate(command)))
    return violations


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    global _VERBOSE
    ap = argparse.ArgumentParser(
        description="Lint acceptance_command fields in a fix_plan.json for vacuous patterns."
    )
    ap.add_argument(
        "--fix-plan",
        required=True,
        metavar="PATH",
        help="Path to the fix_plan.json file to lint",
    )
    ap.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="emit debug diagnostics to stderr",
    )
    args = ap.parse_args()
    _VERBOSE = args.verbose

    fix_plan_path = Path(args.fix_plan)
    if not fix_plan_path.exists():
        print(f"ERROR: file not found: {fix_plan_path}", file=sys.stderr)
        return 2

    try:
        with fix_plan_path.open(encoding="utf-8") as fh:
            fix_plan: dict[str, Any] = json.load(fh)
    except json.JSONDecodeError as exc:
        print(f"ERROR: JSON parse error in {fix_plan_path}: {exc}", file=sys.stderr)
        return 2

    # Optional schema pre-validation
    schema_errors = _validate_fix_plan_schema(fix_plan)
    for err in schema_errors:
        print(f"WARN: fix_plan schema violation: {err}", file=sys.stderr)

    try:
        violations = lint_fix_plan(fix_plan)
    except TypeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    n_tasks = len(fix_plan.get("tasks", []))

    for task_id, rule_name, description, truncated_cmd in violations:
        print(
            f"VIOLATION task={task_id} pattern={rule_name} description={description} command={truncated_cmd}",
            file=sys.stderr,
        )

    print(f"acceptance lint: {n_tasks} tasks checked, {len(violations)} violations")

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
