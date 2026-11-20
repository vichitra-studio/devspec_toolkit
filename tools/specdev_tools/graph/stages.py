"""The stage model: ``dev < ci < staging < prod``, the stage a node requires, and retired bindings.

A binding is a verification record (kind ``verification-record``): it names the verifiers it covers in ``verifies`` and
declares a ``stage``.  The stage names are stated once, here; ``tests/unit/graph/test_stages.py`` checks them
against the ``stageName`` enum of ``schema/core/collections.schema.json``.  Every function takes the graph; none reads a
file.  An environment key that is not a stage raises ``UnknownStageForEnvironment``, which the caller reports as E334.
"""
from __future__ import annotations

from collections.abc import Iterable

from specdev_tools.graph.contract import item_of
from specdev_tools.graph.model import Graph, Node
from specdev_tools.graph.names import BINDING_KIND, ENVIRONMENT, JOB, NFR, REALISES, RULE, VERIFIES

STAGES = ("dev", "ci", "staging", "prod")
DEFAULT_STAGE = "dev"
CI_STAGE = "ci"
COMMAND_RULE_STAGE = CI_STAGE  # a rule enforced by a toolkit command, when the host chose to bind one

_JOB_ENFORCED = ("gate", "secret")
_SCOPE_OUT = "out"


class UnknownStageForEnvironment(ValueError):
    """An environment key that is not one of ``STAGES`` (E334); ``environment`` is the key."""

    def __init__(self, environment: str) -> None:
        super().__init__(f"environment '{environment}' is not a stage ({', '.join(STAGES)})")
        self.environment = environment


def stage_rank(stage: str) -> int:
    """The place of *stage* in ``STAGES`` (``dev`` 0, ``prod`` 3).

    Raises:
        ValueError: *stage* is not a stage name.
    """
    try:
        return STAGES.index(stage)
    except ValueError:
        raise ValueError(f"'{stage}' is not a stage ({', '.join(STAGES)})") from None


def stage_at_least(stage: str, other: str) -> bool:
    """Whether *stage* is *other* or a later stage.

    Raises:
        ValueError: *stage* or *other* is not a stage name.
    """
    return stage_rank(stage) >= stage_rank(other)


def highest_stage(stages: Iterable[str]) -> str:
    """The highest of *stages*; ``dev`` when there are none."""
    return max(stages, key=stage_rank, default=DEFAULT_STAGE)


def environment_stage(environment: str) -> str:
    """The stage an environment key names: the key itself.

    Raises:
        UnknownStageForEnvironment: the key is not one of ``STAGES``.
    """
    if environment not in STAGES:
        raise UnknownStageForEnvironment(environment)
    return environment


def _targets(node: Node, field: str, graph: Graph) -> list[Node]:
    found = (graph.find(link.target) for link in node.links if link.field == field)
    return [target for target in found if target is not None]


def _job_stage(job: Node, graph: Graph) -> str:
    environments = _targets(job, REALISES, graph)
    return highest_stage(environment_stage(env.id) for env in environments if env.kind == ENVIRONMENT)


def _realising_jobs(node: Node, graph: Graph) -> list[Node]:
    sources = (graph.by_id.get(link.source) for link in graph.incoming.get(node.id, ()) if link.field == REALISES)
    return [source for source in sources if source is not None and source.kind == JOB]


def _declared_stage(node: Node, graph: Graph) -> str:
    item = item_of(graph, node)
    value = item.get("stage") if item is not None else None
    return value if isinstance(value, str) else DEFAULT_STAGE


def required_stage(node: Node, graph: Graph, via_job: Node | None = None) -> str:
    """The stage at which *node* is proven.

    An NFR needs its own ``stage``; an environment, the stage of its name; a job, the stage of the environment it
    realises; a gate or a secret, the stage of *via_job* (the job of the binding), else the highest stage of the jobs
    that realise it; a rule, that of *via_job*, else ``ci`` (enforced by a command).  Every other kind (criterion, API,
    error, invariant, fixture) needs ``dev``.

    Raises:
        UnknownStageForEnvironment: an environment involved is not a stage.
        ValueError: an NFR declares a stage that is not one.
    """
    if node.kind == NFR:
        stage = _declared_stage(node, graph)
        stage_rank(stage)
        return stage
    if node.kind == ENVIRONMENT:
        return environment_stage(node.id)
    if node.kind == JOB:
        return _job_stage(node, graph)
    if node.kind == RULE and via_job is None:
        return COMMAND_RULE_STAGE
    if node.kind in (RULE, *_JOB_ENFORCED):
        if via_job is not None:
            return _job_stage(via_job, graph)
        return highest_stage(_job_stage(job, graph) for job in _realising_jobs(node, graph))
    return DEFAULT_STAGE


def binding_required_stage(proves: Iterable[str], graph: Graph, via_job: Node | None = None) -> str:
    """The highest stage the nodes named in *proves* require; ``dev`` for none.  An id no node has is skipped (the resolver reports it)."""
    nodes = (graph.find(node_id) for node_id in proves)
    return highest_stage(required_stage(node, graph, via_job) for node in nodes if node is not None)


def binding_stage(binding: Node, graph: Graph) -> str:
    """The stage a binding (verification record) declares; ``dev`` when it declares none."""
    return _declared_stage(binding, graph)


def is_retired_binding(binding: Node, graph: Graph) -> bool:
    """True when the stage of *binding* names an environment whose node has ``scope: out``; false when no such environment exists."""
    environment = graph.by_id.get(binding_stage(binding, graph))
    return environment is not None and environment.kind == ENVIRONMENT and environment.scope == _SCOPE_OUT


def bindings_of(verifier: Node, graph: Graph) -> list[Node]:
    """The bindings (verification records) that name *verifier* in ``verifies``, in graph order."""
    sources = (graph.by_id.get(link.source) for link in graph.incoming.get(verifier.id, ()) if link.field == VERIFIES)
    return [source for source in sources if source is not None and source.kind == BINDING_KIND]


def retired_binding_ids(verifier: Node, graph: Graph) -> set[str]:
    """Ids of the bindings of *verifier* when it has bindings and all are retired; else empty."""
    bindings = bindings_of(verifier, graph)
    return {b.id for b in bindings} if bindings and all(is_retired_binding(b, graph) for b in bindings) else set()


def is_retired_verifier(verifier: Node, graph: Graph) -> bool:
    """True when *verifier* has bindings and every one is retired (it is out of play; links to it still resolve)."""
    return bool(retired_binding_ids(verifier, graph))
