from __future__ import annotations

import json, os
from typing import Optional

class SchemaRegistry:
    def __init__(self, repo_root: str):
        self.repo_root = os.path.abspath(repo_root)
        registry_path = os.path.join(self.repo_root, "tools", "schema_registry.json")
        if not os.path.exists(registry_path):
            # fallback: allow running tools package standalone if copied elsewhere
            registry_path = os.path.join(self.repo_root, "schema_registry.json")
        with open(registry_path, "r", encoding="utf-8") as f:
            self.map = json.load(f)
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
            except Exception:
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

    def load(self, uri: str) -> dict:
        path = self.resolve(uri)
        if not path or not os.path.exists(path):
            raise FileNotFoundError(f"Schema not found for {uri}: expected {path!r}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
