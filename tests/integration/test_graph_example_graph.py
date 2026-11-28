"""The worked example as a graph (WI-M4-12): ``build_graph`` and the ``graph`` check read against the M3 oracle
(``_graph_example``, which reads the same files through the registry) and against the node list of design section 12.21.

Also the 00-05 same-step set: every ``same_step_kinds`` link the real schemas declare, run through the resolver.
"""
from __future__ import annotations

import dataclasses
import fnmatch
import json
from collections import Counter
from collections.abc import Iterator

import pytest

from integration import _graph_example as oracle
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.check import run_graph_check
from specdev_tools.graph.model import Graph, Link, Node
from specdev_tools.graph.resolve import resolve_graph
from unit.graph._synth import ROOT, graph_check

# Section 12.21, Figures 15 and 16: nodes whose label is their id.  (id, kind)
_DESIGN_NODES = (
    ("seed-accounts", "seed"), ("scope-password-reset", "scope-item"), ("scope-sms-reset", "scope-item"),
    ("asm-member-controls-email", "assumption"), ("need-fewer-reset-tickets", "need"),
    ("sh-support-lead", "stakeholder"), ("risk-reset-link-takeover", "risk"), ("seg-registered-member", "segment"),
    ("metric-recovery-time", "metric"), ("cap-account-recovery", "capability"), ("identity-service", "component"),
    ("conn-identity-to-mailrelay", "connection"), ("tp-argon2", "third-party"), ("tp-mailrelay", "third-party"),
    ("con-staged-delivery", "constraint"), ("fr-password-reset", "fr"), ("ac-password-reset-3", "criterion"),
    ("api-password-reset-confirm", "api"), ("inv-reset-token-single-use", "invariant"),
    ("nfr-latency-reset-email", "nfr"), ("milestone-account-recovery", "design-milestone"),
    ("rule-contract-tests-on-every-pr", "rule"), ("rule-spec-check-on-every-pr", "rule"),
    ("rule-security-review-of-token-handling", "rule"), ("threat-reset-token-replay", "threat"),
    ("ec-token-at-expiry-second", "edge-case"), ("job-contract-tests", "job"), ("ms-account-recovery", "roadmap-milestone"),
    ("tc-confirm-expired-token", "task-criterion"), ("tc-confirm-reused-token", "task-criterion"),
    ("PWRESET_CONFIRM_EXPIRED_01", "plan-item"),
)
# Nodes the design shows by a short label (the label is not an id): the label -> (id in the example, kind).
_DESIGN_SHORT_LABELS = {
    "environment ci": ("ci", "environment"),
    "gate contract-tests": ("contract-tests", "gate"),
    "secret reset-token-signing-key": ("secret-reset-token-signing-key", "secret"),
    "secret mailrelay-api-key": ("secret-mailrelay-api-key", "secret"),
    "err token-expired": ("err-password-reset-confirm-token-expired", "api-error"),
    "fix expired-token": ("fix-password-reset-expired-token", "fixture"),
    "fix reused-token": ("fix-password-reset-reused-token", "fixture"),
    "scaffold row": ("scaffold-password-reset-confirm", "scaffold-row"),
    "anchor row": ("anchor-ms-account-recovery", "anchor-row"),
}
# Figure 16 also draws ``ver expired-token`` and ``evd-20261202-0007``: records written at run time, not in the example.
_STEPS_00_05 = frozenset({"00", "01", "02", "02a", "03", "04", "05"})


@pytest.fixture(scope="module")
def graph() -> Graph:
    return build_graph(str(oracle.SPEC), str(ROOT))


def _registered_files() -> list[str]:
    """Example files (relative to its spec folder) that the registry has a key for, as the M3 oracle reads them."""
    registry = json.loads((ROOT / "tools" / "entry_key_registry.json").read_text(encoding="utf-8"))["registry"]
    found = sorted(path.relative_to(oracle.SPEC).as_posix() for path in oracle.SPEC.rglob("*.json"))
    return [name for name in found if any(fnmatch.fnmatchcase(name, key) for key in registry)]


def _oracle_kinds() -> dict[str, str]:
    """Id -> kind of every example node (the seed included) as the M3 oracle reads them."""
    kinds = {node.node_id: node.kind for node in oracle.nodes_of(tuple(_registered_files()))}
    return kinds | {oracle.SEED_ID: "seed"}


def test_worked_example_graph_builds(graph: Graph) -> None:
    """Every registered example file is read, none is skipped, and the nodes carry the step of their file."""
    read = set(graph.documents)
    assert graph.load_errors == []
    assert read == {*_registered_files(), "common/seed_manifest.json"}
    assert {node.step for node in graph.nodes} >= {"seed", "00", "02a", "05", "09", "12", "14", "16", "16a"}
    assert all(node.file in read or node.kind == "seed" for node in graph.nodes)
    assert graph.dups == {}


def test_worked_example_has_no_resolver_errors() -> None:
    """The whole ``graph`` check passes on the example, and it passes because it saw the links, not because it saw none."""
    spec = oracle.SPEC
    assert run_graph_check(str(spec), str(ROOT)) == []
    summary = graph_check(spec)
    assert summary["status"] == "PASS" and summary["findings"] == []
    graph = build_graph(str(spec), str(ROOT))
    oracle_links = sum(
        len(value if isinstance(value, list) else [value])
        for node in oracle.nodes_of(tuple(_registered_files()))
        for link in node.links
        if (value := node.item.get(link["field"]))
    )
    assert oracle_links > 0
    assert sum(len(links) for links in graph.outgoing.values()) == oracle_links


def test_worked_example_node_counts(graph: Graph) -> None:
    """Section 12.21's ids and kinds are all on the graph, and the graph has the oracle's nodes and no others."""
    found = {node.id: node.kind for node in graph.nodes}
    missing = [(node_id, kind) for node_id, kind in _DESIGN_NODES if found.get(node_id) != kind]
    assert missing == []
    short = [label for label, (node_id, kind) in _DESIGN_SHORT_LABELS.items() if found.get(node_id) != kind]
    assert short == []
    assert found == _oracle_kinds()
    assert Counter(found.values()) == Counter(_oracle_kinds().values())
    assert len(graph.nodes) == len(found)


def _same_step_cases(graph: Graph) -> Iterator[tuple[str, str, str, str]]:
    """``(holder kind, field, target kind, step)`` for each ``same_step_kinds`` entry of a link of steps 00-05."""
    for kind, decl in sorted(graph.decls.items()):
        steps = graph.shape.kind_steps.get(kind, ())
        if len(steps) != 1 or steps[0] not in _STEPS_00_05:
            continue
        for link in decl.links:
            for target in link.same_step_kinds:
                yield kind, link.field, target, steps[0]


def _pair(graph: Graph, holder_kind: str, field: str, target_kind: str, step: str, *, declared: bool) -> Graph:
    """Two nodes of *step*: a holder linking a target through the real declaration of *field*, optionally undeclared."""
    decl = next(link for link in graph.decls[holder_kind].links if link.field == field)
    if not declared:
        decl = dataclasses.replace(decl, same_step_kinds=())
    holder = Node(
        id="holder", kind=holder_kind, step=step, role="obligation-system", file=f"{step}.json", jq_path=".h", parent=None,
        children=(), lifecycle="active", scope=None, links=(Link("holder", field, "target", decl),), label="",
    )
    target = dataclasses.replace(holder, id="target", kind=target_kind, links=(), jq_path=".t")
    return Graph.from_nodes([holder, target], shape=graph.shape)


def test_every_declared_same_step_link_of_steps_00_05_resolves_only_through_its_declaration(graph: Graph) -> None:
    """Each same-step link the real schemas declare is accepted; with the declaration removed it is E702."""
    cases = list(_same_step_cases(graph))
    assert len(cases) >= 20
    for holder_kind, field, target_kind, step in cases:
        label = f"{holder_kind}.{field} -> {target_kind} in step {step}"
        assert resolve_graph(_pair(graph, holder_kind, field, target_kind, step, declared=True)) == [], label
        refused = resolve_graph(_pair(graph, holder_kind, field, target_kind, step, declared=False))
        assert [error.code for error in refused] == ["E702"], label
