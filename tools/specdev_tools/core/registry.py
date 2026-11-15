from __future__ import annotations

import json, os, threading
from typing import Any, Callable, Optional

from referencing import Registry as _ReferencingRegistry, Resource as _Resource

def _resolve_rel(repo_root: str, rel: str) -> Optional[str]:
    for base in [repo_root, os.getcwd()]:
        cand = os.path.join(base, rel)
        if os.path.exists(cand):
            return cand
    return None


class SchemaRegistry:
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
        store = {
            uri: _Resource.from_contents(schema)
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
                f"Schema not found for {uri}: expected {path!r}. "
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
# (realpath(repo_root), schema_uri) -> (SchemaRegistry it was built from, validator)
_VALIDATOR_CACHE: dict[tuple[str, str], tuple[SchemaRegistry, Any]] = {}


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


def get_shared_registry(repo_root: str) -> SchemaRegistry:
    """Return a memoised ``SchemaRegistry`` for *repo_root*.

    Keyed by ``realpath``; a fresh instance is built when the signature of the
    registry map or any mapped schema file changed.  The signature is taken
    before the load and the instance is cached only if it is unchanged after
    it, so a file edited mid-load is never cached under its new signature with
    the old content.  Constructor errors propagate unchanged and are never
    cached.
    """
    key = os.path.realpath(repo_root)
    with _SHARED_LOCK:
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


def get_cached_validator(
    repo_root: str,
    schema_uri: str,
    registry: SchemaRegistry,
    factory: Callable[[], Any],
) -> Any:
    """Return the validator cached for ``(repo_root, schema_uri)``, building it with *factory* on a miss.

    A cached validator is reused only while it was built from the same
    ``SchemaRegistry`` instance (so a rebuilt shared registry invalidates it).
    The caller supplies *factory* so it constructs ``Draft202012Validator``
    from its own module namespace.  A failing factory caches nothing.
    """
    key = (os.path.realpath(repo_root), schema_uri)
    with _SHARED_LOCK:
        entry = _VALIDATOR_CACHE.get(key)
        if entry is not None and entry[0] is registry:
            return entry[1]
        validator = factory()
        _VALIDATOR_CACHE[key] = (registry, validator)
        return validator


def clear_shared_caches() -> None:
    """Clear the shared-registry map, and the validator cache (crawled registries live on the instances)."""
    with _SHARED_LOCK:
        _SHARED_REGISTRIES.clear()
        _VALIDATOR_CACHE.clear()


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
