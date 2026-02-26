from __future__ import annotations

import json
import os
from typing import Any

from ..canonical.lint import lint_canon_dir
from ..canonical.registry import CanonicalRegistry
from ..core.trace_types import is_valid_trace_type


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


def lint_hallucinations(
    spec_dir: str,
    repo_root: str | None = None,
    canon_dir: str = "canon",
    require_canon_dir: bool = False,
    require_manifest_schema_registration: bool = True,
) -> list[str]:
    errors: list[str] = []
    known_ids: set[str] = set()
    refs: list[tuple[str, str, str]] = []
    root = repo_root or spec_dir
    canon_root = os.path.join(root, canon_dir)
    if require_canon_dir and not os.path.isdir(canon_root):
        return [f"E520 UNRESOLVED_INPUT missing_canon_dir {canon_root}"]
    if os.path.isdir(canon_root):
        preflight_errors = lint_canon_dir(
            root,
            canon_dir=canon_dir,
            require_manifest_schema_registration=require_manifest_schema_registration,
        )
        if preflight_errors:
            return list(dict.fromkeys(preflight_errors))
    canon = CanonicalRegistry.load(root, canon_dir=canon_dir)
    if canon.load_errors:
        return list(dict.fromkeys(canon.load_errors))
    known_command_prefixes = _load_command_prefixes(root)
    # D13: Build canonical term index for free-text scanning
    canonical_terms = _build_canonical_term_index(canon)
    nfr_ids = _load_nfr_ids(spec_dir)
    if nfr_ids is None:
        errors.append("W570 GRACEFUL_SKIP nfr_refs 07_nfrs.json_absent")
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
        errors.extend(_check_free_text_terms(rel, data, canonical_terms))
        errors.extend(_check_existing_structures_paths(rel, data, root))
        errors.extend(_check_linked_test_expectations(rel, data, root))
        if nfr_ids is not None:
            errors.extend(_check_nfr_refs(rel, data, nfr_ids))
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


# D13: Free-text canonical term scanning

# Fields checked for unbound canonical term mentions
_FREE_TEXT_FIELDS = {"name", "description", "rationale", "justification", "definition"}

# Fields that indicate a canonical ref is already bound nearby
_REF_SUFFIXES = {"_ref", "_refs"}


def _build_canonical_term_index(canon: CanonicalRegistry) -> dict[str, set[str]]:
    """Build a lowercase label → set of canonical IDs index for term/acronym kinds."""
    index: dict[str, set[str]] = {}
    for cid, entry in canon.entries.items():
        if entry.status == "retired":
            continue
        if entry.kind not in ("term", "acronym"):
            continue
        label = entry.payload.get("preferred_label", "")
        if isinstance(label, str) and len(label) >= 3:
            index.setdefault(label.lower(), set()).add(cid)
        # Also index aliases
        aliases = entry.payload.get("aliases", [])
        if isinstance(aliases, list):
            for alias in aliases:
                if isinstance(alias, str) and len(alias) >= 3:
                    index.setdefault(alias.lower(), set()).add(cid)
    return index


_PATH_EXTENSIONS = (".py", ".ts", ".js", ".go", ".java", ".rb", ".sh", ".json")


def _looks_like_path(s: str) -> bool:
    return "/" in s or any(s.endswith(ext) for ext in _PATH_EXTENSIONS)


def _collect_values_under_key(obj: Any, target_key: str) -> list[str]:
    results: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == target_key and isinstance(v, str):
                results.append(v)
            elif k == target_key and isinstance(v, list):
                for i in v:
                    if isinstance(i, str):
                        results.append(i)
                    elif isinstance(i, dict) and "source_file" in i and isinstance(i["source_file"], str):
                        results.append(i["source_file"])
            else:
                results.extend(_collect_values_under_key(v, target_key))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(_collect_values_under_key(item, target_key))
    return results


def _check_existing_structures_paths(rel: str, data: Any, repo_root: str) -> list[str]:
    errs: list[str] = []
    for path in _collect_values_under_key(data, "existing_structures"):
        if _looks_like_path(path) and not os.path.exists(os.path.join(repo_root, path)):
            errs.append(f"E530 EXISTING_STRUCTURE_PATH_NOT_FOUND {rel}:existing_structures path={path}")
    return errs


def _check_linked_test_expectations(rel: str, data: Any, repo_root: str) -> list[str]:
    errs: list[str] = []
    for path in _collect_values_under_key(data, "linked_test_expectation"):
        if _looks_like_path(path) and not os.path.exists(os.path.join(repo_root, path)):
            errs.append(f"E530 LINKED_TEST_FILE_NOT_FOUND {rel}:linked_test_expectation path={path}")
    return errs


def _load_nfr_ids(spec_dir: str) -> set[str] | None:
    path = os.path.join(spec_dir, "07_nfrs.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return {n["id"] for n in data.get("nfrs", []) if isinstance(n, dict) and "id" in n}
    except (OSError, json.JSONDecodeError):
        return None


def _check_nfr_refs(rel: str, data: Any, nfr_ids: set[str]) -> list[str]:
    errs: list[str] = []
    refs: list[str] = []
    refs.extend(_collect_values_under_key(data, "nfr_refs"))
    refs.extend(_collect_values_under_key(data, "nfr_ref"))
    for ref in refs:
        if ref not in nfr_ids:
            errs.append(f"E530 UNRESOLVED_NFR_REF {rel} nfr_ref={ref}")
    return errs


def _check_free_text_terms(
    rel: str,
    obj: Any,
    canonical_terms: dict[str, set[str]],
    path: str = "",
) -> list[str]:
    """Check free-text fields for mentions of canonical terms without a binding ref."""
    if not canonical_terms:
        return []
    errs: list[str] = []
    if isinstance(obj, dict):
        # Collect all ref keys present at this level
        bound_refs = {
            k for k in obj
            if any(k.endswith(s) for s in _REF_SUFFIXES)
        }
        for key, value in obj.items():
            p = f"{path}.{key}" if path else key
            if key in _FREE_TEXT_FIELDS and isinstance(value, str) and len(value) >= 3:
                # Skip if there's already a ref binding at this level
                if bound_refs:
                    continue
                text_lower = value.lower()
                for term, cids in canonical_terms.items():
                    if term in text_lower:
                        errs.append(
                            f"E541 UNBOUND_CANONICAL_TERM {rel}:{p} "
                            f"mentions canonical term '{term}' "
                            f"(ids={sorted(cids)}) without a binding *_ref"
                        )
                        break  # One warning per field is enough
            errs.extend(_check_free_text_terms(rel, value, canonical_terms, p))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            errs.extend(_check_free_text_terms(rel, item, canonical_terms, f"{path}[{idx}]"))
    return errs

