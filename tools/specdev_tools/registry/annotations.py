"""Annotation reader and lint for the spec-graph ``x-node`` / ``x-link`` keywords.

``collect_annotations`` walks every schema registered in ``tools/schema_registry.json``
(over ``SchemaRegistry.store``) with its own provenance-tracking walk: it follows
``$ref`` hops and records, for every ``x-node`` / ``x-link`` object, the definition
site (schema URI, JSON pointer).  ``schema_nav.effective_schema`` returns merged
copies and loses the origin, so it cannot tell one shared definition from a true
duplicate.

``lint_annotations`` returns issues whose text starts with a stable ``ANNOT-NN``
prefix.  They are toolkit-author diagnostics, not ``SpecError`` codes.

When the toolkit has no ``vc:core:graph`` registry entry, or no schema carries
``x-node`` / ``x-link``, the scan yields nothing and the lint is a no-op, so the
legacy registry output is unchanged.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

from jsonschema import Draft202012Validator

from specdev_tools.core.registry import SchemaRegistry, get_shared_registry

GRAPH_URI = "vc:core:graph"
_KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_OBLIGATION_ROLES = frozenset({"obligation-system", "obligation-delivery"})
_ID_ATOM_REFS = frozenset({
    "vc:core:atoms#kebabId",
    "vc:core:atoms#screamingSnakeId",
    "vc:core:graph#nodeId",
})
_EXTERNAL_KINDS = frozenset({"seed"})
# Keys whose values are data, not subschemas.
_DATA_KEYS = frozenset({"x-node", "x-link", "enum", "const", "default", "examples", "required"})
_MAX_HOPS = 32

Site = tuple[str, str]  # (schema URI, JSON pointer)


class AnnotationError(ValueError):
    """Raised by ``generate_registry`` when the annotation lint finds issues."""

    def __init__(self, issues: list[str]):
        self.issues = list(issues)
        super().__init__(
            f"{len(self.issues)} annotation issue(s):\n" + "\n".join(f"  {i}" for i in self.issues)
        )


@dataclass
class NodeDecl:
    """One ``x-node`` declaration, identified by its definition site."""

    kind: Any
    value: Any
    site: Site
    path: str
    schema_file: str
    container: dict
    uri: str


@dataclass
class LinkDecl:
    """One ``x-link`` declaration, identified by (definition site, field name)."""

    field_name: str | None
    value: Any
    site: Site
    path: str
    schema_file: str
    container: dict
    uri: str
    holders: set[str] = field(default_factory=set)


@dataclass
class AnnotationDecls:
    nodes: list[NodeDecl] = field(default_factory=list)
    links: list[LinkDecl] = field(default_factory=list)
    registry: SchemaRegistry | None = None
    graph_present: bool = False

    @property
    def empty(self) -> bool:
        return not self.graph_present or (not self.nodes and not self.links)


def _esc(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


class _Walker:
    def __init__(self, registry: SchemaRegistry):
        self.reg = registry
        self.store = registry.store
        self.nodes: dict[Site, NodeDecl] = {}
        self.links: dict[tuple[Site, str | None], LinkDecl] = {}
        self._visited: set[tuple[str, str, str | None]] = set()

    def file_of(self, uri: str) -> str:
        rel = self.reg.map.get(uri)
        return rel if rel else uri

    def resolve(self, ref: str, uri: str) -> tuple[Any, str, str] | None:
        """Resolve *ref* seen in schema *uri*: (target, target_uri, target_pointer)."""
        base, _, frag = ref.partition("#")
        target_uri = base or uri
        doc = self.store.get(target_uri)
        if not isinstance(doc, dict):
            return None
        if frag == "":
            return doc, target_uri, ""
        if frag.startswith("/"):
            cur: Any = doc
            for tok in frag[1:].split("/"):
                tok = tok.replace("~1", "/").replace("~0", "~")
                if isinstance(cur, dict) and tok in cur:
                    cur = cur[tok]
                elif isinstance(cur, list) and tok.isdigit() and int(tok) < len(cur):
                    cur = cur[int(tok)]
                else:
                    return None
            return cur, target_uri, frag
        found = self._find_anchor(doc, frag, "")
        if found is None:
            return None
        return found[0], target_uri, found[1]

    def _find_anchor(self, node: Any, anchor: str, ptr: str) -> tuple[dict, str] | None:
        if isinstance(node, dict):
            if node.get("$anchor") == anchor:
                return node, ptr
            for k, v in node.items():
                hit = self._find_anchor(v, anchor, f"{ptr}/{_esc(k)}")
                if hit:
                    return hit
        elif isinstance(node, list):
            for i, v in enumerate(node):
                hit = self._find_anchor(v, anchor, f"{ptr}/{i}")
                if hit:
                    return hit
        return None

    def walk_all(self) -> None:
        for uri, doc in self.store.items():
            if isinstance(doc, dict):
                self.walk(doc, uri, "", None, None)

    def walk(self, node: Any, uri: str, ptr: str, holder: str | None, fname: str | None) -> None:
        if not isinstance(node, dict):
            return
        key = (uri, ptr, holder)
        if key in self._visited:
            return
        self._visited.add(key)
        file = self.file_of(uri)
        if "x-node" in node:
            site = (uri, ptr)
            val = node["x-node"]
            if site not in self.nodes:
                kind = val.get("kind") if isinstance(val, dict) else None
                self.nodes[site] = NodeDecl(kind, val, site, ptr or "/", file, node, uri)
            if isinstance(val, dict) and isinstance(val.get("kind"), str):
                holder = val["kind"]
        if "x-link" in node:
            site = (uri, ptr)
            lk = (site, fname)
            decl = self.links.get(lk)
            if decl is None:
                decl = LinkDecl(fname, node["x-link"], site, ptr or "/", file, node, uri)
                self.links[lk] = decl
            if holder is not None:
                decl.holders.add(holder)
        for k, v in node.items():
            if k in _DATA_KEYS:
                continue
            child = f"{ptr}/{_esc(k)}"
            if k == "$ref" and isinstance(v, str):
                hit = self.resolve(v, uri)
                if hit is not None:
                    self.walk(hit[0], hit[1], hit[2], holder, None)
            elif k == "properties" and isinstance(v, dict):
                for name, sub in v.items():
                    self.walk(sub, uri, f"{child}/{_esc(name)}", holder, name)
            elif isinstance(v, dict):
                self.walk(v, uri, child, holder, None)
            elif isinstance(v, list):
                for i, sub in enumerate(v):
                    self.walk(sub, uri, f"{child}/{i}", holder, None)


def collect_annotations(repo_root: str) -> AnnotationDecls:
    """Collect node and link declarations from every registered schema of *repo_root*."""
    root = os.path.abspath(repo_root)
    if not (
        os.path.exists(os.path.join(root, "tools", "schema_registry.json"))
        or os.path.exists(os.path.join(root, "schema_registry.json"))
    ):
        return AnnotationDecls()
    reg = get_shared_registry(root)
    if GRAPH_URI not in reg.store:
        return AnnotationDecls(registry=reg)
    walker = _Walker(reg)
    walker.walk_all()
    return AnnotationDecls(
        nodes=list(walker.nodes.values()),
        links=list(walker.links.values()),
        registry=reg,
        graph_present=True,
    )


# ---------------------------------------------------------------------------
# Lint
# ---------------------------------------------------------------------------

class _Schemas:
    """Read helpers over the raw store, following ``$ref`` chains."""

    def __init__(self, reg: SchemaRegistry):
        self.w = _Walker(reg)

    def follow(self, node: Any, uri: str) -> tuple[Any, str]:
        for _ in range(_MAX_HOPS):
            if isinstance(node, dict) and isinstance(node.get("$ref"), str):
                hit = self.w.resolve(node["$ref"], uri)
                if hit is None:
                    return node, uri
                node, uri = hit[0], hit[1]
            else:
                break
        return node, uri

    def get(self, node: Any, uri: str, key: str) -> tuple[Any, str]:
        """Value of *key* on node, else on its ``$ref`` chain; (None, uri) if absent."""
        for _ in range(_MAX_HOPS):
            if not isinstance(node, dict):
                break
            if key in node:
                return node[key], uri
            if isinstance(node.get("$ref"), str):
                hit = self.w.resolve(node["$ref"], uri)
                if hit is None:
                    break
                node, uri = hit[0], hit[1]
            else:
                break
        return None, uri

    def properties(self, node: Any, uri: str, _depth: int = 0) -> dict[str, Any]:
        """Union of ``properties`` through ``$ref`` and ``allOf``."""
        out: dict[str, Any] = {}
        if _depth > _MAX_HOPS:
            return out
        node, uri = self.follow(node, uri)
        if not isinstance(node, dict):
            return out
        props = node.get("properties")
        if isinstance(props, dict):
            for name, sub in props.items():
                out[name] = (sub, uri)
        for branch in node.get("allOf") or []:
            out.update(self.properties(branch, uri, _depth + 1))
        return out

    def all_of_refs(self, node: Any, uri: str, _depth: int = 0) -> set[str]:
        refs: set[str] = set()
        if _depth > _MAX_HOPS:
            return refs
        node, uri = self.follow(node, uri)
        if not isinstance(node, dict):
            return refs
        for branch in node.get("allOf") or []:
            if isinstance(branch, dict) and isinstance(branch.get("$ref"), str):
                refs.add(branch["$ref"])
            refs |= self.all_of_refs(branch, uri, _depth + 1)
        return refs

    def is_string(self, node: Any, uri: str, _depth: int = 0) -> bool:
        if _depth > _MAX_HOPS:
            return False
        t, turi = self.get(node, uri, "type")
        if t == "string":
            return True
        cur, curi = self.follow(node, uri)
        if not isinstance(cur, dict):
            return False
        for kw in ("anyOf", "oneOf"):
            branches = cur.get(kw)
            if isinstance(branches, list) and branches and all(
                self.is_string(b, curi, _depth + 1) for b in branches
            ):
                return True
        return any(self.is_string(b, curi, _depth + 1) for b in cur.get("allOf") or [])


def _where(file: str, path: str) -> str:
    return f"{file} {path}"


def _errors_text(validator: Draft202012Validator, instance: Any) -> str:
    errs = sorted(validator.iter_errors(instance), key=lambda e: list(map(str, e.absolute_path)))
    return "; ".join(e.message for e in errs[:3])


def lint_annotations(decls: AnnotationDecls) -> list[str]:
    """Return the ANNOT-nn issues for *decls* (empty when the scan found nothing)."""
    if decls.empty or decls.registry is None:
        return []
    reg = decls.registry
    sch = _Schemas(reg)
    reg_ref = reg.to_referencing_registry()
    v_node = Draft202012Validator({"$ref": f"{GRAPH_URI}#xNode"}, registry=reg_ref)
    v_link = Draft202012Validator({"$ref": f"{GRAPH_URI}#xLink"}, registry=reg_ref)
    verbs = set(reg.store[GRAPH_URI].get("$defs", {}).get("linkVerb", {}).get("enum", []))
    issues: list[str] = []

    # ANNOT-01: values validate against the annotation language.
    valid_nodes: list[NodeDecl] = []
    for n in decls.nodes:
        text = _errors_text(v_node, n.value)
        if text:
            issues.append(f"ANNOT-01 {_where(n.schema_file, n.path)}: invalid x-node: {text}")
        else:
            valid_nodes.append(n)
    valid_links: list[LinkDecl] = []
    for lk in decls.links:
        text = _errors_text(v_link, lk.value)
        if text:
            issues.append(f"ANNOT-01 {_where(lk.schema_file, lk.path)}: invalid x-link: {text}")
        else:
            valid_links.append(lk)

    # ANNOT-02: kebab-case kind names; one definition site per kind.
    sites_by_kind: dict[str, list[NodeDecl]] = {}
    for n in decls.nodes:
        if not isinstance(n.kind, str):
            continue
        if not _KEBAB.match(n.kind):
            issues.append(f"ANNOT-02 {_where(n.schema_file, n.path)}: kind {n.kind!r} is not kebab-case")
        sites_by_kind.setdefault(n.kind, []).append(n)
    for kind, group in sorted(sites_by_kind.items()):
        if len(group) > 1:
            where = ", ".join(_where(g.schema_file, g.path) for g in group)
            issues.append(f"ANNOT-02 kind {kind!r} is declared at more than one site: {where}")

    # ANNOT-03 / ANNOT-08 per valid node.
    for n in valid_nodes:
        val = n.value
        loc = _where(n.schema_file, n.path)
        if val.get("map_keyed"):
            item, iuri = sch.get(n.container, n.uri, "additionalProperties")
            if not isinstance(item, dict):
                issues.append(
                    f"ANNOT-03 {loc}: map_keyed node {n.kind!r} needs additionalProperties "
                    "as an object schema holding the item schema"
                )
                continue
        else:
            item, iuri = sch.get(n.container, n.uri, "items")
            if not isinstance(item, dict):
                issues.append(f"ANNOT-03 {loc}: node {n.kind!r} has no items schema")
                continue
            props = sch.properties(item, iuri)
            id_name = val["id"]
            if id_name not in props:
                issues.append(f"ANNOT-03 {loc}: item schema of {n.kind!r} has no id property {id_name!r}")
            elif not sch.is_string(props[id_name][0], props[id_name][1]):
                issues.append(f"ANNOT-03 {loc}: id property {id_name!r} of {n.kind!r} is not a string")
        # ANNOT-08
        if val.get("top_of_graph") or val.get("role") == "record":
            continue
        props = sch.properties(item, iuri)
        lc = props.get("lifecycle")
        if lc is None or not (isinstance(lc[0], dict) and lc[0].get("$ref") == f"{GRAPH_URI}#lifecycle"):
            issues.append(
                f"ANNOT-08 {loc}: item of {n.kind!r} must declare lifecycle as $ref {GRAPH_URI}#lifecycle"
            )
        if val.get("role") in _OBLIGATION_ROLES:
            for need in ("scope", "scope_reason"):
                if need not in props:
                    issues.append(f"ANNOT-08 {loc}: obligation item of {n.kind!r} must declare {need}")
            if f"{GRAPH_URI}#scopeReasonRule" not in sch.all_of_refs(item, iuri):
                issues.append(
                    f"ANNOT-08 {loc}: obligation item of {n.kind!r} must carry "
                    f"{GRAPH_URI}#scopeReasonRule in allOf"
                )

    declared = {n.kind for n in valid_nodes} | _EXTERNAL_KINDS

    # ANNOT-05 / ANNOT-07 per valid link.
    for lk in valid_links:
        loc = _where(lk.schema_file, lk.path)
        name = lk.field_name
        if name is None or name not in verbs:
            issues.append(f"ANNOT-05 {loc}: x-link field {name!r} is not a verb of linkVerb")
        t, _ = sch.get(lk.container, lk.uri, "type")
        items, iuri = sch.get(lk.container, lk.uri, "items")
        ref = items.get("$ref") if isinstance(items, dict) else None
        if t != "array" or ref not in _ID_ATOM_REFS:
            issues.append(
                f"ANNOT-05 {loc}: x-link field {name!r} must be an array whose items $ref one of "
                f"{', '.join(sorted(_ID_ATOM_REFS))}"
            )
        kinds = lk.value["kinds"]
        if (kinds == "*" or name == "about") and ref in _ID_ATOM_REFS and ref != f"{GRAPH_URI}#nodeId":
            issues.append(
                f"ANNOT-05 {loc}: x-link field {name!r} (kinds \"*\" or verb about) must reference "
                f"{GRAPH_URI}#nodeId"
            )
        if not lk.holders:
            issues.append(f"ANNOT-05 {loc}: x-link field {name!r} does not sit on a node item")
        if isinstance(kinds, list):
            for k in kinds:
                if k not in declared:
                    issues.append(f"ANNOT-07 {loc}: x-link kind {k!r} is not a declared kind")
            same = lk.value.get("same_step_kinds") or []
            for k in same:
                if k not in kinds:
                    issues.append(f"ANNOT-07 {loc}: same_step_kinds entry {k!r} is not in kinds")

    return issues
