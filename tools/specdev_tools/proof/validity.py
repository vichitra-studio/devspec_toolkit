"""Evidence validity: when a stored run, or an attestation, still proves what it was made for.

The run of a binding leaves one evidence file per run stage (``evd-<binding suffix>-<stage>.json``); the latest run
overwrites the file.  A file is valid for a binding when the run passed, it ran on the code tree the host has now, the
spec nodes it rests on read as they did, the third parties it names are at the pinned version, and its stage is not
below the stage of the binding.  Spec, seed, plan, anchor, lock and record writes change none of that.

``ProofContext`` is built once by a caller and passed everywhere.  It reads the code tree once and the content hashes once
for each graph, so a caller that edits the code or the spec builds a new context.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import cached_property
from typing import NamedTuple

from specdev_tools.graph.contract import item_of
from specdev_tools.graph.gitview import read_seed_texts_at, read_seed_texts_noting
from specdev_tools.graph.model import Graph
from specdev_tools.graph.queries import relied_on_third_parties
from specdev_tools.proof.stages import STAGES, stage_rank
from specdev_tools.trace.hashing import compute_all
from specdev_tools.verify.bind import targets_of
from specdev_tools.verify.code_tree import code_tree_for_host, same_code_tree
from specdev_tools.verify.records import Attestation, Binding, Evidence, all_bindings, read_evidence
from specdev_tools.verify.run import evidence_id

GUARD_NOT_MATCHED = "GUARD_NOT_MATCHED"
NONZERO_EXIT = "NONZERO_EXIT"
STALE_TREE = "STALE_TREE"
STALE_HASH = "STALE_HASH"
STALE_TP_VERSION = "STALE_TP_VERSION"
STAGE_TOO_LOW = "STAGE_TOO_LOW"
NO_EVIDENCE = "NO_EVIDENCE"
"""The reason of a binding that no run has written evidence for (not a reason of one evidence file)."""
CI_STAGE = "ci"
DEV_STAGE = "dev"


class Validity(NamedTuple):
    """Whether evidence is valid, and if not the reason (one of the subcodes above); ``reason`` is ``None`` when it is valid."""

    valid: bool
    reason: str | None


@dataclass(eq=False)
class ProofContext:
    """What proof reads besides the graph: the host repository, the spec folder, the folder of the evidence files and, for a past state, its commit.

    ``spec_root`` is the absolute path of ``spec_dir``.  With ``commit`` the code tree and the seed texts are those of that commit.
    """

    git_root: str
    spec_dir: str
    evidence_dir: str
    commit: str | None = None
    _hashes: tuple[Graph, dict[str, str]] | None = field(default=None, init=False, repr=False)

    @property
    def spec_root(self) -> str:
        """The absolute path of the spec folder."""
        return os.path.abspath(self.spec_dir)

    @cached_property
    def code_tree(self) -> str:
        """The code tree id of the host now (or at ``commit``), read once; the host declarations are read with it.

        Raises:
            GitViewError: E708 when git fails.
            FindingError: E520 when the host declarations cannot be read.
        """
        return code_tree_for_host(self.git_root, self.spec_root, self.commit)

    def content_hashes(self, graph: Graph) -> dict[str, str]:
        """The content hash of each node of *graph* that has one, computed once for each graph object.

        Raises:
            GitViewError: E708 when ``commit`` does not resolve.
        """
        if self._hashes is None or self._hashes[0] is not graph:
            texts = read_seed_texts_at(self.commit, self.git_root, graph) if self.commit else read_seed_texts_noting(graph, self.git_root)
            self._hashes = (graph, {node_id: pair[0] for node_id, pair in compute_all(graph, texts).items()})
        return self._hashes[1]


def effective_stage(stage: str, treat_ci_as_dev: bool) -> str:
    """The stage a binding counts as: its own, except that with *treat_ci_as_dev* (the close gate) ``ci`` counts as ``dev``."""
    return DEV_STAGE if treat_ci_as_dev and stage == CI_STAGE else stage


def evidence_for(binding: Binding, ctx: ProofContext) -> list[Evidence]:
    """The stored run evidence of *binding*: one file for each run stage that has one, in stage order."""
    found = (read_evidence(ctx.evidence_dir, evidence_id(binding.id, stage)) for stage in STAGES)
    return [evidence for evidence in found if evidence is not None and binding.id in evidence.about]


def node_evidence(graph: Graph, ctx: ProofContext, node_id: str) -> list[Evidence]:
    """The stored run evidence of every binding that proves the node *node_id* (a record that states no ``proves`` proves all its verifier's targets), bindings in graph order, each binding's files in stage order."""
    wanted = graph.canonical_id(node_id)
    return [evidence for binding in all_bindings(graph) if wanted in targets_stated(binding, graph) for evidence in evidence_for(binding, ctx)]


def proved_ids(binding: Binding) -> tuple[str, ...]:
    """The ids a run of *binding* hashes: its verifier and the nodes it states it proves."""
    return (binding.verifier, *binding.proves)


def _passes(evidence: Evidence) -> str | None:
    if evidence.exit_code != 0:
        return NONZERO_EXIT
    return None if evidence.guard_matched else GUARD_NOT_MATCHED


def _stale_hash(evidence: Evidence, binding: Binding, graph: Graph, ctx: ProofContext) -> bool:
    """Whether a node the evidence rests on is gone or reads differently.

    The ids checked are those the file recorded; for a file written for another binding, also this binding's verifier and
    proved nodes, each of which the file must have recorded.
    """
    current = ctx.content_hashes(graph)
    recorded = evidence.recorded_hashes
    names = set(recorded) | (set() if binding.id in evidence.about else set(proved_ids(binding)))
    for name in names:
        node = graph.find(name)
        if node is None or recorded.get(name) != current.get(node.id):
            return True
    return False


def _pin(graph: Graph, third_party: str) -> str:
    pin = (item_of(graph, graph.by_id[third_party]) or {}).get("pin")
    return pin if isinstance(pin, str) else ""


def _stale_third_party(evidence: Evidence, binding: Binding, graph: Graph) -> bool:
    """Whether a third party the proved nodes rely on is at another version than the evidence recorded; one the evidence omits is skipped."""
    installed = {graph.canonical_id(name): version for name, version in evidence.installed_versions.items()}
    proved = [node for name in binding.proves if (node := graph.find(name)) is not None]
    return any(version != _pin(graph, third_party) for third_party in relied_on_third_parties(graph, proved) if (version := installed.get(third_party)) is not None)


def evidence_valid(evidence: Evidence, binding: Binding, graph: Graph, ctx: ProofContext, *, treat_ci_as_dev: bool = False) -> Validity:
    """Whether *evidence* proves *binding* now, with the first reason it does not, in this order.

    ``NONZERO_EXIT`` or ``GUARD_NOT_MATCHED``: the run did not pass.  ``STALE_TREE``: it ran on another code tree than the host has.
    ``STALE_HASH``: a node it rests on changed or is gone.  ``STALE_TP_VERSION``: a third party the proved nodes rely on is at
    another version than the pin.  ``STAGE_TOO_LOW``: the run stage is below the stage of the binding (``effective_stage``).

    Raises:
        GitViewError: E708 when git fails.
        FindingError: E520 when the host declarations cannot be read.
    """
    failed = _passes(evidence)
    if failed is None and not same_code_tree(evidence.tested_tree, ctx.code_tree):
        failed = STALE_TREE
    if failed is None and _stale_hash(evidence, binding, graph, ctx):
        failed = STALE_HASH
    if failed is None and _stale_third_party(evidence, binding, graph):
        failed = STALE_TP_VERSION
    if failed is None and stage_rank(evidence.stage) < stage_rank(effective_stage(binding.stage, treat_ci_as_dev)):
        failed = STAGE_TOO_LOW
    return Validity(failed is None, failed)


def attestation_valid(attestation: Attestation, node_id: str, graph: Graph, ctx: ProofContext) -> Validity:
    """Whether *attestation* still holds for the node *node_id*: it was made on the code tree the host has now (``STALE_TREE``) and the hash it recorded for the node is the node's content hash now (``STALE_HASH``).

    An attestation carries no exit code, guard or third-party version.

    Raises:
        GitViewError: E708 when git fails.
        FindingError: E520 when the host declarations cannot be read.
    """
    if not same_code_tree(attestation.tested_tree, ctx.code_tree):
        return Validity(False, STALE_TREE)
    node = graph.find(node_id)
    recorded = attestation.recorded_hashes.get(node_id)
    if node is None or recorded is None or recorded != ctx.content_hashes(graph).get(node.id):
        return Validity(False, STALE_HASH)
    return Validity(True, None)


def same_run(binding: Binding, other: Binding) -> bool:
    """Whether *other* is another binding of the verifier of *binding* with the same commands and output guard (one run proves both)."""
    return other.verifier == binding.verifier and other.commands == binding.commands and other.guard == binding.guard


def targets_stated(binding: Binding, graph: Graph) -> tuple[str, ...]:
    """The ids *binding* proves: those it states, else every id its verifier can prove (a record that states none, as the worked example's)."""
    verifier = graph.by_id.get(binding.verifier)
    return binding.proves or (targets_of(verifier, graph) if verifier is not None else ())
