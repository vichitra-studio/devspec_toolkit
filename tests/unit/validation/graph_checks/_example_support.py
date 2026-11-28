"""Copies of the worked example with documents edited by name, for the tests that need a spec folder."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from specdev_tools.graph.build import build_graph
from specdev_tools.validation.graph_checks.context import GraphCheckContext
from unit.graph._synth import EXAMPLE_SPEC, ROOT, copy_example, load_doc, write_json

Edit = Callable[[dict[str, Any]], None]
"""An edit of a spec file: a function over the parsed document."""


def edit_documents(spec: Path, **edits: Edit) -> Path:
    """Apply each edit (file name under *spec* to function over the parsed document) to *spec*; *spec*."""
    for rel, edit in edits.items():
        document = load_doc(spec, rel)
        edit(document)
        write_json(spec, rel, document)
    return spec


def edited_example(dest: Path, **edits: Edit) -> Path:
    """A copy of the worked example spec folder at *dest* with each edit applied (see ``edit_documents``); *dest*."""
    return edit_documents(copy_example(dest), **edits)


def context_of_spec(spec: Path | str = EXAMPLE_SPEC, *, git_root: Path | str | None = None) -> GraphCheckContext:
    """The graph check context on the spec folder *spec* (the worked example by default), with no lock and, when *git_root* is given, that host root."""
    return GraphCheckContext.from_graph(build_graph(str(spec), str(ROOT)), None, git_root=None if git_root is None else str(git_root))
