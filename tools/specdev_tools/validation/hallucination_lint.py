from __future__ import annotations

import json
import os
import re
from typing import Any

from ..canonical.lint import lint_canon_dirs
from ..canonical.registry import CanonicalRegistry
from ..core.errors import SpecError, make_error
from ..core.registry import derive_allowed_upstream
from ..core.trace_types import is_valid_trace_type
from .linter_utils import (
    collect_ids_and_refs,
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
    known_command_prefixes = _load_command_prefixes(root)
    # Load canonical stages; fall back to hardcoded KNOWN_STAGES
    canon_stages = load_canonical_stages(canon_root)
    active_stages = canon_stages if canon_stages else KNOWN_STAGES
    # D13: Build canonical term index for free-text scanning
    canonical_terms = _build_canonical_term_index(canon)
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
            errors.extend(_check_free_text_terms(rel, data, canonical_terms))
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
            errors.append(make_error("E530", f"INVENTED_ENUM_OR_ID {rel}:{p}={ref_id}"))
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
                errs.append(make_error("E530", f"INVENTED_ENUM_OR_ID {rel}:{path}.type={t}"))
        for key, value in node.items():
            p = f"{path}.{key}" if path else key
            if key in {"stage", "environment"} and isinstance(value, str) and value not in active_stages:
                errs.append(make_error("E530", f"INVENTED_ENUM_OR_ID {rel}:{p}={value}"))
            if key in {"stages", "environments"} and isinstance(value, list):
                for idx, item in enumerate(value):
                    if isinstance(item, str) and item not in active_stages:
                        errs.append(make_error("E530", f"INVENTED_ENUM_OR_ID {rel}:{p}[{idx}]={item}"))
            if key in {"unit", "units"}:
                if isinstance(value, str) and not _is_valid_unit(value, canon):
                    errs.append(make_error("E530", f"INVENTED_ENUM_OR_ID {rel}:{p}={value}"))
                if isinstance(value, list):
                    for idx, item in enumerate(value):
                        if isinstance(item, str) and not _is_valid_unit(item, canon):
                            errs.append(make_error("E530", f"INVENTED_ENUM_OR_ID {rel}:{p}[{idx}]={item}"))
            if key == "command" and isinstance(value, str):
                prefix = value.strip().split(" ", 1)[0]
                if prefix and prefix not in known_command_prefixes and not canon.resolve_alias("command", prefix):
                    errs.append(make_error("E530", f"INVENTED_ENUM_OR_ID {rel}:{p}={prefix}"))
            if key == "pr_rules" and isinstance(value, list):
                allowed_pr_rules = {
                    "validate", "validate-all", "matrix", "fixtures-lint", "invariants-check",
                    "governance-check", "seed-lint", "test", "build", "lint",
                    "format", "audit", "security"
                }
                for idx, item in enumerate(value):
                    if isinstance(item, str) and item not in allowed_pr_rules:
                        errs.append(make_error("E530", f"INVENTED_ENUM_OR_ID {rel}:{p}[{idx}]={item}"))
            errs.extend(_scan_node(rel, value, canon, known_command_prefixes, p, stages=active_stages))
    elif isinstance(node, list):
        for idx, item in enumerate(node):
            errs.extend(_scan_node(rel, item, canon, known_command_prefixes, f"{path}[{idx}]", stages=active_stages))
    return errs




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


def _extract_path_from_string(value: str) -> str:
    """Extract the file path portion from a composite string.

    Handles four cases:
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
    for value in _collect_values_under_key(data, key):
        path = _extract_path_from_string(value)
        if _looks_like_path(path) and not os.path.exists(os.path.join(path_root, path)):
            errs.append(make_error("E530", f"{error_tag} {rel}:{key} path={path}"))
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
    refs: list[str] = []
    refs.extend(_collect_values_under_key(data, "nfr_refs"))
    refs.extend(_collect_values_under_key(data, "nfr_ref"))
    for ref in refs:
        if ref not in nfr_ids:
            errs.append(make_error("E530", f"UNRESOLVED_NFR_REF {rel} nfr_ref={ref}"))
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


# Keys whose subtrees are excluded from E541 scanning.  Each of these
# contains objects whose schema does not support *_ref binding, so the
# linter cannot request a binding that is structurally impossible.
#
# - canonical_proposals / canonical_refs_used / canonical_conflicts:
#   These ARE canonical vocabulary — definitions naturally reference
#   sibling terms and have no *_ref field to bind.
# - tech_stack: Structured technology references (name, version,
#   rationale) with no *_ref in the schema.
# - user_segments: Charter persona descriptions — free prose that uses
#   domain vocabulary with no *_ref in the schema.
# - seeds: Seed manifest descriptions — metadata, not spec content.
_E541_SKIP_KEYS = {
    "canonical_proposals", "canonical_refs_used", "canonical_conflicts",
    "tech_stack", "user_segments", "seeds",
    # Step 16a/16b implementation subtrees.  Both keys appear exclusively in
    # Step 16 schemas (16_impl_context.schema.json) which define no *_ref field
    # on these items, making a canonical binding structurally impossible.
    # Per-file scoping (like edge_cases → 11_redteam.json) is impractical here
    # because Step 16a artifacts live in impl_context/ with variable filenames
    # (e.g. impl_context/ms_bootstrap_local_ghost_plan.json).  No other current
    # pipeline step defines these keys; if a future step introduces either key
    # with bindable vocabulary, add an explicit E541 test to catch it.
    "actions",
    "coding_examples",
}

# File-scoped exemptions: ``edge_cases`` is an unbindable narrative subtree
# *only* in 11_redteam.json (schema sets additionalProperties:false and
# defines no *_ref field on edge_cases items).  Scoping the skip to that
# file prevents a future step that introduces a literal ``edge_cases`` key
# from silently inheriting the exemption.
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
) -> list[SpecError]:
    """Check free-text fields for mentions of canonical terms without a binding ref."""
    if not canonical_terms:
        return []
    errs: list[SpecError] = []
    if isinstance(obj, dict):
        # Collect all ref keys present at this level
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
            if key in _FREE_TEXT_FIELDS and isinstance(value, str) and len(value) >= 3:
                # Skip if there's already a ref binding at this level
                if bound_refs:
                    continue
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
            errs.extend(_check_free_text_terms(rel, value, canonical_terms, p))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            errs.extend(_check_free_text_terms(rel, item, canonical_terms, f"{path}[{idx}]"))
    return errs

