from __future__ import annotations

import json
import os
import re as _re
from pathlib import Path
from typing import Dict, List

from ..core.errors import SpecError, ensure_spec_errors, make_error
from ..core.constants import SEED_MANIFEST_FILE
from ..core.seed_routing import resolve_seed_paths
from .validate import validate_file


# W554 HARDCODED_SEED_REFERENCE — matches literal seed-doc filenames like
# seed_overview.md, seed_tech_stack.md, etc. that end in .md.
# The pattern seed_\w+\.md cannot match seed_manifest.json because that
# filename ends in .json (not .md), so the \.md suffix acts as the exclusion.
_HARDCODED_SEED_RE = _re.compile(r"\bseed_\w+\.md\b")

# W555 STEP00_SEED_OUT_OF_SCOPE_THIN helpers.
#
# _OUT_OF_SCOPE_HEADING_RE — matches lines that begin a heading for an
# out-of-scope / non-goals section (case-insensitive).  Accepted variants:
#   ### 3.2 Out-of-Scope (Non-Goals)
#   ## Out-of-Scope
#   ### Out-of-Scope
#   ### Non-Goals
#   ### Non-Goal
# Deliberately rejects § 3.1 "In-Scope Goals (Must-Haves)" which contains
# "Scope" but not "out-of-scope" / "non-goal".
_OUT_OF_SCOPE_HEADING_RE = _re.compile(
    r"^#{1,6}\s.*?\b(?:out[\s\-]of[\s\-]scope|non[\s\-]?goals?)\b",
    _re.IGNORECASE,
)

# _HEADING_RE — any Markdown ATX heading; used to detect the *next* heading
# after the out-of-scope section so we know when to stop collecting bullets.
_HEADING_RE = _re.compile(r"^#{1,6}\s")

# _BULLET_RE — standard Markdown bullet markers (-, *, +).
_BULLET_RE = _re.compile(r"^\s*[-*+]\s+(.*)")

# _BRACKET_PLACEHOLDER_RE — a bullet whose entire content is a bracketed token,
# e.g. `- [Non-goal 1]`.  These are template placeholders; they are NOT counted
# as substantive out-of-scope items.
_BRACKET_PLACEHOLDER_RE = _re.compile(r"^\[[^\]]*\]\s*$")

# _SCAFFOLD_LABEL_RE — the seed_overview.md template uses "- **Expectation**:"
# and "- **Content**:" as STRUCTURAL labels in every subsection (3.1, 3.2, 3.3,
# metrics, …); the actual items are the nested/placeholder bullets beneath
# "**Content**:". These label bullets are template scaffolding, not real
# out-of-scope items, so they must not be counted. Keying on these two reserved
# template tokens (not arbitrary prose) is therefore intentional, not fragile.
# Accepted limitation: a genuine non-goal authored to literally begin with the
# reserved token "**Content**:" / "**Expectation**:" would be skipped — but that
# collides with a reserved structural label of the very template being filled in,
# so it is a pathological, accepted false-negative for a warning-level check.
_SCAFFOLD_LABEL_RE = _re.compile(r"^\*\*(expectation|content)\*\*\s*:", _re.IGNORECASE)


def _scan_prompts_dir(
    prompts_dir: Path,
    display_root: Path,
    label: str,
    errors: List[SpecError],
) -> None:
    """Scan *prompts_dir* for W554 hits and append findings to *errors*.

    Args:
        prompts_dir: Absolute path to the ``prompts/`` directory to scan.
        display_root: Root used to compute relative paths in error messages.
        label: Short prefix (e.g. ``"toolkit"`` or ``"host"``) shown in
            error messages so callers can tell which prompts tree was hit.
        errors: Mutable list to append :class:`SpecError` objects into.
    """
    for prompt_path in sorted(prompts_dir.rglob("*.md")):
        try:
            text = prompt_path.read_text(encoding="utf-8")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            m = _HARDCODED_SEED_RE.search(line)
            if m:
                rel = str(prompt_path.relative_to(display_root))
                errors.append(make_error(
                    "W554",
                    f"HARDCODED_SEED_REFERENCE [{label}] {rel}:{lineno}: literal seed"
                    f" filename '{m.group()}' — route seeds via seed_manifest.json instead",
                ))


def check_hardcoded_seed_reference(
    repo_root: str,
    git_root: str | None = None,
) -> List[SpecError]:
    r"""Scan prompt files for literal seed-doc filenames (W554 HARDCODED_SEED_REFERENCE).

    Globs ``prompts/**/*.md`` recursively from *repo_root* and, when *git_root*
    differs from *repo_root*, also scans ``<git_root>/prompts/`` (host-repo
    prompts).  This covers submodule deployments where ``repo_root`` is the
    toolkit and ``git_root`` is the host repo.

    The pattern ``seed_\w+\.md`` deliberately excludes ``seed_manifest.json``
    (wrong suffix) and the manifest-anchored ``**Seeds**:`` bullets that only
    reference ``seed_manifest.json``.

    Args:
        repo_root: Path to the toolkit (or host-repo) root containing ``prompts/``.
        git_root: Optional path to the host-repo root.  When provided and
            different from *repo_root*, ``<git_root>/prompts/`` is also
            scanned.  Defaults to ``None`` (toolkit-only scan, backward-
            compatible behaviour).

    Returns:
        List of W554 SpecError objects, one per matching line.
    """
    errors: List[SpecError] = []
    abs_repo_root = Path(os.path.abspath(repo_root))
    prompts_dir = abs_repo_root / "prompts"
    if prompts_dir.is_dir():
        _scan_prompts_dir(prompts_dir, abs_repo_root, "toolkit", errors)

    # In submodule deployments git_root points to the host repo (different from
    # the toolkit root).  Scan host prompts/ only when it is a distinct tree.
    if git_root is not None:
        abs_git_root = Path(os.path.abspath(git_root))
        if abs_git_root != abs_repo_root:
            host_prompts_dir = abs_git_root / "prompts"
            if host_prompts_dir.is_dir():
                _scan_prompts_dir(host_prompts_dir, abs_git_root, "host", errors)

    return errors


def project_root_from_spec_dir(spec_dir: str) -> str:
    """Derive the project root from a spec directory path (one level up)."""
    return os.path.abspath(os.path.join(spec_dir, os.pardir))


# Keep private alias for backward compatibility within this module
_project_root_from_spec_dir = project_root_from_spec_dir


def _load_manifest(repo_root: str, project_root: str, errors: List[SpecError]) -> Dict:
    manifest_path = os.path.join(project_root, "spec", SEED_MANIFEST_FILE)
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


def _count_substantive_out_of_scope(text: str) -> int:
    """Count substantive out-of-scope bullet items in *text*.

    Scans for the first heading matching ``_OUT_OF_SCOPE_HEADING_RE``, then
    collects bullet-list items until the next Markdown heading.

    A bullet item is counted as **substantive** when it is NOT:
    - A bracket-only placeholder such as ``[Non-goal 1]``
      (matched by ``_BRACKET_PLACEHOLDER_RE``).
    - A toolkit scaffold label such as ``- **Expectation**:`` or
      ``- **Content**:`` (matched by ``_SCAFFOLD_LABEL_RE``).

    Returns the integer count of substantive items found.  Returns 0 when no
    out-of-scope heading is present.
    """
    in_section = False
    fence_char: str | None = None  # None = outside fence; "`" or "~" = inside fence
    count = 0
    for line in text.splitlines():
        # Track fenced code block state by the opening delimiter character so
        # that cross-delimiter lines inside a fence (e.g. a ~~~ line inside a
        # ```-opened fence) are treated as fence content, not toggles.
        # Accepted limitation: the scanner tracks the opening delimiter character
        # but does NOT match fence-delimiter LENGTHS per CommonMark (e.g. `````
        # vs ```) — that length simplification remains an accepted simplification
        # for a warning-level check.
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            delim = stripped[0]
            if fence_char is None:
                # Open the fence; record which delimiter started it.
                fence_char = delim
            elif delim == fence_char:
                # Matching closing delimiter — close the fence.
                fence_char = None
            # else: non-matching delimiter inside the fence — fence content; fall through.
            continue
        if fence_char is not None:
            continue
        if _HEADING_RE.match(line):
            if in_section:
                # Reached the next heading — stop collecting.
                break
            if _OUT_OF_SCOPE_HEADING_RE.match(line):
                in_section = True
            continue
        if not in_section:
            continue
        m = _BULLET_RE.match(line)
        if not m:
            continue
        content = m.group(1).strip()
        # Empty bullet ("- " with no text) is not substantive content.
        if not content:
            continue
        if _BRACKET_PLACEHOLDER_RE.match(content):
            continue
        if _SCAFFOLD_LABEL_RE.match(content):
            continue
        count += 1
    return count


def _check_step00_out_of_scope_thin(
    manifest: Dict, project_root: str, errors: List[SpecError]
) -> None:
    """Emit W555 when seeds routed to step 00 supply fewer than 3 substantive
    out-of-scope items combined.

    Only runs when step "00" is present in ``manifest["step_requirements"]``
    and the list is non-empty.  Counts across ALL seeds routed to step 00 and
    fires exactly once if the aggregate count < 3.
    """
    step00_seed_ids: List[str] = manifest.get("step_requirements", {}).get("00") or []
    # Guard: no step-00 routing at all, or explicit empty list → skip.
    if not step00_seed_ids:
        return

    seed_paths = resolve_seed_paths(manifest, step00_seed_ids, project_root)
    total_substantive = 0
    for _sid, seed_path in seed_paths.items():
        if not os.path.isfile(seed_path):
            continue
        try:
            with open(seed_path, "r", encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue
        total_substantive += _count_substantive_out_of_scope(text)

    # The threshold is a seed-quality heuristic, not a mirror of a schema bound.
    # It is stated inline (not read from a schema at runtime) so the seed layer
    # stays decoupled from Step 00, which is what W555 exists to preserve.
    if total_substantive < 3:
        errors.append(make_error(
            "W555",
            f"STEP00_SEED_OUT_OF_SCOPE_THIN seeds routed to step 00 supply"
            f" {total_substantive} out-of-scope or non-goal bullet(s);"
            " at least 3 are expected",
        ))


def _is_blank_file(path: str) -> bool:
    """True when the file at *path* holds nothing but whitespace.

    A file that cannot be opened is not reported here (the existence check
    of ``lint_seeds`` is the only one that applies to it).
    """
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read().strip() == ""
    except OSError:
        return False


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
        elif _is_blank_file(resolved):
            errors.append(make_error(
                "E520",
                f"Seed '{seed_id}' path '{seed_path}' is empty (a seed that a step reads must hold text)",
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

    _check_step00_out_of_scope_thin(manifest, project_root, errors)

    return errors
