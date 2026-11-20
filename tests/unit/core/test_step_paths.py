"""``STEP_JSON_RE``: the one rule for "a root spec file of a step"."""
from __future__ import annotations

import pytest

from specdev_tools.core.step_paths import STEP_JSON_RE


@pytest.mark.parametrize(("name", "step"), [("05_x.json", "05"), ("13a_x.json", "13a"), ("05_.json", "05")])
def test_a_root_spec_file_name_gives_its_step(name: str, step: str) -> None:
    match = STEP_JSON_RE.match(name)
    assert match is not None and match.group(1) == step


@pytest.mark.parametrize("name", ["5_x.json", "05_x.txt", "13A_x.json", "impl_context/ms_a_plan.json", "05x.json"])
def test_other_names_are_no_root_spec_file(name: str) -> None:
    assert STEP_JSON_RE.match(name) is None
