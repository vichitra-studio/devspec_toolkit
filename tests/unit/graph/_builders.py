"""Builders shared by the graph tests: small documents and graphs for the diff, the recipes and the link resolver."""
from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from specdev_tools.graph.diff import GraphDiff, diff_snapshots
from specdev_tools.graph.gitview import Snapshot
from specdev_tools.graph.kinds import LinkDecl
from specdev_tools.graph.model import Graph, Link, Node, SpecShape

from ._synth import ROOT, docs_graph

_FR_FILE = "04_fr_list.json"
_TASK_FILE = "14_roadmap.json"


def _criterion(criterion_id: str, text: str) -> dict[str, Any]:
    return {"criterion_id": criterion_id, "text": text}


def _fr(fr_id: str, statement: str, **extra: Any) -> dict[str, Any]:
    return {"fr_id": fr_id, "statement": statement, **extra}


def _docs(*requirements: dict[str, Any]) -> dict[str, Any]:
    return {_FR_FILE: {"functional_requirements": list(requirements)}}


def _snapshot(docs: Mapping[str, Any]) -> Snapshot:
    return Snapshot(docs_graph(docs), {})


def _diff(old: Mapping[str, Any], new: Mapping[str, Any]) -> GraphDiff:
    return diff_snapshots(_snapshot(old), _snapshot(new))


TABLE_PATH = ROOT / "tools" / "graph_recipes.json"


def _raw() -> dict[str, Any]:
    return json.loads(TABLE_PATH.read_text(encoding="utf-8"))


def _section(raw: dict[str, Any], name: str, role: str) -> dict[str, Any]:
    return next(section for section in raw["sections"] if section["name"] == name and role in section["roles"])


def _set(path: Callable[[dict[str, Any]], dict[str, Any]], key: str, value: Any) -> Callable[[dict[str, Any]], None]:
    return lambda raw: path(raw).__setitem__(key, value)


def _core_16b(raw: dict[str, Any]) -> dict[str, Any]:
    return _section(raw, "core criteria", "16b")


_RANKS = {"seed": -1, "s1": 0, "s2": 1, "s3": 2}


def _decl(field: str, kinds: Iterable[str], same_step: Iterable[str] = ()) -> LinkDecl:
    return LinkDecl(field=field, kinds=tuple(kinds), required=False, built=True, same_step_kinds=tuple(same_step))


def _node(
    node_id: str, kind: str, step: str | None, links: Iterable[tuple[LinkDecl, str]] = (), *,
    role: str = "obligation-system", lifecycle: str = "active",
) -> Node:
    return Node(
        id=node_id, kind=kind, step=step, role=role, file=f"{step}.json", jq_path=f".{kind}[0]", parent=None,
        children=(), lifecycle=lifecycle, scope=None, links=tuple(Link(node_id, d.field, t, d) for d, t in links),
        label="",
    )


def _graph(nodes: Sequence[Node], *, files: Mapping[str, tuple[str, ...]] | None = None) -> Graph:
    kind_steps: dict[str, set[str]] = {}
    for node in nodes:
        if node.step:
            kind_steps.setdefault(node.kind, set()).add(node.step)
    present = files if files is not None else {step: (f"{step}.json",) for steps in kind_steps.values() for step in steps}
    shape = SpecShape(
        step_ranks=_RANKS,
        kind_steps={kind: tuple(sorted(steps)) for kind, steps in kind_steps.items()},
        files_by_step=present,
    )
    return Graph.from_nodes(list(nodes), shape=shape)
