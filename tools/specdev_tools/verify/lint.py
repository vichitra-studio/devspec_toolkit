"""The lint of verification and evidence records, and the pruning of records whose node is gone.

``lint_verification_records`` reports what the record check (``trace/records.py``) cannot know: a binding whose stored stage no
longer matches the nodes it proves (E330), a binding that proves an environment that is not a stage (E334), and a ``proves`` id
that names no node (``spec-check`` runs it in its ``records`` check).  ``prune_orphan_records`` deletes the records the ``graph`` check reports as E700: a record whose every
``verifies`` or ``about`` target is gone, repeated until no record is left dangling, so evidence about a pruned binding goes too.
"""
from __future__ import annotations

from pathlib import Path

from specdev_tools.core.errors import SpecError, make_error
from specdev_tools.graph.kinds import RECORD_ROLE
from specdev_tools.graph.model import Graph, Node
from specdev_tools.proof.stages import UnknownStageForEnvironment, is_retired_binding
from specdev_tools.trace.lockfile import MERGE_CHECK_OWNER
from specdev_tools.verify.bind import computed_stage, targets_of
from specdev_tools.verify.records import BINDING_KIND, Binding, binding_of

PROVES_UNKNOWN_CODE = "E774"  # the plan gives no code for a record that speaks about a node that no longer exists
_RECORD_LINKS = ("verifies", "about")


def _finding(code: str, node: Node, message: str) -> SpecError:
    return make_error(code, f"verification record {node.id}: {message}", file=node.file, owner=MERGE_CHECK_OWNER, node_id=node.id)


def _unknown_proves(node: Node, binding: Binding, graph: Graph) -> list[SpecError]:
    """One finding for each id of ``proves`` that no node has, even through a rename (``binding_of`` resolves aliases)."""
    gone = [node_id for node_id in dict.fromkeys(binding.proves) if graph.find(node_id) is None]
    return [_finding(PROVES_UNKNOWN_CODE, node, f"proves '{node_id}', which names no node; remove it from proves") for node_id in gone]


def _stage_findings(node: Node, binding: Binding, verifier: Node, graph: Graph) -> list[SpecError]:
    """E334 when a node it proves involves an environment that is not a stage; E330 when the stored stage is not the one its nodes need."""
    proves = binding.proves or targets_of(verifier, graph)
    try:
        needed = computed_stage(proves, verifier, graph)
    except UnknownStageForEnvironment as exc:
        return [_finding("E334", node, f"environment '{exc.environment}' is not a stage; name it dev, ci, staging or prod")]
    if binding.stage == needed or is_retired_binding(node, graph):
        return []
    return [_finding("E330", node, f"stage '{binding.stage}' does not match the stage '{needed}' the nodes it proves need; set its stage to '{needed}'")]


def lint_verification_records(graph: Graph) -> list[SpecError]:
    """E330, E334 and the unknown ``proves`` ids (E774) of the verification records of *graph*, in graph order; owner ``merge-check``.

    A binding whose verifier is gone is skipped (the ``graph`` check reports it as E700).
    """
    findings: list[SpecError] = []
    for node in graph.by_kind.get(BINDING_KIND, ()):
        binding = binding_of(node, graph)
        verifier = graph.find(binding.verifier)
        findings.extend(_unknown_proves(node, binding, graph))
        if verifier is not None:
            findings.extend(_stage_findings(node, binding, verifier, graph))
    return findings


def _dangling(node: Node, graph: Graph, gone: set[str]) -> bool:
    """Whether every target of the ``verifies`` or ``about`` links of the record *node* is no node of *graph* or is in *gone*."""
    targets = [graph.canonical_id(link.target) for link in node.links if link.field in _RECORD_LINKS]
    return bool(targets) and all(graph.find(target) is None or target in gone for target in targets)


def orphan_records(graph: Graph) -> list[Node]:
    """The record nodes whose every ``verifies``/``about`` target is gone, in graph order.

    A record about an orphan record is an orphan too: the rule is applied again until no record is added.
    """
    records = [node for node in graph.nodes if node.role == RECORD_ROLE]
    gone: set[str] = set()
    while added := [node.id for node in records if node.id not in gone and _dangling(node, graph, gone)]:
        gone.update(added)
    return [node for node in records if node.id in gone]


def prune_orphan_records(spec_dir: str, graph: Graph, dry_run: bool = False) -> list[Path]:
    """Delete the orphan records of *graph* from *spec_dir* and return their paths in graph order; with *dry_run*, delete nothing.

    The caller holds the write lock and built *graph* under it.
    """
    paths = [Path(spec_dir) / node.file for node in orphan_records(graph)]
    if not dry_run:
        for path in paths:
            path.unlink()
    return paths
