"""``graph.contract.path_steps`` and ``value_at``: one reading of a jq-style path for every caller."""
from __future__ import annotations

from typing import Any

import pytest

from specdev_tools.graph.contract import path_steps, value_at

DOCUMENT: dict[str, Any] = {"milestones": [{"tasks": [{"id": "t0"}, {"id": "t1"}]}], "environments": {"prod": {"url": "u"}, "a.b": 1}}


@pytest.mark.parametrize(
    ("path", "steps"),
    [
        ("", []),
        (".milestones[0].tasks[1]", ["milestones", 0, "tasks", 1]),
        ('.environments["prod"].url', ["environments", "prod", "url"]),
        ('.environments["a.b"]', ["environments", "a.b"]),
        ('.environments["q\\"x"]', ["environments", 'q"x']),
    ],
)
def test_path_steps_gives_the_keys_and_the_indexes_in_order(path: str, steps: list[str | int]) -> None:
    assert path_steps(path) == steps


@pytest.mark.parametrize("path", ["milestones", ".a[", ".a[x]", '.a["unclosed', ".a..b"])
def test_a_path_that_is_not_made_only_of_steps_has_none(path: str) -> None:
    assert path_steps(path) is None


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (".milestones[0].tasks[1].id", "t1"),
        ('.environments["prod"].url', "u"),
        ('.environments["a.b"]', 1),
        (".milestones[3]", None),
        (".milestones.tasks", None),
        (".nope", None),
        ("milestones", None),
    ],
)
def test_value_at_follows_the_steps_and_never_raises(path: str, value: Any) -> None:
    assert value_at(DOCUMENT, path) == value
