"""A seed file is a lock target: its text moves the chain stamps below it and makes the links into it suspect (WI-M5-08)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from specdev_tools.graph.resolve import HISTORY_FIELDS
from specdev_tools.trace.hashing import compute_all
from specdev_tools.trace.suspects import CAUSE_CONTENT, CAUSE_UPSTREAM
from specdev_tools.validation.spec_check import run_spec_check_json

from unit.graph._synth import ROOT, run_cli
from unit.trace._lock_support import EXAMPLE_HOST
from unit.trace._suspects_support import SEED_FILE, Example

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


def _chain_holds_the_seed(example: Example) -> set[tuple[str, str, str]]:
    """Keys of the lock entries whose target is the seed or has the seed above it: read from the graph, not from ``find_suspects``.

    "Above" is what the chain stamp is built from: the containment parent, the folded criteria and the link targets
    (not the history fields), followed to the top.
    """
    graph = example.graph()

    def above(node_id: str) -> set[str]:
        seen: set[str] = set()
        pending = [node_id]
        while pending:
            node = graph.by_id[pending.pop()]
            ups = [node.parent, *node.children, *(target.id for link in node.links if link.field not in HISTORY_FIELDS and (target := graph.find(link.target)))]
            for up in ups:
                if up is not None and up in graph.by_id and up not in seen:
                    seen.add(up)
                    pending.append(up)
        return seen

    holding = {SEED, *(node.id for node in graph.nodes if SEED in above(node.id))}
    return {entry.key for entry in example.lock().entries if graph.find(entry.target).id in holding}  # type: ignore[union-attr]


def _stale_listing(example: Example) -> dict[str, Any]:
    code, out = run_cli("stale", "--json", "--repo-root", str(ROOT), "--spec-root", str(example.spec), "--git-root", str(example.host))
    assert code == 0, out
    return json.loads(out)


def test_seed_edit_lists_00_and_02_nodes_and_everything_below(example: Example) -> None:
    """DOC 13.8: a seed edit makes the link into the seed content_changed and every link whose target has the seed above it upstream_changed."""
    before = _hashes(example)
    example.edit_seed()
    after = _hashes(example)
    assert {node_id for node_id in after if after[node_id][0] != before[node_id][0]} == {SEED}
    for node_id in (SCOPE, CAP, FR):
        assert after[node_id][1] != before[node_id][1], f"{node_id}: chain stamp must move"

    expected = _chain_holds_the_seed(example)
    assert expected == {entry.key for entry in example.lock().entries}  # on the worked example the seed is above every link
    assert example.suspect_keys() == expected
    causes = {suspect.key: suspect.cause for suspect in example.suspects()}
    assert causes[SEED_LINK] == CAUSE_CONTENT
    assert {key for key, cause in causes.items() if cause == CAUSE_CONTENT} == {key for key in expected if key[2] == SEED}
    assert {cause for key, cause in causes.items() if key[2] != SEED} == {CAUSE_UPSTREAM}

    document = _stale_listing(example)
    listed = {(node["node"], link["field"], link["target"]) for step in document["steps"] for node in step["suspect_nodes"] for link in node["links"]}
    assert listed == expected
    graph = example.graph()
    assert [step["step"] for step in document["steps"]] == sorted({graph.by_id[holder].step for holder, _field, _target in expected}, key=graph.shape.step_key)
    assert {"00", "02"} <= {step["step"] for step in document["steps"]}
    assert {node["node"] for step in document["steps"] if step["step"] in ("00", "02") for node in step["suspect_nodes"]} >= {SCOPE}
    assert document["totals"]["suspect_links"] == len(expected)


def test_whitespace_only_seed_edit_makes_no_suspects(example: Example) -> None:
    path = example.host / SEED_FILE
    path.write_text("\n\n".join(path.read_text(encoding="utf-8").split("\n")) + "\n\n  ", encoding="utf-8")
    assert example.suspect_keys() == set()


def test_missing_seed_file_makes_links_suspect_and_adds_no_trace_lock_finding(example: Example) -> None:
    (example.host / SEED_FILE).unlink()
    assert SEED_LINK in example.suspect_keys()
    graph = example.graph()
    assert SEED not in example.seed_texts(graph)
    _errors, context = run_spec_check_json(str(ROOT), str(example.spec), git_root=str(example.host), spec_root=str(example.spec))
    codes = {finding["code"] for finding in context["checks"]["trace-lock"]["findings"]}
    assert codes == {"E763"}, codes  # the suspects, and no E760, E761, E762 or E882 for the missing file
