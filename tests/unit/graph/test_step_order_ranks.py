"""``step_order_ranks``: an unreadable step order is an E520 whose message does not repeat the file (the finding's path holds it)."""
from __future__ import annotations

from pathlib import Path

import pytest

from specdev_tools.graph.build import step_order_ranks
from specdev_tools.graph.kinds import KindRegistryError


@pytest.mark.parametrize(("content", "reason"), [("[1]", "not a JSON object"), ("{", None)])
def test_unreadable_step_order_names_the_file_once(tmp_path: Path, content: str, reason: str | None) -> None:
    (tmp_path / "tools").mkdir()
    path = tmp_path / "tools" / "step_order.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(KindRegistryError) as caught:
        step_order_ranks(str(tmp_path))
    error = caught.value.error
    assert error.code == "E520" and error.path == str(path)
    assert error.message.startswith("step order is unreadable: ") and str(path) not in error.message
    assert reason is None or error.message.endswith(reason)
    assert error.render().count(str(path)) == 1


def test_a_missing_step_order_names_the_file_once(tmp_path: Path) -> None:
    with pytest.raises(KindRegistryError) as caught:
        step_order_ranks(str(tmp_path))
    error = caught.value.error
    assert error.code == "E520" and error.path == str(tmp_path / "tools" / "step_order.json")
    assert error.message == "step order is unreadable: No such file or directory"
    assert error.render().count(str(tmp_path)) == 1
