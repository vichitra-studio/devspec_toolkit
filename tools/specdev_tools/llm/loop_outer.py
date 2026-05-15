"""loop_outer.py — Outer apply-side closed loop (snapshot/edit/check/rollback).

Implements §5.2 of docs/agents/llm_protocol.md.

The outer loop takes a validated set of pointers and a task, then:
  1. Snapshots all affected step files for rollback safety.
  2. Calls the LLM to propose edits (outer_edit.md template).
  3. Applies edits via json_patch.
  4. Runs spec-check; on clean → returns success.
  5. On failures → feeds findings back and loops (repair).
  6. On exhaustion or stagnation → rolls back from snapshot and returns failure.

Bound: ``SPECDEV_LLM_MAX_ITERS`` env var (default 3).
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import jsonschema

from specdev_tools.core.json_utils import json_patch
from specdev_tools.context.snapshot import restore_snapshot, save_snapshot
from specdev_tools.validation.spec_check import run_spec_check_json

if TYPE_CHECKING:
    from .adapter import LLMAdapter

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema loading (lazy cache)
# ---------------------------------------------------------------------------

_EDIT_SCHEMA_PATH = Path(__file__).parent / "schemas" / "edit_response.schema.json"
_SCHEMA_CACHE: dict[str, Any] | None = None


def _get_edit_schema() -> dict[str, Any]:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        try:
            with _EDIT_SCHEMA_PATH.open("r", encoding="utf-8") as fh:
                _SCHEMA_CACHE = json.load(fh)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Outer-loop edit response schema not found: {_EDIT_SCHEMA_PATH}. "
                "Ensure specdev_tools is installed with package_data (llm/schemas/*.json)."
            ) from None
    assert _SCHEMA_CACHE is not None
    return _SCHEMA_CACHE


# ---------------------------------------------------------------------------
# Prompt templates (lazy cache)
# ---------------------------------------------------------------------------

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_TEMPLATE_CACHE: dict[str, tuple[str, str]] = {}  # name → (system, user)


def _parse_template(template_name: str) -> tuple[str, str]:
    """Parse a prompt template file into (system, user) sections."""
    if template_name in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[template_name]

    path = _PROMPTS_DIR / template_name
    try:
        with path.open("r", encoding="utf-8") as fh:
            content = fh.read()
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Outer-loop prompt template not found: {path}. "
            "Ensure specdev_tools is installed with package_data (llm/prompts/*.md)."
        ) from None

    section_pattern = re.compile(r"^# (\w+)\s*$", re.MULTILINE)
    matches = list(section_pattern.finditer(content))

    sections: dict[str, str] = {}
    for i, match in enumerate(matches):
        name = match.group(1).lower()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        sections[name] = content[start:end].strip()

    system = sections.get("system", "")
    user = sections.get("user", "")
    _TEMPLATE_CACHE[template_name] = (system, user)
    return system, user


def _render(template_str: str, vars: dict[str, str]) -> str:
    """Replace ``{{ key }}`` placeholders in *template_str* with *vars* values."""
    result = template_str
    for key, value in vars.items():
        result = re.sub(r"\{\{\s*" + re.escape(key) + r"\s*\}\}", str(value), result)
    return result


# ---------------------------------------------------------------------------
# Forward-replay scope detection
# ---------------------------------------------------------------------------

_STEP_ID_RE = re.compile(r"^(\d+[a-z]?)_", re.IGNORECASE)

# Step-order cache keyed by repo_root so library callers with different toolkit
# paths get independent caches. Reset to {} in tests that create synthetic toolkits.
_STEP_ORDER_CACHE: dict[str, list[str]] = {}


def _get_step_order(repo_root: str) -> list[str]:
    """Load and cache the steps list from step_order.json, keyed by repo_root."""
    global _STEP_ORDER_CACHE
    if repo_root not in _STEP_ORDER_CACHE:
        path = os.path.join(repo_root, "tools", "step_order.json")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            _STEP_ORDER_CACHE[repo_root] = data.get("steps", [])
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            _STEP_ORDER_CACHE[repo_root] = []
    return _STEP_ORDER_CACHE[repo_root]


def _extract_step_id(file_path: str) -> str | None:
    """Extract step ID from a spec file basename (e.g. '04_fr_list.json' → '04')."""
    basename = os.path.basename(file_path)
    m = _STEP_ID_RE.match(basename)
    if m:
        return m.group(1)
    return None


def _needs_forward_replay(edits: list[dict[str, Any]], repo_root: str) -> bool:
    """Return True if any edit targets a file that is upstream of the last step.

    An edit file is "upstream" if its derived step ID appears in step_order.json
    at any position except the last (i.e., any edit to a non-final step triggers
    forward replay since downstream steps may be affected).
    """
    steps = _get_step_order(repo_root)
    if not steps:
        return False
    last_step = steps[-1]
    for edit in edits:
        step_id = _extract_step_id(edit.get("file", ""))
        if step_id is not None and step_id != last_step:
            return True
    return False


# ---------------------------------------------------------------------------
# Error count helper
# ---------------------------------------------------------------------------


def _count_errors(ctx: dict[str, Any]) -> int:
    """Sum all error_count fields from spec-check context checks."""
    total = 0
    for check_info in ctx.get("checks", {}).values():
        if isinstance(check_info, dict):
            total += check_info.get("error_count", 0)
    return total


def _derive_overall_status(ctx: dict[str, Any], has_errors: bool) -> str:
    """Return the overall spec-check status string (PASS / WARN / FAIL)."""
    if has_errors:
        return "FAIL"
    for check_info in ctx.get("checks", {}).values():
        if isinstance(check_info, dict) and check_info.get("status") == "WARN":
            return "WARN"
    return "PASS"


def _collect_findings(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect all findings from spec-check context checks into a flat list."""
    findings: list[dict[str, Any]] = []
    for check_info in ctx.get("checks", {}).values():
        if isinstance(check_info, dict):
            findings.extend(check_info.get("findings", []))
    return findings


def _collect_forward_replay_findings(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract findings from the forward-replay-check entry in ctx."""
    check_info = ctx.get("checks", {}).get("forward-replay-check", {})
    if isinstance(check_info, dict):
        return check_info.get("findings", [])
    return []


# ---------------------------------------------------------------------------
# Snapshot helpers for multiple steps
# ---------------------------------------------------------------------------


def _snapshot_steps(
    step_ids: list[str], spec_dir: str, repo_root: str
) -> dict[str, dict[str, Any]]:
    """Save snapshots for each step ID. Returns {step_id: save_result}."""
    results: dict[str, dict[str, Any]] = {}
    for step_id in step_ids:
        result = save_snapshot(step_id=step_id, spec_dir=spec_dir, _repo_root=repo_root)
        results[step_id] = result
        if result.get("status") != "saved":
            log.warning("snapshot save failed for step %s: %s", step_id, result)
    return results


def _rollback_steps(step_ids: list[str], spec_dir: str) -> None:
    """Restore all step snapshots. Logs failures but does not raise."""
    for step_id in step_ids:
        result = restore_snapshot(step_id=step_id, spec_dir=spec_dir)
        if result.get("status") != "restored":
            log.warning(
                "snapshot restore failed for step %s: %s", step_id, result
            )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_outer_loop(
    *,
    task: str,
    validated_pointers: list[dict[str, Any]],
    step_structure_summary: dict[str, Any],
    adapter: "LLMAdapter",
    repo_root: str,
    spec_dir: str,
    git_root: str | None = None,
    spec_root: str | None = None,
    max_iters: int | None = None,
) -> dict[str, Any]:
    """Run the outer apply-side closed loop.

    Parameters
    ----------
    task:
        Natural-language description of the edit task.
    validated_pointers:
        Pointer dicts that have been confirmed to exist (output of inner loop).
    step_structure_summary:
        Dict describing step structure (from run_bundle). Used as context for LLM.
    adapter:
        Injected :class:`~specdev_tools.llm.adapter.LLMAdapter` implementation.
    repo_root:
        Absolute path to the toolkit root.
    spec_dir:
        Absolute path to the host project's spec directory.
    git_root:
        Absolute path to the host repo git root. Defaults to None.
    spec_root:
        Absolute path to the spec root for canon resolution. Defaults to None.
    max_iters:
        Maximum iterations. When None, read from ``SPECDEV_LLM_MAX_ITERS`` (default 3).

    Returns
    -------
    dict with keys:
        ``applied``   True iff edits survived to final state (ok=True + edits applied).
        ``snapshot_id`` Unique sortable id in ``snap-<step>-<YYYYmmddTHHMMSSZ>-<4hex>`` format (§15).
        ``spec_check_status`` Final spec-check status string ("PASS", "FAIL", etc.).
        ``files_changed`` List of files modified (empty on rollback).
        ``iterations`` Number of outer-loop iterations run.
        ``partial`` True iff ``unresolved`` is non-empty.
        ``ok`` True iff no unresolved issues remain.
        ``unresolved`` List of issue dicts for failures not resolved.
    """
    # Resolve max_iters and dry-run flag from config when not explicitly provided.
    from specdev_tools.core.config import get_config
    _cfg = get_config()
    if max_iters is None:
        max_iters = _cfg.llm_outer_max_iters

    # Guard: SPECDEV_LLM_DRY_RUN=1 → no LLM calls, no filesystem mutations.
    if _cfg.llm_dry_run:
        return {
            "applied": False,
            "snapshot_id": "",
            "spec_check_status": "NOT_RUN",
            "files_changed": [],
            "iterations": 0,
            "partial": True,
            "ok": False,
            "unresolved": [
                {"reason": "SPECDEV_LLM_DRY_RUN=1: no LLM calls or filesystem mutations performed"}
            ],
            "spec_check": {"forward_replay": []},
        }

    # Guard: max_iters=0 → no LLM calls, no snapshot cost.
    if max_iters <= 0:
        return {
            "applied": False,
            "snapshot_id": "",
            "spec_check_status": "NOT_RUN",
            "files_changed": [],
            "iterations": 0,
            "partial": True,
            "ok": False,
            "unresolved": [{"reason": "max_iters=0; no LLM calls attempted"}],
            "spec_check": {"forward_replay": []},
        }

    # Determine which step IDs are touched by the validated pointers.
    touched_step_ids: list[str] = []
    seen_steps: set[str] = set()
    for ptr in validated_pointers:
        file_ = ptr.get("file", "")
        sid = _extract_step_id(file_)
        if sid and sid not in seen_steps:
            seen_steps.add(sid)
            touched_step_ids.append(sid)

    # Guard: §5.2 requires single-step invocation — multi-step mutations need
    # sequential calls, one per step.
    if len(touched_step_ids) > 1:
        return {
            "applied": False,
            "snapshot_id": "",
            "spec_check_status": "NOT_RUN",
            "files_changed": [],
            "iterations": 0,
            "partial": True,
            "ok": False,
            "unresolved": [
                {
                    "reason": (
                        f"run_outer_loop must operate on one step per invocation "
                        f"(validated_pointers span steps: "
                        f"{', '.join(sorted(touched_step_ids))}). "
                        "Use sequential calls for multi-step edits."
                    )
                }
            ],
            "spec_check": {"forward_replay": []},
        }

    # Build a unique, sortable snapshot_id per §15.
    step_str = "-".join(sorted(touched_step_ids)) if touched_step_ids else "nostep"
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    short_hash = uuid.uuid4().hex[:4]
    snapshot_id = f"snap-{step_str}-{ts}-{short_hash}"

    # Take snapshots of all affected steps upfront; fail fast if snapshot fails.
    snap_results = _snapshot_steps(touched_step_ids, spec_dir, repo_root)
    failed_snaps = [sid for sid, r in snap_results.items() if r.get("status") != "saved"]
    if failed_snaps:
        return {
            "applied": False,
            "snapshot_id": snapshot_id,
            "spec_check_status": "NOT_RUN",
            "files_changed": [],
            "iterations": 0,
            "partial": True,
            "ok": False,
            "unresolved": [
                {"reason": f"snapshot failed for step(s): {', '.join(sorted(failed_snaps))}"}
            ],
            "spec_check": {"forward_replay": []},
        }

    # Track ALL snapshotted step IDs so late-appearing edit targets are also covered.
    snapshotted_step_ids: set[str] = set(touched_step_ids)

    # Stagnation tracking (only on valid — non-discarded — iterations).
    stall_count = 0
    prev_error_count: int | None = None

    # Track discards.
    discard_count = 0

    # Track files actually mutated (cleared on rollback).
    files_changed: set[str] = set()

    # Current spec-check findings to feed back into repair prompt.
    current_findings: list[dict[str, Any]] = []
    last_spec_check_status = "NOT_RUN"
    last_ctx: dict[str, Any] = {}

    iteration = 0

    while iteration < max_iters:
        iteration += 1

        # ------------------------------------------------------------------
        # Render prompt (same template for all iters; findings vary)
        # ------------------------------------------------------------------
        system_tmpl, user_tmpl = _parse_template("outer_edit.md")
        render_vars = {
            "task": task,
            "pointers": json.dumps(validated_pointers, indent=2),
            "step_structure_summary": json.dumps(step_structure_summary, indent=2),
            "spec_check_findings": json.dumps(current_findings, indent=2),
        }
        system_msg = _render(system_tmpl, render_vars)
        user_msg = _render(user_tmpl, render_vars)

        # ------------------------------------------------------------------
        # Call LLM
        # ------------------------------------------------------------------
        raw_response = adapter.chat(system_msg, user_msg)

        # ------------------------------------------------------------------
        # Parse JSON
        # ------------------------------------------------------------------
        try:
            parsed = json.loads(raw_response)
        except (json.JSONDecodeError, ValueError):
            discard_count += 1
            log.debug("outer loop iter %d: invalid JSON response, discarding", iteration)
            continue

        # ------------------------------------------------------------------
        # Schema validation
        # ------------------------------------------------------------------
        schema = _get_edit_schema()
        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(parsed))
        if errors:
            discard_count += 1
            log.debug("outer loop iter %d: schema validation failed, discarding", iteration)
            continue

        # ------------------------------------------------------------------
        # Apply edits
        # ------------------------------------------------------------------
        edits: list[dict[str, Any]] = parsed.get("edits", [])
        apply_error: str | None = None

        for edit in edits:
            file_ = edit["file"]
            jq_path = edit["jq_path"]
            value = edit["value"]
            # Resolve the file path relative to git_root if provided.
            # When git_root is absent, derive the root from spec_dir's parent so
            # that nested paths like "spec/impl_context/ms_plan.json" resolve correctly.
            if git_root:
                file_abs = os.path.join(git_root, file_) if not os.path.isabs(file_) else file_
            else:
                file_abs = os.path.join(os.path.dirname(spec_dir), file_) if not os.path.isabs(file_) else file_
            file_abs = os.path.normpath(file_abs)

            try:
                # Guard: only step-prefixed files (NN_*.json) can be snapshotted and
                # rolled back. Non-step files (canon, seed, etc.) must not be mutated
                # by the outer loop — the snapshot system has no recovery path for them.
                edit_sid = _extract_step_id(file_abs)
                if edit_sid is None:
                    apply_error = (
                        f"edit targets non-step file '{file_}': outer loop may only "
                        "mutate step-prefixed artifacts (NN_*.json). "
                        "Non-step files cannot be snapshotted or rolled back."
                    )
                    break
                if edit_sid not in snapshotted_step_ids:
                    save_snapshot(step_id=edit_sid, spec_dir=spec_dir, _repo_root=repo_root)
                    snapshotted_step_ids.add(edit_sid)
                    log.debug("outer loop iter %d: late-snapshot for step %s", iteration, edit_sid)

                json_patch(file_abs, jq_path, json.dumps(value))
                files_changed.add(file_abs)
                log.debug("outer loop iter %d: patched %s at %s", iteration, file_abs, jq_path)
            except Exception as exc:  # json_utils raises JsonUtilsError or similar
                apply_error = str(exc)
                log.warning(
                    "outer loop iter %d: apply failed for %s at %s: %s",
                    iteration, file_abs, jq_path, exc
                )
                break

        if apply_error:
            # Apply failure is not a discard (the response was valid); treat as
            # an unresolvable error → rollback and return failure.
            _rollback_steps(list(snapshotted_step_ids), spec_dir)
            return {
                "applied": False,
                "snapshot_id": snapshot_id,
                "spec_check_status": "NOT_RUN",
                "files_changed": [],
                "iterations": iteration,
                "partial": True,
                "ok": False,
                "unresolved": [{"reason": f"apply error: {apply_error}"}],
                "spec_check": {"forward_replay": []},
            }

        # ------------------------------------------------------------------
        # Run spec-check
        # ------------------------------------------------------------------
        use_forward_replay = _needs_forward_replay(edits, repo_root)
        spec_errors, ctx = run_spec_check_json(
            repo_root,
            spec_dir,
            include_forward_replay=use_forward_replay,
            git_root=git_root,
            spec_root=spec_root,
        )
        # Determine overall spec-check status (PASS / WARN / FAIL).
        error_count = _count_errors(ctx)
        has_errors = error_count > 0 or bool(spec_errors)

        last_spec_check_status = _derive_overall_status(ctx, has_errors)
        current_findings = _collect_findings(ctx)
        last_ctx = ctx

        # ------------------------------------------------------------------
        # Termination condition 1: spec-check clean
        # ------------------------------------------------------------------
        if not has_errors:
            return {
                "applied": True,
                "snapshot_id": snapshot_id,
                "spec_check_status": last_spec_check_status,
                "files_changed": sorted(files_changed),
                "iterations": iteration,
                "partial": False,
                "ok": True,
                "unresolved": [],
                "spec_check": {"forward_replay": _collect_forward_replay_findings(ctx)},
            }

        # ------------------------------------------------------------------
        # Termination condition 2: stagnation — error count doesn't shrink
        # for 2 consecutive valid iterations.
        # ------------------------------------------------------------------
        if prev_error_count is not None:
            if error_count >= prev_error_count:
                stall_count += 1
            else:
                stall_count = 0  # shrink → reset

        if stall_count >= 2:
            log.info(
                "outer loop: stagnation after %d iterations (error_count=%d), rolling back",
                iteration, error_count
            )
            _rollback_steps(list(snapshotted_step_ids), spec_dir)
            unresolved = _build_unresolved(current_findings, iteration, discard_count)
            return {
                "applied": False,
                "snapshot_id": snapshot_id,
                "spec_check_status": last_spec_check_status,
                "files_changed": [],
                "iterations": iteration,
                "partial": bool(unresolved),
                "ok": False,
                "unresolved": unresolved,
                "spec_check": {"forward_replay": _collect_forward_replay_findings(ctx)},
            }

        prev_error_count = error_count

    # ------------------------------------------------------------------
    # Termination condition 3: max_iters reached — rollback
    # ------------------------------------------------------------------
    log.info(
        "outer loop: max_iters=%d exhausted, rolling back",
        max_iters,
    )
    _rollback_steps(list(snapshotted_step_ids), spec_dir)
    unresolved = _build_unresolved(current_findings, iteration, discard_count)
    return {
        "applied": False,
        "snapshot_id": snapshot_id,
        "spec_check_status": last_spec_check_status,
        "files_changed": [],
        "iterations": iteration,
        "partial": bool(unresolved),
        "ok": False,
        "unresolved": unresolved,
        "spec_check": {"forward_replay": _collect_forward_replay_findings(last_ctx)},
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_unresolved(
    findings: list[dict[str, Any]],
    iteration: int,
    discard_count: int,
) -> list[dict[str, Any]]:
    """Build unresolved list from spec-check findings.

    Injects a sentinel when all iterations were discarded (contract: partial=True
    iff unresolved non-empty).
    """
    if findings:
        return [
            {
                "reason": f.get("message", f.get("code", f"spec-check finding after {iteration} iteration(s)")),
                "finding": f,
            }
            for f in findings
        ]

    # No findings but we exhausted iters (all discards, or error_count > 0 but findings[]==[]?)
    if discard_count > 0:
        return [
            {
                "reason": (
                    f"response discarded {discard_count} time(s); "
                    f"no valid LLM response within {iteration} iteration(s)"
                )
            }
        ]

    # Spec-check reported errors but no parseable findings → sentinel.
    return [
        {
            "reason": (
                f"spec-check reported errors but no parseable findings "
                f"after {iteration} iteration(s)"
            )
        }
    ]
