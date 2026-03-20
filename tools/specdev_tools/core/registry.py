from __future__ import annotations

import json, os
from typing import Optional

from referencing import Registry as _ReferencingRegistry, Resource as _Resource

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
        for base in [self.repo_root, os.getcwd()]:
            cand = os.path.join(base, rel)
            if os.path.exists(cand):
                return cand
        return None

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
        """
        store = {
            uri: _Resource.from_contents(schema)
            for uri, schema in self.store.items()
        }
        return _ReferencingRegistry().with_resources(store.items())

    def load(self, uri: str) -> dict:
        path = self.resolve(uri)
        if not path or not os.path.exists(path):
            raise FileNotFoundError(
                f"Schema not found for {uri}: expected {path!r}. "
                "Check tools/schema_registry.json for the correct URI mapping "
                "and verify --repo-root points to the devspec_toolkit directory."
            )
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


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
