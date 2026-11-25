"""What ``spec-check --step`` and ``spec-check --paths`` print: the text report and the ``step_gate`` JSON object.

Both views are made from the ``StepGateResult`` of each gated step and the baseline the run measured "new" against;
nothing here runs a check or reads a file.  The text report is one block per step; the JSON object has the shape of
``tests/unit/validation/step_gate_output.schema.json`` (for several steps each bucket is the union over the steps).

Blocking and waiting findings, and the warnings of the step, are always listed in full; upstream debt, pending and
gate-owned findings are counted per owner, and listed in full only with ``--detail all``.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Literal

from specdev_tools.core.errors import SpecError
from specdev_tools.core.git_base import BaselineResult, BaseResolution
from specdev_tools.core.json_output import error_to_dict
from specdev_tools.graph.ownership import STEP_PREFIX
from specdev_tools.validation.step_gate import (
    EXIT_CLEAR,
    StepGateResult,
    WaitingError,
    gate_exit_code,
    union_errors,
    union_waiting,
)

Detail = Literal["summary", "all"]
DETAIL_SUMMARY: Detail = "summary"
DETAIL_ALL: Detail = "all"
DETAIL_CHOICES = (DETAIL_SUMMARY, DETAIL_ALL)

_SUSPECT_CODES = frozenset({"E762", "E763"})
_SUSPECT_HINT = "(incl. suspects: specdev stale)"
_WAITING_PREFIX = "waiting on "
_TITLE_WIDTH = 19
_LABEL_WIDTH = 20
_NEW_MARK = "  (new since the base)"
_NO_OWNER = "unowned"
_NO_BASELINE = "unavailable"
_UNAVAILABLE = BaseResolution(None, None, "unavailable")


# --- shared helpers ---------------------------------------------------------------------------------------------

def _who(error: SpecError) -> str:
    """The owner of *error* without the ``step:`` prefix (``05``, ``merge-check``, ``unowned``)."""
    owner = error.owner or _NO_OWNER
    return owner[len(STEP_PREFIX):] if owner.startswith(STEP_PREFIX) else owner


def _by_owner(errors: Iterable[SpecError]) -> Counter[str]:
    return Counter(_who(error) for error in errors)


def _flatten(pending: Mapping[str, tuple[SpecError, ...]]) -> list[SpecError]:
    return [error for found in pending.values() for error in found]


# --- text -------------------------------------------------------------------------------------------------------

def render_step_gate(results: Sequence[StepGateResult], baseline: BaselineResult, detail: Detail = DETAIL_SUMMARY) -> str:
    """The text report: one block per step in *results*, each ending in its ``RESULT`` line."""
    base = _base_text(baseline)
    return "\n".join(line for result in results for line in _block(result, base, detail == DETAIL_ALL))


def _base_text(baseline: BaselineResult) -> str:
    resolution = baseline.resolution if baseline.mode == "ok" else None
    return (resolution or _UNAVAILABLE).describe()


def _block(result: StepGateResult, base: str, full: bool) -> list[str]:
    lines = [f"step gate: step {result.step}   {base}"]
    lines += _blocking_lines(result)
    lines += _waiting_lines(result.waiting)
    lines += _warning_lines(result)
    lines += _debt_lines(result, full)
    lines += _pending_lines(result, full)
    lines += _gate_owned_lines(result, full)
    lines += _listed("NO LONGER PRESENT", result.no_longer_present, "(the base had them; --detail all to list)", full)
    lines.append(f"RESULT: {'CLEAR' if result.clear else 'BLOCKED'}")
    return lines


def _title(name: str, count: int, summary: str) -> str:
    head = f"{name} ({count})"
    return f"{head:<{max(_TITLE_WIDTH, len(head) + 2)}}{summary}".rstrip()


def _row(error: SpecError, label: str) -> str:
    where = error.node_id or error.file or "-"
    return f"  {error.code:<5} {f'[{label}]':<{_LABEL_WIDTH}}{where}  {' '.join(error.message.split())}"


def _counts(counter: Counter[str]) -> str:
    return ", ".join(f"{owner}: {count}" for owner, count in sorted(counter.items()))


def _blocking_lines(result: StepGateResult) -> list[str]:
    blocking = result.blocking
    if not blocking.errors:
        return []
    lines = [_title("BLOCKING", len(blocking.errors), f"own {len(blocking.own)}, new upstream {len(blocking.new_upstream)}")]
    lines += [_row(error, f"{result.step} own") for error in blocking.own]
    lines += [_row(error, f"{_who(error)} new upstream") for error in blocking.new_upstream]
    return lines


def _waiting_lines(waiting: Sequence[WaitingError]) -> list[str]:
    if not waiting:
        return []
    reasons = sorted({reason.removeprefix(_WAITING_PREFIX) for entry in waiting for reason in entry.reasons})
    lines = [_title("WAITING", len(waiting), f"{_WAITING_PREFIX}{', '.join(reasons)}")]
    lines += [_row(entry.error, f"{_who(entry.error)} own") for entry in waiting]
    return lines


def _warning_lines(result: StepGateResult) -> list[str]:
    count = len(result.own_warnings) + len(result.new_upstream_warnings)
    if not count:
        return []
    new = result.new_own_warnings
    summary = f"own {len(result.own_warnings)}" + (f" ({len(new)} new)" if new else "") + f", new upstream {len(result.new_upstream_warnings)}"
    lines = [_title("WARNINGS", count, summary)]
    lines += [_row(error, f"{result.step} own") + (_NEW_MARK if error in new else "") for error in result.own_warnings]
    lines += [_row(error, f"{_who(error)} new upstream") for error in result.new_upstream_warnings]
    return lines


def _listed(title: str, errors: Sequence[SpecError], hint: str, full: bool) -> list[str]:
    """A summarised section (``<owner>: <count>`` list), with every finding under it when *full*."""
    if not errors:
        return []
    summary = _counts(_by_owner(errors))
    lines = [_title(title, len(errors), summary if full else f"{summary}   {hint}".rstrip())]
    if full:
        lines += [_row(error, _who(error)) for error in errors]
    return lines


def _debt_lines(result: StepGateResult, full: bool) -> list[str]:
    return _listed("UPSTREAM DEBT", result.upstream_debt, "(--detail all to list)", full)


def _pending_lines(result: StepGateResult, full: bool) -> list[str]:
    return _listed("PENDING", _flatten(result.pending), "(clears when those steps run)", full)


def _gate_owned_lines(result: StepGateResult, full: bool) -> list[str]:
    suspects = any(error.code in _SUSPECT_CODES for error in result.gate_owned)
    hint = _SUSPECT_HINT if suspects else ""
    if not full:
        hint = f"{hint} (--detail all to list)".strip()
    return _listed("GATE-OWNED", result.gate_owned, hint, full)


# --- JSON -------------------------------------------------------------------------------------------------------

def step_gate_json(results: Sequence[StepGateResult], baseline: BaselineResult) -> dict[str, Any]:
    """The ``step_gate`` object of the ``--json`` payload.

    ``new_own_warnings`` is the part of ``own_warnings`` the base did not have, and ``no_longer_present`` what the base had
    (owned by a listed step or a step above it) and the tree no longer has; both are empty without a base and neither blocks.
    ``blocking`` and ``own_warnings`` hold finding objects (``error_to_dict``); ``waiting`` holds ``{"error", "waiting_on"}``;
    ``new_upstream_warnings`` and ``upstream_debt`` and ``gate_owned`` are finding lists; ``pending`` maps an owner step to
    its findings.  With several steps every bucket is the union over the steps.
    """
    return {
        "steps": [result.step for result in results],
        "baseline": _baseline_json(baseline),
        "blocking": _dicts(union_errors(result.blocking.errors for result in results)),
        "waiting": [_waiting_json(entry) for entry in union_waiting(results)],
        "own_warnings": _dicts(union_errors(result.own_warnings for result in results)),
        "new_own_warnings": _dicts(union_errors(result.new_own_warnings for result in results)),
        "no_longer_present": _dicts(union_errors(result.no_longer_present for result in results)),
        "new_upstream_warnings": _dicts(union_errors(result.new_upstream_warnings for result in results)),
        "upstream_debt": _dicts(union_errors(result.upstream_debt for result in results)),
        "pending": _pending_json(results),
        "gate_owned": _dicts(union_errors(result.gate_owned for result in results)),
        "result": "clear" if gate_exit_code(results) == EXIT_CLEAR else "blocked",
    }


def _baseline_json(baseline: BaselineResult) -> dict[str, str | None]:
    resolution = baseline.resolution
    if baseline.mode != "ok" or resolution is None:
        return {"ref": None, "commit": None, "mode": _NO_BASELINE}
    return {"ref": resolution.ref, "commit": resolution.commit, "mode": resolution.mode}


def _dicts(errors: Iterable[SpecError]) -> list[dict[str, Any]]:
    return [error_to_dict(error) for error in errors]


def _waiting_json(entry: WaitingError) -> dict[str, Any]:
    return {
        "error": error_to_dict(entry.error),
        "waiting_on": [reason.removeprefix(_WAITING_PREFIX) for reason in entry.reasons],
    }


def _pending_json(results: Sequence[StepGateResult]) -> dict[str, list[dict[str, Any]]]:
    owners = sorted({owner for result in results for owner in result.pending})
    return {owner: _dicts(union_errors(result.pending.get(owner, ()) for result in results)) for owner in owners}
