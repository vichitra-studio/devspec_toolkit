from __future__ import annotations

import json
import os
from typing import Any

from .canonical_registry import CanonicalRegistry
from .trace_types import is_valid_trace_type


KNOWN_STAGES = {"dev", "ci", "staging", "prod"}
DEFAULT_COMMAND_PREFIXES = {
    "python", "python3", "bash", "sh", "npm", "pnpm", "yarn", "npx", "make",
    "pytest", "uv", "node", "go", "cargo", "bun", "vitest", "jest", "tsx",
    "ruff", "poetry",
}
KNOWN_UNITS = {
    "%", "percent", "ratio", "count", "ms", "s", "sec", "second", "seconds",
    "minute", "minutes", "hour", "hours", "day", "days",
    "bytes", "kb", "mb", "gb", "tb", "rps", "rpm",
}


def lint_hallucinations(spec_dir: str, repo_root: str | None = None, canon_dir: str = "canon") -> list[str]:
    errors: list[str] = []
    known_ids: set[str] = set()
    refs: list[tuple[str, str, str]] = []
    root = repo_root or spec_dir
    canon = CanonicalRegistry.load(root, canon_dir=canon_dir)
    known_command_prefixes = _load_command_prefixes(root)
    for path in _iter_json(spec_dir):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            rel = os.path.relpath(path, spec_dir)
            errors.append(f"E520 UNRESOLVED_INPUT {rel} invalid_json {exc}")
            continue
        rel = os.path.relpath(path, spec_dir)
        errors.extend(_scan_node(rel, data, canon, known_command_prefixes))
        _collect_ids_and_refs(data, rel, known_ids, refs)
    for rel, p, ref_id in refs:
        if ref_id.startswith(("external:", "file:", "refs/", "cn:")):
            continue
        if ref_id not in known_ids:
            errors.append(f"E530 INVENTED_ENUM_OR_ID {rel}:{p}={ref_id}")
    return errors


def _scan_node(
    rel: str,
    node: Any,
    canon: CanonicalRegistry,
    known_command_prefixes: set[str],
    path: str = "",
) -> list[str]:
    errs: list[str] = []
    if isinstance(node, dict):
        in_trace_container = any(token in path for token in ("trace", "targets", "target_ids", "mitigations"))
        if "type" in node and "id" in node and in_trace_container:
            t = node.get("type")
            if isinstance(t, str) and not is_valid_trace_type(t):
                errs.append(f"E530 INVENTED_ENUM_OR_ID {rel}:{path}.type={t}")
        for key, value in node.items():
            p = f"{path}.{key}" if path else key
            if key in {"stage", "environment"} and isinstance(value, str) and value not in KNOWN_STAGES:
                errs.append(f"E530 INVENTED_ENUM_OR_ID {rel}:{p}={value}")
            if key in {"stages", "environments"} and isinstance(value, list):
                for idx, item in enumerate(value):
                    if isinstance(item, str) and item not in KNOWN_STAGES:
                        errs.append(f"E530 INVENTED_ENUM_OR_ID {rel}:{p}[{idx}]={item}")
            if key in {"unit", "units"}:
                if isinstance(value, str) and not _is_valid_unit(value, canon):
                    errs.append(f"E530 INVENTED_ENUM_OR_ID {rel}:{p}={value}")
                if isinstance(value, list):
                    for idx, item in enumerate(value):
                        if isinstance(item, str) and not _is_valid_unit(item, canon):
                            errs.append(f"E530 INVENTED_ENUM_OR_ID {rel}:{p}[{idx}]={item}")
            if key == "command" and isinstance(value, str):
                prefix = value.strip().split(" ", 1)[0]
                if prefix and prefix not in known_command_prefixes and not canon.resolve_alias("command", prefix):
                    errs.append(f"E530 INVENTED_ENUM_OR_ID {rel}:{p}={prefix}")
            if key == "pr_rules" and isinstance(value, list):
                allowed_pr_rules = {
                    "validate", "validate-all", "matrix", "fixtures-lint", "invariants-check",
                    "governance-check", "seed-lint", "docs-lint", "test", "build", "lint",
                    "format", "audit", "security"
                }
                for idx, item in enumerate(value):
                    if isinstance(item, str) and item not in allowed_pr_rules:
                        errs.append(f"E530 INVENTED_ENUM_OR_ID {rel}:{p}[{idx}]={item}")
            errs.extend(_scan_node(rel, value, canon, known_command_prefixes, p))
    elif isinstance(node, list):
        for idx, item in enumerate(node):
            errs.extend(_scan_node(rel, item, canon, known_command_prefixes, f"{path}[{idx}]"))
    return errs


def _iter_json(spec_dir: str):
    for root, _, files in os.walk(spec_dir):
        for fn in files:
            if fn.endswith(".json"):
                yield os.path.join(root, fn)


def _collect_ids_and_refs(obj: Any, rel: str, ids: set[str], refs: list[tuple[str, str, str]], path: str = "") -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            if k.endswith("_id") and isinstance(v, str):
                ids.add(v)
            if k == "id" and isinstance(v, str) and not _in_ref_context(path):
                ids.add(v)
            if k in {"id", "target_id"} and isinstance(v, str) and _in_ref_context(path):
                refs.append((rel, p, v))
            if k.endswith("_ref") and isinstance(v, str):
                refs.append((rel, p, v))
            if k.endswith("_refs") and isinstance(v, list):
                for idx, item in enumerate(v):
                    if isinstance(item, str):
                        refs.append((rel, f"{p}[{idx}]", item))
            if k == "requires" and isinstance(v, list):
                for idx, item in enumerate(v):
                    if isinstance(item, str):
                        refs.append((rel, f"{p}[{idx}]", item))
            _collect_ids_and_refs(v, rel, ids, refs, p)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _collect_ids_and_refs(item, rel, ids, refs, f"{path}[{i}]")


def _in_ref_context(path: str) -> bool:
    normalized = path.replace("[", ".").replace("]", "")
    segments = {seg for seg in normalized.split(".") if seg}
    return bool(segments & {"trace", "targets", "target_ids", "mitigations", "dependencies", "links", "requires"})


def _is_valid_unit(value: str, canon: CanonicalRegistry) -> bool:
    if canon.resolve_alias("unit", value):
        return True
    return " ".join(value.strip().lower().split()) in KNOWN_UNITS


def _load_command_prefixes(repo_root: str) -> set[str]:
    prefixes = set(DEFAULT_COMMAND_PREFIXES)
    cfg_path = os.path.join(repo_root, "tools", "command_prefixes.json")
    if not os.path.exists(cfg_path):
        return prefixes
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return prefixes

    values = data.get("allowed_prefixes", [])
    if not isinstance(values, list):
        return prefixes
    for item in values:
        if isinstance(item, str):
            token = item.strip().split(" ", 1)[0]
            if token:
                prefixes.add(token)
    return prefixes
