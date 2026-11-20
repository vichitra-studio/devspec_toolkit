"""``specdev step create NN --from <draft>``: write the artifact of a step from a draft, with its lock entries.

The draft is the whole artifact as JSON; ids of sub-items may be left out and are minted.  The file name is the step's
key in ``tools/entry_key_registry.json`` (``04_fr_list.json``); step 16 (the anchor and the plans of the trinity)
cannot be created this way.  The draft is checked against the schema of the step, the candidate
graph (the spec with the draft in it) must resolve every link, and the file and the lock entries of all its links are
written under the write lock of the spec folder by ``id_writes.write_new_file``, the writer the id-keyed writes use.
Edits to an artifact that exists go through ``specdev json patch|insert|delete --id``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from specdev_tools.core.errors import make_error
from specdev_tools.core.json_utils import resolve_effective_toolkit_root
from specdev_tools.core.registry import get_shared_registry
from specdev_tools.core.schema_validate import SchemaValidationError, jq_path_of, schema_violations, violation_text
from specdev_tools.graph.kinds import FileDecl, load_kind_registry
from specdev_tools.graph.model import Graph
from specdev_tools.trace.id_writes import WriteRefusedError, WriteResult, with_ids, write_new_file
from specdev_tools.trace.writing import writing_graph
from specdev_tools.validation.linter_utils import graph_known_ids

ANCHOR_STEP = "16"
MAX_SHOWN_VIOLATIONS = 10


@dataclass(frozen=True)
class StepCreateRequest:
    """One ``step create``: the step *step* (``"04"``) from the draft file at *draft*."""

    step: str
    draft: str


def _refuse(message: str) -> WriteRefusedError:
    return WriteRefusedError(make_error("E767", message))


def creatable_files(graph: Graph, repo_root: str) -> dict[str, FileDecl]:
    """The registry file of every step ``step create`` writes, by step, in waterfall order (not step 16 or its plans)."""
    declared = {file.step: file for file in load_kind_registry(repo_root).files if not file.is_glob and file.step != ANCHOR_STEP}
    return {step: declared[step] for step in sorted(declared, key=graph.shape.step_key)}


def step_file(graph: Graph, repo_root: str, step: str) -> FileDecl:
    """The registry file of *step*; E767 naming the steps that can be created when *step* has no file ``step create`` writes."""
    files = creatable_files(graph, repo_root)
    if step not in files:
        raise _refuse(f"step {step} has no spec file that step create writes; it creates steps {', '.join(files)}")
    return files[step]


def read_draft(path: str) -> dict[str, Any]:
    """The draft at *path*: a JSON object; E767 when the file cannot be read, is not JSON or is not an object."""
    try:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
    except OSError as error:
        raise _refuse(f"cannot read the draft {path}: {error.strerror or error}") from None
    except ValueError as error:
        raise _refuse(f"the draft {path} is not valid JSON ({error})") from None
    if not isinstance(document, dict):
        raise _refuse(f"the draft {path} must be a JSON object: the whole artifact of the step")
    return document


def mint_ids(graph: Graph, decl: FileDecl, draft: dict[str, Any]) -> tuple[dict[str, Any], tuple[str, ...]]:
    """*draft* with an id minted for every item of the file's collections (and nested items) that has none, and the ids minted."""
    taken, minted = set(graph_known_ids(graph)), []
    document = dict(draft)
    for kind in decl.kinds:
        name = kind.array_path.lstrip(".")
        if isinstance(document.get(name), list):
            document[name] = [with_ids(item, kind, taken, minted) for item in document[name]]
    return document, tuple(minted)


def _step_schema_uri(repo_root: str, decl: FileDecl) -> str | None:
    """The ``$schema`` URI whose schema file is ``schema/<stem of the step's file>.schema.json``, or ``None``."""
    wanted = f"schema/{decl.pattern.removesuffix('.json')}.schema.json"
    registry = get_shared_registry(resolve_effective_toolkit_root(repo_root))
    return next((uri for uri, path in registry.map.items() if path == wanted), None)


def check_draft(repo_root: str, decl: FileDecl, document: dict[str, Any]) -> None:
    """E767 unless *document* declares the schema of the step and has no violation of it (a new file has nothing to compare with)."""
    uri = _step_schema_uri(repo_root, decl)
    if uri is not None and document.get("$schema") != uri:
        raise _refuse(f"the draft declares $schema {document.get('$schema')!r}; the schema of step {decl.step} is {uri!r}")
    try:
        violations = schema_violations(resolve_effective_toolkit_root(repo_root), document)
    except SchemaValidationError as error:
        raise _refuse(f"cannot validate the draft: {error}") from None
    if violations:
        shown = sorted(violations, key=lambda item: (item.path, item.message))[:MAX_SHOWN_VIOLATIONS]
        lines = "\n".join(f"  {jq_path_of(item.path)}: {violation_text(item)}" for item in shown)
        more = len(violations) - len(shown)
        tail = f"\n  ... and {more} more" if more > 0 else ""
        raise _refuse(f"the draft is not valid against its schema; nothing was written:\n{lines}{tail}")


def _create_on(graph: Graph, spec_root: str, repo_root: str, git_root: str, request: StepCreateRequest, *, write: bool) -> WriteResult:
    decl = step_file(graph, repo_root, request.step)
    if graph.shape.files_by_step.get(request.step):
        raise _refuse(f"step {request.step} already has a spec file ({', '.join(graph.shape.files_by_step[request.step])}); edit it with `specdev json patch|insert|delete --id`")
    document, minted = mint_ids(graph, decl, read_draft(request.draft))
    check_draft(repo_root, decl, document)
    node_id = str(document.get("id") or decl.pattern.removesuffix(".json"))
    return write_new_file(graph, spec_root, repo_root, git_root, decl.pattern, document, node_id, minted, write=write)


def create_step(graph: Graph, spec_root: str, repo_root: str, git_root: str, request: StepCreateRequest, *, dry_run: bool = False) -> WriteResult:
    """Create the artifact of ``request.step`` from the draft; writes the file and the lock entries unless *dry_run*.

    *graph* is the graph of *spec_root* (used as it is for a dry run).  A write takes the write lock of the folder
    first and builds the graph again under it, so the existence check and the link checks run on the files as they are
    when the artifact is written.

    Raises:
        WriteRefusedError: E767 (step not creatable, artifact exists, draft unreadable or invalid, a link that does not
            resolve; nothing is written).
        LockError: E769 when another specdev write holds the lock; E760 when the lock file cannot be read.
    """
    with writing_graph(graph, spec_root, repo_root, "step create", write=not dry_run) as planned:
        return _create_on(planned, spec_root, repo_root, git_root, request, write=not dry_run)
