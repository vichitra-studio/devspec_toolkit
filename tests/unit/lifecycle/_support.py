"""Builders the lifecycle tests share: a spec folder of the worked example with a closed or open milestone."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from unit.graph._synth import ROOT, copy_example

MILESTONE = "ms-account-recovery"
ANCHOR = "16_impl_context.json"
PLAN = "impl_context/ms_account_recovery_plan.json"
HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64


def example_spec(tmp_path: Path) -> Path:
    """A copy of the worked example spec folder under *tmp_path*."""
    return copy_example(tmp_path / "spec")


def load(spec: Path, rel: str) -> Any:
    """The parsed JSON of ``spec/rel``."""
    return json.loads((spec / rel).read_text(encoding="utf-8"))


def edit_row(spec: Path, edit: Any) -> None:
    """Apply *edit* (a function of the one anchor row, in place) and write the anchor file back."""
    document = load(spec, ANCHOR)
    edit(document["plan"]["milestone_index"][0])
    (spec / ANCHOR).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def closed_record(**extra: Any) -> dict[str, Any]:
    """A valid ``close`` object of a milestone closed under 1.2.0, with *extra* fields on top."""
    return {"signed_off_by": "a@example.invalid", "signoff": "so-ms-account-recovery-0001", "tree": "4b825dc642cb6eb9a060e54bf8d69288fbee4904", "plan_hash": HASH_A, **extra}


def toolkit_root() -> str:
    return str(ROOT)
