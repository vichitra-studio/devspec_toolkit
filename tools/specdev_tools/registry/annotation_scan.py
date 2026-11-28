"""Annotation-driven node discovery for the registry generator (WI-M1-04).

Where ``annotations.collect_annotations`` answers "which ``x-node`` / ``x-link`` objects exist
and where are they defined", this module answers "which registry entries does each host
schema file get".  A *host* is a step schema file (``schema/NN_*.schema.json``), the seed manifest, or any other
registered schema whose own file declares an ``x-node`` with ``files`` (a *record host*; see
``AnnotationScan.record_hosts``).  Starting at
the host root the scan walks ``properties``, ``items`` (array) and ``additionalProperties``
(map), follows ``$ref`` and the ``allOf`` / ``anyOf`` / ``oneOf`` / ``if`` / ``then`` /
``else`` branches, and records a node wherever a schema object carries ``x-node``.

Path grammar of the entries it emits (see ``schema/entry_key_registry.schema.json``):
``.name`` descends an object property, ``[]`` follows an array property, ``{}`` follows a map
property whose keys are the node ids.  A recorded node nested inside another recorded node
becomes a ``nested`` entry of it with a path relative to the parent item.

A kind declared in a shared definition (``schema/core``) is registered once per host that
reaches it by ``$ref`` ("once per occurrence").  A host file that declares ``x-node`` at a
definition site inside itself is *annotation-only* (the heuristic scan is off for it); a host
that merely reaches a shared node keeps its heuristic entries and gains the shared kind.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from specdev_tools.core.constants import SEED_MANIFEST_FILE
from specdev_tools.registry.annotations import (
    AnnotationDecls,
    SchemaReader,
    SchemaRefs,
    collect_annotations,
)

#: Host schema files are ``schema/NN_*.schema.json`` (``NN`` is the step id, e.g. ``02a``).
_STEP_PREFIX = re.compile(r"^([0-9]{2}[a-z]?)_")

#: The seed manifest is the one external (non-step) host: its kind sits at the top of the graph.
SEED_SCHEMA_BASENAME = "seed_manifest.schema.json"

_BRANCH_KEYS = ("allOf", "anyOf", "oneOf")
_COND_KEYS = ("if", "then", "else")


def step_of_schema_file(basename: str) -> str | None:
    """Numeric step prefix of a schema file name (``02a_delivery.schema.json`` -> ``02a``)."""
    m = _STEP_PREFIX.match(basename)
    return m.group(1) if m else None


@dataclass
class ScanNode:
    """One recorded node occurrence, with its place in the host's path grammar."""

    kind: str
    value: dict
    path: str
    nested: list["ScanNode"] = field(default_factory=list)
    links: list[dict] = field(default_factory=list)

    @property
    def map_keyed(self) -> bool:
        return bool(self.value.get("map_keyed"))

    def to_entry(self) -> dict[str, Any]:
        """The registry ``arrayEntry`` dict for this node."""
        v = self.value
        entry: dict[str, Any] = {
            "array_path": self.path + ("{}" if self.map_keyed else ""),
            "kind": self.kind,
            "source": "x-node",
        }
        if self.map_keyed:
            entry["map_keyed"] = True
        else:
            entry["id_field"] = v["id"]
        for key in ("role", "contract", "coarse"):
            if key in v:
                entry[key] = v[key]
        if self.links:
            entry["links"] = list(self.links)
        if self.nested:
            entry["nested"] = [n.to_entry() for n in self.nested]
        return entry


@dataclass
class Occurrence:
    """A top-level recorded node of one host: the entry plus where it is registered."""

    entry: dict[str, Any]
    node: ScanNode
    step: str | None
    files: list[str] | None


@dataclass
class HostScan:
    annotation_only: bool
    occurrences: list[Occurrence] = field(default_factory=list)


def _walk_nothing(uri: str) -> list[ScanNode]:
    """Host walk of an empty scan: no schema is a host."""
    return []


@dataclass
class AnnotationScan:
    decls: AnnotationDecls
    _walk_host: Callable[[str], list[ScanNode]] = _walk_nothing
    _declaring_uris: frozenset[str] = frozenset()
    _rel_to_uri: dict[str, str] = field(default_factory=dict)
    _hosts: dict[str, HostScan | None] = field(default_factory=dict)

    @property
    def empty(self) -> bool:
        return self.decls.empty

    def host(self, schema_rel: str) -> HostScan | None:
        """Scan of the host schema file *schema_rel* (``schema/04_fr_list.schema.json``)."""
        if self.empty:
            return None
        key = schema_rel.replace(os.sep, "/")
        if key not in self._hosts:
            uri = self._rel_to_uri.get(key)
            if uri is None:
                self._hosts[key] = None
            else:
                nodes = self._walk_host(uri)
                own = uri in self._declaring_uris
                occs = [
                    Occurrence(n.to_entry(), n, n.value.get("step"), n.value.get("files"))
                    for n in nodes
                    if not n.value.get("top_of_graph")
                ]
                self._hosts[key] = HostScan(own, occs) if (own or occs) else None
        return self._hosts[key]

    def record_hosts(self) -> list[Occurrence]:
        """Occurrences declared by registered non-step schemas, in schema-path order.

        A registered schema that is neither a step schema nor the seed manifest is a host only
        when its own file declares an ``x-node`` with ``files``; only those occurrences (the ones
        with ``files``) are returned.  ``x-node.step`` is not read: the generator registers them
        under step ``extras``.  A node there without ``files`` is not registered.
        """
        if self.empty:
            return []
        out: list[Occurrence] = []
        for rel, uri in sorted(self._rel_to_uri.items()):
            base = os.path.basename(rel)
            if step_of_schema_file(base) is not None or base == SEED_SCHEMA_BASENAME:
                continue
            if uri not in self._declaring_uris:
                continue
            host = self.host(rel)
            if host is None:
                continue
            out.extend(o for o in host.occurrences if o.files)
        return out

    @property
    def external_kinds(self) -> list[dict[str, Any]]:
        """Kinds whose ids come from outside the step schemas (only ``seed`` today)."""
        if self.empty:
            return []
        out: list[dict[str, Any]] = []
        for rel, uri in sorted(self._rel_to_uri.items()):
            if os.path.basename(rel) != SEED_SCHEMA_BASENAME:
                continue
            for n in self._walk_host(uri):
                if n.value.get("top_of_graph"):
                    out.append({
                        "kind": n.kind,
                        "source_file": SEED_MANIFEST_FILE,
                        "array_path": n.path,
                        "id_field": n.value["id"],
                        "top_of_graph": True,
                    })
        return sorted(out, key=lambda e: e["kind"])


def scan_annotations(repo_root: str, decls: AnnotationDecls | None = None) -> AnnotationScan:
    """Scan *repo_root*'s schemas; the result is empty when no schema carries an annotation."""
    decls = decls if decls is not None else collect_annotations(repo_root)
    if decls.empty or decls.registry is None:
        return AnnotationScan(decls)
    reg = decls.registry
    refs = SchemaRefs(reg)
    return AnnotationScan(
        decls,
        _walk_host=lambda uri: HostWalk(refs, SchemaReader(refs)).run(uri),
        _declaring_uris=frozenset(n.uri for n in decls.nodes),
        _rel_to_uri={rel.replace(os.sep, "/"): uri for uri, rel in reg.map.items()},
    )


class HostWalk:
    """Walk one host schema and return its top-level ``ScanNode`` list.

    The generator walks the step schemas of the toolkit with it; ``graph.host_kinds`` walks the extension schemas of a
    spec folder with it, so the entries of an extension are the ones the generator would write for the same schema.

    A schema may refer to itself (a host's tree of groups).  A schema node that is reached again while it is being
    walked for the same kind is not entered a second time, so a cycle that carries no ``x-node`` adds nothing.  An
    ``x-node`` reached again from inside its own items is a kind nested in itself, which a tree of entries cannot hold:
    it is not entered either and its value is kept in ``nested_in_itself`` for the caller to refuse.
    """

    def __init__(self, refs: SchemaRefs, reader: SchemaReader):
        self.refs = refs
        self.sch = reader
        self.top: list[ScanNode] = []
        self.nested_in_itself: list[dict] = []
        self._seen: set[tuple[int, int, str]] = set()
        self._active: set[tuple[int, int]] = set()
        self._recording: list[int] = []

    def run(self, uri: str) -> list[ScanNode]:
        doc = self.refs.store.get(uri)
        if isinstance(doc, dict):
            self._visit(doc, uri, "", None, None)
        return self.top

    def _visit(
        self,
        node: Any,
        uri: str,
        rel: str,
        scope: ScanNode | None,
        fname: str | None,
    ) -> None:
        if not isinstance(node, dict):
            return
        guard = (id(node), id(scope))  # not the path: it grows on each turn of a cycle
        if guard in self._active:
            return
        self._active.add(guard)
        try:
            self._visit_inner(node, uri, rel, scope, fname)
        finally:
            self._active.discard(guard)

    def _visit_inner(
        self,
        node: dict,
        uri: str,
        rel: str,
        scope: ScanNode | None,
        fname: str | None,
    ) -> None:
        if scope is not None and fname is not None and "x-link" in node:
            self._add_link(scope, fname, node["x-link"])

        xn = node.get("x-node")
        if isinstance(xn, dict) and isinstance(xn.get("kind"), str) and self._valid(xn):
            self._record(node, uri, rel, scope, xn)
            return

        ref = node.get("$ref")
        if isinstance(ref, str):
            hit = self.refs.resolve(ref, uri)
            if hit is not None:
                self._visit(hit[0], hit[1], rel, scope, fname)
        for key in _BRANCH_KEYS:
            branches = node.get(key)
            if isinstance(branches, list):
                for b in branches:
                    self._visit(b, uri, rel, scope, None)
        for key in _COND_KEYS:
            self._visit(node.get(key), uri, rel, scope, None)
        props = node.get("properties")
        if isinstance(props, dict):
            for name, sub in props.items():
                self._visit(sub, uri, f"{rel}.{name}", scope, name)
        items = node.get("items")
        if isinstance(items, dict):
            self._visit(items, uri, f"{rel}[]", scope, None)
        extra = node.get("additionalProperties")
        if isinstance(extra, dict):
            self._visit(extra, uri, f"{rel}{{}}", scope, None)

    @staticmethod
    def _valid(xn: dict) -> bool:
        """Lint (ANNOT-01) rejects invalid annotations before the scan; stay defensive."""
        if xn.get("map_keyed"):
            return True
        return isinstance(xn.get("id"), str)

    def _record(
        self, node: dict, uri: str, rel: str, scope: ScanNode | None, xn: dict
    ) -> None:
        if id(xn) in self._recording:
            if not any(known is xn for known in self.nested_in_itself):
                self.nested_in_itself.append(xn)
            return
        seen = (id(xn), id(scope), rel)
        if seen in self._seen:
            return
        self._seen.add(seen)
        sn = ScanNode(kind=xn["kind"], value=xn, path=rel)
        (scope.nested if scope is not None else self.top).append(sn)
        key = "additionalProperties" if xn.get("map_keyed") else "items"
        item, iuri = self.sch.get(node, uri, key)
        if isinstance(item, dict):
            self._recording.append(id(xn))
            try:
                self._visit(item, iuri, "", sn, None)
            finally:
                self._recording.pop()

    @staticmethod
    def _add_link(scope: ScanNode, fname: str, lk: Any) -> None:
        if not isinstance(lk, dict) or any(x["field"] == fname for x in scope.links):
            return
        scope.links.append({
            "field": fname,
            "kinds": lk.get("kinds"),
            "required": bool(lk.get("required")),
            "built": bool(lk.get("built", False)),
            "same_step_kinds": list(lk.get("same_step_kinds") or []),
            **({"additional_kinds": list(lk["additional_kinds"])} if lk.get("additional_kinds") else {}),
            **({"roles": list(lk["roles"])} if lk.get("roles") else {}),
        })
