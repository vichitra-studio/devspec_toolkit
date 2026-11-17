"""A seed file is a lock target: its text moves the chain stamps below it and makes the links into it suspect (WI-M5-08)."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from specdev_tools.trace.hashing import compute_all
from specdev_tools.trace.suspects import CAUSE_CONTENT, CAUSE_UPSTREAM

from unit.trace._lock_support import EXAMPLE_HOST
from unit.trace.test_suspects import SEED_FILE, Example

SEED = "seed-accounts"
SCOPE, CAP, FR = "scope-password-reset", "cap-account-recovery", "fr-password-reset"
SEED_LINK = (SCOPE, "derives_from", SEED)


@pytest.fixture
def example(tmp_path: Path) -> Example:
    host = tmp_path / "host"
    shutil.copytree(EXAMPLE_HOST, host)
    return Example(host)


def _hashes(example: Example) -> dict[str, tuple[str, str]]:
    graph = example.graph()
    return compute_all(graph, example.seed_texts(graph))


def test_committed_lock_has_no_suspect_before_a_seed_edit(example: Example) -> None:
    assert example.suspect_keys() == set()


def test_seed_edit_makes_links_into_the_seed_and_below_suspect(example: Example) -> None:
    before = _hashes(example)
    example.edit_seed()
    after = _hashes(example)
    for node_id in (SCOPE, CAP, FR):
        assert after[node_id][0] == before[node_id][0], f"{node_id}: content hash must not move"
        assert after[node_id][1] != before[node_id][1], f"{node_id}: chain stamp must move"
    assert after[SEED][0] != before[SEED][0]
    causes = {suspect.key: suspect.cause for suspect in example.suspects()}
    assert causes[SEED_LINK] == CAUSE_CONTENT
    below = {key for key, cause in causes.items() if cause == CAUSE_UPSTREAM}
    assert any(target in (SCOPE, CAP, FR) for _holder, _field, target in below)
    assert {key[2] for key in causes if key[2] != SEED} <= {node_id for node_id in after if after[node_id][1] != before[node_id][1]}


def test_seed_whitespace_only_edit_makes_no_link_suspect(example: Example) -> None:
    path = example.host / SEED_FILE
    path.write_text("\n\n".join(path.read_text(encoding="utf-8").split("\n")) + "\n\n  ", encoding="utf-8")
    assert example.suspect_keys() == set()


def test_missing_seed_file_makes_links_into_it_suspect(example: Example) -> None:
    (example.host / SEED_FILE).unlink()
    assert SEED_LINK in example.suspect_keys()
    graph = example.graph()
    assert SEED not in example.seed_texts(graph)
