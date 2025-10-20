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

    def resolve(self, uri: str) -> Optional[str]:
        rel = self.map.get(uri)
        if not rel:
            return None
        # Support both repo-root and external run where schema lives under ./schema
        for base in [self.repo_root, os.getcwd()]:
            cand = os.path.join(base, rel)
            if os.path.exists(cand):
                return cand
        return rel  # best effort

    def load(self, uri: str) -> dict:
        path = self.resolve(uri)
        if not path or not os.path.exists(path):
            raise FileNotFoundError(f"Schema not found for {uri}: expected {path!r}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
