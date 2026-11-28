from __future__ import annotations

import copy, json, os, threading
from collections.abc import Mapping
from typing import Any, Callable, Optional

from jsonschema import Draft202012Validator
from referencing import Registry as _ReferencingRegistry, Resource as _Resource
from referencing.jsonschema import DRAFT202012 as _DRAFT202012

from .host_schemas import HostSchema, HostSchemas, clear_host_schema_cache, find_host_schemas, missing_schema_text

def _resolve_rel(repo_root: str, rel: str) -> Optional[str]:
    for base in [repo_root, os.getcwd()]:
        cand = os.path.join(base, rel)
        if os.path.exists(cand):
            return cand
    return None


class SchemaRegistry:
    spec_root: Optional[str] = None
    """The spec folder (a realpath) whose extension schemas this registry also holds; ``None`` for the toolkit's schemas alone."""
    _host_uris: frozenset[str] = frozenset()

    def __init__(self, repo_root: str):
        self.repo_root = os.path.abspath(repo_root)
        registry_path = os.path.join(self.repo_root, "tools", "schema_registry.json")
        if not os.path.exists(registry_path):
            # fallback: allow running tools package standalone if copied elsewhere
            registry_path = os.path.join(self.repo_root, "schema_registry.json")
        with open(registry_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        self.map = _validate_registry_map(loaded)
        self.store: dict[str, dict] = {}
        self._crawled_registry: _ReferencingRegistry | None = None
        self._preload_store()

    def _preload_store(self) -> None:
        for uri, rel in self.map.items():
            path = self._resolve_path(rel)
            if not path:
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.store[uri] = json.load(f)
            except (OSError, json.JSONDecodeError):
                pass

    def _resolve_path(self, rel: str) -> Optional[str]:
        return _resolve_rel(self.repo_root, rel)

    def resolve(self, uri: str) -> Optional[str]:
        rel = self.map.get(uri)
        if not rel:
            return None
        return self._resolve_path(rel) or rel

    def with_host_schemas(self, spec_root: str, schemas: Mapping[str, HostSchema]) -> "SchemaRegistry":
        """A registry of this toolkit plus the accepted extension *schemas* of the spec folder *spec_root* (``core/host_schemas.py``).

        The toolkit's schemas are shared with this registry (the same parsed documents; no file is read again), so a
        host schema's ``$ref`` to ``vc:core:*`` resolves in one store.  The result has its own crawled registry and
        its ``spec_root`` says whose schemas it holds.  *schemas* never holds a URI of the toolkit.
        """
        derived = copy.copy(self)
        derived.map = {**self.map, **{uri: found.path for uri, found in schemas.items()}}
        derived.store = {**self.store, **{uri: found.schema for uri, found in schemas.items()}}
        derived._crawled_registry = None
        derived._host_uris = frozenset(schemas)
        derived.spec_root = os.path.realpath(spec_root)
        return derived

    def uri_exists(self, uri: str) -> bool:
        """Check whether a URI is registered and its schema file exists on disk."""
        path = self.resolve(uri)
        return path is not None and os.path.exists(path)

    def load_with_fallback(self, uri: str, default: dict | None = None) -> dict:
        """Load a schema by URI, returning *default* if the URI is unregistered or missing.

        Raises ``FileNotFoundError`` only when *default* is ``None``.
        """
        try:
            return self.load(uri)
        except FileNotFoundError:
            if default is not None:
                return default
            raise

    def to_referencing_registry(self) -> _ReferencingRegistry:
        """Build a ``referencing.Registry`` from the pre-loaded schema store.

        This consolidates the pattern previously duplicated across validate,
        canonical lint, canonical autofix, and prompt-schema sync modules.

        The crawled registry is built once per ``SchemaRegistry`` instance and
        reused (``referencing`` otherwise re-crawls the whole store on the
        first lookup of each new registry).  A failed build is not cached.
        """
        cached = self._crawled_registry
        if cached is not None:
            return cached
        # A host schema is read as draft 2020-12 whatever its own ``$schema`` says (it was checked as one), so a
        # host schema without the keyword cannot stop the crawl for every file of the spec.
        store = {
            uri: _DRAFT202012.create_resource(schema) if uri in self._host_uris else _Resource.from_contents(schema)
            for uri, schema in self.store.items()
        }
        built = _ReferencingRegistry().with_resources(store.items()).crawl()
        self._crawled_registry = built
        return built

    def load(self, uri: str) -> dict:
        """Return the schema for *uri*.

        Served from the pre-loaded ``self.store`` when present (the same dict
        object each call; callers must treat it as read-only).  Falls back to
        reading the file so missing/malformed schemas raise as before.
        """
        cached = self.store.get(uri)
        if cached is not None:
            return cached
        path = self.resolve(uri)
        if not path or not os.path.exists(path):
            raise FileNotFoundError(
                missing_schema_text(uri)
                or f"Schema not found for {uri}: expected {path!r}. "
                "Check tools/schema_registry.json for the correct URI mapping "
                "and verify --repo-root points to the devspec_toolkit directory."
            )
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


# ---------------------------------------------------------------------------
# Shared (memoised) registry and validator caches
# ---------------------------------------------------------------------------

_SHARED_LOCK = threading.RLock()
# realpath(repo_root) -> (signature, SchemaRegistry)
_SHARED_REGISTRIES: dict[str, tuple[tuple, SchemaRegistry]] = {}
# (realpath(repo_root), realpath(spec_root)) -> (toolkit registry it extends, registry with the host schemas of that spec root)
_HOST_REGISTRIES: dict[tuple[str, str], tuple[SchemaRegistry, SchemaRegistry]] = {}
_HOST_REGISTRY_LIMIT = 8
"""Spec roots with extension schemas remembered at once: a step gate holds two (head and baseline), a test session many."""
# (realpath(repo_root), registry.spec_root, schema_uri) -> (SchemaRegistry it was built from, validator)
_VALIDATOR_CACHE: dict[tuple[str, Optional[str], str], tuple[SchemaRegistry, Any]] = {}


def _stat_sig(path: Optional[str]) -> Optional[tuple[int, int]]:
    if not path:
        return None
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


def _map_path_for(repo_root: str) -> str:
    map_path = os.path.join(repo_root, "tools", "schema_registry.json")
    if not os.path.exists(map_path):
        map_path = os.path.join(repo_root, "schema_registry.json")
    return map_path


def _compute_signature(repo_root: str, schema_map: dict[str, str]) -> tuple:
    map_path = _map_path_for(repo_root)
    parts: list[Any] = [(map_path, _stat_sig(map_path))]
    for uri, rel in schema_map.items():
        path = _resolve_rel(repo_root, rel)
        parts.append((uri, path, _stat_sig(path)))
    return tuple(parts)


def _registry_signature(reg: SchemaRegistry) -> tuple:
    """Cheap change signature: mtime_ns + size of the registry map and each mapped schema file."""
    return _compute_signature(reg.repo_root, reg.map)


def _signature_before_load(repo_root: str) -> Optional[tuple]:
    """Signature of *repo_root* taken before a ``SchemaRegistry`` is built (``None`` if the map is unreadable)."""
    root = os.path.abspath(repo_root)
    try:
        with open(_map_path_for(root), "r", encoding="utf-8") as f:
            schema_map = _validate_registry_map(json.load(f))
    except (OSError, ValueError):
        return None
    return _compute_signature(root, schema_map)


def get_shared_registry(repo_root: str, spec_root: Optional[str] = None) -> SchemaRegistry:
    """Return a memoised ``SchemaRegistry`` for *repo_root*, with the extension schemas of *spec_root* when it has any.

    Keyed by ``realpath``; a fresh instance is built when the signature of the
    registry map or any mapped schema file changed.  The signature is taken
    before the load and the instance is cached only if it is unchanged after
    it, so a file edited mid-load is never cached under its new signature with
    the old content.  Constructor errors propagate unchanged and are never
    cached.

    *spec_root* is the spec folder of the document being validated.  Without it, or when that folder has no accepted
    schema under ``extensions/``, the result is the toolkit's registry itself: the very object a call without
    *spec_root* returns.  Otherwise it is one registry per ``(repo_root, spec_root)`` that holds both (see
    ``SchemaRegistry.with_host_schemas``), built again when a host schema file or the toolkit's registry changed.
    Two spec roots in one process (the head and the baseline of the step gate) each keep their own.
    """
    key = os.path.realpath(repo_root)
    with _SHARED_LOCK:
        base = _toolkit_registry(key, repo_root)
        if spec_root is None:
            return base
        found = find_host_schemas(spec_root, base.map)
        if not found.accepted:
            return base
        host_key = (key, os.path.realpath(spec_root))
        entry = _HOST_REGISTRIES.get(host_key)
        if entry is not None and entry[0] is base and _holds(entry[1], found):
            return entry[1]
        reg = base.with_host_schemas(spec_root, found.accepted)
        _remember_host_registry(host_key, base, reg)
        return reg


def _toolkit_registry(key: str, repo_root: str) -> SchemaRegistry:
    """The memoised registry of the toolkit's own schemas (the caller holds ``_SHARED_LOCK``)."""
    entry = _SHARED_REGISTRIES.get(key)
    if entry is not None:
        sig, reg = entry
        if _registry_signature(reg) == sig:
            return reg
    before = _signature_before_load(repo_root)
    reg = SchemaRegistry(repo_root)
    if before is not None and _registry_signature(reg) == before:
        _SHARED_REGISTRIES[key] = (before, reg)
    else:
        _SHARED_REGISTRIES.pop(key, None)
    return reg


def _holds(reg: SchemaRegistry, found: HostSchemas) -> bool:
    """Whether *reg* holds exactly the host schemas *found*, as the very documents the last read of the folder gave.

    ``find_host_schemas`` gives the same parsed document for a file until the file changes, so identity is "unchanged".
    """
    return set(found.accepted) == reg._host_uris and all(reg.store.get(uri) is item.schema for uri, item in found.accepted.items())


def _remember_host_registry(host_key: tuple[str, str], base: SchemaRegistry, reg: SchemaRegistry) -> None:
    """Cache *reg* for *host_key*; the oldest spec root beyond ``_HOST_REGISTRY_LIMIT`` is dropped with its validators."""
    _HOST_REGISTRIES.pop(host_key, None)
    while len(_HOST_REGISTRIES) >= _HOST_REGISTRY_LIMIT:
        dropped = next(iter(_HOST_REGISTRIES))
        del _HOST_REGISTRIES[dropped]
        for cache_key in [k for k in _VALIDATOR_CACHE if k[:2] == dropped]:
            del _VALIDATOR_CACHE[cache_key]
    _HOST_REGISTRIES[host_key] = (base, reg)


def get_cached_validator(
    repo_root: str,
    schema_uri: str,
    registry: SchemaRegistry,
    factory: Callable[[], Any],
) -> Any:
    """Return the validator cached for ``(repo_root, registry.spec_root, schema_uri)``, building it with *factory* on a miss.

    A cached validator is reused only while it was built from the same
    ``SchemaRegistry`` instance (so a rebuilt shared registry invalidates it).
    The spec root is part of the key so that the registries of two spec roots
    (head and baseline), and the toolkit's own, do not evict each other's validators.
    The caller supplies *factory* so it constructs ``Draft202012Validator``
    from its own module namespace.  A failing factory caches nothing.
    """
    key = (os.path.realpath(repo_root), getattr(registry, "spec_root", None), schema_uri)
    with _SHARED_LOCK:
        entry = _VALIDATOR_CACHE.get(key)
        if entry is not None and entry[0] is registry:
            return entry[1]
        validator = factory()
        _VALIDATOR_CACHE[key] = (registry, validator)
        return validator


def get_schema_validator(registry: SchemaRegistry, schema_uri: str, schema: dict[str, Any]) -> Draft202012Validator:
    """Return the cached ``Draft202012Validator`` for *schema_uri*, built from *schema* and *registry* on a miss.

    Cached per ``(registry.repo_root, registry.spec_root, schema_uri)`` as ``get_cached_validator`` does.  Raises whatever
    ``to_referencing_registry`` or the validator constructor raises (nothing is cached then).
    """
    return get_cached_validator(
        registry.repo_root,
        schema_uri,
        registry,
        lambda: Draft202012Validator(
            schema,
            registry=registry.to_referencing_registry(),
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        ),
    )


def clear_shared_caches() -> None:
    """Clear the shared-registry maps (toolkit and host), the validator cache and the host schema scans (crawled registries live on the instances)."""
    with _SHARED_LOCK:
        _SHARED_REGISTRIES.clear()
        _HOST_REGISTRIES.clear()
        _VALIDATOR_CACHE.clear()
        clear_host_schema_cache()


def derive_allowed_upstream(step_id: str, steps: list) -> list:
    """Return all steps preceding step_id in the ordered steps list.

    Under strict_waterfall, allowed upstream is simply all steps before
    the given step in the ordered sequence.

    Args:
        step_id: The step to find allowed upstream steps for
        steps: The ordered list of all step IDs

    Returns:
        List of step IDs that precede step_id, or empty list if not found
    """
    try:
        idx = steps.index(step_id)
        return steps[:idx]
    except ValueError:
        return []


def _validate_registry_map(raw: object) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise ValueError(
            f"schema_registry.json must be a JSON object mapping schema URI -> relative path; got {type(raw).__name__}"
        )
    validated: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError(
                "schema_registry.json contains non-string key/value; "
                f"got key={type(key).__name__}, value={type(value).__name__}"
            )
        validated[key] = value
    return validated
