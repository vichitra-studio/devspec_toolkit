"""W837 PLAN_FILE_LARGE: the step-16 validator reports a plan file above 750000 bytes."""
from __future__ import annotations

import json
from pathlib import Path


from specdev_tools.validation.validators.step_16 import PLAN_BYTES_WARN, validate_step_16
from unit.lifecycle._support import PLAN, example_spec, load, toolkit_root


def _w837(spec: Path) -> list[str]:
    plan = spec / PLAN
    return [e.message for e in validate_step_16(load(spec, PLAN), toolkit_root(), str(plan), str(spec)) if e.code == "W837"]


def _pad_to(spec: Path, size: int) -> None:
    """Grow the example plan to exactly *size* bytes with one long string in an ordinary field."""
    plan = load(spec, PLAN)
    plan["plan"]["summary"]["functional_summary"] = ""
    base = len(json.dumps(plan).encode("utf-8"))
    plan["plan"]["summary"]["functional_summary"] = "x" * (size - base)
    (spec / PLAN).write_text(json.dumps(plan), encoding="utf-8")
    assert (spec / PLAN).stat().st_size == size


def test_w837_fires_above_750000_bytes(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    _pad_to(spec, PLAN_BYTES_WARN + 1)
    (message,) = _w837(spec)
    assert "PLAN_FILE_LARGE" in message and str(PLAN_BYTES_WARN + 1) in message


def test_w837_silent_at_the_threshold(tmp_path: Path) -> None:
    spec = example_spec(tmp_path)
    _pad_to(spec, PLAN_BYTES_WARN)
    assert _w837(spec) == []
