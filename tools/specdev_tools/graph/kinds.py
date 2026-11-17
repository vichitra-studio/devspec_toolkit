"""Kind adapter: the one reader of the M1 entry-key registry for the spec graph.

``load_kind_registry`` turns ``tools/entry_key_registry.json`` into frozen declarations (``KindDecl``, ``LinkDecl``)
that ``graph.build`` walks.  Nothing else in the graph package parses the registry JSON.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from specdev_tools.core.entry_key_registry import is_glob_key
from specdev_tools.core.errors import FindingError, SpecError, make_error
from specdev_tools.core.scope_helpers import as_dict, as_str, dict_items, str_items

SEED_KIND = "seed"
SEED_STEP = "seed"
RECORD_ROLE = "record"
EXTRAS_STEP = "extras"
ANY_KIND = "*"
_REGISTRY_RELATIVE = os.path.join("tools", "entry_key_registry.json")


def has_lifecycle(kind: str, role: str | None) -> bool:
    """False for a record-role kind and for the seed kind: their nodes have no lifecycle and always read ``active``."""
    return role != RECORD_ROLE and kind != SEED_KIND


class KindRegistryError(FindingError):
    """The registry cannot be read; ``error`` is the E520 ``SpecError`` that reports it."""


@dataclass(frozen=True)
class LinkDecl:
    """One ``x-link`` field of a kind: ``kinds`` holds concrete kind names (``"*"`` already expanded)."""

    field: str
    kinds: tuple[str, ...]
    required: bool
    built: bool
    same_step_kinds: tuple[str, ...]

    def accepts(self, kind: str) -> bool:
        """True when a node of *kind* may be the target of this link."""
        return kind in self.kinds


@dataclass(frozen=True)
class KindDecl:
    """One declared collection of nodes.

    ``array_path`` is relative to the parent item for a nested kind and to the document otherwise; ``id_field`` is
    ``None`` when ``map_keyed`` (the map key is the id).
    """

    kind: str
    array_path: str
    id_field: str | None
    map_keyed: bool
    role: str | None
    contract: tuple[str, ...]
    links: tuple[LinkDecl, ...]
    nested: tuple[KindDecl, ...] = ()


@dataclass(frozen=True)
class FileDecl:
    """The kinds one registry file key (a file name or a glob) holds, and the step they belong to."""

    pattern: str
    step: str
    kinds: tuple[KindDecl, ...]

    @property
    def is_glob(self) -> bool:
        return is_glob_key(self.pattern)


@dataclass(frozen=True)
class KindRegistry:
    """Every declared kind: the files in registry order, the external kinds (``seed``) and all kind names."""

    files: tuple[FileDecl, ...]
    external: tuple[FileDecl, ...]
    kind_names: tuple[str, ...]


def _expand_kinds(raw: Any, all_kinds: tuple[str, ...]) -> tuple[str, ...]:
    """Concrete target kinds of a link: the string ``"*"`` means every declared kind."""
    if raw == ANY_KIND:
        return all_kinds
    return tuple(str_items(raw))


def _link_decl(raw: dict[str, Any], all_kinds: tuple[str, ...]) -> LinkDecl:
    return LinkDecl(
        field=as_str(raw.get("field")),
        kinds=_expand_kinds(raw.get("kinds"), all_kinds),
        required=raw.get("required") is True,
        built=raw.get("built") is True,
        same_step_kinds=tuple(str_items(raw.get("same_step_kinds"))),
    )


def _kind_decl(raw: dict[str, Any], all_kinds: tuple[str, ...]) -> KindDecl:
    map_keyed = raw.get("map_keyed") is True
    role = raw.get("role")
    return KindDecl(
        kind=as_str(raw.get("kind")),
        array_path=as_str(raw.get("array_path")),
        id_field=None if map_keyed else as_str(raw.get("id_field")),
        map_keyed=map_keyed,
        role=role if isinstance(role, str) else None,
        contract=tuple(str_items(raw.get("contract"))),
        links=tuple(_link_decl(link, all_kinds) for link in dict_items(raw.get("links"))),
        nested=tuple(_kind_decl(child, all_kinds) for child in dict_items(raw.get("nested"))),
    )


def _kind_names(raw_entries: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for entry in raw_entries:
        names.append(as_str(entry.get("kind")))
        names.extend(_kind_names(dict_items(entry.get("nested"))))
    return names


def _registry_error(path: str, reason: str) -> KindRegistryError:
    message = (
        f"entry-key registry {path} is {reason}; run 'specdev registry-generate --repo-root <toolkit>' to regenerate it"
    )
    return KindRegistryError(make_error("E520", message, path))


def _read_registry(path: str) -> dict[str, Any]:
    """The parsed registry document; raises ``KindRegistryError`` (E520) when it is missing, unreadable or not an object."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError:
        raise _registry_error(path, "missing") from None
    except (OSError, ValueError, RecursionError):
        raise _registry_error(path, "unreadable") from None
    if not isinstance(raw, dict):
        raise _registry_error(path, "not a JSON object")
    return raw


def _parse(raw: dict[str, Any]) -> KindRegistry:
    registry = as_dict(raw.get("registry"))
    external = dict_items(raw.get("external_kinds"))
    entries = [e for value in registry.values() for e in dict_items(as_dict(value).get("arrays"))]
    names = sorted({*_kind_names(entries), *(as_str(e.get("kind")) for e in external)} - {""})
    all_kinds = tuple(names)
    files = tuple(
        FileDecl(
            pattern=key,
            step=as_str(as_dict(value).get("step")),
            kinds=tuple(_kind_decl(e, all_kinds) for e in dict_items(as_dict(value).get("arrays"))),
        )
        for key, value in registry.items()
        if not as_dict(value).get("_special")
    )
    externals = tuple(
        FileDecl(
            pattern=as_str(e.get("source_file")),
            step=SEED_STEP,
            kinds=(
                KindDecl(
                    kind=as_str(e.get("kind")),
                    array_path=as_str(e.get("array_path")),
                    id_field=as_str(e.get("id_field")),
                    map_keyed=False,
                    role=None,
                    contract=(),
                    links=(),
                ),
            ),
        )
        for e in external
    )
    return KindRegistry(files=files, external=externals, kind_names=all_kinds)


# Parsed registries by realpath of the toolkit root, valid while the file's mtime and size are unchanged.
_CACHE: dict[str, tuple[tuple[int, int], KindRegistry]] = {}


def load_kind_registry(repo_root: str) -> KindRegistry:
    """Read ``<repo_root>/tools/entry_key_registry.json`` into a ``KindRegistry`` (cached per file mtime and size).

    Raises:
        KindRegistryError: the file is missing, unreadable or not a JSON object; ``.error`` is the E520
            ``UNRESOLVED_INPUT`` finding.
    """
    path = os.path.join(repo_root, _REGISTRY_RELATIVE)
    try:
        stat = os.stat(path)
    except OSError:
        raise _registry_error(path, "missing") from None
    stamp = (stat.st_mtime_ns, stat.st_size)
    key = os.path.realpath(path)
    cached = _CACHE.get(key)
    if cached is not None and cached[0] == stamp:
        return cached[1]
    registry = _parse(_read_registry(path))
    _CACHE[key] = (stamp, registry)
    return registry
