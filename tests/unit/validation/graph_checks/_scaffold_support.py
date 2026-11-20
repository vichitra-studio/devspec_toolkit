"""A context over hand-built scaffold rows, for the unit and the integration tests of the scaffold path check."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path

from specdev_tools.graph.ownership import load_owner_context
from specdev_tools.validation.graph_checks.context import GraphCheckContext
from unit.graph._synth import ROOT

from ._built_support import closed_work, context_of, current_lock, graph_of, node

SCAFFOLD_FILE = "15_scaffold.json"
Row = tuple[str, Sequence[str]]
"""A scaffold row as a test writes it: its path and the APIs it realises."""


def scaffold_context(rows: Mapping[str, Row], git_root: Path | str | None, *, built: Sequence[str] = (), **node_fields: object) -> GraphCheckContext:
    """A context on rows ``{row id: (path, apis)}``; the APIs in *built* are refined by a task criterion of a closed milestone."""
    apis = sorted({api for _, realised in rows.values() for api in realised})
    work, documents = closed_work({f"tc-{api}": api for api in built})
    row_nodes = [
        node(row_id, "scaffold-row", "context", step="15", links=[("realises", api) for api in realised], file=SCAFFOLD_FILE, jq_path=f".rows[{index}]", **node_fields)
        for index, (row_id, (_, realised)) in enumerate(rows.items())
    ]
    documents[SCAFFOLD_FILE] = {"rows": [{"path": path} for path, _ in rows.values()]}
    graph = graph_of([*(node(api, "api") for api in apis), *row_nodes, *work], documents)
    context = context_of(graph, current_lock(graph))
    return replace(context, git_root=None if git_root is None else str(git_root), owner_context=load_owner_context(str(ROOT)))


