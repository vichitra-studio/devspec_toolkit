"""Deterministic milestone-state engine for the DevSpec Toolkit.

Replaces the LLM-evaluated ``milestone_state`` mode of ``specdev-scope.md``
with a pure, unit-testable Python derivation (DEVSPEC-38, D7/D7a).

## Design notes

**Status string only — no status_ref.**  After DEVSPEC-38 removes ``status_ref``,
both per-group ``verified`` and milestone ``closed`` read ``implementation.status``
directly.  This is a *conscious semantic consolidation*: the original agent read
``status`` AND ``status_ref.id`` for ``verified``, and ``status_ref.id`` ONLY for
``closed``.  After the port, both predicates key on the ``status`` string — the
single retained encoding.  On the host, ``status`` and ``status_ref.id`` agreed
for all 240 impl objects (XOR = 0), so the semantic change is invisible in
practice but correct in principle.

**Predicate precedence (per-group, first match wins):**
``deferred/wont_do > verified > blocked > code_converged > pending``.
``wont_do`` (DEVSPEC-122 follow-up) has the same precedence and roll-up
exclusion as ``deferred`` — both mean "not part of the active work being
tracked" (paused vs. permanently cancelled) and are excluded identically from
``derive_phase_position``'s progress computations. They are kept as distinct
state literals (not collapsed into one) so callers can still tell "paused" from
"cancelled" when inspecting per-group state.

This ensures that a group with ``implementation.status == "verified"`` reaches
``verified`` state even if no convergence file exists on the filesystem — exactly
the "string-verified ⇒ group-verified ⇒ milestone-closed" property tested by the
mandatory keystone case.

**``executing`` is omitted.**  It is a transient in-flight state that is never
persisted in plan files or findings.  The engine never emits it; the contract
documents it as "not normally observed".

**``impl_complete`` vs ``review_pending`` disambiguation.**
The original contract's two predicates collapse to the same condition when read
literally.  The engine disambiguates:
- ``impl_complete``: every active (non-deferred, non-wont_do) group in
  {code_converged, blocked, verified} AND *no milestone-review file exists at all*.
- ``review_pending``: same group condition AND milestone-review file(s) exist but
  *none* has empty findings.
- ``review_complete``: same group condition AND ≥1 milestone-review file has
  ``findings == []``.

**``impl_in_progress`` includes verified groups.**
The roll-up's "progress" set is {executing, code_converged, *verified*} so that a
mixed milestone (some verified, some pending) correctly resolves to
``impl_in_progress`` instead of falling through all predicates.

**All-deferred/wont_do milestone.**  If every group is deferred or wont_do,
``derived_phase_position`` defaults to ``"pending"`` (no active group fails any
predicate; treat as if nothing has started).

**``resolved`` field defaults to False.**  Ambiguity objects that lack a
``resolved`` key (as seen in real host data) are treated as unresolved, which is
the conservative safe default.

**Filesystem robustness.**  Findings files whose top-level JSON value is not a
``dict`` (e.g. a bare list) are silently skipped for convergence detection.

**Cross-platform mtime.**  Uses ``os.stat().st_mtime`` + ``datetime.fromtimestamp``
with ``timezone.utc`` — no shell-outs, no macOS/Linux branch.
"""
from __future__ import annotations

import glob as _glob
import json
import os
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_json(path: str) -> Any:
    """Load JSON from *path*, returning the parsed value."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _mtime_to_iso(path: str) -> str:
    """Return the UTC mtime of *path* as an ISO 8601 string (``YYYY-MM-DDTHH:MM:SSZ``)."""
    mtime = os.stat(path).st_mtime
    return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_empty_findings(path: str) -> bool:
    """Return True iff *path* is a valid findings file with ``findings == []``."""
    try:
        data = _load_json(path)
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    return data.get("findings") == []


def _latest_empty_findings(files: list[str]) -> str | None:
    """Return the path of the most-recent empty-findings file from *files*, or None."""
    empty = [f for f in files if _is_empty_findings(f)]
    if not empty:
        return None
    return max(empty, key=lambda f: os.stat(f).st_mtime)


# ---------------------------------------------------------------------------
# Per-group derivation
# ---------------------------------------------------------------------------

def derive_group_state(
    group: dict,
    findings_dir: str,
    ambiguities: list[dict],
) -> dict:
    """Derive the state object for a single checklist group.

    Parameters
    ----------
    group:
        One entry from ``plan.spec_alignment.checklist``.
    findings_dir:
        Absolute path to the ``.specdev/findings/`` directory.
    ambiguities:
        The ``execution.emergent_ambiguities`` list from the plan.

    Returns
    -------
    dict
        A group object conforming to the milestone-state output contract::

            {
              "group_id": str,
              "state": "pending|code_converged|blocked|verified|deferred|wont_do",
              "implementation_converged_at": str | None,
              "reviewer_rounds": int,
              "findings_resolved_path": str | None,
              "blocking_amb_ids": list[str],
              "blocking_amb_health": list[dict],
              "fixtures_exercised": list[str],
            }
    """
    group_id: str = group["id"]

    # --- Filesystem probes -----------------------------------------------
    all_group_files: list[str] = _glob.glob(
        os.path.join(findings_dir, f"findings_{group_id}_*")
    )

    # Per-reviewer outputs: match _<N>_r<reviewer_id>.json shapes.
    # The last segment (after the final underscore) must be "r" followed by digits,
    # matching both "_r1" and "_rr1" patterns (double-r is also a reviewer output).
    per_reviewer_files: list[str] = [
        f for f in all_group_files
        if _is_per_reviewer_file(os.path.basename(f), group_id)
    ]

    # Round-output files (convergence signals): match _<N>.json
    # These are non-reviewer files (no _rN or _rrN or _fixer suffix)
    round_output_files: list[str] = [
        f for f in all_group_files
        if _is_round_output_file(os.path.basename(f), group_id)
    ]

    # Three findings-file shapes exist for a group:
    #   per-reviewer:   findings_<group_id>_<N>_r<M>.json   (and _rr<M> double-r variant)
    #   round-output:   findings_<group_id>_<N>.json         (convergence signal when findings==[])
    #   halt-archive:   findings_<group_id>_<N>_<unix_ts>.json
    # Halt-archive files are intentionally excluded — per SKILL.md they are NOT promoted to a
    # canonical convergence name and must not be treated as convergence signals.
    findings_resolved_path: str | None = _latest_empty_findings(
        round_output_files + per_reviewer_files
    )
    implementation_converged_at: str | None = (
        _mtime_to_iso(findings_resolved_path) if findings_resolved_path else None
    )
    reviewer_rounds: int = len(per_reviewer_files)

    # --- Blocking ambiguities --------------------------------------------
    blocking_amb_ids: list[str] = []
    blocking_amb_health: list[dict] = []

    for amb in ambiguities:
        amb_id = amb.get("id", "")
        status = amb.get("status", "")
        # Missing 'resolved' key → treat as unresolved (conservative default)
        resolved = bool(amb.get("resolved", False))

        if status != "blocked" or resolved:
            continue

        # Deterministic substring match: group_id referenced in impact or description
        impact_refs: list[str] = []
        for imp in amb.get("impact", []):
            if isinstance(imp, str):
                impact_refs.append(imp)
        references_group = (
            any(group_id in imp for imp in impact_refs)
            or group_id in amb.get("description", "")
        )
        if not references_group:
            continue

        blocking_amb_ids.append(amb_id)

        # well_formed: severity present AND description present
        # (the old "status consistent with status_ref" sub-rule is dropped —
        # status_ref no longer exists per DEVSPEC-38 D7)
        well_formed = (
            "severity" in amb
            and "description" in amb
        )
        blocking_amb_health.append({
            "id": amb_id,
            "status": status,
            "resolved": resolved,
            "well_formed": well_formed,
        })

    # --- Fixtures exercised ----------------------------------------------
    fixture_ref = group.get("fixture_ref")
    fixtures_exercised: list[str] = [fixture_ref] if fixture_ref else []

    # --- State derivation (precedence: deferred/wont_do > verified > blocked > code_converged > pending) --
    checklist_status: str = group.get("checklist_status", "")
    impl: dict = group.get("implementation", {}) or {}
    impl_status: str = impl.get("status", "")

    if checklist_status == "deferred":
        state = "deferred"
    elif checklist_status == "wont_do":
        state = "wont_do"
    elif impl_status == "verified":
        state = "verified"
    elif (
        implementation_converged_at is not None
        and findings_resolved_path is not None
        and blocking_amb_ids
    ):
        # code_converged AND ≥1 blocking amb with status==blocked AND resolved==false
        state = "blocked"
    elif implementation_converged_at is not None and findings_resolved_path is not None:
        state = "code_converged"
    else:
        state = "pending"

    return {
        "group_id": group_id,
        "state": state,
        "implementation_converged_at": implementation_converged_at,
        "reviewer_rounds": reviewer_rounds,
        "findings_resolved_path": findings_resolved_path,
        "blocking_amb_ids": blocking_amb_ids,
        "blocking_amb_health": blocking_amb_health,
        "fixtures_exercised": fixtures_exercised,
    }


def _is_per_reviewer_file(basename: str, group_id: str) -> bool:
    """Return True iff *basename* is a per-reviewer findings file.

    Matches ``findings_<group_id>_<N>_r<reviewer_id>.json`` and
    ``findings_<group_id>_<N>_rr<reviewer_id>.json`` (double-r variant).
    The last underscore-separated token must be ``r<digits>`` or ``rr<digits>``.
    Fixer files (``_fixer-discovered``) are explicitly excluded.
    """
    prefix = f"findings_{group_id}_"
    if not basename.startswith(prefix):
        return False
    if not basename.endswith(".json"):
        return False
    if "fixer" in basename:
        return False
    middle = basename[len(prefix):-len(".json")]
    # last segment after final underscore
    last = middle.rsplit("_", 1)[-1] if "_" in middle else ""
    if last.startswith("rr") and last[2:].isdigit():
        return True
    if last.startswith("r") and last[1:].isdigit():
        return True
    return False


def _is_round_output_file(basename: str, group_id: str) -> bool:
    """Return True iff *basename* is a round-output (non-reviewer) findings file.

    Round-output files follow ``findings_<group_id>_<N>.json`` where the only
    part after the prefix is a plain decimal integer.  Files with ``_rN``,
    ``_rrN``, or ``fixer`` suffixes are per-reviewer or fixer outputs and are
    excluded.
    """
    prefix = f"findings_{group_id}_"
    if not basename.startswith(prefix):
        return False
    if not basename.endswith(".json"):
        return False
    middle = basename[len(prefix):-len(".json")]
    return middle.isdigit()


# ---------------------------------------------------------------------------
# Roll-up
# ---------------------------------------------------------------------------

# States that represent meaningful forward progress (used in impl_in_progress)
_PROGRESS_STATES = frozenset({"executing", "code_converged", "verified"})
# States considered "implementation-advanced" (beyond pending)
_ADVANCED_STATES = frozenset({"code_converged", "blocked", "verified"})


def derive_phase_position(
    groups: list[dict],
    findings_dir: str,
    batch_id: str,
) -> str:
    """Compute ``derived_phase_position`` from per-group state objects.

    Parameters
    ----------
    groups:
        List of group state objects (output of :func:`derive_group_state`).
    findings_dir:
        Absolute path to the ``.specdev/findings/`` directory.
    batch_id:
        The milestone batch identifier (used to glob milestone-review files).

    Returns
    -------
    str
        One of ``pending``, ``impl_in_progress``, ``impl_complete``,
        ``review_pending``, ``review_complete``, ``operator_pending``, ``closed``.
    """
    # "active" excludes both deferred (paused) and wont_do (permanently
    # cancelled) groups from every progress computation below -- neither is
    # part of the work currently being tracked (DEVSPEC-122 follow-up).
    active_groups = [g for g in groups if g["state"] not in ("deferred", "wont_do")]

    # All-deferred/wont_do → treat as pending (nothing to track)
    if not active_groups:
        return "pending"

    # --- closed: every active group has implementation.status == "verified"
    # (the original used status_ref.id; after DEVSPEC-38 we use the status string)
    # Note: "state == verified" is an exact proxy since verified state ↔ impl.status=="verified"
    if all(g["state"] == "verified" for g in active_groups):
        return "closed"

    # --- Milestone-review files
    review_glob = os.path.join(
        findings_dir,
        f"findings_{batch_id}_review_*",
    )
    review_files = _glob.glob(review_glob)
    has_any_review_file = bool(review_files)
    has_review_empty = any(_is_empty_findings(f) for f in review_files)

    # --- operator_pending requires review_complete first
    all_advanced = all(g["state"] in _ADVANCED_STATES for g in active_groups)

    if all_advanced and has_review_empty:
        # review_complete condition met — check operator_pending
        has_blocked = any(g["state"] == "blocked" for g in active_groups)
        has_unresolved_blocking_amb = any(
            h for g in active_groups
            for h in g.get("blocking_amb_health", [])
            if not h["resolved"]
        )
        if has_blocked or has_unresolved_blocking_amb:
            return "operator_pending"
        return "review_complete"

    if all_advanced and has_any_review_file and not has_review_empty:
        # All advanced, review files exist but none empty → review_pending
        return "review_pending"

    if all_advanced and not has_any_review_file:
        # All advanced, no review file at all → impl_complete
        return "impl_complete"

    # --- impl_in_progress: ≥1 progress, ≥1 pending
    has_progress = any(g["state"] in _PROGRESS_STATES for g in active_groups)
    has_pending = any(g["state"] == "pending" for g in active_groups)
    if has_progress and has_pending:
        return "impl_in_progress"

    # --- pending: every active group is pending
    if all(g["state"] == "pending" for g in active_groups):
        return "pending"

    # Fallback: covers transient executing-bearing cases not captured by the named predicates
    # (e.g. executing alone, executing+blocked without pending).  executing is never persisted
    # in plan files, so this path is not expected to appear in steady-state.
    return "impl_in_progress"


# ---------------------------------------------------------------------------
# Top-level compute
# ---------------------------------------------------------------------------

def compute_milestone_state(
    plan: dict,
    findings_dir: str,
    batch_id: str,
) -> dict:
    """Compute the full milestone-state output contract object.

    Parameters
    ----------
    plan:
        The parsed ``ms_<batch_id>_plan.json`` document.
    findings_dir:
        Absolute path to the ``.specdev/findings/`` directory.
    batch_id:
        The milestone batch identifier (e.g. ``"phase2_newsletter_send"``).

    Returns
    -------
    dict
        Full output contract object::

            {
              "milestone_id": str,
              "groups": list[dict],
              "derived_phase_position": str,
              "blockers": list[dict],
            }

    Notes
    -----
    **``blockers[]`` is advisory — do NOT gate on its emptiness.**
    Downstream consumers MUST gate on ``derived_phase_position``, not on
    ``blockers[]`` emptiness.  ``blockers[]`` CAN be non-empty even when
    ``derived_phase_position == "closed"``: this occurs when an operator marks
    all groups verified while a blocking ambiguity remained unresolved.  The
    amb is surfaced in ``blockers[]`` for visibility, not as a gate.

    **``verified`` outranks ``blocked`` by design.**  Per-group state resolution
    applies ``deferred/wont_do > verified > blocked > code_converged > pending``
    (first match wins).  Operator verification (``impl_status == "verified"``)
    is the terminal override — it cannot be downgraded by an unresolved amb.
    """
    # Use batch_id directly per the output contract (specdev-scope.md:226: "milestone_id": "<batch_id>").
    # SKILL.md:201 confirms the consumer only parses groups[] and derived_phase_position;
    # milestone_id in the output is not gate-critical for downstream consumers.
    milestone_id: str = batch_id

    checklist: list[dict] = (
        plan.get("plan", {})
        .get("spec_alignment", {})
        .get("checklist", [])
    )
    ambiguities: list[dict] = (
        plan.get("execution", {})
        .get("emergent_ambiguities", [])
    )

    group_states: list[dict] = [
        derive_group_state(item, findings_dir, ambiguities)
        for item in checklist
    ]

    phase_position = derive_phase_position(group_states, findings_dir, batch_id)

    # Build blockers list from all blocking ambs across all groups
    seen_ids: set[str] = set()
    blockers: list[dict] = []
    for g in group_states:
        for h in g.get("blocking_amb_health", []):
            if not h["resolved"] and h["id"] not in seen_ids:
                seen_ids.add(h["id"])
                blockers.append({
                    "kind": "ambiguity",
                    "id": h["id"],
                    "issue": (
                        "not well_formed" if not h["well_formed"]
                        else f"blocked ambiguity unresolved in group {g['group_id']}"
                    ),
                })

    return {
        "milestone_id": milestone_id,
        "groups": group_states,
        "derived_phase_position": phase_position,
        "blockers": blockers,
    }
