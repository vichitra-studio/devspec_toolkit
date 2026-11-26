"""Hallucination checks (E530, E520, W570): an invented stage, environment, unit or command prefix, a ``*_ref`` that names
no id, an ``existing_structures`` path that does not exist, an ``nfr_ref`` that names no NFR, and a canon directory
that does not load."""
from __future__ import annotations

import json
import os
import sys
from typing import TYPE_CHECKING, Any

from ..canonical.lint import lint_canon_dirs
from ..canonical.registry import CanonicalRegistry
from ..core.errors import SpecError, make_error
from ..core.json_utils import find_schema_dir, build_id_index, resolve_ref as _resolve_urn_ref
from .linter_utils import (
    build_lint_graph,
    collect_ids_and_refs,
    graph_covered_files,
    graph_known_ids,
    is_resolved_canonical_ref,
    iter_json,
    load_canonical_stages,
)

if TYPE_CHECKING:
    from ..graph.model import Graph


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
    project_canon_dir: str | None = None,
    git_root: str | None = None,
    *,
    graph: Graph | None = None,
) -> list[SpecError]:
    """Hallucination checks over every artifact of *spec_dir*; returns the findings, never raises.

    Ids a ``*_ref`` may name come from *graph* (built from the toolkit at *repo_root* when ``None``) for the files it
    covers and from a scan of the file for the others.
    """
    errors: list[SpecError] = []
    graph = build_lint_graph(spec_dir, repo_root) if graph is None else graph
    covered = graph_covered_files(graph)
    known_ids = graph_known_ids(graph)
    refs: list[tuple[str, str, str]] = []
    root = repo_root or spec_dir
    # path_root: for host-file existence checks in submodule deployments,
    # resolve against git_root (host repo root) not the toolkit submodule root.
    path_root = git_root or root
    canon_root = os.path.join(root, canon_dir)
    if require_canon_dir and not os.path.isdir(canon_root):
        return [make_error("E520", f"UNRESOLVED_INPUT missing_canon_dir {canon_root}")]
    if os.path.isdir(canon_root):
        preflight_errors = lint_canon_dirs(
            root,
            canon_dir=canon_dir,
            project_canon_dir=project_canon_dir,
            require_manifest_schema_registration=require_manifest_schema_registration,
        )
        if preflight_errors:
            return list(dict.fromkeys(preflight_errors))
    canon = CanonicalRegistry.load(root, canon_dir=canon_dir, project_canon_dir=project_canon_dir)
    if canon.load_errors:
        return list(dict.fromkeys(canon.load_errors))
    known_command_prefixes = _load_command_prefixes(root, project_canon_dir=project_canon_dir)
    # Load canonical stages; fall back to hardcoded KNOWN_STAGES
    canon_stages = load_canonical_stages(canon_root)
    active_stages = canon_stages if canon_stages else KNOWN_STAGES
    nfr_ids = _load_nfr_ids(spec_dir)
    if nfr_ids is None:
        errors.append(make_error("W570", "GRACEFUL_SKIP nfr_refs 07_nfrs.json_absent"))
    for path in iter_json(spec_dir):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            rel = os.path.relpath(path, spec_dir)
            errors.append(make_error("E520", f"UNRESOLVED_INPUT {rel} invalid_json {exc}"))
            continue
        rel = os.path.relpath(path, spec_dir)
        errors.extend(_scan_node(rel, data, canon, known_command_prefixes, stages=active_stages))
        errors.extend(_check_existing_structures_paths(rel, data, path_root))
        if nfr_ids is not None:
            errors.extend(_check_nfr_refs(rel, data, nfr_ids))
        collect_ids_and_refs(data, rel, known_ids, refs, skip_ids_for_files=covered)
    for rel, p, ref_id in refs:
        if ref_id.startswith(("external:", "file:", "refs/", "cn:")):
            continue
        if ref_id not in known_ids:
            errors.append(make_error(
                "E530",
                f"INVENTED_ENUM_OR_ID {rel}:{p}={ref_id}",
                subcode="INVENTED_ENUM_OR_ID",
                file=rel,
                jq_path=f".{p}" if not p.startswith(".") else p,
                value=ref_id,
            ))
    return errors


def _scan_node(
    rel: str,
    node: Any,
    canon: CanonicalRegistry,
    known_command_prefixes: set[str],
    path: str = "",
    *,
    stages: set[str] | None = None,
) -> list[SpecError]:
    active_stages = stages if stages is not None else KNOWN_STAGES
    errs: list[SpecError] = []
    if isinstance(node, dict):
        for key, value in node.items():
            p = f"{path}.{key}" if path else key
            if key in {"stage", "environment"} and isinstance(value, str) and value not in active_stages:
                errs.append(make_error(
                    "E530",
                    f"INVENTED_ENUM_OR_ID {rel}:{p}={value}",
                    subcode="INVENTED_ENUM_OR_ID",
                    file=rel,
                    jq_path=f".{p}",
                    value=value,
                ))
            if key in {"stages", "environments"} and isinstance(value, list):
                for idx, item in enumerate(value):
                    if isinstance(item, str) and item not in active_stages:
                        errs.append(make_error(
                            "E530",
                            f"INVENTED_ENUM_OR_ID {rel}:{p}[{idx}]={item}",
                            subcode="INVENTED_ENUM_OR_ID",
                            file=rel,
                            jq_path=f".{p}[{idx}]",
                            value=item,
                        ))
            if key in {"unit", "units"}:
                if isinstance(value, str) and not _is_valid_unit(value, canon):
                    errs.append(make_error(
                        "E530",
                        f"INVENTED_ENUM_OR_ID {rel}:{p}={value}",
                        subcode="INVENTED_ENUM_OR_ID",
                        file=rel,
                        jq_path=f".{p}",
                        value=value,
                    ))
                if isinstance(value, list):
                    for idx, item in enumerate(value):
                        if isinstance(item, str) and not _is_valid_unit(item, canon):
                            errs.append(make_error(
                                "E530",
                                f"INVENTED_ENUM_OR_ID {rel}:{p}[{idx}]={item}",
                                subcode="INVENTED_ENUM_OR_ID",
                                file=rel,
                                jq_path=f".{p}[{idx}]",
                                value=item,
                            ))
            if key == "command" and isinstance(value, str):
                errs.extend(_command_prefix_errors(rel, f".{p}", value, node.get("command_ref"), canon, known_command_prefixes))
            if key == "test_commands" and isinstance(value, list):
                for idx, item in enumerate(value):
                    if isinstance(item, str):
                        errs.extend(_command_prefix_errors(rel, f".{p}[{idx}]", item, None, canon, known_command_prefixes))
            errs.extend(_scan_node(rel, value, canon, known_command_prefixes, p, stages=active_stages))
    elif isinstance(node, list):
        for idx, item in enumerate(node):
            errs.extend(_scan_node(rel, item, canon, known_command_prefixes, f"{path}[{idx}]", stages=active_stages))
    return errs


def _command_prefix_errors(
    rel: str,
    jq_path: str,
    command: str,
    command_ref: Any,
    canon: CanonicalRegistry,
    known_command_prefixes: set[str],
) -> list[SpecError]:
    """E530 for a *command* whose first word is in no prefix allowlist, unless *command_ref* asserts a canon ref.

    The ref is not re-validated here: verb validation is deferred, canonical-integrity (E210/E110) owns *ref*
    resolution and fails loudly if the asserted id is unresolvable.  *jq_path* locates the command in the file.
    """
    if is_resolved_canonical_ref(command_ref):
        return []
    prefix = command.strip().split(" ", 1)[0]
    if not prefix or prefix in known_command_prefixes or canon.resolve_alias("command", prefix):
        return []
    return [make_error(
        "E530",
        f"INVENTED_ENUM_OR_ID {rel}:{jq_path.lstrip('.')}={prefix} "
        f"Command prefix '{prefix}' is not in the allowlist. "
        f"Resolve by either (a) attaching a sibling command_ref to a registered canon entry "
        f"under <spec-root>/canon/kinds/command.json, "
        f"or (b) appending the prefix to <spec-root>/canon/command_prefixes.json.",
        subcode="INVENTED_ENUM_OR_ID",
        file=rel,
        jq_path=jq_path,
        value=prefix,
    )]


def _is_valid_unit(value: str, canon: CanonicalRegistry) -> bool:
    if canon.resolve_alias("unit", value):
        return True
    return " ".join(value.strip().lower().split()) in KNOWN_UNITS


class SchemaResolverCtx:
    """Schema resolution context: the schema a file names in ``$schema``, and a ``$ref`` resolver for it.

    Holds the built id_index and a ref cache; ``make_resolve_fn`` returns a closure suitable for use with
    schema_nav's ``effective_schema``.  Only the id_index scan (once per schema dir) is expensive.  If the schema
    dir is unavailable the instance is still usable but every lookup returns ``None``.
    """

    def __init__(self, repo_root: str | None) -> None:
        schema_dir = find_schema_dir(repo_root)
        self._id_index: dict[str, str] = build_id_index(schema_dir) if schema_dir else {}
        self._ref_cache: dict[str, dict] = {}

    def make_resolve_fn(self, root_schema: dict):
        """Return a ``resolve_ref`` closure bound to this invocation's caches.

        The closure handles both local ``#/$defs/...`` references (using
        ``root_schema``) and toolkit URN references (``vc:...``) via
        ``_resolve_urn_ref``.  Unresolvable references return ``None``,
        which ``effective_schema`` treats as an empty branch.
        """
        def _resolve(node: dict):
            if not isinstance(node, dict) or "$ref" not in node:
                return node
            ref: str = node["$ref"]
            if ref.startswith("#/$defs/"):
                def_name = ref.split("/")[-1]
                resolved = root_schema.get("$defs", {}).get(def_name)
                return resolved if isinstance(resolved, dict) else None
            return _resolve_urn_ref(ref, self._id_index, self._ref_cache)
        return _resolve

    def load_raw_schema(self, data: dict) -> dict | None:
        """The schema file named by the ``$schema`` of *data*, as written (nothing merged), or ``None`` when *data* names none the toolkit has or the file cannot be read."""
        schema_uri = data.get("$schema") if isinstance(data, dict) else None
        if not isinstance(schema_uri, str) or not schema_uri:
            return None
        schema_path = self._id_index.get(schema_uri)
        if not schema_path:
            return None
        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                raw_schema = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None
        return raw_schema if isinstance(raw_schema, dict) else None


def _load_command_prefixes(
    repo_root: str,
    project_canon_dir: str | None = None,
) -> set[str]:
    prefixes = set(DEFAULT_COMMAND_PREFIXES)
    _merge_prefixes_from_file(
        os.path.join(repo_root, "tools", "command_prefixes.json"),
        prefixes,
    )
    if project_canon_dir:
        _merge_prefixes_from_file(
            os.path.join(project_canon_dir, "command_prefixes.json"),
            prefixes,
        )
    return prefixes


def _merge_prefixes_from_file(cfg_path: str, prefixes: set[str]) -> None:
    if not os.path.exists(cfg_path):
        return
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        print(
            f"warning: hallucination-lint failed to load command-prefix allowlist "
            f"at {cfg_path} ({type(exc).__name__}); using defaults only.",
            file=sys.stderr,
        )
        return
    values = data.get("allowed_prefixes", [])
    if not isinstance(values, list):
        print(
            f"warning: hallucination-lint ignored {cfg_path}: "
            f"'allowed_prefixes' must be a list of strings.",
            file=sys.stderr,
        )
        return
    for item in values:
        if isinstance(item, str):
            token = item.strip().split(" ", 1)[0]
            if token:
                prefixes.add(token)


_PATH_EXTENSIONS = (".py", ".ts", ".js", ".go", ".java", ".rb", ".sh", ".json")


def _looks_like_path(s: str) -> bool:
    return "/" in s or any(s.endswith(ext) for ext in _PATH_EXTENSIONS)


def _collect_path_value_pairs(
    obj: Any, target_key: str, prefix: str = ""
) -> list[tuple[str, str]]:
    """Recurse through ``obj`` and return ``(jq_path, value)`` pairs for every
    occurrence of ``target_key``.  ``jq_path`` uses leading-dot notation so it
    can be used directly in ``specdev json patch`` commands."""
    results: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            current = f"{prefix}.{k}" if prefix else f".{k}"
            if k == target_key:
                if isinstance(v, str):
                    results.append((current, v))
                elif isinstance(v, list):
                    for idx, item in enumerate(v):
                        item_path = f"{current}[{idx}]"
                        if isinstance(item, str):
                            results.append((item_path, item))
                        elif isinstance(item, dict) and "source_file" in item and isinstance(item["source_file"], str):
                            results.append((f"{item_path}.source_file", item["source_file"]))
            else:
                results.extend(_collect_path_value_pairs(v, target_key, current))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            results.extend(_collect_path_value_pairs(item, target_key, f"{prefix}[{idx}]"))
    return results


def _unwrap_shell_c(value: str) -> str:
    """Strip a leading ``bash -c "..."`` / ``sh -c '...'`` wrapper.

    Returns the inner command unquoted, or ``value`` unchanged if no recognised
    wrapper is present or the surrounding quotes are malformed. Authors who wrap
    a test invocation in ``bash -c`` to satisfy the canonical command-prefix
    allowlist should not be penalised by path extraction; unwrap before parsing.
    """
    s = value.strip()
    for prefix in ("bash -c ", "sh -c "):
        if s.startswith(prefix):
            inner = s[len(prefix):].strip()
            if len(inner) >= 2 and inner[0] in ("\"", "'") and inner[-1] == inner[0]:
                return inner[1:-1]
            return inner
    return value


def _extract_path_from_string(value: str) -> str:
    """Extract the file path portion from a composite string.

    Handles five cases:
    - Wrapped invocation ``bash -c "..."`` / ``sh -c '...'``: unwrap the inner
      command first so subsequent parsing sees the unquoted invocation.
    - Em-dash composite "path/to/file.ext \u2014 description": splits on the
      em-dash (with or without surrounding spaces) and returns the left side.
    - Compound shell command containing &&, ||, or " ; ": returns "" because
      there is no single authoritative file path to validate.
    - Single command "npx playwright test path/to/file.ext --grep '...'":
      returns the first token that passes _looks_like_path. Tokens that
      immediately follow a long option (--name) are treated as option values
      and skipped, preventing false positives from --prefix <dir> patterns.
    - Bare path or no path-like token found: returns the first path-like token
      or "" if none exists.

    Returns "" when no path can be extracted so callers receive a falsy
    value that _looks_like_path rejects, preventing a bogus os.path.exists call.
    """
    # Unwrap shell -c wrappers before any other parsing.
    value = _unwrap_shell_c(value)
    # Em-dash separator: path is everything before the em-dash (spaces optional).
    if "\u2014" in value:
        return value.split("\u2014")[0].strip()
    # Compound commands have no single path to validate — skip entirely.
    if "&&" in value or "||" in value or " ; " in value:
        return ""
    # Single command or bare path: first token that looks like a file path.
    # Skip long-option argument values (e.g. --prefix <dir>) to avoid treating
    # directory arguments as file paths to validate.
    prev_was_long_opt = False
    for token in value.split():
        if token.startswith(("-", "'", '"')):
            prev_was_long_opt = token.startswith("--")
            continue
        if prev_was_long_opt:
            prev_was_long_opt = False
            continue
        prev_was_long_opt = False
        if _looks_like_path(token):
            return token
    return ""


def _check_path_values(
    rel: str, data: Any, path_root: str, key: str, error_tag: str
) -> list[SpecError]:
    errs: list[SpecError] = []
    for jq_path, raw_value in _collect_path_value_pairs(data, key):
        path = _extract_path_from_string(raw_value)
        if _looks_like_path(path) and not os.path.exists(os.path.join(path_root, path)):
            errs.append(make_error(
                "E530",
                f"{error_tag} {rel}:{key} path={path}",
                subcode=error_tag,
                file=rel,
                jq_path=jq_path,
                value=path,
            ))
    return errs


def _check_existing_structures_paths(rel: str, data: Any, path_root: str) -> list[SpecError]:
    return _check_path_values(rel, data, path_root, "existing_structures", "EXISTING_STRUCTURE_PATH_NOT_FOUND")


def _load_nfr_ids(spec_dir: str) -> set[str] | None:
    path = os.path.join(spec_dir, "07_nfrs.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return {str(n.get("nfr_id")) for n in data.get("nfrs", []) if isinstance(n, dict) and n.get("nfr_id")}
    except (OSError, json.JSONDecodeError):
        return None


def _check_nfr_refs(rel: str, data: Any, nfr_ids: set[str]) -> list[SpecError]:
    errs: list[SpecError] = []
    for key in ("nfr_refs", "nfr_ref"):
        for jq_path, ref in _collect_path_value_pairs(data, key):
            if ref not in nfr_ids:
                errs.append(make_error(
                    "E530",
                    f"UNRESOLVED_NFR_REF {rel} nfr_ref={ref}",
                    subcode="UNRESOLVED_NFR_REF",
                    file=rel,
                    jq_path=jq_path,
                    value=ref,
                ))
    return errs
