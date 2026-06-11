from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

from ..canonical.lint import lint_canon_dirs
from ..canonical.registry import CanonicalRegistry
from ..core.errors import SpecError, make_error
from ..core.json_utils import find_schema_dir, build_id_index, resolve_ref as _resolve_urn_ref
from ..core.registry import derive_allowed_upstream
from ..core.schema_nav import effective_schema as _nav_effective_schema
from ..core.trace_types import is_valid_trace_type
from .linter_utils import (
    collect_ids_and_refs,
    is_resolved_canonical_ref,
    iter_json,
    load_canonical_stages,
    tokenize_free_text,
    DERIVATION_STOPWORDS,
)


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
) -> list[SpecError]:
    errors: list[SpecError] = []
    known_ids: set[str] = set()
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
    # D13: Build canonical term index for free-text scanning
    canonical_terms = _build_canonical_term_index(canon)
    # Build schema resolver context once per invocation (id_index scan is ~O(schema-dir))
    _schema_ctx = _SchemaResolverCtx(root)
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
        is_canon = rel.startswith("canon" + os.sep) or rel.startswith("canon/")
        errors.extend(_scan_node(rel, data, canon, known_command_prefixes, stages=active_stages))
        # Skip E541 for canon files — canon definitions ARE the vocabulary;
        # they cannot bind *_ref to themselves and should not be flagged.
        if not is_canon:
            # Resolve file-level schema context for structural E541 suppression.
            # Falls back to (None, None) if $schema is absent or unresolvable —
            # in that case _check_free_text_terms behaves exactly as before.
            _file_schema, _file_resolve_fn = _schema_ctx.load_file_schema(data)
            errors.extend(_check_free_text_terms(
                rel, data, canonical_terms,
                schema_node=_file_schema,
                resolve_fn=_file_resolve_fn,
            ))
        errors.extend(_check_existing_structures_paths(rel, data, path_root))
        errors.extend(_check_linked_test_expectations(rel, data, path_root))
        if nfr_ids is not None:
            errors.extend(_check_nfr_refs(rel, data, nfr_ids))
        # Derivation reads step_order.json from the toolkit (repo_root/tools/),
        # not the host repo, so it uses `root` (toolkit root), not `path_root`.
        errors.extend(_check_content_derivation(rel, data, spec_dir, root))
        collect_ids_and_refs(data, rel, known_ids, refs)
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
        in_trace_container = any(token in path for token in ("trace", "targets", "target_ids", "mitigations"))
        if "type" in node and "id" in node and in_trace_container:
            t = node.get("type")
            if isinstance(t, str) and not is_valid_trace_type(t):
                _type_jq = f".{path}.type" if path else ".type"
                errs.append(make_error(
                    "E530",
                    f"INVENTED_ENUM_OR_ID {rel}:{path}.type={t}",
                    subcode="INVENTED_ENUM_OR_ID",
                    file=rel,
                    jq_path=_type_jq,
                    value=t,
                ))
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
                # Skip prefix check when a sibling command_ref asserts a canon ref.
                # We DO NOT re-validate that the ref resolves — verb validation is
                # intentionally deferred. canonical-integrity (E210/E110) owns *ref*
                # resolution and will fail loudly if the asserted id is unresolvable.
                if not is_resolved_canonical_ref(node.get("command_ref")):
                    prefix = value.strip().split(" ", 1)[0]
                    if prefix and prefix not in known_command_prefixes and not canon.resolve_alias("command", prefix):
                        errs.append(make_error(
                            "E530",
                            f"INVENTED_ENUM_OR_ID {rel}:{p}={prefix} "
                            f"Command prefix '{prefix}' is not in the allowlist. "
                            f"Resolve by either (a) attaching a sibling command_ref to a registered canon entry "
                            f"under <spec-root>/canon/kinds/command.json, "
                            f"or (b) appending the prefix to <spec-root>/canon/command_prefixes.json.",
                            subcode="INVENTED_ENUM_OR_ID",
                            file=rel,
                            jq_path=f".{p}",
                            value=prefix,
                        ))
            if key == "pr_rules" and isinstance(value, list):
                allowed_pr_rules = {
                    "validate", "validate-all", "matrix", "fixtures-lint", "invariants-check",
                    "governance-check", "seed-lint", "test", "build", "lint",
                    "format", "audit", "security"
                }
                for idx, item in enumerate(value):
                    if isinstance(item, str) and item not in allowed_pr_rules:
                        errs.append(make_error(
                            "E530",
                            f"INVENTED_ENUM_OR_ID {rel}:{p}[{idx}]={item}",
                            subcode="INVENTED_ENUM_OR_ID",
                            file=rel,
                            jq_path=f".{p}[{idx}]",
                            value=item,
                        ))
            errs.extend(_scan_node(rel, value, canon, known_command_prefixes, p, stages=active_stages))
    elif isinstance(node, list):
        for idx, item in enumerate(node):
            errs.extend(_scan_node(rel, item, canon, known_command_prefixes, f"{path}[{idx}]", stages=active_stages))
    return errs




def _is_valid_unit(value: str, canon: CanonicalRegistry) -> bool:
    if canon.resolve_alias("unit", value):
        return True
    return " ".join(value.strip().lower().split()) in KNOWN_UNITS


# ---------------------------------------------------------------------------
# E541 structural schema resolver
#
# Builds a per-lint-invocation schema resolution context so that
# _check_free_text_terms can determine whether a dict node's schema is
# structurally ref-capable (additionalProperties:false AND at least one
# *_ref/*_refs property).  If it is NOT ref-capable, E541 cannot be satisfied
# by the spec author and must be suppressed.
#
# The resolver mirrors the pattern in json_utils.json_schema_discovery
# (lines 760–787) but is shaped for use in a recursive linter rather than
# an interactive CLI command.  Schema loading is done once per lint invocation,
# not per file, to avoid repeated directory scans.
# ---------------------------------------------------------------------------

class _SchemaResolverCtx:
    """Lightweight schema resolution context for structural E541 suppression.

    Holds the built id_index and a per-invocation ref cache; provides a
    ``resolve_node`` closure factory suitable for use with schema_nav's
    ``effective_schema``.

    Instances are cheap — only the id_index scan (once per schema dir) is
    expensive.  If the schema dir is unavailable the instance is still usable
    but all resolution returns ``None`` (fall back to current E541 behaviour).
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

    def load_file_schema(self, data: dict) -> tuple[dict, Any] | tuple[None, None]:
        """Return ``(effective_root_schema, resolve_fn)`` for *data*, or ``(None, None)``.

        Reads the ``$schema`` URI from *data*, looks it up in the id_index,
        loads the schema file, and returns the allOf-merged root node together
        with the bound resolve_fn closure.  Both are needed by
        ``_check_free_text_terms``, which navigates into sub-schemas inline via
        ``_nav_effective_schema`` as it recurses.

        Falls back to ``(None, None)`` on any error so callers treat it as
        "schema unknown → fire E541 as usual."
        """
        schema_uri = data.get("$schema") if isinstance(data, dict) else None
        if not isinstance(schema_uri, str) or not schema_uri:
            return None, None
        schema_path = self._id_index.get(schema_uri)
        if not schema_path:
            return None, None
        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                raw_schema = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None, None
        resolve_fn = self.make_resolve_fn(raw_schema)
        try:
            eff = _nav_effective_schema(raw_schema, resolve_fn, include_conditionals=True)
            return eff, resolve_fn
        except Exception:
            return None, None



def _is_structurally_unbindable(schema_node: dict | None) -> bool:
    """Return True iff *schema_node* describes an object that structurally
    cannot carry a canonical binding ref.

    Criterion: the node sets ``additionalProperties: false`` (explicit, not
    default) AND its ``properties`` map contains no key ending in ``_ref``
    or ``_refs``.

    When this is True, demanding a *_ref binding from the spec author is a
    schema violation — E541 must be suppressed for all free-text fields on
    that object.  When False (or when *schema_node* is None / unresolvable),
    we fall back to the current behaviour (E541 may fire).
    """
    if not isinstance(schema_node, dict):
        return False
    if schema_node.get("additionalProperties") is not False:
        return False
    props = schema_node.get("properties", {})
    has_ref_slot = any(
        k.endswith("_ref") or k.endswith("_refs")
        for k in props
    )
    return not has_ref_slot


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


def _check_linked_test_expectations(rel: str, data: Any, path_root: str) -> list[SpecError]:
    return _check_path_values(rel, data, path_root, "linked_test_expectation", "LINKED_TEST_FILE_NOT_FOUND")


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


# R9/T20: Content derivation check
# Minimum token overlap between a downstream artifact and its upstream
# dependencies before W594 CONTENT_DERIVATION_LOW_OVERLAP fires.  Chosen
# empirically: well-derived artifacts share at least 5 domain-specific tokens.
_DERIVATION_OVERLAP_THRESHOLD = 5

_DERIVATION_FREE_TEXT_FIELDS = {
    "description", "statement", "rationale", "justification", "notes",
    "narrative", "definition", "postconditions", "preconditions",
}


def _extract_free_text_tokens(obj: Any) -> set[str]:
    """Extract tokens from all free-text fields in a spec artifact."""
    tokens: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _DERIVATION_FREE_TEXT_FIELDS and isinstance(v, str):
                tokens |= tokenize_free_text(v, stopwords=DERIVATION_STOPWORDS)
            elif isinstance(v, (dict, list)):
                tokens |= _extract_free_text_tokens(v)
    elif isinstance(obj, list):
        for item in obj:
            tokens |= _extract_free_text_tokens(item)
    return tokens


def _check_content_derivation(
    rel: str,
    data: Any,
    spec_dir: str,
    repo_root: str,
    threshold: int = _DERIVATION_OVERLAP_THRESHOLD,
) -> list[SpecError]:
    """R9/T20: Check that downstream content derives from upstream artifacts."""
    errs: list[SpecError] = []
    # Load step_order.json to find upstream dependencies
    step_order_path = os.path.join(repo_root, "tools", "step_order.json")
    if not os.path.isfile(step_order_path):
        return errs

    # Determine current step from filename
    basename = os.path.basename(rel)
    step_match = re.match(r"^(\d{2}[a-z]?)_", basename)
    if not step_match:
        return errs
    step_id = step_match.group(1)

    try:
        with open(step_order_path, "r", encoding="utf-8") as f:
            order_data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return errs

    upstream_deps = derive_allowed_upstream(step_id, order_data.get("steps", []))
    if not upstream_deps:
        return errs

    # Extract tokens from downstream (current artifact)
    downstream_tokens = _extract_free_text_tokens(data)
    if not downstream_tokens:
        return errs

    # Load and tokenize upstream artifacts
    upstream_tokens: set[str] = set()
    missing_upstreams: list[str] = []
    for dep_step in upstream_deps:
        found = False
        if os.path.isdir(spec_dir):
            for fn in os.listdir(spec_dir):
                if fn.startswith(f"{dep_step}_") and fn.endswith(".json"):
                    dep_path = os.path.join(spec_dir, fn)
                    try:
                        with open(dep_path, "r", encoding="utf-8") as f:
                            dep_data = json.load(f)
                        upstream_tokens |= _extract_free_text_tokens(dep_data)
                        found = True
                    except (OSError, json.JSONDecodeError):
                        pass
                    break
        if not found:
            missing_upstreams.append(dep_step)

    for dep in missing_upstreams:
        errs.append(make_error("W590", f"CROSS_STEP_UPSTREAM_MISSING upstream step {dep} artifact not found; skipping derivation check"))

    if not upstream_tokens:
        return errs

    # Count overlap
    overlap = downstream_tokens & upstream_tokens
    if len(overlap) < threshold:
        errs.append(make_error(
            "W594",
            f"CONTENT_DERIVATION_LOW_OVERLAP {rel} "
            f"overlap={len(overlap)} threshold={threshold} "
            f"(downstream has {len(downstream_tokens)} tokens, upstream has {len(upstream_tokens)} tokens)",
        ))

    return errs


# Keys whose subtrees are excluded from E541 scanning.
#
# PRIMARY MECHANISM (preferred): The structural rule in _check_free_text_terms
# suppresses E541 for any dict whose JSON Schema declares
# additionalProperties:false with no *_ref/*_refs property.  That rule is
# self-maintaining: it fires on schema structure, not key names.
#
# SECONDARY MECHANISM (this list): explicit key-name skips are kept for two
# categories that the structural rule cannot cover:
#
# Category A — SEMANTIC skips: the subtree IS vocabulary (canon definitions),
#   so E541 can never be satisfied by binding a *_ref back to itself.  These
#   remain regardless of schema additionalProperties settings.
#
# Category B — STRUCTURAL skips for keys not reachable by the per-file schema
#   resolver (e.g. Step 16a artifacts in impl_context/ have variable filenames
#   so load_file_schema resolves no $schema → structural rule cannot activate).
#   These are kept as belt-and-suspenders until schema coverage is guaranteed.
#
# Category C — FREE-FORM subtrees: objects whose schema intentionally omits
#   additionalProperties (defaults to true / open), making them structurally
#   bindable in theory but practically unbindable (test-runner output, etc.).
#   The structural rule requires additionalProperties:false to suppress, so
#   these need explicit skips.
#
# Note: emergent_ambiguities / ambiguities / docs_impact / edge_cases all have
#   additionalProperties:false + no ref slot — the structural rule now handles
#   them when $schema resolves.  The key-name entries below act as belt-and-
#   suspenders for files where $schema is absent (old/hand-authored artifacts).
#   They are retained rather than removed to avoid a silent regression if the
#   structural rule ever loses coverage (e.g. schema file absent at runtime).
_E541_SKIP_KEYS = {
    # Category A: Canonical vocabulary subtrees
    "canonical_proposals", "canonical_refs_used", "canonical_conflicts",
    "tech_stack", "user_segments", "seeds",

    # Category B: Step 16a/16b implementation subtrees — belt-and-suspenders
    # for impl_context/ artifacts with variable filenames (no reliable $schema
    # lookup).  Both keys appear exclusively in Step 16 schemas; no other
    # current pipeline step defines them.
    "actions",
    "coding_examples",

    # Category B: Step 16 narrative subtrees — belt-and-suspenders for the same
    # reason as actions/coding_examples.  All three have additionalProperties:false
    # + no *_ref in their Step 16 schemas; structural rule handles them when
    # $schema resolves.  These entries ensure suppression when it does not.
    "emergent_ambiguities",
    "ambiguities",
    "docs_impact",

    # Category C: execution subtree (16_impl_context.schema.json only).
    # execution.final_status.test_results items have additionalProperties unset
    # (intentionally free-form test-runner output — not bindable spec vocabulary).
    # The structural rule requires additionalProperties:false and will NOT suppress
    # items with unset additionalProperties, so this key-name skip is necessary.
    # "execution" appears only in 16_impl_context.schema.json; no other current
    # pipeline step defines it.
    "execution",
}

# File-scoped exemptions: ``edge_cases`` is an unbindable narrative subtree
# *only* in 11_redteam.json (schema sets additionalProperties:false and
# defines no *_ref field on edge_cases items).  Scoping the skip to that
# file prevents a future step that introduces a literal ``edge_cases`` key
# from silently inheriting the exemption.
# NOTE: The structural rule also suppresses edge_cases when $schema resolves;
# this file-scoped entry is belt-and-suspenders for files without $schema.
_E541_SKIP_KEYS_BY_FILE: dict[str, set[str]] = {
    "11_redteam.json": {"edge_cases"},
}


def _is_e541_skipped(rel: str, key: str) -> bool:
    if key in _E541_SKIP_KEYS:
        return True
    basename = os.path.basename(rel)
    return key in _E541_SKIP_KEYS_BY_FILE.get(basename, set())


def _check_free_text_terms(
    rel: str,
    obj: Any,
    canonical_terms: dict[str, set[str]],
    path: str = "",
    schema_node: dict | None = None,
    resolve_fn: Any = None,
) -> list[SpecError]:
    """Check free-text fields for mentions of canonical terms without a binding ref.

    Structural suppression (E541 skip): if *schema_node* describes a dict whose
    JSON Schema sets ``additionalProperties: false`` and defines no ``*_ref`` /
    ``*_refs`` property, a canonical binding ref is a schema violation — E541 is
    suppressed for ALL free-text fields of that object.

    When *schema_node* is ``None`` (schema absent or unresolvable) the function
    falls back to the original behaviour (ref-presence at runtime is the only
    suppressor).  This keeps the change safe: a missing ``$schema`` field never
    causes false silences.
    """
    if not canonical_terms:
        return []
    errs: list[SpecError] = []
    if isinstance(obj, dict):
        # --- Structural suppression check ---
        # Resolve the effective schema for THIS dict level (allOf-merge etc.).
        effective_node: dict | None = None
        if schema_node is not None and resolve_fn is not None:
            try:
                effective_node = _nav_effective_schema(
                    schema_node, resolve_fn, include_conditionals=True
                )
            except Exception:
                effective_node = None

        structurally_unbindable = _is_structurally_unbindable(effective_node)

        # Collect all ref keys present at this level (runtime fallback)
        bound_refs = {
            k for k in obj
            if any(k.endswith(s) for s in _REF_SUFFIXES)
        }
        for key, value in obj.items():
            # Skip canonical metadata subtrees entirely — these are
            # vocabulary definitions, not spec content that should bind refs.
            if _is_e541_skipped(rel, key):
                continue
            p = f"{path}.{key}" if path else key

            # Compute child schema node for recursion
            child_schema: dict | None = None
            if effective_node is not None and resolve_fn is not None:
                props = effective_node.get("properties", {})
                if key in props:
                    child_schema = props[key]

            if key in _FREE_TEXT_FIELDS and isinstance(value, str) and len(value) >= 3:
                # Skip if the schema says this object structurally cannot carry
                # a binding ref (additionalProperties:false, no *_ref slot).
                if structurally_unbindable:
                    pass  # skip the E541 binding check — object cannot carry a *_ref
                    # (the unconditional _check_free_text_terms recursion below is a
                    #  no-op for this string value, so descent is not re-triggered here)
                # Skip if there's already a ref binding at this level (runtime)
                elif bound_refs:
                    pass  # suppressed by runtime ref presence
                else:
                    text_lower = value.lower()
                    for term, cids in canonical_terms.items():
                        if term in text_lower:
                            errs.append(make_error(
                                "E541",
                                f"UNBOUND_CANONICAL_TERM {rel}:{p} "
                                f"mentions canonical term '{term}' "
                                f"(ids={sorted(cids)}) without a binding *_ref",
                            ))
                            break  # One warning per field is enough

            errs.extend(_check_free_text_terms(
                rel, value, canonical_terms, p,
                schema_node=child_schema,
                resolve_fn=resolve_fn,
            ))
    elif isinstance(obj, list):
        # Navigate into items schema for list elements
        items_schema: dict | None = None
        if schema_node is not None and resolve_fn is not None:
            try:
                eff = _nav_effective_schema(schema_node, resolve_fn, include_conditionals=True)
                items_raw = eff.get("items")
                if isinstance(items_raw, dict):
                    items_schema = items_raw
            except Exception:
                items_schema = None
        for idx, item in enumerate(obj):
            errs.extend(_check_free_text_terms(
                rel, item, canonical_terms, f"{path}[{idx}]",
                schema_node=items_schema,
                resolve_fn=resolve_fn,
            ))
    return errs

