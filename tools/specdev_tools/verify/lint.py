"""The lint of verification and evidence records.

``lint_verification_records`` reports what the record check (``trace/records.py``) cannot know: a binding whose stored stage no
longer matches the nodes it proves (E330), a binding that proves an environment that is not a stage (E334), and a ``proves`` id
that names no node (``spec-check`` runs it in its ``records`` check).  The pruning of records whose node is gone (``prune_orphan_records``) is in ``trace/records.py``.
"""
from __future__ import annotations

from specdev_tools.core.errors import SpecError, make_error
from specdev_tools.graph.model import Graph, Node
from specdev_tools.graph.names import BINDING_KIND
from specdev_tools.graph.stages import UnknownStageForEnvironment, is_retired_binding
from specdev_tools.trace.lockfile import MERGE_CHECK_OWNER
from specdev_tools.verify.bind import computed_stage, proved_ids
from specdev_tools.verify.records import Binding, binding_of

PROVES_UNKNOWN_CODE = "E774"  # the plan gives no code for a record that speaks about a node that no longer exists


def _finding(code: str, node: Node, message: str) -> SpecError:
    return make_error(code, f"verification record {node.id}: {message}", file=node.file, owner=MERGE_CHECK_OWNER, node_id=node.id)


def _unknown_proves(node: Node, binding: Binding, graph: Graph) -> list[SpecError]:
    """One finding for each id of ``proves`` that no node has, even through a rename (``binding_of`` resolves aliases)."""
    gone = [node_id for node_id in dict.fromkeys(binding.proves) if graph.find(node_id) is None]
    return [_finding(PROVES_UNKNOWN_CODE, node, f"proves '{node_id}', which names no node; remove it from proves") for node_id in gone]


def _stage_findings(node: Node, binding: Binding, verifier: Node, graph: Graph) -> list[SpecError]:
    """E334 when a node it proves involves an environment that is not a stage; E330 when the stored stage is not the one its nodes need."""
    proves = proved_ids(binding, graph)
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
