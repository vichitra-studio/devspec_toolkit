"""The node kinds a host declares in the schemas of its extensions (step 13), laid over the toolkit's kinds at run time.

A schema under ``<spec>/extensions/`` (``core/host_schemas.py``) may carry the toolkit's ``x-node`` and ``x-link``
annotations.  For a spec folder that has such schemas ``load_kind_registry(repo_root, spec_root)`` gives the toolkit's
kinds plus one file entry per extension (``extensions/<stem>.json``, step 13).  The entries are the ones
``specdev registry-generate`` would write for the same schema placed in the toolkit: the same collection of
annotations, the same lint and the same walk (``registry.annotation_scan.HostWalk``), run on the one schema store that
holds the toolkit's schemas and the host's.  Nothing is written: no kind of a host reaches
``tools/entry_key_registry.json``, and a call without a spec folder never sees one.

What is the host's alone:

- a host kind takes the role ``context`` or ``obligation-system`` and no other (a verifier is bound to evidence by its
  kind name, a record is written by a tool, the plan and the delivery kinds are the toolkit's);
- a host ``x-node`` sets neither ``step`` nor ``files``: the step is 13 and the file is the data file of the extension;
- a link that declares ``roles`` (``refines`` of a task criterion) accepts, besides its ``kinds``, the host kinds of
  those roles.  A kind of the toolkit is never added by role.

Two things the toolkit holds its own schemas to by a unit test, which no host schema passes through, are lines here
too: every entry of a ``contract`` is a property of the item that is neither its id nor a link (else an edit of the
node is never seen), and the id property is in ``required`` of the item (else an item with no id is silently no node).

A host schema may reach an annotated definition by ``$ref``: one of another host schema, or the shared list of open
items of the core schemas.  The annotated array of a toolkit STEP schema is not one of these (its nodes live in the
file of that step, and through it a host would take a role decision 3 keeps from it): a line too.

A host schema that fails the lint, or one of the rules above, stops the graph of that spec folder with one E520
that lists the lines.  So does a kind nested in itself (a group that holds groups): the kinds of a file are a tree.  A spec folder with no ``extensions`` folder costs one ``isdir`` and gets the toolkit's registry
object itself.  The spec folder is always an argument: the step gate reads a head tree and a baseline tree in one
process, and each has its own kinds.
"""
from __future__ import annotations

import copy
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from specdev_tools.core.errors import make_error
from specdev_tools.core.host_schemas import HOST_URI_PREFIX, data_file_of, schema_place_of
from specdev_tools.core.registry import SchemaRegistry, get_shared_registry
from specdev_tools.core.scope_helpers import as_dict, dict_items, str_items
from specdev_tools.core.step_paths import EXTENSION_STEP, EXTENSIONS_DIR_NAME
from specdev_tools.graph import kinds as toolkit_kinds
from specdev_tools.graph.kinds import HostKindsRefused, KindDecl, KindRegistry, KindRegistryError
from specdev_tools.graph.model import Graph, Node
from specdev_tools.graph.names import VERIFIED_BY
from specdev_tools.registry.annotation_scan import HostWalk, ScanNode, step_of_schema_file
from specdev_tools.registry.annotations import GRAPH_URI, AnnotationDecls, SchemaReader, SchemaRefs, collect_annotations, lint_annotations

HOST_ROLES = ("context", "obligation-system")
"""The roles a kind of an extension may take."""
HOST_REFUSED_KEYS = ("step", "files")
"""The ``x-node`` keys a kind of an extension may not set."""
_OWNER = f"step:{EXTENSION_STEP}"
_CACHE_LIMIT = 8
_MAX_DEPTH = 32
"""How deep ``allOf`` is followed for ``required``: a schema may refer to itself."""
"""Spec folders with extension kinds remembered at once: a step gate holds two (head and baseline), a test session many."""


@dataclass(frozen=True)
class HostEntries:
    """What the extension schemas of one spec folder declare.

    ``files`` maps the data file of each extension that declares a node (``extensions/ext_01_database.json``) to its
    registry entries, as the generator writes them; ``roles`` maps each kind a host schema declares to its role.  A kind
    of the toolkit that a host schema reaches by ``$ref`` (an ambiguity item) is in ``files`` and not in ``roles``.
    """

    files: Mapping[str, list[dict[str, Any]]] = field(default_factory=dict)
    roles: Mapping[str, str] = field(default_factory=dict)


# (realpath of the toolkit's registry file, realpath of the spec folder) ->
#   (the toolkit's kind registry, the schema registry with the host schemas, the overlaid registry or the error that refuses it)
_CACHE: dict[tuple[str, str], tuple[KindRegistry, SchemaRegistry, KindRegistry | KindRegistryError]] = {}


def clear_host_kind_cache() -> None:
    """Forget every overlaid registry (a test that rewrites a host schema inside one mtime tick calls this)."""
    _CACHE.clear()


def _host_uris(registry: SchemaRegistry) -> list[str]:
    """The URIs of *registry* that are extension schemas of a host, in file-name order (no schema of the toolkit has that form)."""
    return [uri for uri in registry.map if schema_place_of(uri) is not None]


def _role_issues(decls: AnnotationDecls, uris: Iterable[str]) -> list[str]:
    """The lines for what a host ``x-node`` may not declare: a role that is not a host's, ``top_of_graph``, ``step``, ``files``."""
    wanted = set(uris)
    allowed = " and ".join(HOST_ROLES)
    issues: list[str] = []
    for node in decls.nodes:
        if node.uri not in wanted or not isinstance(node.value, dict):
            continue
        where = f"{node.schema_file} {node.path}"
        role = node.value.get("role")
        if isinstance(role, str) and role not in HOST_ROLES:
            issues.append(f"{where}: an extension kind may not take the role '{role}'; the roles of an extension kind are {allowed}")
        if "top_of_graph" in node.value:
            issues.append(f"{where}: an extension kind may not set 'top_of_graph'; the roles of an extension kind are {allowed}")
        for key in HOST_REFUSED_KEYS:
            if key in node.value:
                issues.append(
                    f"{where}: an extension kind may not set '{key}': its step is {EXTENSION_STEP} and its nodes are in the data file of the extension"
                )
    return issues


def _required_of(reader: SchemaReader, node: Any, uri: str, depth: int = 0) -> set[str]:
    """The names *node* requires, through ``$ref`` and ``allOf`` (as ``SchemaReader.properties`` reads the properties)."""
    node, uri = reader.follow(node, uri)
    if not isinstance(node, dict) or depth > _MAX_DEPTH:
        return set()
    found = set(str_items(node.get("required")))
    for branch in node.get("allOf") or []:
        found |= _required_of(reader, branch, uri, depth + 1)
    return found


def _item_issues(decls: AnnotationDecls, uris: Iterable[str], reader: SchemaReader) -> list[str]:
    """The lines for a host ``x-node`` whose item does not bear out its ``contract`` or its ``id``.

    What ``tests/unit/schema/test_graph_annotations_real.py`` asserts of the toolkit's own schemas, and that the id is required.
    A kind whose shape the lint already refuses (no item schema) adds nothing here.
    """
    wanted = set(uris)
    issues: list[str] = []
    for node in decls.nodes:
        if node.uri not in wanted or not isinstance(node.value, dict):
            continue
        keyed = bool(node.value.get("map_keyed"))
        item, item_uri = reader.get(node.container, node.uri, "additionalProperties" if keyed else "items")
        if not isinstance(item, dict):
            continue
        where, kind, id_name = f"{node.schema_file} {node.path}", node.value.get("kind"), node.value.get("id")
        properties = reader.properties(item, item_uri)
        links = {name for name, (sub, sub_uri) in properties.items() if reader.get(sub, sub_uri, "x-link")[0] is not None}
        for entry in str_items(node.value.get("contract")):
            if entry not in properties:
                issues.append(f"{where}: the contract of the extension kind '{kind}' names '{entry}', which is no property of its item; an edit of a node is seen through its contract fields")
            elif entry == id_name:
                issues.append(f"{where}: the contract of the extension kind '{kind}' names its id property '{entry}'; the id is not part of the text of a node")
            elif entry in links:
                issues.append(f"{where}: the contract of the extension kind '{kind}' names the link field '{entry}'; a link is accepted on its own and is not part of the text of a node")
        if not keyed and isinstance(id_name, str) and id_name in properties and id_name not in _required_of(reader, item, item_uri):
            issues.append(
                f"{where}: the id property '{id_name}' of the extension kind '{kind}' is not in `required` of its item; "
                f"an item with no '{id_name}' would be no node and no check would say so: add it to `required`"
            )
    return issues


def _borrowed_issues(decls: AnnotationDecls, schema_file: str, found: Iterable[ScanNode]) -> list[str]:
    """The lines for the kinds of a toolkit step schema that the host schema *schema_file* reaches by ``$ref`` (*found*: what the walk recorded for it, nested too)."""
    sites = {id(node.value): node for node in decls.nodes}
    issues: list[str] = []
    for scanned in found:
        site = sites.get(id(scanned.value))
        step = step_of_schema_file(os.path.basename(site.schema_file)) if site is not None else None
        if site is not None and step is not None:
            issues.append(
                f"{schema_file} {scanned.path}: reaches by $ref the x-node of the toolkit kind '{scanned.kind}' ({site.schema_file} {site.path}); "
                f"the nodes of kind {scanned.kind} live in the file of step {step}, and an extension file holds the kinds an extension schema declares: "
                "declare a kind of the extension for these items, or name the nodes of the toolkit by id in a link field"
            )
        issues.extend(_borrowed_issues(decls, schema_file, scanned.nested))
    return issues


def _nesting_issues(decls: AnnotationDecls, values: Iterable[Any]) -> list[str]:
    """The lines for the ``x-node`` *values* the walk reached again from inside their own items."""
    sites = {id(node.value): node for node in decls.nodes}
    return [
        f"{sites[id(value)].schema_file} {sites[id(value)].path}: the extension kind '{value.get('kind')}' is nested in itself (its items reach this x-node again); "
        "the kinds of a file form a tree: give the inner level a kind of its own, or keep the x-node off the array that repeats"
        for value in values
        if id(value) in sites
    ]


def _refused(issues: list[str]) -> HostKindsRefused:
    """The one E520 of a spec folder whose extension schemas declare what the graph cannot use, owned by step 13."""
    lines = "\n".join(f"  {issue}" for issue in issues)
    message = (
        f"the extension schemas of the spec folder ({EXTENSIONS_DIR_NAME}/*.schema.json) declare node kinds or links the graph cannot use; "
        f"no kind of an extension is loaded and the graph of this spec is not built until each line is corrected in the schema it names:\n{lines}"
    )
    return HostKindsRefused(make_error("E520", message, file=EXTENSIONS_DIR_NAME, owner=_OWNER), issues)


def _schemas_with_host_kinds(repo_root: str, spec_root: str) -> SchemaRegistry | None:
    """The schema registry of the toolkit and the extension schemas of *spec_root*; ``None`` when the folder adds no schema that can declare a kind.

    One ``isdir`` for a spec folder with no ``extensions`` folder.  The registry is the same object from call to call
    until a schema file of the toolkit or of the host changes (``core.registry.get_shared_registry``).
    """
    if not os.path.isdir(os.path.join(spec_root, EXTENSIONS_DIR_NAME)):
        return None
    try:
        schemas = get_shared_registry(os.path.abspath(repo_root), spec_root)
    except (OSError, ValueError):  # a toolkit whose schema registry cannot be read has no schema to read a host schema with
        return None
    return schemas if GRAPH_URI in schemas.store and _host_uris(schemas) else None


def _entry_kinds(entries: Iterable[Mapping[str, Any]]) -> set[str]:
    """The kind of every entry of *entries*, nested ones too."""
    found: set[str] = set()
    for entry in entries:
        found.add(str(entry.get("kind")))
        found |= _entry_kinds(dict_items(entry.get("nested")))
    return found


def host_entries(repo_root: str, spec_root: str) -> HostEntries:
    """The registry entries and the kinds of the extension schemas of *spec_root*; empty when it has no accepted schema.

    Raises:
        KindRegistryError: E520, owned by step 13, when a host schema fails the annotation lint or declares a role,
            ``top_of_graph``, ``step`` or ``files`` a host may not; the message lists every line.
    """
    if _schemas_with_host_kinds(repo_root, spec_root) is None:
        return HostEntries()
    return _entries_of(collect_annotations(repo_root, spec_root))


def _entries_of(decls: AnnotationDecls) -> HostEntries:
    """The entries of the host schemas among *decls* (the annotations of the toolkit's schemas and the host's together)."""
    registry = decls.registry
    uris = _host_uris(registry) if registry is not None and decls.graph_present else []
    if registry is None or not uris:
        return HostEntries()
    refs = SchemaRefs(registry)
    issues = [*lint_annotations(decls), *_role_issues(decls, uris), *_item_issues(decls, uris, SchemaReader(refs))]
    if issues:
        raise _refused(issues)
    files: dict[str, list[dict[str, Any]]] = {}
    for uri in uris:
        walk = HostWalk(refs, SchemaReader(refs))
        found = walk.run(uri)
        entries = [node.to_entry() for node in found]
        issues.extend(_nesting_issues(decls, walk.nested_in_itself))
        issues.extend(_borrowed_issues(decls, refs.file_of(uri), found))
        if entries:
            files[data_file_of(uri[len(HOST_URI_PREFIX):])] = entries
    if issues:
        raise _refused(issues)
    reached = _entry_kinds(entry for entries in files.values() for entry in entries)
    roles = {node.kind: node.value["role"] for node in decls.nodes if node.uri in uris and node.kind in reached}
    return HostEntries(files, roles)


def _open_by_role(entries: Iterable[dict[str, Any]], roles: Mapping[str, str]) -> None:
    """Add to each link of *entries* (nested entries too) that declares ``roles`` the host kinds of those roles, sorted, after its own kinds."""
    for entry in entries:
        for link in dict_items(entry.get("links")):
            named, kinds = link.get("roles"), link.get("kinds")
            if isinstance(named, list) and isinstance(kinds, list):
                link["kinds"] = [*kinds, *sorted(kind for kind, role in roles.items() if role in named and kind not in kinds)]
        _open_by_role(dict_items(entry.get("nested")), roles)


def overlay(document: Mapping[str, Any], host: HostEntries) -> dict[str, Any]:
    """The registry *document* of the toolkit with the files of *host* added under step 13; *document* is not changed.

    The host files come after the toolkit's, in file-name order.  Every link that declares ``roles``, in a toolkit entry
    or a host one, gains the host kinds of those roles.
    """
    result = copy.deepcopy(dict(document))
    registry = dict(as_dict(result.get("registry")))
    for file_key in sorted(host.files):
        registry[file_key] = {"step": EXTENSION_STEP, "arrays": copy.deepcopy(host.files[file_key])}
    result["registry"] = registry
    for value in registry.values():
        _open_by_role(dict_items(as_dict(value).get("arrays")), host.roles)
    return result


def host_kinds(registry: KindRegistry) -> tuple[KindDecl, ...]:
    """The declarations of *registry* that an extension schema made (nested ones too), in registry order; empty for the toolkit's own registry."""
    found: list[KindDecl] = []

    def add(decls: Iterable[KindDecl]) -> None:
        for decl in decls:
            if decl.host:
                found.append(decl)
            add(decl.nested)

    for file in registry.files:
        add(file.kinds)
    return tuple(found)


def load_kind_registry(repo_root: str, spec_root: str | None = None) -> KindRegistry:
    """The kinds of the toolkit at *repo_root*, with the kinds the extension schemas of the spec folder *spec_root* declare.

    Without *spec_root*, and for a spec folder whose ``extensions`` folder holds no accepted schema that declares a node,
    this is the toolkit's registry: the very object ``graph.kinds.load_kind_registry(repo_root)`` returns.  Otherwise it is one
    registry per ``(repo_root, spec_root)``, built again when the toolkit's registry or a host schema file changed.

    Raises:
        KindRegistryError: E520 when the toolkit's registry is missing or unreadable, or (owned by step 13) when an
            extension schema of *spec_root* declares a kind or a link the graph cannot use.
    """
    base = toolkit_kinds.load_kind_registry(repo_root)
    schemas = _schemas_with_host_kinds(repo_root, spec_root) if spec_root is not None else None
    if schemas is None or spec_root is None:
        return base
    path = toolkit_kinds.registry_path(repo_root)
    key = (os.path.realpath(path), os.path.realpath(spec_root))
    cached = _CACHE.get(key)
    if cached is None or cached[0] is not base or cached[1] is not schemas:
        cached = (base, schemas, _overlaid(base, path, repo_root, spec_root))
        _CACHE.pop(key, None)
        while len(_CACHE) >= _CACHE_LIMIT:
            del _CACHE[next(iter(_CACHE))]
        _CACHE[key] = cached
    if isinstance(cached[2], KindRegistryError):
        raise cached[2]
    return cached[2]


def require_host_kinds(repo_root: str, spec_root: str) -> None:
    """Raise the refusal of the extension schemas of *spec_root*, and nothing else (a toolkit that cannot be read is said by the checks).

    For a reader that goes on without the graph: on an old tree a refused schema means "this tree is not read", not one finding among others.
    """
    try:
        load_kind_registry(repo_root, spec_root)
    except HostKindsRefused:
        raise
    except KindRegistryError:
        return


def _overlaid(base: KindRegistry, path: str, repo_root: str, spec_root: str) -> KindRegistry | KindRegistryError:
    """The toolkit's registry *base* (read from *path*) with the host kinds of *spec_root*, or the error that refuses its schemas (remembered like a result).

    Extension schemas that declare no node add nothing: the answer is *base* itself.
    """
    try:
        host = _entries_of(collect_annotations(repo_root, spec_root))
    except KindRegistryError as error:
        return error
    if not host.files:
        return base
    return toolkit_kinds.parse_registry(overlay(toolkit_kinds.read_registry_document(path), host), frozenset(host.roles))


NAMED_IN_LINK = "link"
DECLARED_IN_SCHEMA = "schema"


def verifier_naming(graph: Graph, node: Node) -> str | None:
    """How a node of an extension kind is given a verifier, for the advice of a finding; ``None`` for a toolkit kind, which a fixture or a job names.

    ``NAMED_IN_LINK``: its kind declares ``verified_by`` and the node names its verifier there.  ``DECLARED_IN_SCHEMA``:
    its kind declares no such link, so the schema of the extension must declare one first.  No rule reads this: a
    verifier counts through the link alone, whatever the kind.
    """
    decl = graph.decls.get(node.kind)
    if decl is None or not decl.host:
        return None
    return NAMED_IN_LINK if any(link.field == VERIFIED_BY for link in decl.links) else DECLARED_IN_SCHEMA
