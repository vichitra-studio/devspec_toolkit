"""Build the spec graph from a spec folder.

Nodes come only from the collections the registry declares (``graph.kinds``); an id comes only from the declared id
field (or the map key of a map-keyed collection) and a link only from a declared ``x-link`` field.  Files are walked in
step order, then by path, and items in document order, so two runs over the same folder give the same graph.
"""
from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from specdev_tools.context._utils import load_step_order
from specdev_tools.core.entry_key_registry import iter_nodes, match_glob_key
from specdev_tools.core.errors import make_error
from specdev_tools.core.loaders import read_json_object
from specdev_tools.core.scope_helpers import as_str, str_in, str_items
from specdev_tools.graph.kinds import (
    EXTRAS_STEP,
    SEED_KIND,
    SEED_STEP,
    FileDecl,
    KindDecl,
    KindRegistry,
    KindRegistryError,
    load_kind_registry,
)
from specdev_tools.graph.model import (
    DEFAULT_LIFECYCLE,
    LIFECYCLES,
    Graph,
    Link,
    LoadError,
    Node,
    SpecShape,
    node_label,
)

PLAN_FILE_KEY = "impl_context/ms_*_plan.json"
SEED_PATH_FIELD = "path"
UNREADABLE_MESSAGE = "unreadable or not a JSON object"


@dataclass(frozen=True)
class _FileContext:
    """What every node of one file shares."""

    file: str
    step: str | None
    milestone: str | None


def _step_ranks(repo_root: str) -> dict[str, int]:
    """Sort rank of each step: seeds first, then ``tools/step_order.json`` order; any other step sorts last."""
    try:
        steps = str_items(load_step_order(repo_root).get("steps"))
    except (OSError, ValueError) as exc:
        path = os.path.join(repo_root, "tools", "step_order.json")
        raise KindRegistryError(make_error("E520", f"step order {path} is unreadable: {exc}", path)) from exc
    ranks = {step: index for index, step in enumerate(steps)}
    ranks[SEED_STEP] = -1
    return ranks


def _files_on_disk(spec_root: Path, pattern: str) -> list[str]:
    """Spec-root-relative paths of the files that match registry file key *pattern*."""
    return [path.relative_to(spec_root).as_posix() for path in spec_root.glob(pattern) if path.is_file()]


def _file_matches(rel: str, pattern: str) -> bool:
    return match_glob_key(rel, pattern) if any(ch in pattern for ch in "*?[") else rel == pattern


def _candidate_files(spec_root: Path, decl: FileDecl, overrides: Mapping[str, Any]) -> list[str]:
    """Files of *decl* to read: those on disk plus override paths that match, each once, sorted."""
    found = set(_files_on_disk(spec_root, decl.pattern))
    found.update(rel for rel in overrides if _file_matches(rel, decl.pattern))
    return sorted(found)


def _wanted(rel: str, decl: FileDecl, files: set[str] | None, steps: set[str] | None) -> bool:
    return (files is None or rel in files) and (steps is None or decl.step in steps)


def _present_files(registry: KindRegistry, spec_root: Path, overrides: Mapping[str, Any]) -> dict[str, FileDecl]:
    """Every registered file that exists (on disk or as an override), each once, mapped to its declaration."""
    chosen: dict[str, FileDecl] = {}
    for decl in (*registry.external, *registry.files):
        for rel in _candidate_files(spec_root, decl, overrides):
            chosen.setdefault(rel, decl)
    return chosen


def _plan(
    present: Mapping[str, FileDecl], ranks: Mapping[str, int], files: set[str] | None, steps: set[str] | None
) -> list[tuple[str, FileDecl]]:
    """The ``(relative path, declaration)`` pairs to read, in step order then path; a file is read once."""
    unranked = len(ranks)
    wanted = [(rel, decl) for rel, decl in present.items() if _wanted(rel, decl, files, steps)]
    return sorted(wanted, key=lambda pair: (ranks.get(pair[1].step, unranked), pair[0]))


def _kind_names_of(decls: Iterable[KindDecl]) -> Iterable[str]:
    for decl in decls:
        yield decl.kind
        yield from _kind_names_of(decl.nested)


def _shape(registry: KindRegistry, present: Mapping[str, FileDecl], ranks: Mapping[str, int]) -> SpecShape:
    """The step ranks, the steps that declare each kind and the present files per step."""
    kind_steps: dict[str, set[str]] = {}
    for decl in (*registry.external, *registry.files):
        for kind in _kind_names_of(decl.kinds):
            kind_steps.setdefault(kind, set()).add(decl.step)
    files_by_step: dict[str, list[str]] = {}
    for rel, decl in present.items():
        files_by_step.setdefault(decl.step, []).append(rel)
    return SpecShape(
        step_ranks=dict(ranks),
        kind_steps={kind: tuple(sorted(found)) for kind, found in kind_steps.items()},
        files_by_step={step: tuple(sorted(found)) for step, found in files_by_step.items()},
    )


def _document(spec_root: Path, rel: str, overrides: Mapping[str, Any]) -> dict[str, Any] | None:
    """The parsed document of *rel*: the override when one is given, else the file; ``None`` when unreadable."""
    if rel in overrides:
        doc = overrides[rel]
        return doc if isinstance(doc, dict) else None
    return read_json_object(spec_root / rel)


def _node_id(item: Mapping[str, Any], decl: KindDecl, key: str | None) -> str | None:
    """The id of an item: the map key under a map-keyed collection, else the non-empty string in its id field."""
    value = key if decl.map_keyed else item.get(decl.id_field or "")
    return value if isinstance(value, str) and value else None


def _links_of(item: Mapping[str, Any], decl: KindDecl, node_id: str) -> tuple[Link, ...]:
    return tuple(
        Link(node_id, link.field, target, link)
        for link in decl.links
        for target in str_items(item.get(link.field))
    )


def _seed_file(item: Mapping[str, Any], default: str) -> str:
    """The seed's own file path from its manifest entry; the manifest path when the entry has none."""
    return as_str(item.get(SEED_PATH_FIELD)) or default


def _collect(
    container: Mapping[str, Any], decl: KindDecl, ctx: _FileContext, prefix: str, parent: str | None
) -> list[Node]:
    """Nodes of *decl* found under *container*, each followed by its nested nodes, in document order."""
    nodes: list[Node] = []
    for item, path, key in iter_nodes(container, decl.array_path):
        node_id = _node_id(item, decl, key)
        jq_path = prefix + path
        nested = [n for child in decl.nested for n in _collect(item, child, ctx, jq_path, node_id)]
        if node_id is None:
            nodes.extend(nested)
            continue
        scope = item.get("scope")
        nodes.append(Node(
            id=node_id,
            kind=decl.kind,
            step=ctx.step,
            role=decl.role,
            file=_seed_file(item, ctx.file) if decl.kind == SEED_KIND else ctx.file,
            jq_path=jq_path,
            parent=parent,
            children=tuple(n.id for n in nested if n.parent == node_id),
            lifecycle=item["lifecycle"] if str_in(item.get("lifecycle"), LIFECYCLES) else DEFAULT_LIFECYCLE,
            scope=scope if isinstance(scope, str) else None,
            links=_links_of(item, decl, node_id),
            label=node_label(item),
            milestone=ctx.milestone,
        ))
        nodes.extend(nested)
    return nodes


def _file_context(rel: str, decl: FileDecl, doc: Mapping[str, Any]) -> _FileContext:
    step = None if decl.step == EXTRAS_STEP else decl.step
    milestone = (as_str(doc.get("milestone")) or None) if decl.pattern == PLAN_FILE_KEY else None
    return _FileContext(rel, step, milestone)


def _posix_set(values: Iterable[str] | None) -> set[str] | None:
    """*values* as a set of ``/``-separated paths, or ``None`` when no selection was given."""
    return None if values is None else {value.replace(os.sep, "/") for value in values}


def build_graph(
    spec_root: str,
    repo_root: str,
    *,
    files: Iterable[str] | None = None,
    steps: Iterable[str] | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> Graph:
    """Build the graph of the spec folder *spec_root* from the registry of the toolkit at *repo_root*.

    Args:
        spec_root: the spec folder; node files are relative to it.
        repo_root: the toolkit root (``tools/entry_key_registry.json`` and ``tools/step_order.json``).
        files: when given, only these paths (relative to *spec_root*) are read.
        steps: when given, only files registered under these steps (``"seed"`` for the seed manifest) are read.
        overrides: ``{path relative to spec_root: parsed document}``; each replaces the on-disk content of that file
            for this build (the file need not exist).

    Returns:
        A ``Graph``.  A file that cannot be read or whose top level is not an object is skipped and listed in
        ``load_errors`` (``validate_file`` reports the file itself); an item with no usable id is not a node.

    Raises:
        KindRegistryError: the registry or the step order of the toolkit is missing or unreadable (E520).
    """
    registry = load_kind_registry(repo_root)
    ranks = _step_ranks(repo_root)
    root = Path(spec_root)
    wanted_files, wanted_steps = _posix_set(files), None if steps is None else set(steps)
    given = overrides or {}
    nodes: list[Node] = []
    load_errors: list[LoadError] = []
    present = _present_files(registry, root, given)
    for rel, decl in _plan(present, ranks, wanted_files, wanted_steps):
        doc = _document(root, rel, given)
        if doc is None:
            load_errors.append(LoadError(rel, UNREADABLE_MESSAGE))
            continue
        ctx = _file_context(rel, decl, doc)
        nodes.extend(n for kind in decl.kinds for n in _collect(doc, kind, ctx, "", None))
    return Graph.from_nodes(nodes, load_errors, _shape(registry, present, ranks))


def build_file_graph(path: str, repo_root: str, document: Mapping[str, Any]) -> Graph:
    """The graph of the single spec file *path*, whose parsed content is *document*.

    The spec root is the file's folder, or its parent when the registry key carries a folder (``impl_context/...``,
    ``common/...``).  A file the registry does not know gives a graph with no nodes.

    Raises:
        KindRegistryError: the registry or the step order of the toolkit is missing or unreadable (E520).
    """
    absolute = Path(path).resolve()
    graph = Graph()
    for root in (absolute.parent, absolute.parent.parent):
        rel = absolute.relative_to(root).as_posix()
        graph = build_graph(str(root), repo_root, files=[rel], overrides={rel: document})
        if graph.nodes:
            break
    return graph
