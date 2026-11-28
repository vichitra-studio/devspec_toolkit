"""``specdev third-party check``: the pins of the spec against the repository, and against what a deploy installed.

Two checks.  ``check_pins`` (repository mode) reads every version source the host declares for a third party and compares it
with the ``pin`` of the node.  ``check_installed`` (deploy mode) compares the versions a deploy job installed with the pins;
when they all match, ``write_install_checks`` records each as an ``install-check`` evidence record, an audit trail that no
proof reads.
"""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from specdev_tools.core.errors import SpecError, make_error
from specdev_tools.core.host_declarations import HostDeclarations, PinSource, pin_sources_by_id
from specdev_tools.core.pin_sources import SourceError, read_source
from specdev_tools.graph.model import Graph
from specdev_tools.graph.names import THIRD_PARTY
from specdev_tools.graph.queries import pin_of
from specdev_tools.thirdparty.pin import not_exact_error, pin_is_exact
from specdev_tools.trace.lockfile import with_write_lock
from specdev_tools.verify.code_tree import code_tree_for_host
from specdev_tools.verify.records import install_check_id, records_folder, write_evidence

INSTALL_CHECK_TYPE = "install-check"


def _where(source: PinSource) -> str:
    return f"{source.file} at {source.pointer}" if source.pointer is not None else f"{source.file} by {source.pattern}"


def _source_error(node_id: str, pin: str, source: PinSource, git_root: str) -> SpecError | None:
    """The E337 or E338 finding for one *source* of the third party *node_id* with the pin *pin*; ``None`` when it agrees."""
    try:
        found = read_source(source, git_root)
    except SourceError as exc:
        return make_error("E338", f"a version source of '{node_id}' gives no version: {exc}; correct the file or its pin_sources entry", node_id=node_id)
    if found == pin:
        return None
    return make_error(
        "E337",
        f"the pin '{pin}' of '{node_id}' differs from {_where(source)}, which gives '{found}'; make them equal with third-party pin or in that file",
        node_id=node_id,
    )


def check_pins(graph: Graph, declarations: HostDeclarations, git_root: str | Path) -> list[SpecError]:
    """The findings for every third-party node, in graph order.

    A pin that is not exact is E336, whether or not the third party declares sources (its sources are not read); a source
    that cannot give a version is E338; a source whose version is not the pin is E337.  A third party with no declared
    source has only its pin checked for exactness; a ``pin_sources`` key that names no third-party node is E338 (a mistyped
    key would otherwise switch the check off).  A node with no pin, or an empty one, is the schema's finding (E520, "'pin' is a
    required property"), not this check's.
    """
    sources_of = pin_sources_by_id(declarations, graph.canonical_id)
    third_parties = {node.id for node in graph.by_kind.get(THIRD_PARTY, ())}
    findings: list[SpecError] = [
        make_error("E338", f"pin_sources names '{name}', which is no third-party node, so its sources are not checked; correct the key")
        for name in declarations.pin_sources
        if graph.canonical_id(name) not in third_parties
    ]
    for node in graph.by_kind.get(THIRD_PARTY, ()):
        sources, pin = sources_of.get(node.id, ()), pin_of(graph, node.id)
        if not pin:
            continue
        if not pin_is_exact(pin):
            findings.append(not_exact_error(node.id, pin))
            continue
        findings.extend(error for source in sources if (error := _source_error(node.id, pin, source, str(git_root))) is not None)
    return findings


def check_installed(graph: Graph, installed: Mapping[str, str]) -> list[SpecError]:
    """An E339 finding for each of *installed* (``{third party id: version}`` as ``installed_overrides`` resolved it) that is not the pin of its node."""
    return [
        make_error(
            "E339",
            f"'{node_id}' is installed at '{version}' but the spec pin is '{pin}'; install the pinned version, or change the pin with third-party pin",
            node_id=node_id,
        )
        for node_id, version in installed.items()
        if version != (pin := pin_of(graph, node_id))
    ]


def install_check_item(third_party_id: str, version: str, env: str, tag: str | None, tested_tree: str) -> dict[str, object]:
    """The install-check evidence record of one third party: only the fields of that type (``tag`` when given)."""
    item: dict[str, object] = {
        "evidence_id": install_check_id(third_party_id, env),
        "about": [third_party_id],
        "type": INSTALL_CHECK_TYPE,
        "tested_tree": tested_tree,
        "installed_versions": {third_party_id: version},
        "env": env,
    }
    if tag is not None:
        item["tag"] = tag
    return item


def write_install_checks(
    spec_root: str, repo_root: str, git_root: str, installed: Mapping[str, str], env: str, tag: str | None
) -> list[str]:
    """Write one install-check record per entry of *installed* (current ids); returns the record files written, in order.

    Takes the write lock around the writes.  Raises ``FindingError``: E767 for an environment that gives no id, E774 for a
    record that would break its schema (nothing after it is written), E520 for unreadable host declarations, E708 for a
    code tree that cannot be computed.
    """
    tree = code_tree_for_host(git_root, spec_root)
    items = [install_check_item(node_id, version, env, tag, tree) for node_id, version in installed.items()]
    with with_write_lock(spec_root):
        return [write_evidence(records_folder(spec_root), repo_root, item) for item in items]
